# Architecture Analysis Playbook

This playbook provides a systematic method for analyzing codebases and producing architecture assessments.

---

## Analysis Process

Follow these four phases in order. Each phase produces outputs that feed into the next.

### Phase 1: Runtime Topology

**Goal:** Understand how the system runs in production.

**What to identify:**

- Runtime types: web/api, worker/queue consumer, CLI tool, cron/batch job
- Entry points: main files, handler functions, worker definitions
- Deployment: Docker, Kubernetes, serverless, bare metal

**How to analyze:**

1. Check `package.json` scripts, `pyproject.toml` entry points, `main.go`
2. Look for `Dockerfile`, `docker-compose.yml`, `.github/workflows/`
3. Search for server definitions: `app.listen()`, `uvicorn.run()`, `http.ListenAndServe()`

**Output:** A simple diagram showing runtime components and their connections.

```text
Example:
[HTTP Client] --> [API Server :8080] --> [PostgreSQL]
                       |
                       +--> [Redis Cache]
                       |
                       +--> [S3 Object Storage]
```

---

### Phase 2: Module Boundaries

**Goal:** Map the code into logical layers and identify module boundaries.

**Standard Layer Model:**

| Layer | Contains | Examples |
|-------|----------|----------|
| Presentation | HTTP handlers, GraphQL resolvers, CLI commands | `routes/`, `controllers/`, `cmd/` |
| Application | Use cases, orchestration, service coordination | `services/`, `usecases/`, `app/` |
| Domain | Business rules, entities, value objects | `domain/`, `models/`, `entities/` |
| Infrastructure | Databases, caches, external APIs | `repository/`, `infra/`, `persistence/` |

**How to analyze:**

1. Map directories to layers using naming conventions
2. Identify the dominant pattern: MVC, Clean Architecture, Hexagonal, etc.
3. Note any deviations from the expected structure

**Boundary Leak Detection:**

| Problem | Pattern to Search | Example |
|---------|-------------------|---------|
| Presentation → Infrastructure skip | `routes/*` importing `db/*` directly | `import { db } from '../db'` in a route file |
| Domain → Framework coupling | Domain files importing HTTP libs | `import express` in `domain/user.ts` |
| Circular dependencies | A imports B, B imports A | Check module dependency graph |

**Output:** A layer diagram with identified violations marked.

---

### Phase 3: Dependency Analysis

**Goal:** Understand how modules depend on each other.

**Expected Direction:**

```
Presentation --> Application --> Domain <-- Infrastructure
                                       |
                                       +-- (implements interfaces)
```

**Key patterns to detect:**

1. **God Modules** - High inbound + outbound references
   - Search: Files imported by 10+ other files
   - Risk: Changes cascade widely

2. **High Fan-In** - Many files depend on this
   - Search: Shared utilities, base classes
   - Risk: Breaking change affects many consumers

3. **Hidden Coupling** - Shared utilities that know too much
   - Search: `utils/` or `common/` importing domain types
   - Risk: Utility becomes domain-coupled over time

**How to analyze:**

1. Use `imports` from snapshot to count references per file
2. Identify top 5 most-imported modules
3. Check if dependencies flow inward (presentation → domain)

**Output:** A table of dependency hotspots with severity.

---

### Phase 4: Cross-Cutting Concerns

**Goal:** Identify how system-wide concerns are handled.

**Concerns to trace:**

| Concern | What to Find | Good Pattern | Bad Pattern |
|---------|--------------|--------------|-------------|
| Configuration | How settings are loaded | Centralized config module | `process.env` scattered everywhere |
| Logging | How events are recorded | Structured logging, correlation IDs | `console.log` in production code |
| Auth | How identity is verified | Middleware + service layer | Auth checks in every handler |
| Error Handling | How failures are managed | Centralized error types | Try-catch with generic catches |
| Data Access | How DB is accessed | Repository pattern, transactions | Direct SQL in handlers |

**How to analyze:**

1. Search for logging calls: `logger.`, `console.`, `log.`
2. Search for env access: `process.env`, `os.Getenv`, `config.`
3. Search for auth patterns: `auth.`, `middleware`, `@Authenticated`
4. Check for consistency across modules

**Output:** A concern matrix showing implementation patterns.

---

## Output Synthesis

After completing all phases, synthesize into:

### Strengths (2-3 items)

- What's already clean or well-organized
- Evidence-based observations

### Risks (prioritized)

- High: Blocks changes, causes bugs, security issues
- Medium: Slows development, increases complexity
- Low: Minor improvements, nice-to-have

### Recommendations

- Tied to specific files/modules
- Include effort estimate (low/medium/high)
- Include impact estimate (low/medium/high)

---

## Quick Reference: Common Patterns

### Monolith

```
src/
  controllers/    # Presentation
  services/       # Application
  models/         # Domain
  database/       # Infrastructure
```

### Clean Architecture

```
src/
  api/            # Presentation
  application/    # Use cases
  domain/         # Business rules
  infrastructure/ # External adapters
```

### Modular Monolith

```
src/
  modules/
    billing/      # Complete billing module
    users/        # Complete users module
    orders/       # Complete orders module
  shared/         # Cross-module utilities
```

### Microservices

```
services/
  user-service/
  order-service/
  payment-service/
packages/
  shared-types/
  shared-utils/
```
