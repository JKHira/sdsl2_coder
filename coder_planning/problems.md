# L0 実装: 追加の穴（L1/L2 への移行で揉める可能性）

## A. Context Pack 仕様未対応（最優先）
### 問題
- `L0_builder/context_pack_gen.py` の出力が Context Pack/Bundle Doc 規定とズレる（YAML構造・Open TODO・Authz/Invariants、source_rev/input_hash、保存先の閉集合など）。
- L2 の determinism/freshness で FAIL しやすい。
- 仕様上の「persisted outputs」の曖昧さと、`OUTPUT/intent_preview.sdsl2` の扱いが衝突しやすい（閉集合に含まれない）。

### 解決策（最も整合的）
- **L2 の Context Pack 仕様に準拠する出力を L0 でも出す**（同一ロジック/同一フォーマット）。
- 出力先は `OUTPUT/context_pack.yaml` 固定（spec の closed set に合わせる）。
- `source_rev`/`input_hash` を含める（SSOTのみの input_hash）。
- 派生出力を **persisted / cache** で明確に分離し、閉集合や freshness 対象を固定する。

### 具体対応案
- `sdslv2_builder.context_pack.extract_context_pack()` を “L2仕様準拠の YAML” へ拡張し、L0/L2 の両方が同じ生成器を使う。
- 既存のテキスト出力は廃止、もしくは `--out -` のみ許可に限定。
- `intent_preview` は cache 扱いと明記するか、persisted に含めるなら閉集合へ追加する（必要なら Conflicts.md に記録）。

---

## B. Intent YAML 生成の扱い（draft_builder の誤用）
### 問題
- `draft_builder.py` を Intent YAML に使うと `contract_candidates` を含みうるため Intent spec 違反になりやすい。
- L1 readiness/intent_lint で詰まりやすい。
- `schema_version` の既定値が古いと MAJOR 不一致で SCHEMA-MIGRATION に引っかかりやすい。

### 解決策（最も整合的）
- **Intent YAML 専用のビルダーを分離**し、出力スキーマを Intent spec に固定する。
- `draft_builder.py` は drafts/*.yaml（一般 Draft）のみを対象に明確化。
- `schema_version` は運用の単一ソースに固定し、デフォルトを明示管理する。

### 具体対応案
- `intent_builder.py` を追加し、`edge_intents_proposed` 必須・許容キーを閉集合化。
- README/tools_doc に「Intent は intent_builder を使う」を最小記述で追記。
- `DRAFT_SCHEMA_VERSION` 定数を用意し、draft/intent 両ビルダーで共有（必要なら policy/spec lock に寄せる）。

---

## C. Context Pack 入力の SSOT/安全性不足
### 問題
- `context_pack_gen.py` が `sdsl2/topology` 以外や symlink を拒否しない。
- 非SSOT混入のリスクが残る。

### 解決策（最も整合的）
- **SSOT root 制約 + symlink 禁止**を追加（draft_lint/edgeintent_diff と同等の境界）。
- `--input` は `sdsl2/topology/**/*.sdsl2` に限定。

---

## D. draft_lint の入力境界
### 問題
- `draft_lint.py` は `drafts/` 配下制約が無く、誤入力でも PASS と誤解される。

### 解決策（最も整合的）
- **Draft Root を `drafts/` に固定**し、外部入力・symlink を FAIL。
- `draft_builder.py` と同じ境界条件に揃える。

---

## E. source_rev の基準不一致
### 問題
- `draft_builder.py` が `project_root` ではなくリポジトリ ROOT で git rev を取るため、worktree 分離時に `source_rev` がズレ得る。

### 解決策（最も整合的）
- `source_rev` は `project_root` を基準に取得する（`git -C <project_root>`）。
- 取得失敗時のみ `UNKNOWN` に落とす。

---

## F. L0→L1 の「次に何を埋めるか」導線が弱い
### 問題
- 曖昧性の分類→ルーティング→不足項目の機械列挙が連結されておらず、L1 の readiness で詰まりやすい。

### 解決策（最も整合的）
- Bundle Doc Supplementary（decisions_needed / diagnostics_summary）を最小実装し、次アクションを機械列挙する。
- Intent/Decision/Evidence のテンプレ生成器を L0/L1 の定番ツールに組み込む。

---

## 実施順（安全性優先）
1) A: Context Pack 仕様整合 + 派生出力の persisted/cache ルール固定
2) B: Intent ビルダー分離 + schema_version 方針の単一化
3) C: Context Pack 入力境界の強化（権威混入を防止）
4) E: source_rev の基準を project_root に統一
5) D: draft_lint の境界強化（運用誤解の防止）
6) F: L0→L1 の不足項目出力とテンプレ導線
