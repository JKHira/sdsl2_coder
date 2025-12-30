# Next Steps Checklist (Fine-Grained)

Note: Operational entrypoint is in `README.md` (Open Interpreter Quickstart).

## Contract v0.1 Hardening
- [x] Align ContractBuilder validations with Closed Set v0.1 (allowed kinds/keys).
- [x] Enforce token placement rules for contract fields (contract/ssot/refs).
- [x] Normalize JSON Pointer paths with segmented inputs only.
- [x] Add Contract success cases (full metadata vs minimal).
- [x] Document JCS usage for any contract hash needs (future-proof).
- [x] Add Contract failure snapshots for edge cases (optional, if gaps found).
- [x] Document ContractBuilder usage and constraints in v0.1 docs.

## Contract Example Outputs
- [x] Select 1-2 real contract examples to target.
- [x] Build Builder-based generation scripts (no new CLI in v0.1).
- [x] Produce contract outputs and compare with expected structures.

## Gate A/B/C Reuse (Core Logic)
- [x] Identify reusable logic from legacy tools for Gate B (semantic checks).
- [x] Extract minimal core logic into runtime validation helpers.
- [x] Decide where Gate C (finalizer) is still needed vs Writer-only.

## Open Interpreter Integration
- [x] Create a wrapper script to run Builder + Writer only.
- [x] Restrict writes to OUTPUT/ and add diff gate workflow.
- [x] Provide a minimal system prompt/instructions for OI usage.

## Contract Inputs (if needed)
- [x] Phase only: decide if Contract needs a ledger or stays Builder-only.

## Future Phase (v0.2+)
- [ ] Phase only: CLI expansion and new input adapters.

## v0.1 Completion: Sample Outputs
- [x] Document SSOT source and scope for each sample case.
- [x] Document repro command for each case (builder script / golden check).
- [x] Add golden output under tests/goldens/<CASE>/ and register in determinism_manifest.
- [x] Verify determinism_check (2x run hash match + golden match).
- [x] Verify Gate A/B pass for OUTPUT/ and tests/goldens/.
- [x] Verify diff gate passes (allowlist-only changes).
- [ ] Update spec locks if any locked files changed.

## v0.2 Planning (Draft, single source)
- [ ] Define spec bump triggers (判定可能).
- [ ] Define spec locks / versioning policy for v0.2.
- [ ] Decide Gate C transform scope and spec updates (optional).
- [ ] Add determinism cases for any transform outputs (optional).
- [ ] Decide Contract ledger introduction and SSOT policy (optional).
- [ ] Update diff gate allowlist rules if inputs expand.
