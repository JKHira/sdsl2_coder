# v0.2 Scope Decision

Goal:
- Freeze which optional changes are in v0.2.
- Keep decisions binary (Yes/No) for unambiguous scope.

## Decisions (Yes/No)
- Gate C transform: No (v0.2 keeps check-only; no output rewriting).
- Contract ledger: No (keep Builder scripts as SSOT in v0.2).
- diff gate allowlist expansion: No (unchanged unless inputs expand).

## Rationale (short)
- Gate C transform changes output semantics and determinism coverage; defer until a clear need exists.
- Contract ledger introduces new schema/validation and review flow; defer until SSOT scale requires it.
- Allowlist expansion depends on new input sources; no change while inputs remain the same.

## DoD
- plan_high_level.md, plan_mid_level.md, plan_next_steps_checklist.md reference this decision.
- v0.2 triggers/locks remain consistent with this scope.
