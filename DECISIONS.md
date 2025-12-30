# Decision Log

## 2025-12-29 - SDSLv2 pipeline core governance

Issue:
- Prevent drift in SDSLv2 generation and ensure determinism and safety.

Root Cause:
- Direct text edits and ambiguous rules led to nondeterminism and profile mixing.

Solution:
- Topology SSOT is ledger-only; graph facts must come from explicit ledger inputs.
- Output directory is `OUTPUT/` (allow subdirectories).
- Closed Set version starts at `0.1`.
- Builder/Writer are the only output path; no raw SDSL edits.
- Open Interpreter writes only to `OUTPUT/` with a diff gate.
- ID policy baseline: Node/Flow are human-named; Edge is machine-derived from PK hash; duplicates fail by default.

Prevention:
- Enforce validator errors with expected/got; CI runs the same command as local.
- Deterministic writer ordering and hashing canonicalization.
- Keep any migration exceptions isolated (if ever needed).

## 2025-12-29 - Open Interpreter ops rules + error code format

Issue:
- Stabilize Open Interpreter operations and make errors machine-repairable.

Root Cause:
- Unbounded commands and write scope cause drift and unsafe edits; ad-hoc errors are hard to fix.

Solution:
- Run mode uses a wrapper; allowlist only:
  - `python -m sdslv2_builder.run ...`
  - `python -m sdslv2_builder.lint ...`
  - `git status`, `git diff`, `git diff --stat`
- Write scope is limited to `OUTPUT/` (subdirectories allowed).
- Diff gate required before applying changes; lint must pass to publish outputs.
- Open Interpreter profile: `safe_mode=ask`, `auto_run=false`.
- Error code format: `E_<SNAKE_CASE>` (e.g., `E_TOKEN_PLACEMENT`).

Prevention:
- CI runs the same commands as local, with determinism checks (diff 0).
- Keep migration exceptions isolated, never in the default run path.

## 2025-12-29 - Closed Set v0.1 rules

Issue:
- Finalize v0.1 closed set without drift in @Rule binding and metadata usage.

Root Cause:
- Optional bind on @Rule and ambiguous metadata synthesis create variance.

Solution:
- @Rule requires bind in all cases (attached or detached).
- title/desc are allowed in v0.1 but must not be synthesized by Builder.

Prevention:
- Enforce E_RULE_BIND_REQUIRED for all @Rule statements.
- Keep closed set versioned; changes require a spec bump.

## 2025-12-29 - Edge id in v0.1

Issue:
- Align closed set keys with ID policy for topology edges.

Root Cause:
- @Edge keys omitted id while ID rules described machine-derived ids.

Solution:
- @Edge includes id (required, machine-derived) in v0.1.

Prevention:
- Keep closed set + ID rules in the same doc and update together on spec bumps.

## 2025-12-29 - Deterministic hashing + ref typing + @Dep bind/from rule

Issue:
- Prevent drift in Edge IDs, references, and @Dep alignment in v0.1.

Root Cause:
- Ad-hoc canonical_json, raw string refs, and bind/from duplication cause variance.

Solution:
- Edge PK canonical_json uses RFC 8785 (JCS).
- contract_refs sorted by Unicode codepoint and deduped before JCS.
- InternalRef/ContractRef/SSOTRef are typed wrappers; raw strings rejected.
- @Dep bind must equal from; Builder auto-sets bind = from_ref.
- Error payload path format is JSON Pointer.

Prevention:
- Keep JCS and ref-typing rules in the v0.1 API spec.
- Validate @Dep bind/from alignment with E_DEP_BIND_MUST_EQUAL_FROM.

## 2025-12-29 - Error catalog v0.1 locked

Issue:
- Finalize error catalog to stabilize CI and self-repair loops.

Root Cause:
- Unlocked error codes cause CI instability and drift in remediation steps.

Solution:
- Lock `coder_planning/errors_v0_1.md` as the v0.1 error catalog.
- Path format fixed to JSON Pointer (RFC 6901) with escape rules (~0, ~1).
- contract_refs error roles fixed (placement vs type vs empty list).
- E_OUTPUT_NONDETERMINISTIC details include fingerprint/ordering_key.

Prevention:
- Update error catalog only via version bump.

## 2025-12-29 - Fixed run/lint commands and diff gate (v0.1)

Issue:
- Ensure local and CI execute the same commands to avoid drift.

Root Cause:
- Ambiguous commands and output paths cause inconsistent results.

Solution:
- Fixed run command:
  - `python -m sdslv2_builder.run --ledger <PATH> --out-dir OUTPUT`
  - Output default: `OUTPUT/<id_prefix>/topology.sdsl2`
  - If ledger has `output.topology_v2_path`, use it only if under OUTPUT; otherwise error.
- Fixed lint command:
  - `python -m sdslv2_builder.lint --input OUTPUT`
  - Directory input scans `*.sdsl2` recursively.
- Diff gate (required):
  - `git status --porcelain` (must show OUTPUT-only changes)
  - `git diff --stat -- OUTPUT/`
  - `git diff -- OUTPUT/`
  - Optional: `git diff --name-only -- OUTPUT/`

Prevention:
- Same command set is used in local runs and CI.

## 2025-12-29 - Golden outputs placement (v0.1)

Issue:
- Prevent drift between generated outputs and golden references.

Root Cause:
- Mixing generated outputs with versioned goldens makes review and rollback unstable.

Solution:
- Generated output: `OUTPUT/<id_prefix>/topology.sdsl2`
- Golden reference: `tests/goldens/<id_prefix>/topology.sdsl2`
- Spec bump: add new golden file (e.g., `topology.v0_2.sdsl2`) instead of overwriting.

Prevention:
- CI compares OUTPUT against tests/goldens, not in-place OUTPUT.

## 2025-12-29 - API spec v0.1 locked

Issue:
- Freeze API spec to prevent breaking changes in v0.1.

Root Cause:
- Core determinism and ops rules become unstable if modified ad-hoc.

Solution:
- Lock `coder_planning/builder_writer_api_v0_1.md` as v0.1.
- Changes require spec bump (v0.2+).
- Golden files are compared as snapshots for CI determinism.

Prevention:
- Treat JCS edge ID, JSON Pointer paths, typed refs/tokens, run/lint/diff gate, and golden layout as breaking if changed.
