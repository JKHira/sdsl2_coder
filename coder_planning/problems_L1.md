[FINDING 1]
File: L1_builder/operational_gate.py
Location: _list_draft_files
Category: A (Flow Dead-End)
Nature of cause: 仕様/設計不備（L0 の ledger YAML が draft として lint 対象に含まれてしまう）
Impact: L0→L1の通常フローで必ず draft_lint が失敗し、L1 operational gate が進めない。
Proof:
- _list_draft_files は drafts/ 配下の *.yaml を intent 以外すべて対象にする。
- L0 の ledger は `drafts/ledger/topology_ledger.yaml` に生成されるが、draft_schema ではないため E_DRAFT_UNKNOWN_FIELD で失敗する。
- 実行時に draft_lint が ledger に対して schema_version 等の必須キー欠落を報告して停止した。
Fix proposal:
- _list_draft_files で drafts/ledger/ を明示的に除外する。
- または draft_lint 対象を「drafts/直下のみ」などに制限して ledger を別扱いにする。

[FINDING 2]
File: L1_builder/schema_migration_check.py
Location: _collect_yaml_files 呼び出し（drafts_root）
Category: A (Flow Dead-End)
Nature of cause: 仕様/設計不備（L0 の ledger YAML が schema_migration の対象に含まれてしまう）
Impact: L0→L1の通常フローで必ず schema_migration_check が失敗し、L1 operational gate が進めない。
Proof:
- schema_migration_check は drafts/ 配下の *.yaml を intent 以外すべて検査する。
- L0 の ledger は `drafts/ledger/topology_ledger.yaml` に生成されるが schema_version を持たない。
- 実行時に `E_SCHEMA_MIGRATION_SCHEMA_INVALID`（schema_version must be string）が発生して停止した。
Fix proposal:
- schema_migration_check の drafts 収集から drafts/ledger/ を除外する。
- もしくは drafts/ledger を schema_migration の対象外とする規則を仕様化し、除外条件を統一する。

[FINDING 3]
File: L1_builder/token_registry_check.py
Location: _load_registry_tokens / main
Category: A (Flow Dead-End)
Nature of cause: 仕様/設計不備（トークン未使用の初期状態でも空レジストリを不正扱い）
Impact: 新規プロジェクトの通常L1フローで token_registry_check が必ず失敗し、L1 を完了できない。
Proof:
- token_registry_gen は SSOT/CONTRACT の使用が無い場合、entries: [] を生成する。
- token_registry_check は tokens が空のレジストリに対して E_TOKEN_REGISTRY_*_INVALID を必ず出す。
- 実行時に SSOT/CONTRACT registry が空であるだけで operational_gate が停止した。
Fix proposal:
- 使用トークンが 0 の場合は空レジストリを許容する（invalid にしない）。
- もしくは token_registry_gen が空でも最低1件の UNRESOLVED を出す規則に統一する。
