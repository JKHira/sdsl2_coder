# Open Interpreter Integration v0.1

## Scope
- v0.1 uses Builder/Writer only (no direct SDSL edits).
- Open Interpreter runs repo-local wrappers; no custom OI plugins required.

## One-command run
Use the wrapper:
```
python scripts/oi_run_v0_1.py
```

Guard order (v0.1):
1) spec locks
2) error catalog coverage
3) Gate A
4) determinism checks
5) Gate B
6) diff gate

This executes, in order:
1) spec locks
2) error catalog coverage
3) Gate A
4) determinism checks
5) Gate B
6) diff gate

## Write allowlist (diff gate)
Only these paths are allowed to change:
- `OUTPUT/`
- `tests/goldens/`

If you need extra paths, pass `--allow` to the wrapper.
Example:
```
python scripts/oi_run_v0_1.py --allow docs/
```
Note: v0.1 expects OUTPUT/tests/goldens only; docs changes should be separate PRs.

### Allow/deny examples (v0.1)
Allowed (OK):
- `OUTPUT/**` generated outputs from `run`.
- `tests/goldens/**` golden updates tied to manifest cases.
- `tests/**/diagnostics.json` snapshot updates for expected failures.
- `tests/determinism_manifest.json` case additions or path updates (no spec changes).

Not allowed (NG):
- `sdslv2_builder/**` or `scripts/**` changes during OI runs.
- `coder_planning/**` changes (spec lock scope).
- Hand-editing `.sdsl2` files outside Builder/Writer.

Allowlist extension examples:
- Add fixtures: `python scripts/oi_run_v0_1.py --allow tests/inputs/`
- Add docs (if approved separately): `python scripts/oi_run_v0_1.py --allow docs/`
- Always state the reason and the review focus when extending allowlist.

### Staged vs unstaged notes
- `git diff --name-only` covers unstaged changes.
- `git diff --name-only --cached` covers staged changes.
- `git status --porcelain` covers untracked changes.

## System message (v0.1)
Suggested Open Interpreter system message:
```
You must not edit raw .sdsl2 files.
Use Builder/Writer only.
Write only to OUTPUT/ and tests/goldens/.
Always show diff and wait for approval before proceeding.
Do not auto-approve any command.
```

## Determinism rule
- Same input -> same output (hash match) and golden match.
- Failure diagnostics must match snapshots.

## Safety note
- Run in a sandboxed environment when possible.
- Keep approvals manual (no auto-run).
- If you see DIFF_GATE_NOT_GIT_REPO, run inside a git repo (or `git init`).
