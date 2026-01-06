[FINDING 1] V
File: l2_gate_runner.py
Location: main（L1 operational gate 実行〜exception_lint 前）
Category: A
Trigger: exceptions.yaml に有効な例外（EVIDENCE-COVERAGE など）を設定し、証拠未整備のまま l2_gate_runner.py --today 2024-01-01 を実行。
Impact: 例外があっても L1 operational gate の FAIL で即終了し、L2 の PASS_WITH_EXCEPTIONS に到達できずフローが詰む。
Proof:

l2_gate_runner.py は operational_gate.py が非0の時点で return 2 し、exception_lint.py に到達しない。
exception_lint.py は例外ファイルの検証のみで、ゲート結果を緩和する処理が存在しない。
Minimal fix:
l2_gate_runner.py で exceptions を読み、対象ターゲットのゲート失敗を PASS_WITH_EXCEPTIONS に反映する処理を追加する。
もしくは operational_gate.py に --exceptions-path を追加し、例外をゲート判定に組み込む。

[FINDING 2] V
File: Operatoon_flow.md
Location: 2.1 C（policy.yaml 記載箇所）
Category: B
Trigger: Operatoon_flow に従って policy.yaml を作成し、--policy-path を付けずに L1/L2 ゲートを実行。
Impact: policy の正準パス解釈が分岐し、CI は既定 FAIL を適用してゲートが落ちる一方、人間は policy が効いている前提で進めるため判定が一致しない。
Proof:
Operatoon_flow.md はゲート運用設定の場所を policy.yaml と明記している。
addendum_policy.py の _find_default_policy は policy.yaml のみを探索し、policy.yaml は既定では読み込まれない。
Minimal fix:
policy の権威パスを 1 本化し、Operatoon_flow.md と既定探索先を一致させる。
もし policy.yaml を採用するなら、addendum_policy.py の探索対象に追加する。

[FINDING 3] V
File: L1_builder/promote.py
Location: _find_target_file_by_scope（component 解決）
Category: B
Trigger: decisions/edges.yaml で scope.kind:"component" を使用し、同一 rel_id の @Node が複数の topology ファイルに存在する状態で promote.py または drift_check.py を実行。
Impact: E_PROMOTE_SCOPE_AMBIGUOUS/E_DRIFT_SCOPE_AMBIGUOUS で停止し、spec に明示された解決規則がないため L1 が継続不能になる。
Proof:
- SDSL2_Decisions_Spec.md は scope.kind:"component" を許可しているが、rel_id のグローバル一意性や同名が複数ファイルにある場合の解決規則を定義していない。
- L1_builder/promote.py は component 値に一致する @Node を含むファイルが 1 件でない場合に E_PROMOTE_SCOPE_AMBIGUOUS を返し、L1_builder/drift_check.py も同様に E_DRIFT_SCOPE_AMBIGUOUS を返す。
Minimal fix:
- component スコープの解決規則（グローバル一意性の必須化、または id_prefix/file の追加指定）を spec に明記し、decisions_lint/readiness_check で検証する。
- もしくは component スコープを仕様から削除し、file/id_prefix のみに限定する。

[FINDING 4] V
File: scripts/determinism_check.py
Location: main（expect 処理の直下）
Category: A
Trigger: `python scripts/determinism_check.py --manifest tests/determinism_manifest.json` を実行。
Impact: IndentationError で即時停止し、決定性ゲートが実行不能になる。
Proof:
- `expected_code = int(...)` の直後で `diag_golden = ...` が不正に深いインデントになっており、Python が構文解析で失敗する。
- `scripts/oi_run_v0_1.py` は determinism_check を必須ステップとして呼ぶため、パイプライン全体が詰む。
Minimal fix:
- `diag_golden` の代入ブロックを `expected_code` と同じインデントに修正する。

[FINDING 5] V
File: scripts/oi_run_v0_1.py
Location: main（check_error_catalog 呼び出し）
Category: A
Trigger: `python scripts/oi_run_v0_1.py` をデフォルト引数で実行。
Impact: ERROR_CATALOG_NOT_FOUND で即時停止し、フローが開始時点で詰む。
Proof:
- `scripts/oi_run_v0_1.py` は `coder_planning/errors_v0_1.md` を渡して `scripts/check_error_catalog.py` を実行する。
- リポジトリ内に `coder_planning/errors_v0_1.md` は存在せず、`coder_planning/archives/errors_v0_1.md` のみが存在するため必ず失敗する。
Minimal fix:
- `scripts/oi_run_v0_1.py` と `scripts/check_error_catalog.py` の既定パスを `coder_planning/archives/errors_v0_1.md` に統一する。



FINDING 4（determinism_check の構文エラーでパイプライン自体が即死）
FINDING 5（oi_run_v0_1 の既定エラーカタログパス不一致で開始不能）
FINDING 1（L2 例外運用がフローで詰む設計）
FINDING 2（policy パスの不一致による判定分岐）
FINDING 3（component スコープの曖昧性）

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
