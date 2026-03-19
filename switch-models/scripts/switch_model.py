#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path
from typing import Optional

MODEL_FILE_GLOB = "settings.model.*.json"
MODEL_FILE_PATTERN = re.compile(r"^settings\.model\.(?P<model>.+)\.json$")
EXCLUDED_FILES = {
    "settings.json",
    "settings.local.json",
    "settings.model.json",
    "settings.model.local.json",
}
UPDATED_FIELD = "env"


def json_out(payload: dict) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def error_out(code: str, message: str, exit_code: int, **extra: object) -> int:
    payload = {
        "ok": False,
        "code": code,
        "message": message,
    }
    payload.update(extra)
    print(json.dumps(payload, ensure_ascii=False))
    return exit_code


def build_error_payload(code: str, message: str, **extra: object) -> dict:
    payload = {
        "ok": False,
        "code": code,
        "message": message,
    }
    payload.update(extra)
    return payload


def emit_payload(payload: dict, exit_code: int) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return exit_code


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def discover_models(claude_dir: Path) -> list[str]:
    models: set[str] = set()
    for path in claude_dir.glob(MODEL_FILE_GLOB):
        if not path.is_file():
            continue
        if path.name in EXCLUDED_FILES:
            continue
        match = MODEL_FILE_PATTERN.match(path.name)
        if not match:
            continue
        model_name = match.group("model").strip()
        if model_name:
            models.add(model_name)
    return sorted(models)


def resolve_model_input(model_input: str, available_models: list[str]) -> dict:
    query = model_input.strip()
    if not query:
        return {
            "ok": False,
            "code": "INVALID_MODEL",
            "message": "Model input is empty",
            "matched_models": [],
        }

    query_lower = query.lower()
    query_normalized = normalize(query)

    def unique_matches(matcher):
        return sorted({model for model in available_models if matcher(model)})

    strategies = [
        ("exact", lambda model: model == query),
        ("exact_case_insensitive", lambda model: model.lower() == query_lower),
        ("prefix_case_insensitive", lambda model: model.lower().startswith(query_lower)),
        ("contains_case_insensitive", lambda model: query_lower in model.lower()),
        (
            "normalized_contains",
            lambda model: bool(query_normalized) and query_normalized in normalize(model),
        ),
    ]

    for strategy_name, matcher in strategies:
        matches = unique_matches(matcher)
        if len(matches) == 1:
            return {
                "ok": True,
                "resolved_model": matches[0],
                "match_strategy": strategy_name,
            }
        if len(matches) > 1:
            return {
                "ok": False,
                "code": "AMBIGUOUS_MODEL",
                "message": "Model input matches multiple available models",
                "matched_models": matches,
                "match_strategy": strategy_name,
            }

    return {
        "ok": False,
        "code": "INVALID_MODEL",
        "message": "Selected model is not in available model list",
        "matched_models": [],
    }


def model_settings_path(claude_dir: Path, model: str) -> Path:
    return claude_dir / f"settings.model.{model}.json"


def load_json_object(path: Path, label: str) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"{label} file not found: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid json in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"{label} root must be a JSON object: {path}")

    return data


def read_settings_env(claude_dir: Path) -> dict:
    settings_path = claude_dir / "settings.json"
    settings_data = load_json_object(settings_path, "settings")
    env = settings_data.get("env")
    if isinstance(env, dict):
        return env
    return {}


def read_current_model(claude_dir: Path) -> Optional[str]:
    env = read_settings_env(claude_dir)
    model = env.get("ANTHROPIC_MODEL")
    if isinstance(model, str) and model.strip():
        return model.strip()
    return None


def resolve_current_selected_model(claude_dir: Path, available_models: list[str]) -> Optional[str]:
    env = read_settings_env(claude_dir)

    for model in available_models:
        model_path = model_settings_path(claude_dir, model)
        try:
            model_data = load_json_object(model_path, "model settings")
        except (FileNotFoundError, ValueError):
            continue

        model_env = model_data.get("env")
        if isinstance(model_env, dict) and model_env == env:
            return model

    anthropic_model = env.get("ANTHROPIC_MODEL")
    if isinstance(anthropic_model, str):
        if anthropic_model in available_models:
            return anthropic_model
        lower_map = {m.lower(): m for m in available_models}
        fallback = lower_map.get(anthropic_model.lower())
        if fallback:
            return fallback

    return None


def apply_model_env_result(
    claude_dir: Path,
    selected_model: str,
    available_models: list[str],
    requested_model: str,
    match_strategy: Optional[str],
) -> tuple[dict, int]:
    settings_path = claude_dir / "settings.json"
    model_path = model_settings_path(claude_dir, selected_model)

    try:
        settings_data = load_json_object(settings_path, "settings")
    except FileNotFoundError as exc:
        return (
            build_error_payload(
                code="SETTINGS_NOT_FOUND",
                message=str(exc),
                settings_path=str(settings_path),
            ),
            4,
        )
    except ValueError as exc:
        return (
            build_error_payload(
                code="INVALID_SETTINGS_JSON",
                message=str(exc),
                settings_path=str(settings_path),
            ),
            5,
        )

    try:
        model_data = load_json_object(model_path, "model settings")
    except FileNotFoundError as exc:
        return (
            build_error_payload(
                code="MODEL_SETTINGS_NOT_FOUND",
                message=str(exc),
                model_settings_path=str(model_path),
                selected_model=selected_model,
            ),
            6,
        )
    except ValueError as exc:
        return (
            build_error_payload(
                code="INVALID_MODEL_SETTINGS_JSON",
                message=str(exc),
                model_settings_path=str(model_path),
                selected_model=selected_model,
            ),
            7,
        )

    target_env = model_data.get("env")
    if not isinstance(target_env, dict):
        return (
            build_error_payload(
                code="INVALID_MODEL_ENV",
                message=f"model settings env must be a JSON object: {model_path}",
                model_settings_path=str(model_path),
                selected_model=selected_model,
            ),
            8,
        )

    current_env = settings_data.get("env")
    if not isinstance(current_env, dict):
        current_env = {}

    if current_env == target_env:
        return (
            {
                "ok": True,
                "status": "unchanged",
                "requested_model": requested_model,
                "selected_model": selected_model,
                "match_strategy": match_strategy,
                "current_model": target_env.get("ANTHROPIC_MODEL"),
                "available_models": available_models,
                "settings_path": str(settings_path),
                "model_settings_path": str(model_path),
                "updated_field": UPDATED_FIELD,
            },
            0,
        )

    previous_model = current_env.get("ANTHROPIC_MODEL")
    settings_data["env"] = target_env
    settings_path.write_text(
        json.dumps(settings_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return (
        {
            "ok": True,
            "status": "updated",
            "requested_model": requested_model,
            "selected_model": selected_model,
            "match_strategy": match_strategy,
            "previous_model": previous_model,
            "current_model": target_env.get("ANTHROPIC_MODEL"),
            "available_models": available_models,
            "settings_path": str(settings_path),
            "model_settings_path": str(model_path),
            "updated_field": UPDATED_FIELD,
        },
        0,
    )


def apply_model_env(
    claude_dir: Path,
    selected_model: str,
    available_models: list[str],
    requested_model: str,
    match_strategy: Optional[str],
) -> int:
    payload, exit_code = apply_model_env_result(
        claude_dir=claude_dir,
        selected_model=selected_model,
        available_models=available_models,
        requested_model=requested_model,
        match_strategy=match_strategy,
    )
    return emit_payload(payload, exit_code)


def no_models_result() -> tuple[dict, int]:
    return (
        build_error_payload(
            code="NO_MODELS",
            message="No settings.model.<model-name>.json files found under ~/.claude",
            available_models=[],
            excluded_files=sorted(EXCLUDED_FILES),
        ),
        2,
    )


def cmd_list_result(claude_dir: Path) -> tuple[dict, int]:
    models = discover_models(claude_dir)
    if not models:
        return no_models_result()

    return (
        {
            "ok": True,
            "available_models": models,
            "excluded_files": sorted(EXCLUDED_FILES),
        },
        0,
    )


def cmd_list(claude_dir: Path) -> int:
    payload, exit_code = cmd_list_result(claude_dir)
    return emit_payload(payload, exit_code)


def cmd_set_result(claude_dir: Path, selected_model_input: str) -> tuple[dict, int]:
    available_models = discover_models(claude_dir)
    if not available_models:
        return no_models_result()

    resolution = resolve_model_input(selected_model_input, available_models)
    if not resolution["ok"]:
        code = str(resolution["code"])
        if code == "AMBIGUOUS_MODEL":
            return (
                build_error_payload(
                    code="AMBIGUOUS_MODEL",
                    message=str(resolution["message"]),
                    selected_model=selected_model_input,
                    available_models=available_models,
                    matched_models=resolution.get("matched_models", []),
                    match_strategy=resolution.get("match_strategy"),
                ),
                9,
            )

        return (
            build_error_payload(
                code="INVALID_MODEL",
                message=str(resolution["message"]),
                selected_model=selected_model_input,
                available_models=available_models,
                matched_models=resolution.get("matched_models", []),
            ),
            3,
        )

    resolved_model = str(resolution["resolved_model"])
    match_strategy = resolution.get("match_strategy")
    return apply_model_env_result(
        claude_dir=claude_dir,
        selected_model=resolved_model,
        available_models=available_models,
        requested_model=selected_model_input,
        match_strategy=match_strategy,
    )


def cmd_set(claude_dir: Path, selected_model_input: str) -> int:
    payload, exit_code = cmd_set_result(claude_dir, selected_model_input)
    return emit_payload(payload, exit_code)


def cmd_switch_result(claude_dir: Path, model_input: Optional[str]) -> tuple[dict, int]:
    available_models = discover_models(claude_dir)
    if not available_models:
        return no_models_result()

    raw_input = (model_input or "").strip()
    if not raw_input:
        return (
            {
                "ok": True,
                "status": "needs_selection",
                "reason": "NO_INPUT",
                "requested_model": "",
                "selection_options": available_models,
                "available_models": available_models,
            },
            0,
        )

    resolution = resolve_model_input(raw_input, available_models)
    if not resolution["ok"]:
        code = str(resolution["code"])
        if code == "AMBIGUOUS_MODEL":
            matched_models = resolution.get("matched_models", [])
            return (
                {
                    "ok": True,
                    "status": "needs_selection",
                    "reason": "AMBIGUOUS_MODEL",
                    "requested_model": raw_input,
                    "selection_options": matched_models,
                    "matched_models": matched_models,
                    "match_strategy": resolution.get("match_strategy"),
                    "available_models": available_models,
                },
                0,
            )

        return (
            {
                "ok": True,
                "status": "needs_selection",
                "reason": "INVALID_MODEL",
                "requested_model": raw_input,
                "selection_options": available_models,
                "available_models": available_models,
            },
            0,
        )

    resolved_model = str(resolution["resolved_model"])
    match_strategy = resolution.get("match_strategy")
    return apply_model_env_result(
        claude_dir=claude_dir,
        selected_model=resolved_model,
        available_models=available_models,
        requested_model=raw_input,
        match_strategy=match_strategy,
    )


def cmd_switch(claude_dir: Path, model_input: Optional[str]) -> int:
    payload, exit_code = cmd_switch_result(claude_dir, model_input)
    return emit_payload(payload, exit_code)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Switch Claude model via settings.model.<model-name>.json with deterministic script flow"
    )
    parser.add_argument(
        "--claude-dir",
        default="~/.claude",
        help="Claude config directory (default: ~/.claude)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="List available models from settings.model.<model-name>.json")

    switch_parser = subparsers.add_parser(
        "switch",
        help="One-shot switch flow: resolve input and either apply directly or return selection options",
    )
    switch_parser.add_argument(
        "model",
        nargs="?",
        help="Optional model input (full name or keyword), e.g. glm-5 or gpt",
    )

    set_parser = subparsers.add_parser(
        "set",
        help="Compatibility mode: set target model by exact/fuzzy input and apply immediately",
    )
    set_parser.add_argument(
        "model",
        help="Target model input (full name or keyword), e.g. glm-5 or gpt",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    claude_dir = Path(args.claude_dir).expanduser()
    if not claude_dir.is_dir():
        return error_out(
            code="CLAUDE_DIR_NOT_FOUND",
            message=f"Claude directory not found: {claude_dir}",
            exit_code=1,
            claude_dir=str(claude_dir),
        )

    if args.command == "list":
        return cmd_list(claude_dir)

    if args.command == "switch":
        return cmd_switch(claude_dir, args.model)

    if args.command == "set":
        return cmd_set(claude_dir, args.model)

    return error_out(code="UNKNOWN_COMMAND", message="Unknown command", exit_code=99)


if __name__ == "__main__":
    raise SystemExit(main())
