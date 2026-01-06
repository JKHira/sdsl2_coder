# Safety Ideas (Reusable)

Purpose: minimal, reusable safeguards to prevent authority violations, unsafe writes, and nondeterministic outputs.

## Authority and Write Rules
- SSOT is read-only. Any SSOT change must be unified diff only.
- Tool outputs are non-authoritative and must be reproducible.
- Default allowed write roots: `project_root/drafts`, `project_root/drafts/ledger`, `project_root/OUTPUT`.
- Decisions are explicit inputs; write only when role/step allows it.

## Project Root Isolation
- Every tool accepts `--project-root` and resolves all relative paths under it.
- `project_root` is the repository root (Draft Root = `drafts/` at repo root).
- Reject any input path outside `project_root` (prevent leaks/mixed scope).
- Reject output paths outside allowed roots.
- Reject if the allowed root itself is a symlink (e.g., `OUTPUT/`, `sdsl2/`, `sdsl2/topology/`, `sdsl2/contract/`).
- If `--out` is a directory, FAIL (avoid accidental overwrite).
- If output file path is a symlink, FAIL (prevent SSOT overwrite via symlink).
- If output parent exists and is not a directory, FAIL (avoid mkdir crash/overwrite).
- Reject input paths that are directories when a file is required.
- For directory scans, reject symlinked files and re-check each file is inside `project_root`.

## Determinism and Canonicalization
- Always sort file lists and stable-order output sections.
- Use canonical key order and fixed formatting for emitted statements.
- Compute deterministic `input_hash` over the declared input set.
- When outputs embed supplementary inputs, include those files in `input_hash` to avoid freshness false-pass.
- Fail on missing inputs; never silently skip.
- Avoid wall-clock dependent checks unless an explicit `--today`/`--as-of` is provided.
- Use the same symlink/inside checks for generator and checker inputs to avoid false FAIL drift.
- Require provenance blocks where specified; missing provenance is a hard FAIL for persisted outputs.

## Placeholder and Ambiguity Handling
- Placeholders (None/TBD/Opaque) are forbidden in SDSL statements.
- Placeholders are allowed only in Context Pack Open TODO.
- Ambiguity routing must never create Graph Facts or decisions.

## Scope and SSOT Path Rules
- `scope.kind=file` must point to `sdsl2/topology/*.sdsl2` under project root.
- Reject absolute or external scope paths.
- Promote must fail if EdgeDecision has no matching EdgeIntent.

## Lint and Gate Safety
- Manual gate always FAIL on violations.
- Addendum gate obeys policy; default to FAIL if policy is unclear.
- No auto-fix in CI; only report diagnostics.
- Gates must include the contract SDSL lint when publishing L2 artifacts.

## Diff-Only Discipline
- EdgeIntent changes are unified diff output only.
- Never apply diffs automatically; require human approval.

## Error Design
- Diagnostics are JSON with `code/message/expected/got/path`.
- Use JSON Pointer for path; escape `~` and `/`.
- Always fail fast on invalid input type or duplicate keys.

## Common Failure Guards
- Reject block comments if not supported by parser.
- Reject duplicate metadata keys (silent overwrite is forbidden).
- Validate ids and refs at input boundaries; fail on unknown kinds.
- Validate identifier format (RELID) at boundaries to avoid YAML-injection and parse ambiguity.
- Write outputs atomically: temp file + `os.replace()`, and re-check symlink before replacement.
- Allow `source_rev` fallback to UNKNOWN only in non-strict stages; emit a warning when it happens.
- For test runners, only clean `OUTPUT/` with strict guards; never delete `.` or repo root via manifest mistakes.
- Resolve manifest-relative paths against repo root (or manifest directory) to avoid cwd-dependent flakiness.
