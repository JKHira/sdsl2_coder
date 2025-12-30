# Contract Example Outputs v0.1

## Example 1: P3 Schema Validation (excerpt)
- Case ID: `P3_SCHEMA_VALIDATION_EXCERPT`
- Builder source: `scripts/contract_golden_check.py`
- Golden output: `tests/goldens/P3_SCHEMA_VALIDATION/contract.sdsl2`
- Repro command: `python3 scripts/contract_golden_check.py --case P3_SCHEMA_VALIDATION_EXCERPT --emit-stdout --golden tests/goldens/P3_SCHEMA_VALIDATION/contract.sdsl2`
- Source SSOT: `C_T/Contract/P3_SCHEMA_VALIDATION_SDSL_CONTRACT.md`
- Scope: selected anchors only (versioned reference, validation result, reload channel const, error code rule).
- Notes: v0.1 Builder supports a single DocMeta; this example omits DocMeta and focuses on anchors.

Operational entrypoint: see `README.md` (Open Interpreter Quickstart).

## Example 2: P5 Execution Message (excerpt)
- Case ID: `P5_EXECUTION_MESSAGE_EXCERPT`
- Builder source: `scripts/contract_golden_check.py`
- Golden output: `tests/goldens/P5_EXECUTION_MESSAGE/contract.sdsl2`
- Repro command: `python3 scripts/contract_golden_check.py --case P5_EXECUTION_MESSAGE_EXCERPT --emit-stdout --golden tests/goldens/P5_EXECUTION_MESSAGE/contract.sdsl2`
- Source SSOT: `C_T/Contract/P5_EXECUTION_MESSAGE_SDSL_CONTRACT.md`
- Scope: ID wrappers, two message structures, and core rules (L6 clordid, link signal, retry max, redis orders).
- Notes: DocMeta is omitted to keep the excerpt minimal and deterministic.

## Contract Inputs (v0.1)
- Contract SSOT is Builder scripts (e.g., `scripts/contract_golden_check.py`).
- Contract ledger input is deferred to v0.2+.
