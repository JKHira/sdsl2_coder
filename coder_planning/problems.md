[PROPOSAL 1]
Topic: YAML 重複キーの安全な収束
Goal: 安全性と運用継続を両立し、判定の不一致を根本排除する。
Approach:
- 段階導入: まず「重複キー検出専用の lint」を追加し、CI では DIAG として運用（影響把握）。
- 明示ガード: policy.gates に `duplicate_keys` を追加して段階的に FAIL へ昇格（仕様更新とセット）。
- 実装分離: op_yaml は `strict_keys` オプション対応に留め、既存ツールは opt-in で使用（既存挙動を壊さない）。
- 収束計画: 一定期間 DIAG で検出→修正完了後に default strict へ移行（spec バージョンを上げて合意形成）。
Notes:
- 重複キーはツール間の判定不一致を生むため、最終状態は「禁止」が整合的。
- 影響範囲が広いので “検出→移行→強制” の三段階に分けるのが最も低リスク。
- 診断は「ファイル/行/重複キー/JSON Pointer」と「どちらを残すか」を明示し、修正手順が一目で分かる形式にする。

[FINDING 1]
File: sdslv2_builder/writer.py
Location: write_topology
Category: Flow Dead-End (L0 addendum)
Nature of cause: 仕様/設計不備（L0で必須のstage指定を出力できる経路がない）
Impact: ツールのみ運用では @File.stage:"L0" を満たせず、L0の正規形が作れない。
Proof:
- SDSLv2_Manual_Addendum_L0.md で L0 は @File.stage:"L0" を必須としている。
- write_topology は @File に profile/id_prefix しか出力せず、ledger から stage を渡す仕組みが存在しない。
- .sdsl2 直接編集は禁止なので、手修正で埋める運用は不可。
Fix proposal:
- topology ledger に stage を追加し、writer が @File.stage を出力する。
- もしくは L0 専用の stage 付与ツールを追加し、手編集を不要にする。

次のステップ（L0 再生成が必要なら）

project_testing/ 配下の ledger を再生成（ledger_builder.py は既定で stage:L0 を出力）
python3 -m sdslv2_builder.run --ledger project_testing/drafts/ledger/topology_ledger.yaml --out-dir project_testing/OUTPUT
生成物を project_testing/sdsl2/topology/ に反映
必要ならその再生成までこちらで実施します。


[FINDING 2]
File: L0_builder/ledger_builder.py
Location: module imports (top)
Category: Flow Dead-End (tool execution)
Nature of cause: コードのバグ（sys.path に repo root を追加していない）
Impact: README の手順どおり `python L0_builder/ledger_builder.py` で実行すると ModuleNotFoundError になり、L0 の起点が詰まる。
Proof:
- ledger_builder.py は sdslv2_builder を import するが、sys.path に ROOT を追加していない。
- draft_builder/intent_builder は sys.path を追加しており、ledger_builder だけ挙動が不一致。
- 実行時に `ModuleNotFoundError: No module named 'sdslv2_builder'` が発生した。
Fix proposal:
- ledger_builder.py に `sys.path.insert(0, str(ROOT))` を追加し、他の L0 ツールと揃える。


