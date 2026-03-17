# Analysis Playbook

## 1. Runtime Topology

Identify:

- Primary runtime types: `web/api`, `worker`, `cli`, `cron/batch`.
- Startup entry points and bootstrap files.
- Deployment hints (Docker, compose, CI, infra manifests).

Output:

- A short map of runtime components and how they interact.

## 2. Boundary and Layer Model

Create a module map from directory structure and imports:

- `interface/presentation`: handlers, controllers, routes, UI adapters.
- `application`: use-cases, orchestration, service layer.
- `domain`: core business rules and entities.
- `infrastructure`: db, cache, external APIs, messaging.

Check for boundary leaks:

- Presentation directly importing infrastructure internals.
- Domain importing framework-specific packages.
- Circular dependencies between sibling modules.

## 3. Dependency Direction

Validate intended direction:

- Outer layers can depend inward.
- Inner layers should not depend on outer frameworks.

Use import hotspots to detect:

- God modules (many inbound + outbound references).
- High fan-in modules that can become bottlenecks.
- Shared utility modules that hide domain coupling.

## 4. Cross-Cutting Concerns

Trace where each concern is implemented:

- Configuration and env management.
- Logging and observability.
- Authentication/authorization.
- Error handling and resilience.
- Data access strategy and transaction boundaries.

Look for inconsistency and duplication.
