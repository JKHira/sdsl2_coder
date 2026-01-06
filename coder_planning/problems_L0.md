[FINDING 1]
File: sdslv2_builder/input_hash.py
Location: _ssot_files (around lines 24-41)
Category: B
Trigger: Add a symlinked directory under `project_root/sdsl2/topology` pointing outside the repo and run any L0 tool that calls `compute_input_hash` (e.g., `draft_builder.py`).
Impact: The input_hash will include external non-SSOT files, violating authority boundaries and making L0 artifacts depend on out-of-scope data.
Proof:
- `_ssot_files()` uses `base.rglob("*.sdsl2")`, which follows symlinked directories by default.
- `_validate_path()` only checks `path.is_symlink()` and never rejects symlink parents, so files reached via symlinked dirs are accepted.
Minimal fix:
- Reject any SSOT file whose path has a symlinked parent (same `has_symlink_parent` logic used elsewhere).
- Alternatively, enumerate with `os.walk(..., followlinks=False)` and fail on symlinked directories.

[FINDING 2]
File: L0_builder/ledger_builder.py
Location: _ensure_allowed / output write path (around lines 70-130, 175-210)
Category: B
Trigger: Make `project_root/drafts/ledger` a symlink to an external directory and run `ledger_builder.py --out drafts/ledger/topology_ledger.yaml`.
Impact: The tool writes outside allowed L0 roots, enabling unintended overwrites outside the project boundary.
Proof:
- `_ensure_allowed()` only checks `path.resolve().relative_to(root.resolve())` and never rejects symlinked allowed roots.
- There is no symlink check for `project_root/drafts/ledger` or `out_path.parent` before writing.
Minimal fix:
- Fail if `project_root/drafts/ledger` is a symlink or has a symlink parent.
- Reject output paths that are symlinks (or whose parents are symlinks) before write.



## F. L0→L1 の「次に何を埋めるか」導線が弱い
### 問題
- 曖昧性の分類→ルーティング→不足項目の機械列挙が連結されておらず、L1 の readiness で詰まりやすい。

### 解決策（最も整合的）
- Bundle Doc Supplementary（decisions_needed / diagnostics_summary）を最小実装し、次アクションを機械列挙する。
- Intent/Decision/Evidence のテンプレ生成器を L0/L1 の定番ツールに組み込む。