#!/usr/bin/env python3
import argparse
import fnmatch
import json
import shutil
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


EXCLUDED_DIRS = {".git", "node_modules", "dist", "build", "target", ".next"}
EXCLUDED_STATS_DIRS = EXCLUDED_DIRS | {".architecture-snapshot"}
EXCLUDED_TREE_DIRS = EXCLUDED_DIRS | {".architecture-snapshot"}
MAX_TREE_DEPTH = 4

EXACT_MANIFESTS = {
    "package.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "package-lock.json",
    "pyproject.toml",
    "poetry.lock",
    "go.mod",
    "go.sum",
    "pom.xml",
    "Cargo.toml",
    "Cargo.lock",
}
GLOB_MANIFESTS = [
    "requirements*.txt",
    "build.gradle*",
    "Dockerfile*",
    "docker-compose*.yml",
    "docker-compose*.yaml",
]

IMPORT_PATTERN = r"^(import |from .* import |#include |use |require\()"
ENDPOINT_PATTERN = (
    r"(router\.|app\.|entry\.|@RequestMapping|@GetMapping|@PostMapping|FastAPI\(|Blueprint\(|"
    r"gin\.|echo\.|HandleFunc\()"
)

LANGUAGE_BY_EXTENSION = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".c": "C",
    ".h": "C/C++",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".cs": "C#",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".m": "Objective-C",
    ".mm": "Objective-C++",
    ".scala": "Scala",
    ".lua": "Lua",
    ".sh": "Shell",
    ".zsh": "Shell",
}


@dataclass
class GitIgnoreRule:
    pattern: str
    negated: bool
    dir_only: bool
    anchored: bool
    has_slash: bool


def load_gitignore_rules(repo_path: Path) -> list[GitIgnoreRule]:
    gitignore = repo_path / ".gitignore"
    if not gitignore.is_file():
        return []

    rules: list[GitIgnoreRule] = []
    for raw_line in gitignore.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        negated = line.startswith("!")
        if negated:
            line = line[1:].strip()
        if not line:
            continue

        anchored = line.startswith("/")
        if anchored:
            line = line[1:]

        dir_only = line.endswith("/")
        if dir_only:
            line = line[:-1]
        if not line:
            continue

        rules.append(
            GitIgnoreRule(
                pattern=line,
                negated=negated,
                dir_only=dir_only,
                anchored=anchored,
                has_slash="/" in line,
            )
        )
    return rules


def _rule_matches(rule: GitIgnoreRule, rel_path: Path, is_dir: bool) -> bool:
    rel_posix = rel_path.as_posix()
    parts = rel_path.parts
    basename = rel_path.name

    if rule.dir_only:
        if rule.has_slash:
            base = rule.pattern
            if rule.anchored:
                return rel_posix == base or rel_posix.startswith(f"{base}/")
            return rel_posix == base or rel_posix.startswith(f"{base}/") or f"/{base}/" in f"/{rel_posix}/"
        for idx, part in enumerate(parts):
            if fnmatch.fnmatch(part, rule.pattern):
                if idx < len(parts) - 1 or is_dir:
                    return True
        return False

    if rule.has_slash:
        if rule.anchored:
            return fnmatch.fnmatch(rel_posix, rule.pattern)
        return fnmatch.fnmatch(rel_posix, rule.pattern) or fnmatch.fnmatch(
            rel_posix, f"*/{rule.pattern}"
        )

    return fnmatch.fnmatch(basename, rule.pattern)


def _matches_gitignore(
    rel_path: Path, is_dir: bool, gitignore_rules: list[GitIgnoreRule]
) -> bool:
    ignored = False
    for rule in gitignore_rules:
        if _rule_matches(rule, rel_path, is_dir):
            ignored = not rule.negated
    return ignored


def _is_excluded(
    rel_path: Path,
    excluded_dirs: set[str],
    gitignore_rules: list[GitIgnoreRule],
    is_dir: bool,
) -> bool:
    return any(part in excluded_dirs for part in rel_path.parts) or _matches_gitignore(
        rel_path, is_dir, gitignore_rules
    )


def _sorted_tree_entries(
    repo_path: Path, dir_path: Path, gitignore_rules: list[GitIgnoreRule]
) -> list[Path]:
    entries: list[Path] = []
    try:
        for entry in dir_path.iterdir():
            rel = entry.relative_to(repo_path)
            if _is_excluded(rel, EXCLUDED_TREE_DIRS, gitignore_rules, entry.is_dir()):
                continue
            entries.append(entry)
    except OSError:
        return []

    dirs = sorted([p for p in entries if p.is_dir()], key=lambda p: p.name.lower())
    files = sorted([p for p in entries if p.is_file()], key=lambda p: p.name.lower())
    return dirs + files


def collect_tree(
    repo_path: Path, max_depth: int, gitignore_rules: list[GitIgnoreRule]
) -> dict[str, object]:
    root: dict[str, object] = {
        "name": ".",
        "type": "directory",
        "children": [],
    }
    if max_depth <= 0:
        return root

    def walk(dir_path: Path, node: dict[str, object], depth: int) -> None:
        children_nodes: list[dict[str, object]] = []
        for child in _sorted_tree_entries(repo_path, dir_path, gitignore_rules):
            child_node: dict[str, object] = {
                "name": child.name,
                "type": "directory" if child.is_dir() else "file",
            }
            if child.is_dir() and depth < max_depth:
                child_node["children"] = []
                walk(child, child_node, depth + 1)
            children_nodes.append(child_node)
        node["children"] = children_nodes

    walk(repo_path, root, 1)
    return root


def render_tree_lines(tree: dict[str, object]) -> list[str]:
    lines = [str(tree.get("name", "."))]
    children = tree.get("children", [])
    if not isinstance(children, list):
        return lines

    def walk(nodes: list[dict[str, object]], prefix: str) -> None:
        for idx, node in enumerate(nodes):
            is_last = idx == len(nodes) - 1
            branch = "└── " if is_last else "├── "
            name = str(node.get("name", ""))
            lines.append(f"{prefix}{branch}{name}")
            child_nodes = node.get("children", [])
            if isinstance(child_nodes, list) and child_nodes:
                extension = "    " if is_last else "│   "
                walk(child_nodes, prefix + extension)

    normalized_children = [n for n in children if isinstance(n, dict)]
    walk(normalized_children, "")
    return lines


def render_match_lines(values: list[dict[str, object]]) -> list[str]:
    lines: list[str] = []
    for item in values:
        file_path = str(item.get("file_path", ""))
        line_number = item.get("line_number", 0)
        line_text = str(item.get("line_text", ""))
        lines.append(f"{file_path}:{line_number}:{line_text}")
    return lines


def collect_root_files(repo_path: Path) -> list[str]:
    files = sorted([p.name for p in repo_path.iterdir() if p.is_file()])
    return files


def is_manifest_file(repo_path: Path, file_path: Path) -> bool:
    name = file_path.name
    rel = file_path.relative_to(repo_path).as_posix()
    if name in EXACT_MANIFESTS:
        return True
    if any(fnmatch.fnmatch(name, pattern) for pattern in GLOB_MANIFESTS):
        return True
    if rel.startswith(".github/workflows/") and (
        rel.endswith(".yml") or rel.endswith(".yaml")
    ):
        return True
    return False


def collect_manifests(repo_path: Path, gitignore_rules: list[GitIgnoreRule]) -> list[str]:
    manifests: list[str] = []
    for path in sorted(repo_path.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(repo_path)
        if _is_excluded(rel, EXCLUDED_DIRS, gitignore_rules, False):
            continue
        if is_manifest_file(repo_path, path):
            manifests.append(f"./{rel.as_posix()}")
    return sorted(manifests)


def run_rg(repo_path: Path, pattern: str) -> list[dict[str, object]]:
    rg = shutil.which("rg")
    if not rg:
        return []

    cmd = [
        rg,
        "-n",
        "--hidden",
        "--glob",
        "!.git/*",
        "--glob",
        "!node_modules/*",
        "--glob",
        "!dist/*",
        "--glob",
        "!build/*",
        "--glob",
        "!target/*",
        "--glob",
        "!.architecture-snapshot/*",
        pattern,
        ".",
    ]
    result = subprocess.run(
        cmd,
        cwd=repo_path,
        text=True,
        capture_output=True,
        check=False,
    )
    # rg exit code: 0 matches, 1 no matches.
    if result.returncode in {0, 1}:
        if not result.stdout:
            return []
        matches: list[dict[str, object]] = []
        for raw in result.stdout.splitlines():
            line = raw.strip()
            if not line:
                continue
            parts = line.split(":", 2)
            if len(parts) < 3:
                continue
            rel_path, line_no, text = parts
            try:
                line_number = int(line_no)
            except ValueError:
                continue
            file_path = rel_path if rel_path.startswith("./") else f"./{rel_path}"
            matches.append(
                {
                    "file_name": Path(rel_path).name,
                    "file_path": file_path,
                    "line_number": line_number,
                    "line_text": text,
                }
            )
        return matches
    raise RuntimeError(result.stderr.strip() or "rg failed")


def remove_legacy_txt_outputs(out_dir: Path) -> None:
    for txt in out_dir.glob("*.txt"):
        txt.unlink(missing_ok=True)


def clean_non_target_artifacts(out_dir: Path, output_format: str) -> None:
    json_path = out_dir / "snapshot.json"
    md_path = out_dir / "snapshot.md"
    if output_format == "json":
        md_path.unlink(missing_ok=True)
    elif output_format == "md":
        json_path.unlink(missing_ok=True)


def iter_project_files(
    repo_path: Path, excluded_dirs: set[str], gitignore_rules: list[GitIgnoreRule]
):
    for path in sorted(repo_path.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(repo_path)
        if _is_excluded(rel, excluded_dirs, gitignore_rules, False):
            continue
        yield path


def detect_language(path: Path) -> Optional[str]:
    lower_name = path.name.lower()
    if lower_name.startswith("dockerfile"):
        return "Dockerfile"
    return LANGUAGE_BY_EXTENSION.get(path.suffix.lower())


def collect_project_stats(
    repo_path: Path, gitignore_rules: list[GitIgnoreRule]
) -> dict[str, object]:
    total_files = 0
    largest_path = ""
    largest_size = -1
    language_counts: dict[str, int] = {}

    for path in iter_project_files(repo_path, EXCLUDED_STATS_DIRS, gitignore_rules):
        total_files += 1

        size = path.stat().st_size
        if size > largest_size:
            largest_size = size
            largest_path = f"./{path.relative_to(repo_path).as_posix()}"

        language = detect_language(path)
        if language:
            language_counts[language] = language_counts.get(language, 0) + 1

    language_total = sum(language_counts.values())
    sorted_languages = sorted(
        language_counts.items(),
        key=lambda item: (-item[1], item[0]),
    )
    language_usage = [
        {
            "language": lang,
            "files": count,
            "percentage": round((count / language_total) * 100, 2)
            if language_total
            else 0.0,
        }
        for lang, count in sorted_languages
    ]

    return {
        "total_files": total_files,
        "largest_file": {
            "path": largest_path if largest_size >= 0 else "",
            "size_bytes": largest_size if largest_size >= 0 else 0,
        },
        "languages": language_usage,
        "primary_languages": [item["language"] for item in language_usage[:3]],
    }


def collect_git_activity(repo_path: Path, commit_limit: int = 100) -> dict[str, object]:
    git = shutil.which("git")
    if not git:
        return {
            "available": False,
            "reason": "git command not found",
            "commit_limit": commit_limit,
            "total_commits": 0,
            "top_contributors": [],
            "commits": [],
            "branch_naming": {
                "local_branches": [],
                "remote_branches": [],
                "naming_tokens_top10": [],
                "prefixes_top10": [],
            },
        }

    inside = subprocess.run(
        [git, "-C", str(repo_path), "rev-parse", "--is-inside-work-tree"],
        text=True,
        capture_output=True,
        check=False,
    )
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return {
            "available": False,
            "reason": "not a git repository",
            "commit_limit": commit_limit,
            "total_commits": 0,
            "top_contributors": [],
            "commits": [],
            "branch_naming": {
                "local_branches": [],
                "remote_branches": [],
                "naming_tokens_top10": [],
                "prefixes_top10": [],
            },
        }

    def list_branches(args: list[str]) -> list[str]:
        res = subprocess.run(
            [git, "-C", str(repo_path)] + args,
            text=True,
            capture_output=True,
            check=False,
        )
        if res.returncode != 0:
            return []
        branches: list[str] = []
        for raw in res.stdout.splitlines():
            name = raw.strip()
            if not name:
                continue
            if name.startswith("* "):
                name = name[2:].strip()
            if " -> " in name:
                continue
            branches.append(name)
        return branches

    local_branches = list_branches(["branch", "--format=%(refname:short)"])
    remote_branches = list_branches(["branch", "-r", "--format=%(refname:short)"])

    fmt = "%H%x1f%an%x1f%ae%x1f%ad%x1f%s"
    result = subprocess.run(
        [
            git,
            "-C",
            str(repo_path),
            "log",
            "--no-merges",
            f"-n{commit_limit}",
            "--date=iso-strict",
            f"--pretty=format:{fmt}",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        token_counter: Counter[str] = Counter()
        prefix_counter: Counter[str] = Counter()
        for branch in local_branches + remote_branches:
            normalized = branch.replace("/", "-").replace("_", "-")
            parts = [p for p in normalized.split("-") if p]
            if parts:
                prefix_counter[parts[0].lower()] += 1
                for p in parts:
                    token_counter[p.lower()] += 1
        return {
            "available": False,
            "reason": result.stderr.strip() or "git log failed",
            "commit_limit": commit_limit,
            "total_commits": 0,
            "top_contributors": [],
            "commits": [],
            "branch_naming": {
                "local_branches": local_branches,
                "remote_branches": remote_branches,
                "naming_tokens_top10": [
                    {"token": token, "count": count}
                    for token, count in token_counter.most_common(10)
                ],
                "prefixes_top10": [
                    {"prefix": prefix, "count": count}
                    for prefix, count in prefix_counter.most_common(10)
                ],
            },
        }

    commits: list[dict[str, object]] = []
    contributor_counter: Counter[tuple[str, str]] = Counter()

    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\x1f")
        if len(parts) != 5:
            continue
        commit_hash, author_name, author_email, commit_date, subject = parts
        commits.append(
            {
                "hash": commit_hash,
                "author_name": author_name,
                "author_email": author_email,
                "date": commit_date,
                "subject": subject,
            }
        )
        contributor_counter[(author_name, author_email)] += 1

    top_contributors = [
        {
            "rank": idx,
            "contributor": name,
            "email": email,
            "commits": count,
        }
        for idx, ((name, email), count) in enumerate(
            contributor_counter.most_common(3),
            start=1,
        )
    ]

    token_counter: Counter[str] = Counter()
    prefix_counter: Counter[str] = Counter()
    all_branches = local_branches + remote_branches
    for branch in all_branches:
        normalized = branch.replace("/", "-").replace("_", "-")
        parts = [p for p in normalized.split("-") if p]
        if parts:
            prefix_counter[parts[0].lower()] += 1
            for p in parts:
                token_counter[p.lower()] += 1

    return {
        "available": True,
        "reason": "",
        "commit_limit": commit_limit,
        "total_commits": len(commits),
        "top_contributors": top_contributors,
        "commits": commits,
        "branch_naming": {
            "local_branches": local_branches,
            "remote_branches": remote_branches,
            "naming_tokens_top10": [
                {"token": token, "count": count}
                for token, count in token_counter.most_common(10)
            ],
            "prefixes_top10": [
                {"prefix": prefix, "count": count}
                for prefix, count in prefix_counter.most_common(10)
            ],
        },
    }


def render_markdown(snapshot: dict[str, object]) -> str:
    lines: list[str] = [
        "# Architecture Snapshot",
        "",
        f"- Repository: `{snapshot['repo_path']}`",
        f"- Generated at: `{snapshot['generated_at']}`",
        "",
    ]
    stats = snapshot.get("project_stats", {})
    if isinstance(stats, dict):
        largest_file = stats.get("largest_file", {})
        largest_path = ""
        largest_size = 0
        if isinstance(largest_file, dict):
            largest_path = str(largest_file.get("path", ""))
            largest_size = int(largest_file.get("size_bytes", 0))
        lines.extend(
            [
                "## Project Stats",
                "",
                f"- Total files: `{stats.get('total_files', 0)}`",
                f"- Largest file: `{largest_path}` (`{largest_size}` bytes)",
            ]
        )
        primary_languages = stats.get("primary_languages", [])
        if isinstance(primary_languages, list) and primary_languages:
            lines.append(
                "- Primary languages: "
                + ", ".join(f"`{str(lang)}`" for lang in primary_languages)
            )
        else:
            lines.append("- Primary languages: _No recognized code files found._")
        lines.append("")

        language_usage = stats.get("languages", [])
        lines.append("### Language Breakdown")
        lines.append("")
        if isinstance(language_usage, list) and language_usage:
            lines.append("| Language | Files | Share |")
            lines.append("| --- | ---: | ---: |")
            for item in language_usage:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    f"| {item.get('language', '')} | {item.get('files', 0)} | {item.get('percentage', 0)}% |"
                )
        else:
            lines.append("_No recognized code files found._")
        lines.append("")

    git_activity = snapshot.get("git_activity", {})
    if isinstance(git_activity, dict):
        lines.append("## Git Activity")
        lines.append("")
        lines.append(
            f"- Non-merge commits analyzed: `{git_activity.get('total_commits', 0)}` (limit `{git_activity.get('commit_limit', 100)}`)"
        )
        if not git_activity.get("available", False):
            lines.append(f"- Status: `{git_activity.get('reason', 'unavailable')}`")
            lines.append("")
        else:
            top = git_activity.get("top_contributors", [])
            lines.append("### Top 3 Contributors in the Latest 100 Commits")
            lines.append("")
            if isinstance(top, list) and top:
                lines.append("| Rank | Contributor | Email | Commits |")
                lines.append("| --- | --- | --- | ---: |")
                for item in top:
                    if not isinstance(item, dict):
                        continue
                    lines.append(
                        f"| {item.get('rank', '')} | {item.get('contributor', '')} | {item.get('email', '')} | {item.get('commits', 0)} |"
                    )
            else:
                lines.append("_No contributor data found._")
            lines.append("")

            branch_naming = git_activity.get("branch_naming", {})
            lines.append("### Branch Naming Sample")
            lines.append("")
            if isinstance(branch_naming, dict):
                local_branches = branch_naming.get("local_branches", [])
                remote_branches = branch_naming.get("remote_branches", [])
                prefixes = branch_naming.get("prefixes_top10", [])
                lines.append(f"- Local branches sampled: `{len(local_branches) if isinstance(local_branches, list) else 0}`")
                lines.append(
                    f"- Remote branches sampled: `{len(remote_branches) if isinstance(remote_branches, list) else 0}`"
                )
                if isinstance(prefixes, list) and prefixes:
                    lines.append("- Common branch prefixes: " + ", ".join(
                        f"`{str(item.get('prefix', ''))}`({int(item.get('count', 0))})"
                        for item in prefixes
                        if isinstance(item, dict)
                    ))
                else:
                    lines.append("- Common branch prefixes: _No branch naming data found._")
            else:
                lines.append("_No branch naming data found._")
            lines.append("")

    lines.append("## Tree")
    lines.append("")
    tree_data = snapshot.get("tree", {})
    if isinstance(tree_data, dict):
        tree_lines = render_tree_lines(tree_data)
    else:
        tree_lines = []
    if tree_lines:
        lines.append("```text")
        lines.extend(tree_lines)
        lines.append("```")
    else:
        lines.append("_No entries found._")
    lines.append("")

    sections: list[tuple[str, str]] = [
        ("Root Files", "root_files"),
        ("Manifests", "manifests"),
        ("Imports", "imports"),
        ("Endpoints", "endpoints"),
    ]
    for title, key in sections:
        values = snapshot.get(key, [])
        lines.append(f"## {title}")
        lines.append("")
        if not values:
            lines.append("_No entries found._")
            lines.append("")
            continue
        if key in {"imports", "endpoints"} and isinstance(values, list):
            values = render_match_lines([item for item in values if isinstance(item, dict)])
        lines.append("```text")
        lines.extend(values)  # type: ignore[arg-type]
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect deterministic architecture snapshot artifacts."
    )
    parser.add_argument("repo_path", help="Path to the repository")
    parser.add_argument(
        "--format",
        choices=("json", "md", "both"),
        default="both",
        help="Output format to generate (default: both).",
    )
    parser.add_argument(
        "--tree-depth",
        type=int,
        default=MAX_TREE_DEPTH,
        help="Tree depth (like `tree -L`). 0 means only root.",
    )
    args = parser.parse_args()
    if args.tree_depth < 0:
        print("Error: --tree-depth must be >= 0", file=sys.stderr)
        return 1

    repo_path = Path(args.repo_path).expanduser().resolve()
    if not repo_path.is_dir():
        print(f"Error: directory not found: {repo_path}", file=sys.stderr)
        return 1

    out_dir = repo_path / ".architecture-snapshot"
    out_dir.mkdir(parents=True, exist_ok=True)
    remove_legacy_txt_outputs(out_dir)
    clean_non_target_artifacts(out_dir, args.format)
    gitignore_rules = load_gitignore_rules(repo_path)

    snapshot = {
        "repo_path": str(repo_path),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tree_depth": args.tree_depth,
        "project_stats": collect_project_stats(repo_path, gitignore_rules),
        "git_activity": collect_git_activity(repo_path, commit_limit=100),
        "tree": collect_tree(repo_path, args.tree_depth, gitignore_rules),
        "root_files": collect_root_files(repo_path),
        "manifests": collect_manifests(repo_path, gitignore_rules),
        "imports": run_rg(repo_path, IMPORT_PATTERN),
        "endpoints": run_rg(repo_path, ENDPOINT_PATTERN),
    }

    created_files: list[Path] = []
    if args.format in {"json", "both"}:
        json_path = out_dir / "snapshot.json"
        json_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        created_files.append(json_path)

    if args.format in {"md", "both"}:
        md_path = out_dir / "snapshot.md"
        md_path.write_text(render_markdown(snapshot), encoding="utf-8")
        created_files.append(md_path)

    print(f"Snapshot generated at: {out_dir}")
    print("Artifacts:")
    for path in created_files:
        print(f"- {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
