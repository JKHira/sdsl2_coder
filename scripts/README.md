# scripts (CI and helper tools)

Purpose: CI/gate helpers, determinism checks, and golden test utilities.
Non-scope: L0/L1/L2 production tools (those live in L0_builder/L1_builder/L2_builder).

## Gate / Lint
- `gate_a_check.py`: SDSL @File header + metadata syntax checks.
- `addendum_check.py`: stage policy/addendum lint (uses `.sdsl/policy.yaml` by default).
- `gate_b_check.py`: SDSL binding/placement checks (refs/contract_refs/ssot).
- `context_pack_bundle_doc_check.py`: validate Context Pack and Bundle Doc structure/order.

## Determinism / Diff / Spec
- `determinism_check.py`: manifest-driven determinism checks for outputs/diagnostics.
- `ssot_determinism_check.py`: run SSOT publish twice and compare OUTPUT/ssot hashes.
- `diff_gate.py`: enforce diff allowlist (default: OUTPUT/ and tests/goldens/).
- `check_spec_locks.py`: verify or write spec lock file (`spec_locks_v0_1.json`).
- `check_error_catalog.py`: ensure diagnostics codes are covered by error catalog.

## Tests / Goldens
- `addendum_test.py`: manifest-based addendum diagnostics golden tests.
- `context_pack_test.py`: manifest-based context pack golden tests.
- `contract_builder_check.py`: ContractBuilder error-case diagnostics (test helper).
- `contract_golden_check.py`: generate/verify contract golden outputs.

## Utilities
- `addendum_policy_reader.py`: print resolved addendum policy + diagnostics.
- `context_pack_extract.py`: extract Context Pack to stdout or file.
- `oi_run_v0_1.py`: convenience runner for spec locks, error catalog, determinism, gates, diff gate.

## Usage (minimal)
- Gate A: `python3 scripts/gate_a_check.py --input sdsl2/topology`
- Addendum: `python3 scripts/addendum_check.py --input sdsl2/topology --policy-path .sdsl/policy.yaml`
- Bundle/Context check: `python3 scripts/context_pack_bundle_doc_check.py --project-root /repo`
- Determinism: `python3 scripts/determinism_check.py --manifest tests/determinism_manifest.json`
- SSOT determinism: `python3 scripts/ssot_determinism_check.py --project-root project_testing --kernel-root . --today YYYY-MM-DD`
- Diff gate: `python3 scripts/diff_gate.py --allow OUTPUT/`
- Addendum tests: `python3 scripts/addendum_test.py --manifest tests/addendum_manifest.json`
- Context pack tests: `python3 scripts/context_pack_test.py --manifest tests/context_pack_manifest.json`

## Notes
- Golden files are updated only with `--update`.
- Paths are repo-relative unless stated in the script help.
- determinism_check cleans OUTPUT/ under repo root; run in an isolated worktree.
