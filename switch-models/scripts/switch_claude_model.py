#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from switch_model import (
    apply_model_env_result,
    build_error_payload,
    discover_models,
    read_current_model,
    resolve_current_selected_model,
    resolve_model_input,
)


def emit_json(payload: dict) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else int(payload.get("exit_code", 1))


def print_model_list(models: list[str], current_selected: Optional[str], current_hint: Optional[str], current_error: Optional[dict]) -> None:
    print("Available models:")
    for index, model in enumerate(models, start=1):
        marker = " (current)" if model == current_selected else ""
        print(f"  {index}. {model}{marker}")

    if current_selected:
        print(f"Current profile: {current_selected}")
    elif current_hint:
        print(f"Current model in settings: {current_hint} (no matching profile file)")
    elif current_error:
        print(f"Current model: unavailable ({current_error['code']})")
    else:
        print("Current model: unavailable")


def prompt_for_selection(selection_options: list[str]) -> Optional[str]:
    while True:
        user_input = input("Select model by number (or 'c' to cancel): ").strip()
        lowered = user_input.lower()
        if lowered in {"c", "q", "cancel", "exit"}:
            return None
        if not user_input:
            print("Please enter a number.")
            continue
        if not user_input.isdigit():
            print("Invalid input. Enter a number or 'c' to cancel.")
            continue

        selected_index = int(user_input)
        if 1 <= selected_index <= len(selection_options):
            return selection_options[selected_index - 1]

        print(f"Please enter a number between 1 and {len(selection_options)}.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Switch Claude model locally via terminal selection without LLM interaction"
    )
    parser.add_argument(
        "model_input",
        nargs="?",
        help="Optional model input (full name or keyword), for example gpt or glm-5",
    )
    parser.add_argument(
        "--claude-dir",
        default="~/.claude",
        help="Claude config directory (default: ~/.claude)",
    )
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Disable terminal prompts and fail fast if selection is required",
    )
    return parser


def detect_current_state(claude_dir: Path, available_models: list[str]) -> tuple[Optional[str], Optional[str], Optional[dict]]:
    try:
        current_selected = resolve_current_selected_model(claude_dir, available_models)
        current_hint = read_current_model(claude_dir)
        return current_selected, current_hint, None
    except FileNotFoundError as exc:
        return None, None, build_error_payload(
            code="SETTINGS_NOT_FOUND",
            message=str(exc),
            settings_path=str(claude_dir / "settings.json"),
        )
    except ValueError as exc:
        return None, None, build_error_payload(
            code="INVALID_SETTINGS_JSON",
            message=str(exc),
            settings_path=str(claude_dir / "settings.json"),
        )


def main() -> int:
    args = build_parser().parse_args()

    claude_dir = Path(args.claude_dir).expanduser()
    if not claude_dir.is_dir():
        payload = build_error_payload(
            code="CLAUDE_DIR_NOT_FOUND",
            message=f"Claude directory not found: {claude_dir}",
            claude_dir=str(claude_dir),
        )
        if args.json:
            payload["exit_code"] = 1
            return emit_json(payload)
        print(f"Error [{payload['code']}]: {payload['message']}", file=sys.stderr)
        return 1

    available_models = discover_models(claude_dir)
    if not available_models:
        payload = build_error_payload(
            code="NO_MODELS",
            message="No settings.model.<model-name>.json files found under ~/.claude",
            available_models=[],
            excluded_files=[
                "settings.json",
                "settings.local.json",
                "settings.model.json",
                "settings.model.local.json",
            ],
            hint="Create files like ~/.claude/settings.model.<model-name>.json first",
        )
        if args.json:
            payload["exit_code"] = 2
            return emit_json(payload)
        print(f"Error [{payload['code']}]: {payload['message']}", file=sys.stderr)
        print(payload["hint"], file=sys.stderr)
        return 2

    current_selected, current_hint, current_error = detect_current_state(claude_dir, available_models)

    if not args.json:
        print_model_list(available_models, current_selected, current_hint, current_error)

    raw_input = (args.model_input or "").strip()
    selection_options: list[str]
    reason: Optional[str] = None

    if raw_input:
        resolution = resolve_model_input(raw_input, available_models)
        if resolution.get("ok"):
            resolved_model = str(resolution["resolved_model"])
            payload, exit_code = apply_model_env_result(
                claude_dir=claude_dir,
                selected_model=resolved_model,
                available_models=available_models,
                requested_model=raw_input,
                match_strategy=resolution.get("match_strategy"),
            )
        else:
            code = str(resolution.get("code"))
            if code == "AMBIGUOUS_MODEL":
                selection_options = list(resolution.get("matched_models", []))
                reason = "AMBIGUOUS_MODEL"
            else:
                selection_options = available_models
                reason = "INVALID_MODEL"
    else:
        selection_options = available_models
        reason = "NO_INPUT"

    if reason is not None:
        is_tty = sys.stdin.isatty() and sys.stdout.isatty()
        non_interactive = args.non_interactive or args.json or not is_tty
        if non_interactive:
            payload = build_error_payload(
                code="NEEDS_SELECTION",
                message="Model selection is required but interactive input is disabled",
                status="needs_selection",
                reason=reason,
                requested_model=raw_input,
                selection_options=selection_options,
                available_models=available_models,
                current_selected_model=current_selected,
                current_model=current_hint,
            )
            if args.json:
                payload["exit_code"] = 11
                return emit_json(payload)
            print(f"Error [{payload['code']}]: {payload['message']}", file=sys.stderr)
            print("Candidates:", file=sys.stderr)
            for model in selection_options:
                print(f"- {model}", file=sys.stderr)
            return 11

        print()
        if reason == "AMBIGUOUS_MODEL":
            print(f"Input '{raw_input}' matches multiple models.")
        elif reason == "INVALID_MODEL":
            print(f"Input '{raw_input}' does not match any model.")
        else:
            print("No model input provided.")

        print("Choose from:")
        for index, model in enumerate(selection_options, start=1):
            marker = " (current)" if model == current_selected else ""
            print(f"  {index}. {model}{marker}")

        selected_model = prompt_for_selection(selection_options)
        if selected_model is None:
            payload = build_error_payload(
                code="SELECTION_CANCELLED",
                message="Selection cancelled by user",
                status="cancelled",
                requested_model=raw_input,
                available_models=available_models,
            )
            if args.json:
                payload["exit_code"] = 12
                return emit_json(payload)
            print(payload["message"])
            return 12

        payload, exit_code = apply_model_env_result(
            claude_dir=claude_dir,
            selected_model=selected_model,
            available_models=available_models,
            requested_model=raw_input,
            match_strategy="interactive_selection",
        )

    payload["requested_model"] = raw_input
    payload["final_model"] = payload.get("selected_model")
    payload["replacement_source"] = payload.get("model_settings_path")
    payload["restart_hint"] = "Exit current session and restart Claude to apply the model change"

    if current_selected and "current_selected_model" not in payload:
        payload["current_selected_model"] = current_selected
    if current_hint and "current_model" not in payload:
        payload["current_model"] = current_hint

    if args.json:
        payload["exit_code"] = exit_code
        return emit_json(payload)

    if not payload.get("ok"):
        print(f"Error [{payload['code']}]: {payload['message']}", file=sys.stderr)
        if payload.get("code") == "INVALID_SETTINGS_JSON":
            print("Fix ~/.claude/settings.json JSON before switching.", file=sys.stderr)
        if payload.get("code") == "INVALID_MODEL_ENV":
            print("Target model file must contain an object at 'env'.", file=sys.stderr)
        return exit_code

    status = payload.get("status")
    selected_model = payload.get("selected_model")
    if status == "updated":
        print()
        print(f"Switched model to: {selected_model}")
    else:
        print()
        print(f"Already using model profile: {selected_model}")

    print(f"Updated file: {payload.get('settings_path')}")
    print(f"Replaced field: {payload.get('updated_field')}")
    print(f"Replacement source: {payload.get('model_settings_path')}")
    print(payload["restart_hint"])
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
