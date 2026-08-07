# Repository Instructions

Before changing business logic, read `docs/philosophy.md`, `docs/mvp-spec.md`, and `docs/project-state.md`. Treat them as the project source of truth.

Follow `docs/development-workflow.md` for risk classification, repository grounding, BUILD/REVIEW gates, review discipline, and commit workflow.

- Do not turn the project into a directional prediction or recommendation system.
- Do not invent market data, Greeks, probabilities, or historical values.
- Prefer the smallest implementation that satisfies the current milestone.
- Do not introduce new frameworks, integrations, folders, or abstractions unless required by the current task.
- Keep Python compatible with Python 3.9 or later.
- Add tests for new business rules.
- Ordinary completed work units may be committed and pushed automatically
  after the required validation and review pass; force pushes, history
  rewrites, releases, destructive external operations, credentials, and
  destructive migrations still require user approval. A task-specific
  instruction not to commit or push takes precedence.
- After each completed milestone, update `docs/project-state.md`.
- If a requested change conflicts with the philosophy or MVP specification, stop and clearly report the conflict instead of silently implementing it.

## Documentation map

- `docs/philosophy.md` — guiding research principles and boundaries
- `docs/mvp-spec.md` — MVP scope, screening model, and output requirements
- `docs/project-state.md` — current milestone, decisions, progress, and open questions
- `docs/development-workflow.md` — risk-tiered development, grounding, BUILD/REVIEW, review, checkpoint, and commit workflow
