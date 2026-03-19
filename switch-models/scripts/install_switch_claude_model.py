#!/usr/bin/env python3

import argparse
import os
import stat
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install switch-claude-model command into user bin directory"
    )
    parser.add_argument(
        "--bin-dir",
        default="~/.local/bin",
        help="Target bin directory (default: ~/.local/bin)",
    )
    parser.add_argument(
        "--command-name",
        default="switch-claude-model",
        help="Installed command name (default: switch-claude-model)",
    )
    return parser


def is_path_in_env(target_dir: Path) -> bool:
    path_env = os.environ.get("PATH", "")
    parts = [Path(part).expanduser().resolve() for part in path_env.split(os.pathsep) if part]
    try:
        target_resolved = target_dir.expanduser().resolve()
    except FileNotFoundError:
        target_resolved = target_dir.expanduser()
    return any(part == target_resolved for part in parts)


def shell_hint(target_dir: Path) -> str:
    target_str = str(target_dir)
    return (
        "Add this to your shell config, then restart shell:\n"
        f"  export PATH=\"{target_str}:$PATH\""
    )


def write_launcher(launcher_path: Path, target_script: Path) -> None:
    launcher = "#!/usr/bin/env bash\n"
    launcher += f'exec python3 "{target_script}" "$@"\n'
    launcher_path.write_text(launcher, encoding="utf-8")
    mode = launcher_path.stat().st_mode
    launcher_path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def main() -> int:
    args = build_parser().parse_args()

    this_script = Path(__file__).resolve()
    target_script = this_script.parent / "switch_claude_model.py"
    if not target_script.is_file():
        print(f"Error: target script not found: {target_script}")
        return 1

    bin_dir = Path(args.bin_dir).expanduser()
    bin_dir.mkdir(parents=True, exist_ok=True)

    launcher_path = bin_dir / args.command_name
    write_launcher(launcher_path, target_script)

    print(f"Installed: {launcher_path}")
    print(f"Target: {target_script}")

    if is_path_in_env(bin_dir):
        print("PATH check: OK")
    else:
        print("PATH check: missing")
        print(shell_hint(bin_dir))

    print(f"Run: {args.command_name} --help")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
