# Flow Refine Plan (L0/L1/L2 Integration)

目的
- L0/L1/L2 の運用フローを一本化し、SSOT汚染・運用ブレ・手戻りを減らす。
- 「どの入力→どのツール→どの出力が権威か」を明確化する。

前提
- SSOT は `sdsl2/**` のみ。
- Intent は SSOT 外（`drafts/intent/`）固定。
- Promote は diff-only で人間レビュー前提。
- L0（Draft/Intent）の input_hash は SSOT のみ（decisions を含めない）。
- L1/L2 の input_hash は SSOT + decisions を含める。

---

## 1) L0 の Intent 入口を一本化

意図
- “SSOT に @EdgeIntent を置かない”運用を機械的に保証する。

改良
- `edgeintent_diff.py` を **プレビュー専用**に固定。
  - 出力は `OUTPUT/intent_preview.sdsl2` のみ。
  - SSOT (sdsl2/..) への diff を生成しない。
- `edgeintent_diff.py` は SSOT パスを入力に取らない（preview 以外の用途を禁止）。
  - 必要なら `intent_preview_gen.py` を新設し、Intent YAML → preview を決定論的に生成。
- 誤用を防ぐため、`edgeintent_diff.py` を `intent_preview_gen.py` へ改名するか、
  deprecated として明示し、実行入口を preview に一本化する。
- Intent の唯一入口を `drafts/intent/*.yaml` に固定。
  - 例外を許さない（policy で FAIL）。
 - Draft lint は symlink を必ず FAIL（DRAFT-SCHEMA要件の機械化）。

成果
- L0 で意図を集めても SSOT を汚さない。

---

## 1.1) L0 input_hash の仕様と実装を整合させる

意図
- L0（Draft/Intent）は SSOT のみを対象にし、決定（decisions）と混線させない。

改良
- `draft_builder.py` の input_hash 計算から decisions/edges.yaml を除外。
  - 必要なら `decisions_hash` を別フィールドで管理（input_hash とは分離）。
  - `decisions_hash` の用途（参照用/検証用）を明確化して運用に組み込む。
- L0 では decisions/edges.yaml を必須入力にしない（未作成でも Draft を生成できるようにする）。

成果
- L0 の再現性と責務境界が揃う。

---

## 2) Contract 確定の「一本道」を定義

意図
- Topology と同様に、Contract も「人間レビュー済み入力→diff-only」で昇格する。

改良（どちらかを選択し固定）
A) Decisions 方式
- `decisions/contracts.yaml` を導入。
- `contract_promote.py` が diff を出す。
- 監査導線の一貫性を優先するなら A を先に採用。

B) Contract Ledger 方式
- `contract_ledger.yaml` を入力。
- Builder → Writer → diff-only で SSOT 反映。

成果
- 「どこから何を確定したか」が監査可能になる。

---

## 3) Evidence 作成の補助ツール

意図
- evidence 手書きの負担を下げ、L1/L2 を止めない。

改良
- `evidence_template_gen.py`:
  - `decisions/edges.yaml` から claims 骨格を生成。
- `evidence_hash_helper.py`:
  - Evidence 用の content_hash 規則（LF 正規化＋末尾空白トリム）を実装し、ヘルプ/READMEに明記。
  - `source_path + locator → content_hash` を算出。
  - 既存 evidence の検証モード（--verify）を追加。
  - locator の範囲仕様（行番号の含み方/改行の扱い/末尾改行）を固定する。
  - 行番号の基準は「正規化後テキスト」と明記する。

成果
- Evidence 作成が再現可能になり、Readiness が安定する。

---

## 4) ゲート担当のマップ化

意図
- 「どのツールがどのゲートを担保するか」を明文化し、運用ブレを防ぐ。

改良
- 1枚の表を作成（tools_doc.md に追記）
  - Drift / No-SSOT-Promotion / Token Registry / Determinism
  - decisions_lint / evidence_lint / readiness_check の必須化位置
  - 担当ツールと入力/出力を明記
  - 実行順（Gate Order）と失敗時の扱いを明記
  - L1/L2 用ランナーを追加し、Operational Gate の必須列を実行順に組み込む
  - readiness_check PASS を満たさない限り Promote を実行しない（L0→L1 単調性）。
  - conformance/freshness PASS を満たさない限り L2 の publish を許可しない（L1→L2 単調性）。

成果
- 統合時の空白や重複を防げる。

---

## 5) TS SSOT kernel の扱い整理

意図
- 「現運用」と「将来計画」を混同しない。

改良
- TS SSOT kernel を **Planned** として分離。
- 実装済みなら担当ツールと検証ゲートを明記。
- 事前に「Token Registry の検証ゲート」と「Contract Registry の所在」を明記。

成果
- 文書が正確になり誤解が消える。

---

## 6) パス/シンボリックリンク検査の統一

意図
- ツール間の抜け・実装差をなくし、逸脱を機械的に遮断する。

改良
- resolve_path / ensure_inside / has_symlink_parent を共通化し、全ツールで利用する。
- OUTPUT 以外への書き込み禁止ツールは、入力側で sdsl2/ を拒否する。

成果
- パス逸脱や SSOT 汚染の再発を防げる。

## 実行順（安全優先）

1. L0 Intent 入口の一本化（edgeintent_diff 出力固定）
2. L0 input_hash の仕様・実装整合
3. Contract 確定ルートの選択と固定
4. Evidence 補助ツールの最小実装
5. Drift / No-SSOT-Promotion / Readiness の担当を明記
6. ゲート担当マップの追記（実行順込み）
7. パス/シンボリックリンク検査の統一
8. TS SSOT kernel の Planned 明記

---

## Done の定義

- Intent が SSOT に入るルートが完全に塞がれている。
- Contract の確定ルートが1本に固定され、diff-only で昇格できる。
- Evidence 生成がテンプレと hash 補助で再現可能。
- Drift / No-SSOT-Promotion が明文化され、CI で早期に止まる。
- Drift / No-SSOT-Promotion / Readiness が明文化され、CI で早期に止まる。
- ゲート担当が明文化され、CI と運用が一致（実行順を含む）。
- TS SSOT kernel が現状/将来で明確に分離されている。

---

## 実装済みメモ（1) L0 Intent 入口の一本化）

- edgeintent_diff は preview 専用。出力ターゲットは `OUTPUT/intent_preview.sdsl2` に固定。
- 入力制約:
  - topology は `sdsl2/topology/*.sdsl2` のみ許可（SSOT以外はFAIL）
  - draft は `drafts/intent/*.yaml` のみ許可（それ以外はFAIL）
  - symlink は input/output と親ディレクトリで FAIL
- SSOT への diff 出力は不可（from/to は preview 固定）。
- Intent YAML は専用スキーマで検証（`intent_schema.normalize_intent`）。
  - `contract_candidates` は Intent では禁止（未知キーとして FAIL）。
  - `edge_intents_proposed` 必須／id 重複は禁止／並び順は id 昇順。
  - placeholders 禁止（None/TBD/Opaque）。
  - input_hash は SSOT のみ前提。
- topo 判定は `relative_to(sdsl2/topology)` で実施し、`.sdsl2` 拡張子を必須化。
- intent_root が project_root 外へ解決される場合は FAIL（intent_root 自体の symlink/親symlink禁止）。
- draft_lint は `is_file()` と親ディレクトリ symlink を追加で FAIL。
- 
次の確認ポイント（必要なら）：
edgeintent_diff.py が今後も “Intent YAML のみ” を対象にする前提で、E_EDGEINTENT_DIFF_DRAFT_LINT の名称をどう扱うか（名称だけの問題なので後回しでも可）
---

## 実装済みメモ（1.1) L0 input_hash の仕様整合）

- `draft_builder.py` の input_hash から decisions/edges.yaml を除外。
- input_hash の基準 root を `project_root` に変更（L0 は SSOT のみを対象）。
- decisions 未作成でも Draft 生成を阻害しない。
- 動作確認:
  - `python3 L0_builder/draft_lint.py --input drafts/example.yaml --project-root project_x` → PASS
  - `python3 L0_builder/edgeintent_diff.py --input sdsl2/topology/MINIMAL_L0.sdsl2 --draft drafts/intent/minimal_intent.yaml --project-root project_x` → PASS

---

## 実装済みメモ（2) Contract 確定の一本道：A/Decisions 方式）

- `decisions/contracts.yaml` を導入（最小粒度は Structure + Rule）。
- `contract_decisions_lint.py` を追加：
  - scope.kind: file|id_prefix のみ
  - structures: id + decl（decl_lines も許可、line配列で多行対応）
  - rules: id + bind + refs/contract/ssot（並び順と重複チェック）
  - placeholders 禁止
- `contract_promote.py` を追加（diff-only）：
  - scope で対象 contract を特定（file / id_prefix）
  - 既存 Structure/Rule id 重複は FAIL
  - 既存順序が崩れている場合は FAIL
  - OUTPUT/ 配下に unified diff を出力
- 動作確認:
  - `python3 L1_builder/contract_decisions_lint.py --input decisions/contracts.yaml --project-root project_x` → PASS
  - `python3 L1_builder/contract_promote.py --project-root project_x --out OUTPUT/contract_promote.patch` → PASS

---

## 仕様要約（Contract Decisions: A/Decisions 方式）

入力（SSOT外・人間レビュー対象）
- `decisions/contracts.yaml` を唯一の入力とする（標準パス固定）。
- scope:
  - kind: `file` | `id_prefix`
  - file の value: `sdsl2/contract/*.sdsl2`（repo相対）
  - id_prefix の value: RELID

決定対象（最小粒度）
- `structures`: Structure の追加のみ
  - keys: `id`, `decl` または `decl_lines`
  - `decl_lines`: `{ line: "<text>" }` の配列で多行を表現
- `rules`: Rule の追加のみ
  - keys: `id`, `bind`, `refs`, `contract`, `ssot`

検証ルール（lint）
- RELID は UPPER_SNAKE_CASE を必須。
- `bind/refs` は InternalRef のみ。
- `contract` は `CONTRACT.*` のみ、`ssot` は `SSOT.*` のみ。
- 並び順は id で昇順、重複 id は FAIL。
- placeholders（None/TBD/Opaque）は禁止。

Promote の動作（diff-only）
- scope に一致する contract を特定して統一 diff を出力。
- 既存 id がある場合は FAIL（上書きしない）。
- 既存の並び順が崩れている場合は FAIL。
- 出力は OUTPUT/ 配下のみ（自動適用なし）。

draft_builder.py 実行で input_hash が SSOT のみになることを実測して確認する（必要なら実行します）。


---

## 実装済みメモ（3) Evidence 作成の補助ツール）

- `evidence_template_gen.py`：
  - `decisions/edges.yaml` から decision_id ごとに claims 骨格を生成。
  - claims は `edge` → `contract_ref` の順で安定整列。
  - `source_path` / `locator` / `content_hash` は空文字で生成（未入力のまま lint を通さない前提）。
- `evidence_hash_helper.py`：
  - `source_path` は `design/|docs/|specs/|src/|policy/attestations/` のみ許可。
  - `drafts/` / `OUTPUT/` / `sdsl2/` / `decisions/` は明示禁止。
  - content_hash 規則を CLI help に明記（CRLF→LF 正規化、行番号は正規化後テキスト基準、範囲は両端含む、行末空白トリム、末尾改行は空行として数える）。

ドキュメント更新が必要（refine完了後に実施）
- `coder_planning/tools_doc.md`（L1: evidence_template_gen / evidence_hash_helper の仕様・制約・CLI）
- `L1_builder/README.md`（実装済みツール一覧と usage）

テスト（未実行）
- `python3 L1_builder/evidence_template_gen.py --project-root project_x --out OUTPUT/evidence_template.yaml`
- `python3 L1_builder/evidence_hash_helper.py --source-path docs/open_interpreter_v0_1.md --locator L1-L4`
- `python3 L1_builder/evidence_hash_helper.py --verify decisions/evidence.yaml --project-root project_x`

---

## 実装済みメモ（4) ゲート担当のマップ化）

- `L1_builder/intent_lint.py` を追加：
  - `drafts/intent/*.yaml` を対象に Intent YAML を検証。
  - `--allow-empty` で空ディレクトリは PASS。
  - `--allow-nonstandard-path` で標準パス外も許可。
- `L1_builder/no_ssot_promotion_check.py` を追加：
  - `sdsl2/` と `decisions/` 配下の symlink を FAIL。
  - `sdsl2/` / `decisions/` 配下の drafts/intent/evidence/exceptions 混入を FAIL。
  - `policy/exceptions.yaml` 以外の exceptions.yaml を FAIL。
- `L1_builder/operational_gate.py` を追加（Operational Gate ランナー）：
  - Draft lint（`drafts/`、ただし `drafts/intent` は除外）
  - Intent lint
  - decisions_lint / evidence_lint / readiness_check
  - no_ssot_promotion_check
  - `--determinism-manifest` 指定時のみ determinism_check
- `L2_builder/l2_gate_runner.py` を追加：
  - L1 operational gate → exception_lint（`--today` 必須）
  - `--publish` 指定時に conformance_check / freshness_check

未対応（次段で実装が必要）
- drift_check
- token_registry_check
- schema_migration_check
- evidence_repair

ドキュメント更新が必要（refine完了後に実施）
- `coder_planning/tools_doc.md`（L1/L2 ランナー、Intent lint、No-SSOT-Promotion の追加）
- `L1_builder/README.md`（intent_lint / operational_gate 追加）
- `L2_builder/README.md`（l2_gate_runner 追加）

テスト（未実行）
- `python3 L1_builder/intent_lint.py --input drafts/intent --project-root project_x --allow-empty`
- `python3 L1_builder/no_ssot_promotion_check.py --project-root project_x`
- `python3 L1_builder/operational_gate.py --project-root project_x --decisions-path decisions/edges.yaml --evidence-path decisions/evidence.yaml`
- `python3 L2_builder/l2_gate_runner.py --project-root project_x --decisions-path decisions/edges.yaml --evidence-path decisions/evidence.yaml --today 2099-01-01`

---

## 実装済みメモ（5) Drift / Token Registry / Schema Migration / Evidence Repair）

- `L1_builder/drift_check.py` を追加：
  - decisions の scope に一致する topology を特定し、決定と SSOT の不整合を検出。
  - Decision 未反映／SSOT 側の Manual Edge を診断として出力。
- `L1_builder/token_registry_check.py` を追加：
  - SSOT.* / CONTRACT.* の使用トークンを sdsl2/ から抽出し、Registry で検証。
  - Registry の既定パスは `OUTPUT/ssot/ssot_registry.json` と `OUTPUT/ssot/contract_registry.json`。
- `L1_builder/schema_migration_check.py` を追加：
  - drafts / intent / decisions / evidence / contracts / exceptions の schema_version major の混在を検出。
- `L1_builder/evidence_repair.py` を追加：
  - decisions/evidence.yaml の content_hash を再計算し、diff-only で修正案を出力。
- `L1_builder/operational_gate.py` に追加ゲートを組み込み：
  - schema_migration_check / evidence_repair / token_registry_check
- `L2_builder/l2_gate_runner.py` に drift_check を組み込み：
  - Operational Gate → Drift → Exception → (publish時に conformance/freshness)

未対応（次段で実装が必要）
- Token Registry / Contract Registry の生成器
- policy に基づく gate severity の適用（schema_migration / token_registry / drift など）

ドキュメント更新が必要（refine完了後に実施）
- `coder_planning/tools_doc.md`（drift_check / token_registry_check / schema_migration_check / evidence_repair の仕様・CLI）
- `L1_builder/README.md`（drift_check / token_registry_check / schema_migration_check / evidence_repair 追加）
- `L2_builder/README.md`（l2_gate_runner の drift 組み込み）

テスト（未実行）
- `python3 L1_builder/drift_check.py --project-root project_x --decisions-path decisions/edges.yaml`
- `python3 L1_builder/token_registry_check.py --project-root project_x --ssot-registry OUTPUT/ssot/ssot_registry.json --contract-registry OUTPUT/ssot/contract_registry.json`
- `python3 L1_builder/schema_migration_check.py --project-root project_x`
- `python3 L1_builder/evidence_repair.py --project-root project_x --decisions-path decisions/edges.yaml --evidence-path decisions/evidence.yaml --out OUTPUT/evidence_repair.patch`

---

## 実装済みメモ（6) Registry 生成 + Policy severity 適用）

- `L2_builder/token_registry_gen.py` を追加：
  - SDSL2 の SSOT.* / CONTRACT.* 使用トークンから registry を生成。
  - 出力は `OUTPUT/ssot/ssot_registry.json` と `OUTPUT/ssot/contract_registry.json`。
  - `--ssot-map` / `--contract-map` で token->target の対応を指定可能。
  - `--allow-unresolved` で未解決 target を許容。
- `sdslv2_builder/policy_utils.py` を追加：
  - policy の読込と gate severity 解決（FAIL/DIAG/IGNORE）。
- `L1_builder/operational_gate.py` / `L2_builder/l2_gate_runner.py`：
  - `--policy-path` を追加し、policy.gates.* による severity を適用。
  - DIAG/IGNORE は診断出力を保持しつつ実行を継続。
- `L1_builder/evidence_repair.py`：
  - 変更なしの場合は PASS（exit 0）に変更。

未対応（次段で実装が必要）
- Drift gate の policy.drift.* 反映（manual edge / missing decisions の分類）
- Token Registry の target 妥当性検証（<path>#/<json_pointer> 形式）
- Registry 生成の入力源（TS SSOT kernel 側）との統合

ドキュメント更新が必要（refine完了後に実施）
- `coder_planning/tools_doc.md`（token_registry_gen と policy severity 適用の仕様・CLI）
- `L1_builder/README.md`（operational_gate の policy 対応と新ツール追加）
- `L2_builder/README.md`（token_registry_gen / l2_gate_runner の policy 対応）

テスト（未実行）
- `python3 L2_builder/token_registry_gen.py --project-root project_x --allow-unresolved`
- `python3 L1_builder/operational_gate.py --project-root project_x --policy-path project_x/policy/policy.yaml`
- `python3 L2_builder/l2_gate_runner.py --project-root project_x --policy-path project_x/policy/policy.yaml --today 2099-01-01`

---
