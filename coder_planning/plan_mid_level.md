# Mid-Level Steps (Implementation Breakdown)

Phase A: Inputs and constraints
1) Catalog source inputs (files, tables, structured lists) and tag each as Contract or Topology.
2) Extract explicit graph facts sources (allowed set only) and mark missing topology data.
3) Set tool-level policies (ID scheme, canonical order, duplicate handling).
4) Define global Closed Set + token placement tables (versioned, not per-project).
5) Decide if Topology Graph Facts are ledger-SSOT (recommended) or other explicit sources.

Phase B: Canonical data model
6) Define in-memory models for:
   - Contract: Structure, Interface, Function, Const, Type, Dep, DocMeta, Rule.
   - Topology: Node, Edge, Flow, Terminal, DocMeta, Rule.
7) Encode SDSLv2 constraints as validators:
   - Token placement (CONTRACT.* / SSOT.*), binding rules, literal forms, direction set.
   - Contract vs Topology authority separation.
8) Define error codes and expected/got messages for all validator failures.

Phase C: Builder API
9) Implement ContractBuilder with methods like:
   - file(profile, id_prefix), doc_meta(...), structure(...), function(...), const(...), dep(...)
10) Implement TopologyBuilder with methods like:
   - file(profile, id_prefix), node(...), edge(...), flow(...), terminal(...)
11) Make Builder the sole output path (no raw SDSL text outside Builder).
12) Keep validation inside Builder with clear, local errors.
13) Implement Writer as deterministic serializer only (no inference, no validation decisions).

Phase D: Ingestion adapters (optional)
14) Support structured ledgers or other explicit sources as first-class v2 inputs.
15) Build parsers for explicit inputs (tables, ledgers) to extract:
   - Declarations (contract) and explicit graph facts (topology).
16) Map parsed inputs into Builder calls; emit diagnostics for missing or forbidden inference.

Phase E: Open Interpreter integration
17) Provide a Python entry script (e.g., `run_builder.py`) that:
   - Loads inputs, calls Builders, writes outputs.
18) Provide Open Interpreter instructions (system message / profile) to:
   - Import Builders and only use their methods.
   - Re-run on error until the script passes validation.
19) Enforce write allowlist to output dirs + diff/approval gate before applying changes.

Phase F: Verification and CI
20) Reuse Gate A/B/C checks as v2 quality gates (parse safety, semantic checks, finalizer).
21) Add CI checks for rule compliance and missing graph facts.
22) Add determinism tests (same input -> identical output).
23) Generate v2 outputs for the two sample files and confirm expected output patterns.

## v0.1 Completion: Sample Outputs
DoD (per sample case):
- SSOT is documented (source file(s) and scope).
- Repro command is documented (builder script / golden check).
- Golden output exists under tests/goldens/<CASE>/ and is registered in determinism_manifest.
- determinism_check passes (2x run hash match + golden match).
- Gate A/B pass for OUTPUT/ and tests/goldens/.
- Diff gate passes (changes only under allowlist).
- Spec lock updated if any locked files changed.

Progress Checklist (as of now)
- [x] Phase A: Decide topology SSOT as ledger-only and lock v0.1 constraints.
- [x] Phase B: Define topology model + error codes v0.1 (locked).
- [x] Phase C: Implement TopologyBuilder/Writer + run/lint (minimal v0.1).
- [x] Phase F: Determinism tests with golden outputs (success + failure cases).
- [x] Phase F: Spec lock guard in CI (v0.1 files hashed).
- [x] Phase B: Contract model definitions + validators (v0.1).
- [x] Phase C: ContractBuilder/Writer (v0.1).
- [ ] Phase D: Ledger ingestion for contract (if needed).
- [x] Phase E: Open Interpreter integration + run wrapper + allowlist/diff gate.
- [x] Phase F: Apply Gate A/B legacy checks or port core logic.
- [ ] Phase F: Generate v2 outputs for provided Contract/Topology examples.

# v0.2 Planning (Locked)

Phase V2-A: Spec bump definition
1) Spec bump triggers (判定可能):
   - Error codes: add new code or change meaning of message/expected/got/path.
   - Closed Set: add/remove/alter allowed kinds/keys/tokens.
   - Token placement: change allowed fields for CONTRACT/SSOT tokens.
   - Gate C transform: introduce output rewriting rules.
2) Spec locks / versioning policy for v0.2 (diff rules from v0.1).
   - Locked in `coder_planning/v0_2_triggers_locks.md`.

Phase V2-B: Gate C transform (optional)
3) Define transform rules (formatting, normalization) as explicit spec.
4) Add determinism cases for transform outputs.

Phase V2-C: Contract inputs (optional)
5) Decide on Contract ledger introduction and schema (SSOT rules).
6) Add ledger validation + diff gate allowlist policy.

Phase V2-D: Tooling/CLI (optional)
7) Evaluate new CLI commands and update run/lint policy.

v0.2 scope decision:
- Locked in `coder_planning/v0_2_scope_decision.md`.
