# High-Level Plan (SDSLv2 Builder + Open Interpreter Workflow)

**KPI (No-Drift Goals)**
- Single input -> single output (deterministic; diff 0 for same inputs)
- Tool is the only output path (Builder/Writer SSOT, no raw SDSL edits)
- Fail fast, locally, and explainably (what/where/how to fix)
- Reproducible in CI with the same command

**Don't**
- Do not let LLM write SDSLv2 directly (always Builder -> Writer)
- Do not add vague exceptions (use versioned Closed Set, migration mode only if isolated)
- Do not rely on formatter to fix semantics (Builder must reject invalid structure)
- Do not allow repo-wide writes in Open Interpreter (restrict outputs + diff gate)

**Operational Rules (Minimum Set)**
- Rule-1: Output path is Builder/Writer only (handwritten SDSL forbidden)
- Rule-2: Topology Graph Facts come from ledger/explicit sources only (no inference)
- Rule-3: Closed Set is versioned (expansion requires spec bump)
- Rule-4: Errors are coded and auto-repairable (expected/got)
- Rule-5: Writes limited to `_OUTPUT` + diff review required
- Rule-6: Determinism guaranteed by tests

1) Align scope and inputs
   - Confirm target profiles (contract vs topology) and output locations.
   - Inventory inputs and identify authoritative sources for graph facts.
   - Set tool-level policies (ID scheme, canonical order, duplicate handling).
   - Decide whether Topology uses ledger as SSOT (recommended for stability).

2) Define the SDSLv2 target model
   - Formalize canonical data structures for Contract and Topology.
   - Encode SDSLv2 constraints from the manual (no inference, token placement, binding rules).
   - Define a versioned Closed Set of KINDS/keys and token placement tables (global, not per-project).
   - Allow projects to use only a subset of the Closed Set; add new KINDS only via version bump.

3) Design the Builder API (Python)
   - Provide high-level Builder classes for Contract and Topology.
   - Expose safe methods that only allow valid constructs (e.g., edge requires contract_refs).
   - Make Builder the sole output path (no raw SDSL text emission outside Builder).
   - Keep validation + deterministic serialization inside Builder; errors must be actionable.
   - Separate Builder (meaning/constraints) from Writer (deterministic text output).

4) Implement ingestion adapters (optional)
   - Support structured ledgers or other explicit sources as first-class v2 inputs.
   - Map to Builder calls; never infer graph facts from prose/pseudo-code.
   - Keep ledgers as the SSOT when you want stable diffs and reviewable inputs.

5) Integrate Open Interpreter workflow
   - Create a runnable script that imports Builder classes and writes SDSLv2.
   - Provide system instructions for Open Interpreter to use Builder only.
   - Restrict write targets to output directories; keep inputs read-only.
   - Require a diff/approval gate before applying changes to source.

6) Verify with examples and CI
   - Generate v2 outputs from the provided contract/topology examples.
   - Reuse Gate A/B/C checks as v2 quality gates (parse safety, semantic checks, finalizer).
   - Add lint/validation checks (CI) for SDSLv2 rules.
   - Document usage, constraints, and troubleshooting.

Status Checklist (as of now)
- [x] Define v0.1 ledger SSOT for topology (Flow/Terminal deferred).
- [x] Lock v0.1 Closed Set + token placement tables.
- [x] Lock v0.1 error catalog (JSON Pointer paths, codes).
- [x] Implement minimal Topology Builder/Writer + deterministic Edge ID (JCS).
- [x] Provide run/lint CLI and determinism test harness.
- [x] Add golden-based success cases and expected-failure cases (run + lint).
- [x] Add spec lock checks and CI guard.
- [x] Implement ContractBuilder/Writer v0.1 (parity with topology).
- [x] Integrate Gate A/B legacy checks where applicable.
- [x] Build Open Interpreter run wrapper + allowlist/diff gate flow.
- [ ] Generate v2 outputs for provided sample Contract/Topology files.

## v0.1 Completion: Sample Outputs
DoD (per sample case):
- SSOT is documented (source file(s) and scope).
- Repro command is documented (builder script / golden check).
- Golden output exists under tests/goldens/<CASE>/ and is registered in determinism_manifest.
- determinism_check passes (2x run hash match + golden match).
- Gate A/B pass for OUTPUT/ and tests/goldens/.
- Diff gate passes (changes only under allowlist).
- Spec lock updated if any locked files changed.

## v0.2 Planning (Draft)
V2-A: Spec bump definition
1) Spec bump triggers (判定可能):
   - Error codes: add new code or change meaning of message/expected/got/path.
   - Closed Set: add/remove/alter allowed kinds/keys/tokens.
   - Token placement: change allowed fields for CONTRACT/SSOT tokens.
   - Gate C transform: introduce output rewriting rules.
2) Spec locks / versioning policy for v0.2 (diff rules from v0.1).

V2-B: Gate C transform (optional)
3) Define transform rules (what to normalize vs never touch).
4) Add determinism coverage for transform outputs (manifest+golden).

V2-C: Contract inputs (optional)
5) Decide Contract ledger adoption (SSOT, review, migration).
6) If adopted: schema + validation + diff gate allowlist update.

V2-D: Tooling / CLI (optional)
7) New commands only after v0.2 spec bump (Builder/Writer remain SSOT).
