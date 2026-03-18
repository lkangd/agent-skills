---
name: codebase-architecture-analyzer
description: Analyze the architecture of a specified codebase and produce a structured report covering modules, dependency boundaries, runtime topology. Use when users ask to understand project structure, assess maintainability, identify coupling and layering problems, review architecture for migration/refactor planning, or create architecture documentation from an existing repository.
---

# Codebase Architecture Analyzer

## Overview

Use this skill to inspect a codebase and produce a concise, evidence-based architecture assessment. It is intended to help readers quickly understand the project.

## Recommended Workflow

### 1. Scope the target

- Confirm the target repository path.
- Confirm the expected output depth: quick overview or detailed architecture review.
- Prefer reading root-level files first (`README*`, `package.json`, `pyproject.toml`, `go.mod`, `pom.xml`, `Dockerfile*`, CI config).

### 2. Collect a reproducible snapshot

- Run `python3 scripts/collect_architecture_snapshot.py <repo_path>` (optional: `--tree-depth <n>`, like `tree -L n`).
- Use the script's stdout JSON output directly as evidence (do not rely on snapshot files).
- The script returns a structured snapshot with keys including `tree_depth`, `project_stats`, `git_activity`, `tree`, `root_files`, `manifests`, `imports`, `endpoints`.
- `project_stats` includes total file count, largest file, and primary programming languages.
- `git_activity` includes latest non-merge commits (up to 100), top 3 contributors, and local/remote branch naming samples for report filling.
- `tree` is hierarchical (`name/type/children`) and respects `tree_depth`.
- `imports`/`endpoints` use structured match items: `file_name`, `file_path`, `line_number`, `line_text`.

### 3. Build architecture model

Use `references/analysis-playbook.md` to map findings into:

- Entry points and runtime surfaces (API, worker, CLI, batch).
- Module boundaries and layering (presentation/application/domain/infrastructure).
- Dependency flow (expected direction and possible violations).
- Cross-cutting concerns (auth, config, logging, observability, data access).

### 4. Report with concrete risk calls

This step is mandatory: always produce a final report document as the deliverable.

Produce a report with:

- Current architecture summary.
- Strengths (what is already clean).
- Risks ordered by severity.
- Refactor recommendations with effort and impact.

Use `references/report-template.md` as the default output structure.
The final consolidated report file must be named `ARCHITECTURE.md` and stored at `.codebase-architecture-analyzer/ARCHITECTURE.md`.

Output enforcement:

- Do not stop at snapshot interpretation or intermediate analysis notes.
- Always return a complete report document in the final answer, even if some sections are marked as "insufficient evidence".
- If evidence is missing, keep the report structure and explicitly list missing inputs in the corresponding sections.
- The final report document filename is mandatory: `.codebase-architecture-analyzer/ARCHITECTURE.md`.

Language selection for the final report:

- If the user explicitly requests an output language, follow the user request.
- If the user does not specify a language, infer the preferred report language from project signals:
  - Use repository documentation language first (e.g., `README*`, `docs/`, ADRs, architecture docs, comments).
  - Use issue/commit/PR text language if available as a secondary signal.
  - Do not use programming language statistics (for example `project_stats.primary_languages`) to infer reading language.
- Keep the entire report in one language unless the user asks for mixed-language output.

## Quality bar

- When possible, keep document reading time within 10 minutes.
- Provide executable verification steps after each configuration stage.
- Prefer linking to authoritative docs (e.g., the project README) instead of copying lengthy content.
- Project documentation may be outdated; if observed facts from code/runtime/configuration conflict with docs, treat observed facts as source of truth and explicitly note the discrepancy in the report.
- Base all major claims on files or code patterns from the snapshot.
- Distinguish facts from inferences explicitly.
- Avoid generic advice; tie recommendations to exact modules or boundaries.
- If evidence is insufficient, state what is missing and how to collect it.
- Final output must be a report document, not only bullet-point analysis.

## Resources

- `scripts/collect_architecture_snapshot.py`: deterministic snapshot collector.
- `references/analysis-playbook.md`: architecture analysis method.
- `references/report-template.md`: reusable report skeleton.
