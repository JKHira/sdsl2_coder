Scope: L1に進むために不足している「edge_intents_proposed作成」と「contract_map作成」をツール化する計画。
Non-scope: L1/L2ゲートの改修、SSOTの自動書き換え。

用語
- Edge Intent: drafts/intent の edge_intents_proposed に入る明示的な接続意図。
- Contract Map: decisions_from_intent_gen に渡す edge_id → contract_refs の明示マップ。
- 明示入力: 推測ではなく、YAML/CSV/表などの人手で確定した入力。

前提
- 推測禁止（Graph Facts/contract_refs は明示入力からのみ生成）。
- 生成物は diff-only か drafts/OUTPUT 配下のみ。
- 全ての失敗は JSON Diagnostic で返す。

計画チェックリスト（順序固定）

1) 入力仕様の確定
- [x] Edge Intent 用の入力フォーマットを定義（YAML/CSVのどちらかに統一）。
- [x] Contract Map 用の入力フォーマットを定義（YAML優先、CSVは任意）。
- [x] 必須キーと禁止キーを閉集合で明示（id/from/to/direction/contract_refs）。
- [x] 既存の intent_schema / decisions_from_intent_gen との整合を確認。

2) ツール設計（L1追加ツール）
- [x] tool_a: intent_edge_builder（明示入力→drafts/intent の edge_intents_proposed 生成）
  - [x] 入力: 明示入力ファイル + 既存 intent.yaml（上書き/mergeの方針を固定）
  - [x] 出力: diff-only（既存 intent への追記パッチ）
  - [x] ガード: 重複ID、未定義from/to、方向の語彙、禁止プレースホルダ
- [x] tool_b: contract_map_builder（明示入力→decisions/contract_registry_map.yaml or drafts/contract_map.yaml）
  - [x] 入力: 明示入力ファイル
  - [x] 出力: drafts/contract_map.yaml（diff-only推奨）
  - [x] ガード: CONTRACT.* トークン検証、重複ID、空contract_refs禁止

3) 実装ステップ
- [x] I/O安全（symlink拒否、project_root配下限定、atomic write）
- [x] 解析の決定性（安定ソート、LF、同一入力で同一出力）
- [x] 既存 lint と同じバリデーション規則を再利用
- [x] 失敗時は常に JSON Diagnostic

4) 接続点の整備
- [x] decisions_from_intent_gen の入力ガイドに tool_b 生成物を明記
- [x] readiness_check / operational_gate の順序に影響しないことを確認

5) テスト計画
- [x] Test_idea の L0 intent から edge_intents_proposed を生成できる
- [x] contract_map を作成して decisions_from_intent_gen が成功する
- [x] 失敗系（重複ID/未定義from/to/空contract_refs）で診断が出る

完了条件
- L1へ進むための追加入力が「ツールのみ」で作成できる。
- decisions_from_intent_gen と evidence_template_gen の前提を満たす。
