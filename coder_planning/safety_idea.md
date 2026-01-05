# Safety Ideas (Reusable)

Purpose: minimal, reusable safeguards to prevent authority violations, unsafe writes, and nondeterministic outputs.

## Authority and Write Rules
- SSOT is read-only. Any SSOT change must be unified diff only.
- Tool outputs are non-authoritative and must be reproducible.
- Default allowed write roots: `project_root/drafts`, `project_root/ledger`, `project_root/OUTPUT`.
- Decisions are explicit inputs; write only when role/step allows it.

## Project Root Isolation
- Every tool accepts `--project-root` and resolves all relative paths under it.
- Reject any input path outside `project_root` (prevent leaks/mixed scope).
- Reject output paths outside allowed roots.
- If `--out` is a directory, FAIL (avoid accidental overwrite).
- If output file path is a symlink, FAIL (prevent SSOT overwrite via symlink).
- If output parent exists and is not a directory, FAIL (avoid mkdir crash/overwrite).
- Reject input paths that are directories when a file is required.
- For directory scans, reject symlinked files and re-check each file is inside `project_root`.

## Determinism and Canonicalization
- Always sort file lists and stable-order output sections.
- Use canonical key order and fixed formatting for emitted statements.
- Compute deterministic `input_hash` over the declared input set.
- Fail on missing inputs; never silently skip.
- Avoid wall-clock dependent checks unless an explicit `--today`/`--as-of` is provided.
- Use the same symlink/inside checks for generator and checker inputs to avoid false FAIL drift.

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
