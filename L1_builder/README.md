# L1 Builder

Purpose: L1 promotion tooling (Decisions + Evidence -> SSOT patch) and L1 operational gates.

## Tools
- `duplicate_key_lint.py` -> Detect duplicate keys in YAML/JSON inputs.
- `decisions_lint.py` -> Validate decisions/edges.yaml.
- `evidence_lint.py` -> Validate decisions/evidence.yaml.
- `readiness_check.py` -> Promotion readiness gate (Intent + Decisions + Evidence).
- `promote.py` -> Unified diff only; no auto-apply.
- `contract_decisions_lint.py` -> Validate decisions/contracts.yaml.
- `contract_promote.py` -> Contract diff only; no auto-apply.
- `contract_resolution_lint.py` -> Contract resolution lint (skeleton + bind/dep checks).
- `contract_token_bind_check.py` -> Validate contract_refs tokens vs contract SSOT.
- `contract_rule_coverage_check.py` -> Check decisions contract_refs coverage and rule naming rules.
- `contract_error_model_lint.py` -> Validate ERROR_CODE / RETRY_POLICY type alias formats.
- `intent_lint.py` -> Validate drafts/intent/*.yaml.
- `evidence_template_gen.py` -> Generate evidence skeleton from decisions/edges.yaml.
- `evidence_hash_helper.py` -> Compute/verify content_hash for evidence.
- `evidence_repair.py` -> Diff-only evidence repair proposal.
- `schema_migration_check.py` -> Detect schema_version major mismatch.
- `drift_check.py` -> Detect SSOT vs decisions drift.
- `token_registry_check.py` -> Validate SSOT.* / CONTRACT.* tokens vs registries.
- `no_ssot_promotion_check.py` -> Block drafts/evidence under sdsl2/ or decisions/.
- `next_actions_gen.py` -> Write OUTPUT/decisions_needed.yaml and OUTPUT/diagnostics_summary.yaml.
- `operational_gate.py` -> Run L1 operational gates in order with policy severity.

## Notes
- SSOT lives under sdsl2/ only; never write SSOT directly.
- Diff outputs must stay under OUTPUT/.
- Intent input is restricted to drafts/intent/.
- token_registry_check allows UNRESOLVED#/ by default; use --fail-on-unresolved to hard-fail.

## Usage (examples)
- Operational gate (policy optional):
  - python3 L1_builder/operational_gate.py --project-root project_x --decisions-path decisions/edges.yaml --evidence-path decisions/evidence.yaml
- Intent lint:
  - python3 L1_builder/intent_lint.py --input drafts/intent --project-root project_x --allow-empty
- Drift check:
  - python3 L1_builder/drift_check.py --project-root project_x --decisions-path decisions/edges.yaml
- Token registry check:
  - python3 L1_builder/token_registry_check.py --project-root project_x --ssot-registry OUTPUT/ssot/ssot_registry.json --contract-registry OUTPUT/ssot/contract_registry.json
- Evidence hash verify:
  - python3 L1_builder/evidence_hash_helper.py --verify decisions/evidence.yaml --project-root project_x
- Duplicate key lint:
  - python3 L1_builder/duplicate_key_lint.py --input decisions --project-root project_x
- Contract resolution lint:
  - python3 L1_builder/contract_resolution_lint.py --input sdsl2/contract --project-root project_x --fail-on-missing
- Contract token bind check:
  - python3 L1_builder/contract_token_bind_check.py --project-root project_x
- Next actions:
  - python3 L1_builder/next_actions_gen.py --project-root project_x
- Promote (diff only; no auto-apply):
  - python3 L1_builder/promote.py --project-root project_x --out OUTPUT/promote.patch

Non-standard paths (only when needed):
- Add --allow-nonstandard-path to decisions_lint/evidence_lint/readiness_check/intent_lint/operational_gate.
