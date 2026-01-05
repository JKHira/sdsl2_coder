# L1 Builder

Purpose: L1 promotion tooling (Decisions + Evidence -> SSOT patch).

Planned tools (stubs):
- promote.py (unified diff only; no auto-apply)
- contract_decisions_lint.py (decisions/contracts.yaml validation)
- contract_promote.py (contract diff only; no auto-apply)
- decisions_lint.py (decisions/edges.yaml validation)
- evidence_lint.py (decisions/evidence.yaml validation)
- readiness_check.py (L1 readiness gate)

Notes:
- SSOT lives under sdsl2/ only; never write SSOT directly.
- Outputs must be unified diffs under OUTPUT/.
- Inputs are decisions/ and drafts/ per specs.

Usage (examples):
- Validate decisions:
  - python3 L1_builder/decisions_lint.py --input decisions/edges.yaml --project-root project_x
- Validate contract decisions:
  - python3 L1_builder/contract_decisions_lint.py --input decisions/contracts.yaml --project-root project_x
- Validate evidence:
  - python3 L1_builder/evidence_lint.py --project-root project_x
- L1 readiness check:
  - python3 L1_builder/readiness_check.py --project-root project_x
- Promote (diff only; no auto-apply):
  - python3 L1_builder/promote.py --project-root project_x --out OUTPUT/promote.patch
- Contract promote (diff only; no auto-apply):
  - python3 L1_builder/contract_promote.py --project-root project_x --out OUTPUT/contract_promote.patch

Non-standard paths (only when needed):
- Add --allow-nonstandard-path to decisions_lint/evidence_lint/readiness_check.
