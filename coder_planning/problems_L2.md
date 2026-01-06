## P1: L2 context_pack_gen が SSOT ルートのシンボリックリンクを検出できず境界外を読み得る

### 重要度： 高

### 問題：
- `L2_builder/context_pack_gen.py` は `ssot_root = project_root/sdsl2/topology` を `resolve()` した後、`ensure_inside(ssot_root, input_path, ...)` で「SSOT配下」を判定しています。
- `has_symlink_parent(input_path, project_root)` は `input_path` の実体（resolve後）を基準に走るため、`sdsl2/topology` 自体が symlink で外部に向いているケースを検出できません。
- 結果として、SSOT 外のファイルを「SSOT入力」として受け入れる可能性があり、権威境界の破壊に繋がります。

### 解決策案：
- `ssot_root` 自体の symlink/親symlink を明示的に拒否する（`has_symlink_parent(ssot_root, project_root)` と `ssot_root.is_symlink()` を追加）。
- `ensure_inside` の基準は `project_root` に固定し、`sdsl2/topology` 配下かどうかは `relative_to` で別途判定する。

## P2: Bundle Doc の Supplementary 入力が provenance input_hash に含まれず、freshness がすり抜ける

### 重要度： 中

### 問題：
- `L2_builder/bundle_doc_gen.py` は `OUTPUT/decisions_needed.yaml` と `OUTPUT/diagnostics_summary.yaml` が存在する場合、それらを読み込んで Bundle Doc に埋め込みます。
- しかし `compute_input_hash(...)` に `extra_inputs` として渡しておらず、provenance.inputs には SSOT/decisions/policy しか反映されません。
- `L2_builder/freshness_check.py` も同じ input_hash を計算するため、Supplementary の元ファイルが更新されても freshness が PASS し得ます（Bundle Doc の内容が古いまま残りやすい）。

### 解決策案：
- Supplementary 元ファイルを `extra_inputs` として `compute_input_hash` に追加し、provenance.inputs にも列挙する。
- `freshness_check.py` 側でも、同じ Supplementary ファイルを `extra_inputs` に加えて input_hash を一致させる。
- もし「Supplementary は freshness 対象外」とするなら、仕様で明示し、生成器も埋め込みを避ける/別カテゴリ扱いに統一する。

## P3: L2 gate で contract_sdsl_lint が実行されず、契約SSOTの不正が通過し得る

### 重要度： 中

### 問題：
- `L2_builder/contract_sdsl_lint.py` が存在する一方、`L2_builder/l2_gate_runner.py` ではこれを実行していません。
- 現状の L2 publish フローは `conformance_check` / `freshness_check` のみであり、Contract SDSL の profile/placeholder/EdgeIntent 禁止などのルール違反がゲートで検出されない可能性があります。
- 通常運用でも SSOT 直接編集のミスが混入すると、L2 で「通ったのに意味的に壊れている」状態を作り得ます。

### 解決策案：
- `l2_gate_runner.py` に `contract_sdsl_lint.py --input sdsl2/contract` を追加し、publish 時に必須ゲート化する。
- もし既存の別ゲートで必ず検出する前提なら、その前提を README/Policy で明文化し、二重化を避ける。
