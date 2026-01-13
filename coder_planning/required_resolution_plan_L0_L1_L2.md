Scope: docs/Required_Resolution.md の「最小十分」を L0/L1/L2 に段階導入する計画（記述方式ルール/仕組み/ツール設計の追加とゲート統合）。
Non-scope: 既存仕様本文の改稿。

Definitions
- Required_Resolution: docs/Required_Resolution.md に定義された最小十分セット。
- Resolution Profile: L0/L1/L2 で要求される項目と語彙を定義する repo profile（YAML）。
- Resolution Gate: Required_Resolution の不足を検出する lint/check。
- Gap Report: 不足項目と補完先を列挙する出力（OUTPUT 配下のみ）。

Rules
- 既存ツールの再実装はしない。追加は拡張/補助ツールのみ。
- L0/L1 は DIAG を基本、L2 publish は FAIL を基本とする（policy で段階昇格）。
- SSOT は read-only。出力は OUTPUT 配下のみ。symlink/traversal は拒否 MUST。
- 解析は決定的（順序・改行・正規化）であること MUST。

Status (Implemented, removed from plan)
- L0_builder/topology_resolution_lint.py, L0_builder/resolution_gap_report.py
- L0_builder/resolution_profile_lint.py
- L0_builder/resolution_gap_report.py の missing/invalid_vocab/invalid_format 分離
- L1_builder/contract_resolution_lint.py, L1_builder/contract_token_bind_check.py
- L1_builder/contract_rule_coverage_check.py, L1_builder/contract_error_model_lint.py
- L1_builder/operational_gate.py への L1 追加チェック統合
- L2_builder/ssot_kernel_lint.py, L2_builder/ssot_registry_consistency_check.py
- policy/resolution_profile.yaml, policy/contract_resolution_profile.yaml, policy/ssot_kernel_profile.yaml
- L0_builder/topology_resolution.py の profile 読み込み（語彙/書式/summary/io の検査）
- L1_builder/contract_resolution_lint.py の profile 読み込み（required_declarations / required_rule_prefixes）
- L2_builder/ssot_kernel_coverage_check.py, L2_builder/l2_gate_runner.py への publish 組み込み
- policy/ssot_kernel_profile.yaml の required_artifacts / determinism_specs 追加
- ssot_kernel_builder/ssot_definitions.ts の kernel.required_artifacts / kernel.determinism 追加
- L2_builder/ssot_kernel_coverage_check.py の required_artifacts / determinism_specs 検証拡張

---

## L0: Topology の「最低限」を明示させる段階

目的
- Topology の Node/Edge が実装単位へ落とせる最小情報を持つことを強制する。

現在のカバー
- 既存: `L0_builder/topology_resolution_lint.py`, `L0_builder/resolution_gap_report.py`
- Node.summary/io、Edge.channel/contract_refs の存在チェックは実装済み。
- `policy/resolution_profile.yaml` による vocab/summary/io ルールの導入は実装済み。
- `L0_builder/topology_resolution.py` で profile 検査は実装済み。

不足ギャップ（Required_Resolution 由来）
- なし

ツール設計（追加/拡張）
- なし

統合チェックリスト
- [x] `manual_addendum_lint.py` が profile を読む形で実行されること。
- [x] `resolution_gap_report.py` が profile に基づく不足を出力できること。

安全性の注意
- [x] `--project-root` 以外の読み取り禁止（symlink/traversal 拒否）。
- [x] 出力は `OUTPUT/` 配下固定、既存 SSOT への書き込み禁止。

---

## L1: Contract の「実装可能な骨格」を強制する段階

目的
- Contract が API 入出力・失敗条件・依存の最小骨格を持つことを必須化する。

現在のカバー
- 既存: `L1_builder/contract_resolution_lint.py`, `L1_builder/contract_token_bind_check.py`
- Interface/Function/Type/Rule の最小存在は検査済み。
- `policy/contract_resolution_profile.yaml` による最小 required 定義は実装済み。

不足ギャップ（Required_Resolution 由来）
- なし

記述方式ルール（未実装）
- なし

ツール設計（追加/拡張）
- なし

統合チェックリスト
- [x] L1 operational_gate に新規チェックを DIAG で統合（L2 publish では FAIL）。
- [x] decisions/edges.yaml の contract_refs と Rule カバレッジが一致すること。

安全性の注意
- [x] 参照は project_root 内固定、非標準パスは allow でも project_root 外拒否。
- [x] diff-only 原則維持（自動適用禁止）。

---

## L2: SSOT Kernel の「実装直前」保証段階

目的
- SSOT kernel が配布境界 JSON と Registry の整合を満たし、publish で FAIL を保証する。

現在のカバー
- 既存: `L2_builder/ssot_kernel_lint.py`, `L2_builder/ssot_registry_consistency_check.py`
- publish 時の配布境界 JSON と registry 整合は検査済み。
- `policy/ssot_kernel_profile.yaml` と coverage_check の導入は実装済み。

不足ギャップ（Required_Resolution 由来）
- なし

記述方式ルール（未実装）
- なし

ツール設計（追加/拡張）
- なし

詳細計画（L2）
- なし

統合チェックリスト
- [ ] `token_registry_check.py --fail-on-unresolved` と併用し参照穴をゼロにする。

安全性の注意
- [ ] 生成物は OUTPUT 配下固定、symlink 禁止。
- [ ] input_hash は include_decisions の既定方針と矛盾しないこと。
