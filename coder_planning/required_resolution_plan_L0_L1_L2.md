Scope: docs/Required_Resolution.md の「最小十分」を L0/L1/L2 に段階導入する計画（ツール追加とゲート統合）。
Non-scope: 既存仕様本文の改稿、コード実装、既存ファイルの変更。

Definitions
- Required_Resolution: docs/Required_Resolution.md に定義された最小十分セット。
- Resolution Gate: Required_Resolution の不足を検出する lint/check。
- Gap Report: 不足項目と補完先を列挙する出力（OUTPUT 配下のみ）。

Rules
- L0/L1 は DIAG を基本、L2 publish は FAIL を基本とする（policy で段階昇格）。
- SSOT は read-only。出力は OUTPUT 配下のみ。symlink/traversal は拒否 MUST。
- 解析は決定的（順序・改行・正規化）であること MUST。

---

## L0: Topology の「最低限」を明示させる段階

目的
- Topology の Node/Edge が実装単位へ落とせる最小情報を持つことを強制する。

現在のカバー
- 既存: `L0_builder/ledger_builder.py`, `L0_builder/draft_lint.py`, `L0_builder/intent_builder.py`
- 既存は形式チェック中心で、Node/Edge の意味要件は未強制。

不足ギャップ（Required_Resolution 由来）
- Node: 責務の一文要約、入口/出口の概略、kind の閉じた語彙。
- Edge: 通信形態/カテゴリ、contract_refs 必須。

実装すべきツール（新規）
- Tool: Topology Resolution Lint  
  Py: `L0_builder/topology_resolution_lint.py`  
  役割: `sdsl2/topology/**/*.sdsl2` の @Node/@Edge メタを検査（id/kind/summary/io/category/contract_refs）。  
  Gate key: `topology_resolution`

- Tool: Resolution Gap Report  
  Py: `L0_builder/resolution_gap_report.py`  
  役割: lint の不足項目を `OUTPUT/resolution_gaps.yaml` に列挙（修正先と理由）。  
  Gate key: `resolution_gap_report`（FAIL ではなく出力専用）

統合チェックリスト
- [ ] `manual_addendum_lint.py` の後に `topology_resolution_lint.py` を実行（DIAG）。
- [ ] `resolution_gap_report.py` は常に出力し、欠落の可視化のみ行う。
- [ ] Node.kind は閉じた語彙に限定（未定義は DIAG）。
- [ ] Edge.contract_refs は空禁止（不足は DIAG）。

安全性の注意
- [ ] `--project-root` 以外の読み取り禁止（symlink/traversal 拒否）。
- [ ] 出力は `OUTPUT/` 配下固定、既存 SSOT への書き込み禁止。

---

## L1: Contract の「実装可能な骨格」を強制する段階

目的
- Contract が API 入出力・失敗条件・依存の最小骨格を持つことを必須化する。

現在のカバー
- 既存: `L1_builder/contract_decisions_lint.py`, `L1_builder/contract_promote.py`
- 既存は構造/宣言の整合に留まり、API 仕様の最小骨格は未強制。

不足ギャップ（Required_Resolution 由来）
- Interface/Function/Type の存在、入力/出力/エラーの最小定義。
- Rule/Dep の bind 追跡（仕様が浮く問題の防止）。

実装すべきツール（新規/拡張）
- Tool: Contract Resolution Lint  
  Py: `L1_builder/contract_resolution_lint.py`  
  役割: Contract の最小骨格（interface/function/type/error/rule/dep）を検査。  
  Gate key: `contract_resolution`

- Tool: Contract Token Bind Check  
  Py: `L1_builder/contract_token_bind_check.py`  
  役割: Topology の `contract_refs` が Contract 側の最小骨格に対応しているか検査。  
  Gate key: `contract_token_bind`

統合チェックリスト
- [ ] `contract_decisions_lint.py` の後に `contract_resolution_lint.py` を実行（DIAG）。
- [ ] `operational_gate.py` に `contract_token_bind_check.py` を追加（DIAG）。
- [ ] placeholder 禁止（None/TBD/Opaque 等）を検出して DIAG。
- [ ] Interface/Function/Type/Error の各最小項目が欠けると DIAG。

安全性の注意
- [ ] 参照は project_root 内固定、非標準パスは allow でも project_root 外拒否。
- [ ] diff-only 原則維持（自動適用禁止）。

---

## L2: SSOT Kernel の「実装直前」保証段階

目的
- SSOT kernel が配布境界 JSON と Registry の整合を満たし、publish で FAIL を保証する。

現在のカバー
- 既存: `L2_builder/token_registry_gen.py`, `L1_builder/token_registry_check.py`, `L2_builder/conformance_check.py`, `L2_builder/freshness_check.py`
- 既存は Registry の存在/参照整合は検査できるが、SSOT kernel の配布境界 JSON は未必須。

不足ギャップ（Required_Resolution 由来）
- `OUTPUT/ssot/ssot_definitions.json` の必須化。
- schema_version/source_rev/決定性（canonical order）の保証。

実装すべきツール（新規）
- Tool: SSOT Kernel Lint  
  Py: `L2_builder/ssot_kernel_lint.py`  
  役割: `OUTPUT/ssot/ssot_definitions.json` の存在と schema_version/source_rev/順序決定性を検査。  
  Gate key: `ssot_kernel`

- Tool: SSOT Registry Consistency Check  
  Py: `L2_builder/ssot_registry_consistency_check.py`  
  役割: registry targets が distribution boundary JSON を指しているか検証。  
  Gate key: `ssot_registry_consistency`

統合チェックリスト
- [ ] `l2_gate_runner.py --publish` に `ssot_kernel_lint.py` を追加（FAIL）。
- [ ] `token_registry_check.py --fail-on-unresolved` と併用し参照穴をゼロにする。
- [ ] `ssot_registry_consistency_check.py` は publish で FAIL、非 publish で DIAG。

安全性の注意
- [ ] 生成物は OUTPUT 配下固定、symlink 禁止。
- [ ] input_hash は include_decisions の既定方針と矛盾しないこと。

