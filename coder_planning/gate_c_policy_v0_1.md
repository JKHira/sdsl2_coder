# Gate C Policy v0.1

## Decision
Gate C is **check-only** in v0.1. It must not rewrite outputs.

## Rationale
- Builder/Writer already produce canonical output and determinism is enforced.
- A/B gates are pure validators; introducing auto-fix conflicts with SSOT and
  "no formatter-driven repair" policy.
- Responsibility stays: parse (A) -> semantic (B) -> emit (Writer).

## Scope (if/when enabled in v0.1)
- Input targets: `OUTPUT/` and `tests/goldens/`.
- Output: diagnostics JSON (code/message/expected/got/path).
- Only surface-level checks (no semantic inference), e.g.:
  - Statement spacing rules.
  - Annotation block layout rules.
  - File ends with newline.

## Error Catalog
- Use existing v0.1 error codes where applicable.
- Do not introduce new codes without a spec bump.

## v0.2+ Conditions for Transform
Gate C may perform auto-fix only after:
- Spec bump (v0.2+) explicitly defines transform rules.
- `spec_locks_v0_1.json` is updated to v0.2 locks.
- Determinism manifest includes transform outputs and hash checks.
