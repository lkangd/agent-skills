# Architecture Report Template

This template provides the standard structure for architecture analysis reports.
Adapt sections based on the user's goal (understand/refactor/onboard/document).

---

## [Project Name]

### Project Overview

One paragraph: What it does, who uses it, core tech stack.

**Target Users:**

- Primary: [main user group]
- Secondary: [other stakeholders]

---

## Quick Start

### Prerequisites

| Requirement | Version | How to Install |
|-------------|---------|----------------|
| [runtime] | [version] | [method] |

### Commands

```bash
# Install
[install command]

# Run locally
[dev command]

# Build
[build command]

# Test
[test command]
```

### Verification Checklist

- [ ] Service starts without errors
- [ ] Health endpoint responds
- [ ] Core functionality works

---

## Architecture Overview

### System Diagram

```text
[Clients]
    |
    v
[Entry Point] --> [Core Services] --> [Data Layer]
                       |
                       v
                 [External Services]
```

### Layer Model

| Layer | Components | Responsibility |
|-------|------------|----------------|
| Presentation | [files] | [purpose] |
| Application | [files] | [purpose] |
| Domain | [files] | [purpose] |
| Infrastructure | [files] | [purpose] |

---

## Directory Organization

```text
project-root/
  |- src/                    # Core source code
  |   |- [modules]/          # Business modules
  |   |- [shared]/           # Shared utilities
  |   |- [config]/           # Configuration
  |- tests/                  # Test files
  |- scripts/                # Build/deploy scripts
  |- docs/                   # Documentation
```

### Key Files

| File | Purpose |
|------|---------|
| [entry file] | **Main entry point** |
| [config file] | Configuration |
| [main module] | Core business logic |

---

## Recommended Reading Order

**For new developers:**

1. [file 1] - Understand [what]
2. [file 2] - Learn [what]
3. [file 3] - See [what]
4. [file 4] - Explore [what]

---

## Strengths

1. **[Strength 1]**: [evidence from code]
2. **[Strength 2]**: [evidence from code]
3. **[Strength 3]**: [evidence from code]

---

## Risks and Recommendations

### High Priority

| Issue | Location | Impact | Recommendation |
|-------|----------|--------|----------------|
| [issue] | [file:line] | [impact] | [action] |

### Medium Priority

| Issue | Location | Impact | Recommendation |
|-------|----------|--------|----------------|
| [issue] | [file:line] | [impact] | [action] |

### Low Priority

| Issue | Location | Impact | Recommendation |
|-------|----------|--------|----------------|
| [issue] | [file:line] | [impact] | [action] |

---

## Optional Sections

Add these based on user goal:

### For "Refactor" Analysis

#### Coupling Analysis

- [Issue 1 with file:line evidence]
- [Issue 2 with file:line evidence]

#### Proposed Architecture

```text
[Diagram of suggested refactored structure]
```

### For "Onboarding" Documentation

#### Key Concepts

- **Concept 1**: [explanation]
- **Concept 2**: [explanation]

#### Common Tasks

| Task | Command | Notes |
|------|---------|-------|
| [task] | [command] | [notes] |

### For "Document" Output

#### API Reference

[Link to API docs or brief summary]

#### Architecture Decisions

[Links to ADRs or key decisions]

---

## Debugging Guide

### Common Issues

| Issue | Check | Solution |
|-------|-------|----------|
| [symptom] | [what to check] | [how to fix] |

### Debug Commands

```bash
[useful debug commands]
```

---

*Report generated: [date]*
*Analysis type: [understand/refactor/onboard/document]*
