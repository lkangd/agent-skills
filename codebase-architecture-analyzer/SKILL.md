---
name: codebase-architecture-analyzer
description: |
  Analyze codebase architecture and produce structured reports. TRIGGER when users ask about: project structure, code organization, module boundaries, dependency graphs, dependency analysis, data flow, entry points, architecture documentation, maintainability assessment, coupling issues, layering problems, refactoring preparation, migration planning, or onboarding documentation. Also trigger when users mention architecture reviews, architectural health, or want to understand how a codebase is organized - even if they don't explicitly use the word "architecture".
---

# Codebase Architecture Analyzer

Produce concise, evidence-based architecture assessments that help readers quickly understand a project.

## Workflow

Follow these steps in order. Each step builds on the previous one.

### Step 1: Scope and Context

**Ask or infer:**

- Target repository path (default: current directory)
- Analysis depth: `quick` (overview) or `detailed` (full review)
- User's goal: `understand`, `refactor`, `onboard`, or `document`

**Read root-level signals first:**

```
README*, package.json, pyproject.toml, go.mod, pom.xml, Cargo.toml
Dockerfile*, docker-compose*.yml
.github/workflows/*.yml, .gitlab-ci.yml, Jenkinsfile
```

These files reveal: tech stack, build tools, deployment patterns, and project purpose.

### Step 2: Collect Architecture Snapshot

**Run the snapshot script:**

```bash
python3 scripts/collect_architecture_snapshot.py <repo_path> [--tree-depth 4]
```

The script outputs JSON to stdout with these keys:

| Key | Description | Use For |
|-----|-------------|---------|
| `tree` | Hierarchical directory structure | Understanding code organization |
| `project_stats` | File counts, languages, largest files | Tech stack summary |
| `git_activity` | Commits, contributors, branch patterns | Development patterns |
| `root_files` | Files in repository root | Entry points identification |
| `manifests` | Package/dependency files | Dependency analysis |
| `imports` | Import statements with file locations | Dependency graph hints |
| `endpoints` | API endpoint patterns | Runtime surface detection |

**If the script fails:**

- Collect equivalent data manually using Glob, Grep, and Read tools
- Note in the report that snapshot collection was unavailable

### Step 3: Analyze Architecture

Apply the methodology from `references/analysis-playbook.md`:

**Map to layers:**

```
Presentation  → handlers, controllers, routes, UI
Application   → services, orchestration, use-cases
Domain        → business rules, entities, core logic
Infrastructure → db, cache, external APIs, messaging
```

**Identify:**

- **Entry points**: Where execution begins (main files, handlers, workers)
- **Boundaries**: How modules are separated
- **Dependency flow**: Does outer depend on inner? Any violations?
- **Cross-cutting concerns**: Config, logging, auth, error handling

### Step 4: Generate Report

**Output file:** `.codebase-architecture-analyzer/ARCHITECTURE.md`

**Required sections:**

| Section | Content |
|---------|---------|
| Project Overview | What it does, who uses it, tech stack |
| Quick Start | How to run/build the project |
| Architecture Overview | Diagram + layer description |
| Directory Organization | Tree with responsibility annotations |
| Key Files | Entry points and important modules |
| Strengths | What's already clean |
| Risks/Recommendations | Prioritized by severity |

**Use the template:** `references/report-template.md` provides the full structure.

## Adaptation by User Goal

### For "Understand" (Basic Analysis)

- Focus on: entry points, module map, dependency overview
- Output: Standard template with all sections
- Depth: Moderate detail

### For "Refactor" (Architecture Review)

- Focus on: coupling issues, layering violations, boundary problems
- Output: Add "Coupling Analysis" and "Proposed Architecture" sections
- Include: Specific file paths and line numbers for each issue
- Depth: High detail with code evidence

### For "Onboard" (New Developer)

- Focus on: reading order, key concepts, common tasks
- Output: Add "Recommended Reading Order" and "Quick Navigation" sections
- Use: Beginner-friendly language, explain acronyms
- Depth: Practical focus, less theory

### For "Document" (Architecture Docs)

- Focus on: comprehensive coverage, diagrams, ADR references
- Output: Full template with additional context
- Depth: High detail

## Language selection for the final report

- If the user explicitly requests an output language, follow the user request.
- If the user does not specify a language, infer the preferred report language from project signals:
  - Use repository documentation language first (e.g., `README*`, `docs/`, ADRs, architecture docs, comments).
  - Use issue/commit/PR text language if available as a secondary signal.
  - Do not use programming language statistics (for example `project_stats.primary_languages`) to infer reading language.
- Keep the entire report in one language unless the user asks for mixed-language output.

## Quality Standards

- **Evidence-based**: Every claim references a specific file, function, or pattern
- **Actionable**: Recommendations include file paths and concrete steps
- **Honest about uncertainty**: If evidence is missing, say so explicitly
- **Readable**: Target 10-minute reading time; use diagrams and tables
- **Language-aware**: Match output language to project documentation language

## Output Checklist

Before finalizing, verify:

- [ ] Report is saved to `.codebase-architecture-analyzer/ARCHITECTURE.md`
- [ ] All required sections are present
- [ ] Architecture includes a diagram (ASCII or mermaid)
- [ ] Recommendations are tied to specific files/modules
- [ ] Entry points are clearly identified
- [ ] Risks are prioritized (High/Medium/Low)

## Resources

| Resource | Purpose |
|----------|---------|
| `scripts/collect_architecture_snapshot.py` | Deterministic data collection |
| `references/analysis-playbook.md` | Layer/boundary analysis method |
| `references/report-template.md` | Full report structure template |
