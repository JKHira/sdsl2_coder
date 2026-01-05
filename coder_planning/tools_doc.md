# L0 Builder Tools

Purpose: minimal L0 toolchain aligned with `sdsl2_manuals/plan/Recommended_Tools.md`.
This folder contains thin wrappers plus a status map.

## Tools (L0 minimal set)

Ready
- `context_pack_gen.py` -> Context Pack generator (wraps `sdslv2_builder.context_pack`).
- `manual_addendum_lint.py` -> Manual Gate (Gate A) + Addendum lint (wraps scripts).
- `draft_builder.py` -> Normalize/fill Draft YAML and write canonical output.
- `draft_lint.py` -> Draft schema validation.
- `ledger_builder.py` -> Build topology ledger from a node list.
- `edgeintent_diff.py` -> Unified diff for @EdgeIntent updates from Draft.

Planned (not implemented yet)
- (none)

## Project root layout (recommended)

Create a per-project root so drafts/ledger/decisions/OUTPUT are isolated:

```
project_x/
  drafts/
  ledger/
  decisions/
  OUTPUT/
  sdsl2/  # read-only SSOT mirror (contract/topology)
```

Pass `--project-root project_x` to L0 tools.

## Quickstart (L0)


context_pack_gen.py

役割
	•	sdslv2_builder.context_pack.extract_context_pack() をCLIとして提供する Context Pack生成ツール。
	•	入力 .sdsl2（topology）から、指定 @Node.<RELID> を中心に hops 近傍を抽出し、OUTPUT配下に書き出す（またはstdout）。

使い方（最小）

CLI：
	•	ファイル出力（デフォルト）
	•	python3 L2_builder/context_pack_gen.py --input sdsl2/topology/MINIMAL_L0.sdsl2 --target @Node.NODE_A --project-root project_x
	•	stdoutに出す
	•	python3 .../context_pack_gen.py --input ... --target @Node.NODE_A --out -

主な引数
	•	--input：SDSL2ファイルパス（project_root相対可）
	•	--target：@Node.<RELID>（必須）
	•	--hops：近傍のホップ数（>=0、デフォルト1）
	•	--out：出力パス（デフォルトは <repo>/OUTPUT/context_pack.yaml）、- でstdout
	•	--project-root：プロジェクトルート（省略時はrepo root）

安全・制約（コード上のゲート）
	•	--hops < 0 は E_CONTEXT_PACK_HOPS_INVALID
	•	--input は project_root配下必須（E_CONTEXT_PACK_INPUT_OUTSIDE_PROJECT）
	•	--out は project_root/OUTPUT 配下必須（E_CONTEXT_PACK_OUTPUT_OUTSIDE_OUTPUT）
	•	--out が既存ディレクトリは不可（E_CONTEXT_PACK_OUTPUT_IS_DIRECTORY）
	•	入力が存在しない場合：E_CONTEXT_PACK_INPUT_NOT_FOUND: <path>

出力ファイル
	•	既定：OUTPUT/context_pack.yaml
	•	内容：extract_context_pack() が返す 人間可読テキスト（ヘッダ、Nodes/Edges/Contracts、Open TODOなど）。
	•	役割：LLMやレビュー工程に渡す「局所トポロジ要約」。

⸻

draft_builder.py

役割
	•	Draft YAML（設計途中の提案情報）を 正規化・検証して drafts/ 配下に保存する生成器。
	•	Draftに必要なメタ情報を埋める：
	•	schema_version（欠けていれば 0.1）
	•	generator_id（引数で指定、デフォルト draft_builder_v0_1）
	•	source_rev（git rev-parse HEAD、失敗時 UNKNOWN）
	•	input_hash（decisions/edges.yaml を追加入力として compute_input_hash() で算出）
	•	scope（無ければ --scope-from 等から導出）
	•	その上で normalize_draft(fill_missing=False) を通し、違反があれば診断JSONで失敗する。

使い方（最小）

CLI（典型）：
	•	python3 L2_builder/draft_builder.py --input drafts/my_draft.yaml --project-root project_x

scope未記載のDraftを作る場合（scope導出）：
	•	python3 .../draft_builder.py --input <in.yaml> --scope-from sdsl2/topology/MINIMAL_L0.sdsl2 --project-root project_x

主な引数
	•	--input：Draft YAMLパス
	•	--out：出力先（省略時は原則 input を上書き。ただし入力が drafts/ 外なら drafts/ に退避）
	•	--generator-id：generator_id に設定
	•	--scope-from：scope.kind=file として scope.value を project_root相対パスで導出
	•	--scope-kind / --scope-value：scopeが無いときの上書き指定
	•	--project-root：プロジェクトルート（出力は project_root/drafts 配下に制限）

重要な制約（事故防止の観点で効いているところ）
	•	scope_from は project_root配下必須。外なら E_DRAFT_SCOPE_OUTSIDE_PROJECT（診断JSON）
	•	scope.kind=file の場合、sdsl2/topology/<file>.sdsl2 以外を拒否（E_DRAFT_SCOPE_NOT_SSOT）
	•	decisions/edges.yaml が project_root に無いと E_DRAFT_DECISIONS_NOT_FOUND
	•	compute_input_hash() が FileNotFoundError / symlink(ValueError) を起こしたら即失敗（例外文字列をstderr）
	•	出力は project_root/drafts 配下に強制：
	•	外なら E_DRAFT_DRAFTS_OUTSIDE_PROJECT
	•	出力がディレクトリなら E_DRAFT_OUTPUT_IS_DIRECTORY

出力ファイル
	•	出力先：project_root/drafts/<name>.yaml（--out で変更可だが drafts/ 外は禁止）
	•	内容：normalize_draft() 済みの Draft（YAML）
	•	listsはソートされ、プレースホルダ禁止、語彙制約に適合した状態
	•	source_rev / input_hash 等が確定値で埋まる
	•	役割：下流工程（edgeintent_diff など）で機械的に扱えるDraftの“確定版”。

⸻

draft_lint.py

役割
	•	Draft YAMLを lint（正規化検証）だけ行う軽量CLI。
	•	normalize_draft(fill_missing=False) に通し、診断があれば 診断JSONをstderrに出して失敗。

使い方（最小）

CLI：
	•	python3 L2_builder/draft_lint.py --input drafts/my_draft.yaml --project-root project_x

主な引数
	•	--input：Draft YAML
	•	--project-root：入力の相対解決と “外部参照禁止” の境界

制約
	•	inputは project_root配下必須：E_DRAFT_INPUT_OUTSIDE_PROJECT
	•	inputが無い：E_DRAFT_INPUT_NOT_FOUND
	•	rootがdictでない：E_DRAFT_SCHEMA_INVALID（診断JSON）

出力ファイル
	•	生成しない（stdout/stderrのみ）。

⸻

edgeintent_diff.py

役割
	•	Draft（edge_intents_proposed）をソースに、Topology .sdsl2 内の @EdgeIntent ブロックを
	•	既存IDは置換
	•	未存在IDは追記（Node/EdgeIntentの後ろに挿入）
した場合の unified diff を生成するツール。
	•	直接書き換えはせず、差分だけを出す設計（安全側）。

使い方（最小）

CLI：
	•	python3 L2_builder/edgeintent_diff.py --input sdsl2/topology/MINIMAL_L0.sdsl2 --draft drafts/my_draft.yaml --project-root project_x

主な引数
	•	--input：Topology .sdsl2
	•	--draft：Draft YAML（edge_intents_proposed 必須）
	•	--project-root：両入力がこの配下であることを強制

動作の要点
	•	Draftは normalize_draft(fill_missing=False) に通し、NGなら E_EDGEINTENT_DIFF_DRAFT_LINT
	•	edge_intents_proposed が空なら E_EDGEINTENT_DIFF_EMPTY
	•	Draft内 intent id が重複していれば E_EDGEINTENT_DIFF_DUPLICATE_ID
	•	トポロジ内の既存 @EdgeIntent { ... } は、lint._capture_metadata/_parse_metadata_pairs で範囲抽出して置換
	•	新規intentは _find_insert_index() により、最後の @Node / @EdgeIntent の直後にまとめて挿入

出力
	•	stdout：diff -u 形式（unified diff）
	•	変更が無い場合は stderr に E_EDGEINTENT_DIFF_NO_CHANGE を出して終了コード2

出力ファイル
	•	生成しない（差分表示のみ）。
	•	役割：人手レビュー・適用（patch）前提の安全な更新手段。

⸻

ledger_builder.py

役割
	•	Topology ledger v0.1（ledger.py が読む入力）を 半自動で作るジェネレータ。
	•	Node一覧の入力元を2系統持つ：
	1.	--nodes：1行1RELIDのテキスト
	2.	--extract-structures-from：任意ファイルから @Structure.<RELID> を正規表現抽出（オプション）
	•	出力ledgerは edgesを空で作り、必要に応じて evidence_note を付与する。

使い方（最小）

ノード一覧ファイルからledger生成：
	•	python3 L2_builder/ledger_builder.py --nodes inputs/nodes.txt --id-prefix MY_TOPO --out ledger/my_topology.yaml --project-root project_x

@Structureトークン抽出で生成（明示許可が必要）：
	•	python3 .../ledger_builder.py --extract-structures-from some.txt --allow-structure-nodes --id-prefix MY_TOPO --out ledger/my_topology.yaml --line-start 10 --line-end 80 --project-root project_x

主な引数
	•	--id-prefix（必須）
	•	--kind：node.kind（デフォルト component）
	•	--out：出力先（必須）
	•	入力：--nodes または --extract-structures-from のどちらか必須

制約・安全
	•	入力が両方無い：E_LEDGER_BUILDER_INPUT_MISSING
	•	--extract-structures-from を使うには --allow-structure-nodes 必須（E_LEDGER_BUILDER_STRUCTURE_NODES_FORBIDDEN）
	•	入力ファイルは project_root 配下必須（E_LEDGER_BUILDER_INPUT_OUTSIDE_PROJECT 等）
	•	出力は project_root/ledger または project_root/OUTPUT 配下のみ許可
	•	それ以外は E_LEDGER_BUILDER_OUTPUT_OUTSIDE_PROJECT
	•	出力がディレクトリは不可（E_LEDGER_OUTPUT_IS_DIRECTORY）
	•	Node id がRELIDに合わない行は詳細をstderrに列挙し E_LEDGER_BUILDER_INVALID_NODE_ID

出力ファイル
	•	YAML（topology-ledger-v0.1）を生成
	•	version: topology-ledger-v0.1
	•	file_header.profile: topology
	•	file_header.id_prefix: "<id_prefix>"
	•	nodes: - id: "<RELID>" kind: "<kind>"
	•	edges: []
	•	source.evidence_note（任意）
	•	役割：sdslv2_builder.run へ渡すledgerの雛形作成（特に“ノードだけ先に確定”用）。

⸻

manual_addendum_lint.py

役割
	•	人手で選んだファイル群に対して、Gate A → Addendum check を順に実行する“まとめCLI”。
	•	実装はラッパであり、中核ロジックは scripts/gate_a_check.py と scripts/addendum_check.py に委譲。

使い方（最小）

CLI：
	•	python3 L2_builder/manual_addendum_lint.py --input sdsl2/topology --input sdsl2/contract --project-root project_x
	•	ポリシーを明示する場合：
	•	python3 .../manual_addendum_lint.py --input sdsl2/topology --policy-path .sdsl/policy.yaml --project-root project_x

主な引数
	•	--input：ファイルまたはディレクトリ（複数指定可）。ディレクトリは *.sdsl2 を再帰収集。
	•	--policy-path：scripts/addendum_check.py に渡す
	•	--project-root：入力相対解決・境界

制約
	•	inputが project_root 外：E_LINT_INPUT_OUTSIDE_PROJECT
	•	対象ファイルが一つも無い：E_LINT_INPUT_NOT_FOUND
	•	Gate A が失敗したら、その終了コードで即終了（Addendum checkに進まない）

出力ファイル
	•	生成しない（各スクリプトのstdout/stderrと終了コードのみ）。




L0 Builder Tools END
==================================





==================================
# L1 Builder tools

Purpose: L1 promotion tooling (Decisions + Evidence -> SSOT patch).

Notes:
- SSOT lives under sdsl2/ only; never write SSOT directly.
- Outputs must be unified diffs under OUTPUT/.
- Inputs are decisions/ and drafts/ per specs.



decisions_lint.py

役割
	•	decisions/edges.yaml（EdgeDecisionの決定記録）を スキーマ／語彙／並び順／重複まで含めて厳密にlintする。
	•	失敗時は Diagnostic配列（JSON）をstderr に出す（または一部は単独エラーコード文字列）。

使い方（最小）
	•	標準パスをlint（推奨）
	•	python3 L1_builder/decisions_lint.py --input decisions/edges.yaml --project-root <project>
	•	標準パス以外を許可
	•	python3 .../decisions_lint.py --input <path> --allow-nonstandard-path --project-root <project>

主な引数
	•	--input：decisions YAML（通常 decisions/edges.yaml）
	•	--allow-nonstandard-path：標準パス以外を許容
	•	--project-root：境界（入力がこの配下である必要）

入力制約（ファイルレベル）
	•	project_root外：E_DECISIONS_INPUT_OUTSIDE_PROJECT
	•	不在：E_DECISIONS_INPUT_NOT_FOUND
	•	ディレクトリ：E_DECISIONS_INPUT_IS_DIR
	•	symlink：E_DECISIONS_INPUT_SYMLINK
	•	--allow-nonstandard-path が無いのに標準パスでない：E_DECISIONS_INPUT_NOT_STANDARD_PATH

スキーマ（トップレベル）

許可キー：schema_version, provenance, scope, edges
	•	それ以外：E_DECISIONS_UNKNOWN_FIELD

必須／検証
	•	schema_version：非空 string、プレースホルダ禁止（None/TBD/Opaque）
	•	無効：E_DECISIONS_SCHEMA_INVALID / E_DECISIONS_PLACEHOLDER_FORBIDDEN
	•	provenance：object 必須
	•	許可キー：author, reviewed_by, source_link
	•	各値は非空 string、プレースホルダ禁止
	•	Unknown：E_DECISIONS_UNKNOWN_FIELD
	•	値不正：E_DECISIONS_FIELD_INVALID
	•	scope：object 必須
	•	kind ∈ {file,id_prefix,component}
	•	value：非空 string、プレースホルダ禁止
	•	kind=fileの場合：
	•	repo-relative（先頭 / 禁止、.. 禁止）
	•	project_root配下に解決されること
	•	ファイルが存在すること
	•	sdsl2/topology/*.sdsl2 形式であること
	•	いずれも不正：E_DECISIONS_SCOPE_INVALID / E_DECISIONS_PLACEHOLDER_FORBIDDEN

edges（EdgeDecision配列）
	•	edges は list 必須（違反：E_DECISIONS_SCHEMA_INVALID）
	•	各要素は object（違反：E_DECISIONS_EDGE_INVALID）
	•	許可キー：id,from,to,direction,contract_refs
	•	Unknown：E_DECISIONS_EDGE_INVALID

各フィールド検証
	•	id/from/to：RELID（RELID_RE、UPPER_SNAKE_CASE）
	•	direction：DIRECTION_VOCAB に含まれること
	•	placeholders（None/TBD/Opaque）禁止：E_DECISIONS_PLACEHOLDER_FORBIDDEN

contract_refs
	•	list 必須
	•	各要素：CONTRACT.* トークン（CONTRACT_TOKEN_RE）
	•	非空必須（空なら E_DECISIONS_EDGE_INVALID）
	•	ソート済み＋重複排除済みである必要
	•	unsorted/dup：E_DECISIONS_LIST_NOT_SORTED

重複・整列ルール
	•	edges全体：id 昇順でソート必須（E_DECISIONS_LIST_NOT_SORTED）
	•	id の一意性（E_DECISIONS_DUPLICATE_ID）
	•	(from,to,direction) の重複禁止（E_DECISIONS_DUPLICATE_EDGE）

scope=component の追加制約
	•	scope.value は各edgeの from または to と一致必須
	•	違反：E_DECISIONS_SCOPE_INVALID

出力
	•	成功：exit 0（何も出さない）
	•	失敗：exit 2
	•	一部は単独エラー文字列（例：標準パス違反）
	•	それ以外は Diagnostic JSON（stderr）

⸻

evidence_lint.py

役割
	•	decisions/evidence.yaml を、decisions/edges.yaml の内容と突き合わせて 証拠の整合性・形式・並び順・カバレッジを検証する。
	•	parse_decisions_file()（decisions_lintの中核）を再利用し、まず decisions を必ず正として通す。

使い方（最小）
	•	標準パス
	•	python3 L1_builder/evidence_lint.py --project-root <project>
	•	非標準パス許可
	•	python3 .../evidence_lint.py --decisions-path <...> --evidence-path <...> --allow-nonstandard-path --project-root <project>

主な引数
	•	--decisions-path（既定 decisions/edges.yaml）
	•	--evidence-path（既定 decisions/evidence.yaml）
	•	--allow-nonstandard-path
	•	--project-root

入力制約（ファイルレベル）

decisions側／evidence側ともに：
	•	project_root外：E_EVIDENCE_INPUT_OUTSIDE_PROJECT
	•	不在：E_EVIDENCE_DECISIONS_NOT_FOUND / E_EVIDENCE_INPUT_NOT_FOUND
	•	ディレクトリ：E_EVIDENCE_DECISIONS_IS_DIR / E_EVIDENCE_INPUT_IS_DIR
	•	symlink：E_EVIDENCE_DECISIONS_SYMLINK / E_EVIDENCE_INPUT_SYMLINK
	•	標準パス強制（allow無し）：E_EVIDENCE_*_NOT_STANDARD_PATH

evidence.yaml スキーマ（トップレベル）

許可キー：schema_version, source_rev, input_hash, scope, evidence
	•	Unknown：E_EVIDENCE_UNKNOWN_FIELD

必須／検証
	•	schema_version：非空 string、プレースホルダ禁止
	•	source_rev：非空 string、プレースホルダ禁止
	•	input_hash：sha256: で始まる（sha256:<hex>形式を要求するが、厳密正規表現は item 側のみ）
	•	scope：object で、decisionsのscopeと完全一致必須（E_EVIDENCE_SCOPE_MISMATCH）

evidence（辞書）
	•	evidence は object 必須（違反：E_EVIDENCE_SCHEMA_INVALID）
	•	キー（decision_id）は 辞書キー順が辞書式ソートされている必要
	•	unsorted：E_EVIDENCE_LIST_NOT_SORTED
	•	evidenceキーは decisionsのedge id集合に含まれる必要
	•	不明ID：E_EVIDENCE_DECISION_UNKNOWN

evidence item（各decision_id配下の配列要素）

evidence[decision_id] は list 必須
	•	要素は dict 必須
	•	許可キー：source_path, locator, content_hash, note, claims

source_path
	•	非空 string、プレースホルダ禁止
	•	repo-relative（/ 始まり禁止、.. 禁止）
	•	許可プレフィックスのみ：
design/, docs/, specs/, src/, policy/attestations/
	•	禁止ルート：drafts/, OUTPUT/, sdsl2/, decisions/
	•	project_root配下に解決できること（外ならエラー）

locator
	•	正規表現：L<start>-L<end> または H:<heading>#L<start>-L<end>
	•	LOCATOR_RE = ^L\d+-L\d+$|^H:[^#]+#L\d+-L\d+$

content_hash
	•	厳密に sha256: + 64hex（CONTENT_HASH_RE）

note
	•	Noneまたは string（プレースホルダ禁止）

claims
	•	非空 list 必須
	•	各claimは dict、許可キー：kind,decision_id,value
	•	kind ∈ {edge,contract_ref}
	•	decision_id は evidence のキーと一致必須
	•	kind=contract_ref のとき value は CONTRACT.*
	•	kind=edge のとき value は 省略（None以外禁止）
	•	claims は (kind, decision_id, value) の順序で安定整列（kindは edge→contract_ref の順で評価）

重複・整列
	•	evidence items は安定順序（source_path/locator/content_hash/note/claims）で整列必須
	•	完全同一itemの重複禁止：E_EVIDENCE_DUPLICATE_ITEM

出力
	•	成功：exit 0
	•	失敗：exit 2（Diagnostic JSONをstderr）

⸻

evidence_template_gen.py

役割
	•	decisions/edges.yaml から Evidence Map の骨格を生成するテンプレ生成器。
	•	decision_id ごとに claims（edge + contract_ref）を生成し、source_path/locator/content_hash は空文字で出力する。

使い方（最小）
	•	python3 L1_builder/evidence_template_gen.py --project-root <project>
	•	出力先指定
	•	python3 .../evidence_template_gen.py --out OUTPUT/evidence_template.yaml --project-root <project>

主な引数
	•	--decisions-path（既定 decisions/edges.yaml）
	•	--out（既定 OUTPUT/evidence_template.yaml）
	•	--allow-nonstandard-path
	•	--allow-decisions-output（decisions/evidence.yaml への出力を許可）
	•	--project-root

制約
	•	decisions_path は project_root 配下必須、symlink 不可
	•	標準パス強制（allow 無し）
	•	out は project_root/OUTPUT 配下のみ（decisions 出力は allow 指定時のみ）
	•	out が symlink/dir は不可

出力
	•	OUTPUT/evidence_template.yaml（YAML）
	•	schema_version/source_rev/input_hash/scope/evidence を含む

⸻

evidence_hash_helper.py

役割
	•	Evidence 用の content_hash を算出/検証する補助ツール。
	•	LF 正規化＋行末空白トリムを行い、指定 locator の範囲をハッシュ化する。

使い方（最小）
	•	単発計算
	•	python3 L1_builder/evidence_hash_helper.py --source-path docs/example.md --locator L10-L20
	•	検証（evidence.yaml 全体）
	•	python3 .../evidence_hash_helper.py --verify decisions/evidence.yaml --project-root <project>

主な引数
	•	--source-path：repo 相対パス
	•	--locator：L<start>-L<end> / H:<heading>#L<start>-L<end>
	•	--verify：evidence.yaml を検証
	•	--project-root

制約
	•	source_path は design/docs/specs/src/policy/attestations のみ許可
	•	drafts/OUTPUT/sdsl2/decisions 配下は明示禁止
	•	行番号は正規化後テキスト基準（1始まり、両端含む）
	•	末尾改行がある場合は最終空行としてカウント

出力
	•	単発：content_hash を stdout
	•	verify：不一致があれば Diagnostic JSON を stderr

⸻

promote.py

役割
	•	decisions/edges.yaml の確定EdgeDecisionを、対象の sdsl2/topology/*.sdsl2 に **@Edge ブロックとして昇格（promote）**させるための unified diff を生成する。
	•	重要：実ファイルを書き換えず、差分のみ出力（または OUTPUT 配下に保存）。

使い方（最小）
	•	stdoutにdiff
	•	python3 L1_builder/promote.py --project-root <project>
	•	OUTPUTにdiffを書き出し
	•	python3 .../promote.py --out OUTPUT/promote.patch --project-root <project>

主な引数
	•	--decisions-path（既定 decisions/edges.yaml）
	•	--allow-nonstandard-path
	•	--out（省略時 stdout、指定時は project_root/OUTPUT 配下のみ許可）
	•	--project-root

対象トポロジファイルの決定（scope解決）
	•	decisionsの scope から _find_target_file_by_scope() を実行
	•	kind=file：scope.value をそのまま解決（symlink親禁止・存在必須）
	•	kind=component：sdsl2/topology を走査し、@Node に scope.value が含まれるファイルを探す
	•	kind=id_prefix：@File の id_prefix が scope.value と一致するファイルを探す
	•	候補が1つに定まらない：E_PROMOTE_SCOPE_AMBIGUOUS
	•	symlink関係は徹底排除（親がsymlinkでも拒否）：E_PROMOTE_SCOPE_SYMLINK

トポロジ側のパースと制約
	•	@File ヘッダは
	•	存在必須、重複不可、先頭ステートメントである必要
	•	いずれか違反で E_PROMOTE_* を投げ、上位で E_PROMOTE_PARSE_ERROR になる
	•	@EdgeIntent と Flow がトポロジ内にあると即拒否：E_PROMOTE_FORBIDDEN_KIND
	•	@File.profile が topology でないと拒否：E_PROMOTE_PROFILE_INVALID
	•	既存 @Edge の id はソート済み必須：E_PROMOTE_EDGE_ORDER_INVALID
	•	既存Edge群が連続したrunでない（Edgeブロック間に他のステートメントが挟まる）と拒否：E_PROMOTE_EDGE_RUN_NON_CONTIGUOUS → E_PROMOTE_PARSE_ERROR

何を追加するか（決定ロジック）

decisionsの各edgeについて：
	•	from/to がトポロジ内のNode集合に存在しない：E_PROMOTE_NODE_NOT_FOUND
	•	既存Edgeに同一 (from,to,direction,contract_refs) が既にある → 追加不要
	•	同一 id がある：
	•	tuple一致なら追加不要
	•	tuple不一致なら衝突：E_PROMOTE_EDGE_CONFLICT
	•	追加対象がゼロ：E_PROMOTE_NO_CHANGE

生成する差分の内容
	•	stage更新：@File.stage == "L0" の場合、L1 に更新
	•	新規Edgeは id でソートし、既存Edgeの id ソート順に保つ位置へ挿入
	•	既存Edgeが無い場合は Node群の直後にまとめて挿入
	•	@Edge のフォーマットは必ず
	•	@Edge { id:"...", from:@Node.X, to:@Node.Y, direction:"...", contract_refs:[ ... ] }
	•	contract_refs は複数行で整形され、各要素は "..." + カンマ

出力制約（–out）
	•	--out 指定時：
	•	project_root配下必須：E_PROMOTE_OUTPUT_OUTSIDE_PROJECT
	•	さらに project_root/OUTPUT 配下必須：E_PROMOTE_OUTPUT_OUTSIDE_OUTPUT
	•	出力先がディレクトリ：E_PROMOTE_OUTPUT_IS_DIR

⸻

readiness_check.py

役割
	•	「L1へ上げる準備が整っているか」を、以下3点の整合で検証するゲート：
	1.	decisions（edges.yaml）がlint通過
	2.	evidence（evidence.yaml）がlint通過
	3.	drafts/intent/*.yaml（Intentドラフト）が存在し、decisionsと スコープ一致＋ID一致＋from/to一致する
	4.	さらに decisions の contract_refs が evidence の claims で contract_ref としてカバーされている

使い方（最小）
	•	python3 L1_builder/readiness_check.py --project-root <project>
	•	非標準パス許可：
	•	python3 .../readiness_check.py --decisions-path <...> --evidence-path <...> --allow-nonstandard-path --project-root <project>

主な引数
	•	--decisions-path / --evidence-path（既定は標準）
	•	--allow-nonstandard-path
	•	--project-root

入力制約（decisions/evidence）
	•	evidence_lint と同等の 外部／dir／symlink／標準パス強制を実施
	•	例：E_READINESS_DECISIONS_SYMLINK, E_READINESS_EVIDENCE_NOT_STANDARD_PATH など

drafts/intent の読み込みと制約
	•	ルート：project_root/drafts/intent
	•	無い／空：E_READINESS_INTENT_MISSING
	•	symlink関係は拒否（親も含む）：E_READINESS_INTENT_SYMLINK
	•	読むのは *.yaml のみ、各ファイルは object 必須

intent YAML の検証（_validate_intent_data）

許可キー：
	•	schema_version, source_rev, input_hash, generator_id, scope, nodes_proposed, edge_intents_proposed, questions, conflicts

必須キー：
	•	schema_version, source_rev, input_hash, generator_id, scope, edge_intents_proposed

フィールド検証：
	•	schema_version/source_rev/generator_id：非空 string、プレースホルダ禁止
	•	input_hash：sha256: 開始
	•	scope.kind ∈ {file,id_prefix,component}、scope.value 非空
	•	edge_intents_proposed：
	•	list
	•	各要素は object
	•	許可キー：id, from, to, direction, channel, note（ただし格納するのは id/from/to/direction）
	•	id/from/to は RELID
	•	direction は None または DIRECTION_VOCAB
	•	ids は ソートされ 一意であること

readiness の照合ロジック
	•	decisions.scope と一致する intent ファイルだけを対象に集約
	•	(scope.kind, scope.value, intent_id) が intent 集約の一意キー
	•	同一scopeで同一idが複数ファイルにある：E_READINESS_INTENT_DUPLICATE_ID
	•	各 decision edge（decision_id）について：
	•	対応intentがない：E_READINESS_INTENT_MISSING
	•	intentのfrom/toがdecisionと不一致：E_READINESS_INTENT_MISMATCH
	•	evidence が decision_id に対して空：E_READINESS_EVIDENCE_MISSING
	•	contract_refs の各 CONTRACT.* が、evidenceのclaimsに
	•	kind=contract_ref
	•	decision_id一致
	•	value一致
の形で存在しない：E_READINESS_EVIDENCE_COVERAGE

出力
	•	成功：exit 0
	•	失敗：exit 2（Diagnostic JSONをstderr）



⸻

intent_lint.py

役割
	•	drafts/intent/*.yaml の Intent YAML を lint する。
	•	intent_schema.normalize_intent に従って検証する。

使い方（最小）
	•	python3 L1_builder/intent_lint.py --input drafts/intent --project-root <project> --allow-empty

主な引数
	•	--input：ファイル/ディレクトリ（複数可）
	•	--allow-empty：対象が空でも PASS
	•	--allow-nonstandard-path：標準パス外を許容
	•	--project-root

制約
	•	input は project_root 配下必須、symlink 不可
	•	標準パス強制（allow 無し）

⸻

no_ssot_promotion_check.py

役割
	•	SSOT と decisions への混入（drafts/intent/evidence/exceptions）を検出するゲート。
	•	sdsl2/ と decisions/ 配下の symlink を FAIL。

使い方（最小）
	•	python3 L1_builder/no_ssot_promotion_check.py --project-root <project>

制約
	•	policy/exceptions.yaml 以外の exceptions.yaml は FAIL

⸻

schema_migration_check.py

役割
	•	Draft/Intent/Decisions/Evidence/Contracts/Exceptions の schema_version major 混在を検出する。
	•	MAJOR mismatch を診断として出す（policy で severity を制御）。

使い方（最小）
	•	python3 L1_builder/schema_migration_check.py --project-root <project>

主な引数
	•	--decisions-path / --evidence-path / --contracts-path / --exceptions-path
	•	--project-root

⸻

evidence_repair.py

役割
	•	decisions/evidence.yaml の content_hash を再計算し、diff-only で修正案を出す。

使い方（最小）
	•	python3 L1_builder/evidence_repair.py --project-root <project> --out OUTPUT/evidence_repair.patch

主な引数
	•	--decisions-path / --evidence-path
	•	--allow-nonstandard-path
	•	--out（省略時 stdout）
	•	--project-root

制約
	•	証拠の schema/coverage は evidence_lint と同等に検証（NG なら修正しない）
	•	source_path/locator の正規化は evidence_hash_helper と同じ

出力
	•	diff-only（変更無しは exit 0）

⸻

drift_check.py

役割
	•	decisions と SSOT の drift（不整合）を検出する。
	•	Decision 未反映と Manual Edge を診断として出す。

使い方（最小）
	•	python3 L1_builder/drift_check.py --project-root <project> --decisions-path decisions/edges.yaml

主な引数
	•	--decisions-path
	•	--allow-nonstandard-path
	•	--project-root

⸻

token_registry_check.py

役割
	•	sdsl2/ 内の SSOT.* / CONTRACT.* 使用トークンを Registry と突合する。

使い方（最小）
	•	python3 L1_builder/token_registry_check.py --project-root <project>

主な引数
	•	--ssot-registry（既定 OUTPUT/ssot/ssot_registry.json）
	•	--contract-registry（既定 OUTPUT/ssot/contract_registry.json）
	•	--project-root

⸻

operational_gate.py

役割
	•	Operational Gate のまとめ実行ランナー。
	•	Draft/Intent/Decisions/Evidence/Readiness/No-SSOT/Token Registry/Schema Migration/Evidence Repair を順に実行する。
	•	policy.gates.* により FAIL/DIAG/IGNORE を適用。

使い方（最小）
	•	python3 L1_builder/operational_gate.py --project-root <project> --decisions-path decisions/edges.yaml --evidence-path decisions/evidence.yaml

主な引数
	•	--policy-path（明示 policy）
	•	--decisions-path / --evidence-path
	•	--ssot-registry / --contract-registry
	•	--determinism-manifest（任意）
	•	--allow-nonstandard-path


L1 Builder tools END
==================================





==================================
# L2 Builder Tools

Scope: Minimal L2 tools for contract lint, context pack/bundle doc, exceptions, and conformance checks.
Non-scope: Auto-apply, migrations, or any SSOT edits (diff-only only where specified).

## Paths and Authority
- SSOT is read-only under sdsl2/.
- Derived outputs are written only under OUTPUT/.
- Exceptions are read from policy/exceptions.yaml (non-SSOT).

## Notes
- Bundle Doc provenance uses Supplementary Section "provenance" and appends
  input_hash as a string in provenance.inputs to satisfy input_hash requirements.
- exception_lint.py requires --today (YYYY-MM-DD) to keep results deterministic.
- These tools are intended to be run under the L2 stage after L1 is complete.



bundle_doc_gen.py

役割
	•	OUTPUT/context_pack.yaml をベースに、リポジトリの input_hash と source_rev 等の provenance（追跡情報）を末尾に追記して OUTPUT/bundle_doc.yaml を生成する。
	•	L2の「配布用バンドル文書（context + provenance）」生成器。

使い方（最小）
	•	標準出力先で生成：
	•	python3 L2_builder/bundle_doc_gen.py --project-root <project>
	•	decisionsをinput_hashから除外：
	•	python3 ... --no-decisions
	•	policyファイルもinput_hashへ含める：
	•	python3 ... --include-policy
	•	source_revを上書き：
	•	python3 ... --source-rev <rev>

主な引数
	•	--context-pack（既定 OUTPUT/context_pack.yaml）
	•	--out（既定 OUTPUT/bundle_doc.yaml）
	•	--project-root（既定 repo root）
	•	--source-rev（省略時 git rev）
	•	--no-decisions（input_hashから decisions/edges.yaml を除外）
	•	--include-policy（policyをinput_hashに含める）

パス／安全制約（非常に厳格）
	•	context/out ともに project_root 配下であること（ensure_inside）
	•	失敗：E_BUNDLE_DOC_PATH_OUTSIDE_PROJECT
	•	context_path は必ず project_root/OUTPUT/context_pack.yaml と一致必須
	•	不一致：E_BUNDLE_DOC_CONTEXT_PATH_INVALID
	•	out_path は必ず project_root/OUTPUT/bundle_doc.yaml と一致必須
	•	不一致：E_BUNDLE_DOC_OUTPUT_PATH_INVALID
	•	symlink親禁止：context / out.parent で has_symlink_parent チェック
	•	失敗：E_BUNDLE_DOC_SYMLINK

存在・種別
	•	context 不在：E_BUNDLE_DOC_CONTEXT_NOT_FOUND
	•	context がdir：E_BUNDLE_DOC_CONTEXT_IS_DIRECTORY
	•	out がsymlink：E_BUNDLE_DOC_OUTPUT_SYMLINK
	•	out がdir：E_BUNDLE_DOC_OUTPUT_IS_DIRECTORY
	•	out.parent が存在してdirでない：E_BUNDLE_DOC_OUTPUT_PARENT_NOT_DIR

provenance生成内容
	•	source_rev：--source-rev 指定がなければ git rev-parse HEAD（失敗時 E_BUNDLE_DOC_SOURCE_REV_MISSING）
	•	input_hash：compute_input_hash(project_root, include_decisions=..., include_policy=...)
	•	失敗：E_BUNDLE_DOC_INPUT_HASH_FAILED:<exc>

provenanceブロック形式（ファイル末尾へ追記）
	•	context_pack.yaml のテキストを読み、末尾に改行が無ければ追加
	•	その後に以下を追記（YAML的に「補遺」セクション）
	•	---
	•	Supplementary: provenance
	•	generator: "L2_builder.bundle_doc_gen"
	•	source_rev: "<git rev>"
	•	inputs:（result.inputs を project_root 相対パスで列挙）
	•	追加で input_hash:<sha256> を inputs に入れる

出力
	•	成功：exit 0（OUTPUT/bundle_doc.yaml を作成）
	•	失敗：exit 2（stderrにエラーコード）

⸻

common.py（L2_builder.common）

役割

L2系スクリプトで共有する「パス安全ユーティリティ」。

提供関数
	•	resolve_path(project_root, raw)：相対なら project_root 起点で絶対化
	•	ensure_inside(project_root, path, code)：project_root外を ValueError(code) で拒否
	•	has_symlink_parent(path, stop)：stopまでの親にsymlinkがあれば True

⸻

conformance_check.py

役割
	•	OUTPUT/implementation_skeleton.yaml が 現在のリポジトリ状態（contractのStructure/Rule集合＋input_hash＋必要ならsource_rev）と一致することを検証する。
	•	生成物が最新か／改竄されていないか／契約SSOTに追随しているかの整合性チェック。

使い方（最小）
	•	標準入力を検証：
	•	python3 L2_builder/conformance_check.py --project-root <project>
	•	decisionsをhash計算から除外：
	•	python3 ... --no-decisions
	•	source_revもgitと照合：
	•	python3 ... --check-source-rev

主な引数
	•	--input（既定 OUTPUT/implementation_skeleton.yaml）
	•	--project-root
	•	--no-decisions
	•	--check-source-rev

パス／安全制約
	•	project_root外：E_CONFORMANCE_INPUT_OUTSIDE_PROJECT
	•	input_path は必ず標準パス一致（OUTPUT/implementation_skeleton.yaml）
	•	不一致：E_CONFORMANCE_INPUT_PATH_INVALID
	•	symlink親または自身がsymlink：E_CONFORMANCE_INPUT_SYMLINK
	•	不在：E_CONFORMANCE_INPUT_NOT_FOUND

検証内容
	1.	YAMLパース／型

	•	parse失敗：E_CONFORMANCE_PARSE_FAILED:<exc>
	•	rootがdictでない：E_CONFORMANCE_SCHEMA_INVALID

	2.	input_hash

	•	YAML内 input_hash が欠落/空：Diagnostic E_CONFORMANCE_INPUT_HASH_INVALID
	•	compute_input_hash(project_root, include_decisions=...) と一致必須
	•	不一致：Diagnostic E_CONFORMANCE_INPUT_HASH_MISMATCH

	3.	source_rev（オプション）

	•	--check-source-rev 時のみ
	•	git rev取得失敗：Diagnostic E_CONFORMANCE_SOURCE_REV_MISSING
	•	skeletonの source_rev とgit revが不一致：Diagnostic E_CONFORMANCE_SOURCE_REV_MISMATCH

	4.	contracts由来のStructure/Rule集合

	•	sdsl2/contract/**/*.sdsl2 を走査し、各ファイルから @Structure{id:...} と @Rule{id:...} の id を抽出
	•	contract側のファイルが symlink（親含む）：E_CONFORMANCE_CONTRACT_SYMLINK（即失敗）
	•	YAML内 structures / rules が期待集合（ソート済み）と一致必須
	•	不一致：E_CONFORMANCE_STRUCTURES_MISMATCH / E_CONFORMANCE_RULES_MISMATCH

出力
	•	成功：exit 0
	•	失敗：exit 2（Diagnostic JSONをstderr）

⸻

context_pack_gen.py（L2版）

役割
	•	L1の context_pack_gen と同機能だが、L2の共通ユーティリティ（symlink拒否・標準出力固定）に合わせたラッパ。
	•	指定トポロジ（SSOT）から target node 周辺のサブグラフを抽出し、OUTPUT/context_pack.yaml を生成。

使い方（最小）
	•	python3 L2_builder/context_pack_gen.py --input sdsl2/topology/...sdsl2 --target NODE_ID --project-root <project>

主な引数
	•	--input：トポロジ .sdsl2（SSOT）
	•	--target：@Node.<RELID>
	•	--hops：近傍ホップ（>=0）
	•	--out：既定 OUTPUT/context_pack.yaml または -（stdout）
	•	--project-root

制約
	•	hops < 0：E_CONTEXT_PACK_HOPS_INVALID
	•	input が project_root外：E_CONTEXT_PACK_INPUT_OUTSIDE_PROJECT
	•	input の親にsymlink：E_CONTEXT_PACK_INPUT_SYMLINK
	•	input 不在：E_CONTEXT_PACK_INPUT_NOT_FOUND: <path>
	•	input がdir：E_CONTEXT_PACK_INPUT_IS_DIRECTORY
	•	extract_context_pack が ValueError：その文字列を出して exit 2

出力先
	•	--out != "-" の場合、出力パスは標準 OUTPUT/context_pack.yaml に一致必須
	•	不一致：E_CONTEXT_PACK_OUTPUT_PATH_INVALID
	•	out.parent symlink：E_CONTEXT_PACK_OUTPUT_SYMLINK
	•	out symlink/dir：E_CONTEXT_PACK_OUTPUT_SYMLINK / E_CONTEXT_PACK_OUTPUT_IS_DIRECTORY
	•	out.parent が存在してdirでない：E_CONTEXT_PACK_OUTPUT_PARENT_NOT_DIR

出力
	•	成功：exit 0（stdout または OUTPUTへ書き込み）
	•	失敗：exit 2

⸻

contract_sdsl_lint.py

役割
	•	contract profile の .sdsl2 ファイル群を対象に、@Fileヘッダ、profile整合、許可Kind、id_prefix形式、placeholder禁止をlintする。
	•	contract側の「プロフィール分離」と「プレースホルダ禁止」を強制するゲート。

使い方（最小）
	•	python3 L2_builder/contract_sdsl_lint.py --input sdsl2/contract --project-root <project>
	•	--input は複数指定可能（ファイル or ディレクトリ）

主な引数
	•	--input（append, required）：ファイルまたはディレクトリ
	•	--project-root

入力ファイル列挙
	•	inputは project_root配下必須（違反：E_CONTRACT_LINT_INPUT_OUTSIDE_PROJECT）
	•	ディレクトリ指定時は **/*.sdsl2（symlinkは列挙時点で除外）
	•	ファイルが0件：E_INPUT_NOT_FOUND: no .sdsl2 files
	•	各ファイルがsymlink：E_CONTRACT_LINT_INPUT_SYMLINK

検証内容（各ファイル）
	1.	@Fileヘッダ

	•	不在：E_FILE_HEADER_MISSING
	•	先頭ステートメントでない：E_FILE_HEADER_NOT_FIRST
	•	重複：E_FILE_HEADER_DUPLICATE

	2.	profile / stage

	•	@File.stage が存在：ADD_STAGE_IN_CONTRACT_PROFILE（contractではstage禁止）
	•	profile が missing/不一致：E_PROFILE_INVALID（期待 contract）

	3.	id_prefix

	•	@File.id_prefix が RELID（UPPER_SNAKE_CASE）でない：E_ID_FORMAT_INVALID

	4.	許可Kind

	•	行頭 @<Kind> を検出し、Kindが CONTRACT_KINDS に含まれる必要
	•	例：File, DocMeta, Structure, Interface, Function, Const, Type, Dep, Rule
	•	@EdgeIntent は特別に明示禁止：ADD_EDGEINTENT_PROFILE
	•	それ以外で許可外：E_PROFILE_KIND_FORBIDDEN

	5.	Placeholder禁止（None/TBD/Opaque）

	•	//行コメントは無視
	•	/* ... */ ブロックコメントは除外
	•	文字列リテラル内は除外
	•	それ以外で None|TBD|Opaque が出たら：ADD_PLACEHOLDER_IN_SDSL

出力
	•	問題なし：exit 0
	•	何かあれば：exit 2（Diagnostic JSONをstderr）

⸻

exception_lint.py

役割
	•	policy/exceptions.yaml（例外承認の記録）を、**スキーマ・日付・期限・重複・上限（cap）**まで含めて検証する。
	•	特徴：ファイルが無い場合は OK扱い（exit 0）。ただし --today は必須。

使い方（最小）
	•	python3 L2_builder/exception_lint.py --today 2026-01-04 --project-root <project>

主な引数
	•	--input（既定 policy/exceptions.yaml）
	•	--project-root
	•	--policy-path（addendum policyの明示指定）
	•	--allow-nonstandard-path
	•	--today（必須、YYYY-MM-DD）

パス／安全制約
	•	project_root外：E_EXCEPTION_INPUT_OUTSIDE_PROJECT
	•	標準パス強制（allow無し）：E_EXCEPTION_PATH_INVALID
	•	ファイルが無ければ exit 0
	•	symlink親 or 本体symlink：E_EXCEPTION_SYMLINK

重要仕様：–today 必須
	•	--today が無い：即 E_EXCEPTION_TODAY_REQUIRED（stderr, exit 2）
	•	日付形式不正：Diagnostic E_EXCEPTION_TODAY_INVALID

トップレベルスキーマ

必須キー：schema_version, source_rev, input_hash, exceptions
	•	欠落：E_EXCEPTION_REQUIRED_MISSING
	•	余計なキー：E_EXCEPTION_UNKNOWN_KEY

フィールド検証
	•	schema_version：非空 string（E_EXCEPTION_SCHEMA_VERSION_INVALID）
	•	source_rev：非空 string（E_EXCEPTION_SOURCE_REV_INVALID）
	•	input_hash：sha256:<64hex>（E_EXCEPTION_INPUT_HASH_INVALID）
	•	exceptions：list（E_EXCEPTION_LIST_INVALID）

例外項目（exceptions[]）スキーマ

各要素は dict。required_keys（全て必須）：
	•	id, scope, targets, reason_code, owner, expires,
exit_criteria, extend_count, progress_note

検証内容（主要）
	•	id：非空、全体で一意（E_EXCEPTION_ID_INVALID / E_EXCEPTION_ID_DUPLICATE）
	•	scope：
	•	object必須（E_EXCEPTION_SCOPE_INVALID）
	•	kind ∈ {file,id_prefix,component}（E_EXCEPTION_SCOPE_KIND_INVALID）
	•	value 非空（E_EXCEPTION_SCOPE_VALUE_INVALID）
	•	kind=file の場合：.sdsl2 で終わる必要（E_EXCEPTION_SCOPE_VALUE_INVALID）
	•	targets：
	•	非空 list 必須（E_EXCEPTION_TARGETS_INVALID）
	•	各targetは許可集合のみ：EVIDENCE-COVERAGE, DRAFT-SCHEMA, SCHEMA-MIGRATION
	•	違反：E_EXCEPTION_TARGET_INVALID
	•	reason_code：許可集合のみ（LEGACY_MIGRATION, EXTERNAL_APPROVAL, SCHEMA_SYNC）
	•	違反：E_EXCEPTION_REASON_INVALID
	•	owner：非空 string（E_EXCEPTION_OWNER_INVALID）
	•	expires：YYYY-MM-DD（E_EXCEPTION_EXPIRES_INVALID）
	•	exit_criteria：非空 string（E_EXCEPTION_EXIT_CRITERIA_INVALID）
	•	extend_count：0 or 1（E_EXCEPTION_EXTEND_COUNT_INVALID）
	•	progress_note：
	•	extend_count=1 の場合は必須（E_EXCEPTION_PROGRESS_NOTE_REQUIRED）
	•	extend_count=0 の場合は 省略（None/”“のみ許容）（E_EXCEPTION_PROGRESS_NOTE_FORBIDDEN）

アクティブ判定
	•	expires_date >= today を active とする。
	•	activeな例外について：
	•	同一(scope.kind, scope.value, target)で同時に1件まで
	•	違反：E_EXCEPTION_DUPLICATE_ACTIVE_TARGET
	•	scope単位で active件数を集計し、policyのcapを適用

cap（ポリシー由来）
	•	load_addendum_policy() で policy を読み、
	•	dod.l2_exception_cap（全体上限）
	•	dod.l2_exception_scope_cap（scope単位上限）
	•	超過時：
	•	E_EXCEPTION_CAP_EXCEEDED
	•	E_EXCEPTION_SCOPE_CAP_EXCEEDED

診断の扱い
	•	ADD_POLICY_ で始まる診断は「保持はするが fail判定から除外」
	•	それ以外が1つでもあれば exit 2

出力
	•	fileが無い：exit 0
	•	それ以外：
	•	診断があれば Diagnostic JSON（stderr）
	•	fail診断あり：exit 2
	•	policy系のみ：exit 0

⸻

freshness_check.py

役割
	•	OUTPUT/bundle_doc.yaml に含まれる provenance の input_hash と source_rev が、現在のリポジトリ状態と一致するかを検証する。
	•	bundle_doc_gen の生成物が「最新」かをチェックするゲート。

使い方（最小）
	•	python3 L2_builder/freshness_check.py --project-root <project>
	•	bundle_docが無くてもOKにしたい：
	•	python3 ... --allow-missing
	•	policyもhash対象に入れる：
	•	python3 ... --include-policy
	•	source_rev照合：
	•	python3 ... --check-source-rev

主な引数
	•	--input（既定 OUTPUT/bundle_doc.yaml）
	•	--project-root
	•	--no-decisions
	•	--include-policy
	•	--allow-missing
	•	--check-source-rev

パス／安全制約
	•	project_root外：E_FRESHNESS_INPUT_OUTSIDE_PROJECT
	•	標準パス一致必須：不一致 E_FRESHNESS_INPUT_PATH_INVALID
	•	不在：
	•	--allow-missing なら exit 0
	•	それ以外 exit 2
	•	symlink親 or 本体symlink：E_FRESHNESS_INPUT_SYMLINK

provenanceの抽出仕様
	•	ファイル中の行 Supplementary: provenance を探し、そこから後続を簡易パース。
	•	inputs: の配列要素中に input_hash:<sha256> があることを期待。
	•	provenance自体が無い：E_FRESHNESS_PROVENANCE_MISSING

検証内容
	•	--check-source-rev 時：
	•	git rev取得失敗：Diagnostic E_FRESHNESS_SOURCE_REV_MISSING
	•	provenance.source_rev と git rev 不一致：Diagnostic E_FRESHNESS_SOURCE_REV_MISMATCH
	•	input_hash：
	•	provenance.inputs に input_hash: が無い：Diagnostic E_FRESHNESS_INPUT_HASH_MISSING
	•	compute_input_hash(project_root, include_decisions=..., include_policy=...) と一致必須
	•	不一致：Diagnostic E_FRESHNESS_INPUT_HASH_MISMATCH

出力
	•	成功：exit 0
	•	失敗：exit 2（Diagnostic JSONをstderr）

⸻

implementation_skeleton_gen.py

役割
	•	sdsl2/contract/**/*.sdsl2 から @Structure.id と @Rule.id を収集し、
OUTPUT/implementation_skeleton.yaml を生成する。
	•	conformance_check が照合する「期待値（contractの構造/ルール一覧＋input_hash）」の生成器。

使い方（最小）
	•	python3 L2_builder/implementation_skeleton_gen.py --project-root <project>

主な引数
	•	--project-root
	•	--out（既定 OUTPUT/implementation_skeleton.yaml、固定一致必須）
	•	--source-rev（省略時 git rev）
	•	--no-decisions（input_hashからdecisions除外）

パス／安全制約（出力固定）
	•	project_root外：E_SKELETON_OUTPUT_OUTSIDE_PROJECT
	•	out_path は標準パス一致必須：E_SKELETON_OUTPUT_PATH_INVALID
	•	out.parent symlink：E_SKELETON_OUTPUT_SYMLINK
	•	out が symlink/dir：E_SKELETON_OUTPUT_SYMLINK / E_SKELETON_OUTPUT_IS_DIRECTORY
	•	out.parent が存在してdirでない：E_SKELETON_OUTPUT_PARENT_NOT_DIR

contract 走査制約
	•	sdsl2/contract が無い：E_SKELETON_CONTRACT_ROOT_MISSING
	•	dirでない：E_SKELETON_CONTRACT_ROOT_NOT_DIR
	•	.sdsl2 が0件：E_SKELETON_CONTRACT_FILES_MISSING
	•	contractファイルが symlink（親含む）：E_SKELETON_CONTRACT_SYMLINK

生成内容（YAML）
	•	schema_version: "1.0"
	•	source_rev: <git rev or override>（失敗：E_SKELETON_SOURCE_REV_MISSING）
	•	input_hash: <compute_input_hash()>（失敗：E_SKELETON_INPUT_HASH_FAILED:<exc>）
	•	generator_id: "L2_builder.implementation_skeleton_gen"
	•	structures: [...]（ソート済み）
	•	rules: [...]（ソート済み）

出力
	•	成功：exit 0（OUTPUTへ書き込み）
	•	失敗：exit 2

⸻

token_registry_gen.py

役割
	•	sdsl2/**/*.sdsl2 のメタデータから SSOT.* / CONTRACT.* トークン参照を抽出し、
OUTPUT/ssot/ssot_registry.json と OUTPUT/ssot/contract_registry.json を生成する。
	•	token_registry_check / conformance_check の入力になる registry を生成する。

使い方（最小）
	•	python3 L2_builder/token_registry_gen.py --project-root <project>
	•	マッピング指定：
	•	python3 ... --ssot-map decisions/ssot_registry_map.yaml --contract-map decisions/contract_registry_map.yaml
	•	未解決許可：
	•	python3 ... --allow-unresolved

主な引数
	•	--project-root
	•	--ssot-map / --contract-map（YAML）
	•	--allow-unresolved
	•	--ssot-out（既定 OUTPUT/ssot/ssot_registry.json）
	•	--contract-out（既定 OUTPUT/ssot/contract_registry.json）

パス／安全制約
	•	project_root外出力：E_REGISTRY_GEN_OUTPUT_OUTSIDE_PROJECT
	•	out が symlink/dir：E_REGISTRY_GEN_OUTPUT_SYMLINK / E_REGISTRY_GEN_OUTPUT_IS_DIR
	•	out.parent が symlink：E_REGISTRY_GEN_OUTPUT_SYMLINK_PARENT
	•	out が .json 以外：E_REGISTRY_GEN_OUTPUT_INVALID
	•	sdsl2 が symlink（親含む）：E_REGISTRY_GEN_SSOT_SYMLINK
	•	input_hash 失敗：E_REGISTRY_GEN_INPUT_HASH_FAILED:<exc>

マッピング仕様（YAML）
	•	dict：token -> target
	•	list：
	•	{token, target} の配列
	•	token 文字列のみも可（target は UNRESOLVED#/）
	•	使用トークンで mapping 不足の場合：
	•	--allow-unresolved なしなら E_REGISTRY_GEN_MAPPING_REQUIRED

生成内容（JSON）
	•	schema_version: "1.0"
	•	source_rev: <git rev or UNKNOWN>
	•	input_hash: compute_input_hash(project_root, include_decisions=false, extra_inputs=[map])
	•	generator_id: "L2_builder.token_registry_gen.ssot" / ".contract"
	•	entries: [{token, target}...]（token 昇順）

出力
	•	成功：exit 0（JSONを書き込み）
	•	失敗：exit 2

⸻

l2_gate_runner.py

役割
	•	L2 向けゲートランナー。L1 の operational_gate と drift_check を実行した後、
exception_lint を通し、必要に応じて conformance_check / freshness_check を実行する。
	•	policy に基づき exception_lint の severity を適用する（DIAG/IGNORE なら継続）。

実行順
	•	L1 operational_gate → drift_check → exception_lint →（--publish 時）conformance_check → freshness_check

使い方（最小）
	•	python3 L2_builder/l2_gate_runner.py --project-root <project> --today <YYYY-MM-DD>
	•	publish 判定：
	•	python3 ... --publish
	•	policy 指定：
	•	python3 ... --policy-path policy/policy.yaml

主な引数
	•	--project-root
	•	--decisions-path（既定 decisions/edges.yaml）
	•	--evidence-path（既定 decisions/evidence.yaml）
	•	--allow-nonstandard-path
	•	--today（必須、YYYY-MM-DD）
	•	--publish
	•	--policy-path
	•	--verbose

出力
	•	成功：exit 0
	•	失敗：exit 2



L2 Builder Tools END
==================================




==================================
# SDSLv2 builder tools


addendum_policy.py

役割
	•	Addendum（L0/L1/L2などの“アウトオブバンド規約”）の 有効/無効や各種制約値を、ポリシーファイルから読み込む。
	•	ポリシーが見つからない／複数ある／パースに失敗した、などの状態を Diagnostic として返しつつ、**安全側のデフォルト（addendum.enabled=false）**にフォールバックする。

使い方（最小）
	•	通常は上位ツール（例：exception_lint など）から呼ばれる想定。
	•	API：
	•	load_addendum_policy(policy_path: Path|None, repo_root: Path) -> PolicyResult
	•	PolicyResult.policy が辞書、PolicyResult.diagnostics が診断の配列。

例（概念）：
	•	明示パスで読む：load_addendum_policy(Path(".../policy.yaml"), repo_root)
	•	デフォルト探索で読む：load_addendum_policy(None, repo_root)
	•	探索先は repo_root/.sdsl/policy.yaml または .sdsl/policy.yml

出力ファイル
	•	生成しない（読み取りのみ）。

⸻

closed_set_contract_v0_1.py

役割
	•	contractモデル（ContractModel）に対するv0.1の閉集合チェック。
	•	許容されるDecl.kindを Structure/Interface/Function/Const/Type に制限
	•	Depの bind == from_ref 強制
	•	Dep.to は InternalRef か ContractRef に限定
	•	逸脱があると BuilderError(Diagnostic(...)) を投げて止める（fail-fast）。

使い方（最小）
	•	直接使うより、contract.py の ContractBuilder.build() 内から呼ばれる前提。
	•	API：validate_contract_model_v0_1(model) -> None（不正なら例外）

出力ファイル
	•	生成しない。

⸻

context_pack.py

役割
	•	topologyの .sdsl2 から、指定ノード中心に近傍（hops）を切り出し、**Context Pack（人間可読のテキスト）**を生成する。
	•	@Node / @Edge / @EdgeIntent を解析し、以下をまとめる：
	•	対象ノード周辺のノード一覧（canon_id付き）
	•	対象範囲のエッジ一覧（direction/channel/contract_refs）
	•	対象範囲で参照される contract token のユニーク集合
	•	EdgeIntent があれば “Open TODO” として列挙
	•	決定性のために ソートや dedupe を行う。

使い方（最小）
	•	上位のCLI（あなたの L2_builder/context_pack_gen.py）から使われる想定。
	•	API：extract_context_pack(path: Path, target: str, hops: int=1) -> str
	•	target は @Node.NODE_A のようなInternalRef文字列。

注意点（コード上の制約）
	•	/* */ ブロックコメントがあると E_CONTEXT_PACK_BLOCK_COMMENT_UNSUPPORTED
	•	profileは @File { profile:"topology" ... } 必須
	•	Flow / Terminal kind があると unsupported 扱い
	•	Edgeは contract_refs 必須・空禁止

出力ファイル
	•	モジュール単体ではファイル出力しない（文字列を返すだけ）。
	•	ただし上位ツール context_pack_gen.py は通常 OUTPUT/context_pack.yaml に書く設計（内容はこのモジュールが返す「Context Pack…」のテキスト）。

⸻

contract_writer.py

役割
	•	ContractModel（構造化データ）を contract profile の .sdsl2 テキストに整形出力する“writer”。
	•	並び順を固定（決定性）：
	•	decl：kind順（Structure→Interface→Function→Const→Type）＋rel_id
	•	dep：dep_id
	•	rule：rel_id

使い方（最小）
	•	API：write_contract(model: ContractModel) -> str
	•	通常は writer層として上位のBuilder/Writerから呼ばれる想定。

出力ファイル
	•	モジュール単体ではファイル出力しない（文字列を返す）。
	•	上位で sdsl2/contract/.../*.sdsl2 に書く用途。

⸻

contract.py

役割
	•	contract profile の **中間モデル（ContractModel）**と、それを安全に組み立てる ContractBuilder を提供。
	•	生成時に以下を強制：
	•	RELID形式（UPPER_SNAKE_CASE）チェック
	•	bind/refs/contract/ssot の型チェック（InternalRef/ContractRef/SSOTRef）
	•	dep_id を JCS + sha256 で決定的に生成
	•	build時に validate_contract_model_v0_1 を通して閉集合・配置ルールを確定

使い方（最小）
	•	典型：Builderで組み立てて build() → contract_writer.write_contract() で文字列化

概念例：
	•	b = ContractBuilder().file("MY_PREFIX")... .structure(...).dep(...).rule(...).build()

出力ファイル
	•	単体では生成しない（モデルを返す）。
	•	実ファイルは上位 writer が .sdsl2 として書く。

⸻

draft_schema.py

役割
	•	“Draft”形式の辞書（おそらく YAML/JSON）を 正規化（normalize）＋検証する。
	•	重点は次の2点：
	1.	スキーマ制約（必須キー、型、語彙、参照整合）
	2.	決定性（ソート必須、dedupe必須、プレースホルダ禁止）

主なルール（コードから）
	•	top-level keys は REQUIRED_TOP_KEYS のみ許可
	•	schema_version は MAJOR.MINOR 形式
	•	direction は閉集合 {pub,sub,req,rep,rw,call}
	•	CONTRACT.* トークン形式チェック
	•	None/TBD/Opaque を Draft内で禁止
	•	lists（nodes_proposed等）はソートされていないと診断

使い方（最小）
	•	API：normalize_draft(data: dict, fill_missing: bool) -> (normalized: dict, diags: list[Diagnostic])
	•	fill_missing=True なら欠けている必須キーを空値で埋める（それでも型や整合は診断）。

出力ファイル
	•	生成しない（正規化結果を返す）。

⸻

errors.py

役割
	•	すべての検証・lint・ビルドで使う 共通診断フォーマット。
	•	json_pointer(...) でパスを機械可読に統一。
	•	BuilderError は “診断1件を抱えた例外” として扱える。

使い方（最小）
	•	Diagnostic(code,message,expected,got,path)
	•	raise BuilderError(diagnostic)

出力ファイル
	•	生成しない。

⸻

input_hash.py

役割
	•	リポジトリ内の所定入力群から **決定的な入力ハッシュ（sha256:…）**を計算。
	•	何を入力に含めるかが明確：
	•	SSOT：sdsl2/contract/**/*.sdsl2 と sdsl2/topology/**/*.sdsl2
	•	include_decisions=True なら decisions/edges.yaml
	•	include_policy=True なら .sdsl/policy.yaml と policy/exceptions.yaml（存在すれば）
	•	extra_inputs も加算可能
	•	symlinkは入力として拒否（INPUT_HASH_SYMLINK）

使い方（最小）
	•	API：compute_input_hash(root: Path, extra_inputs=None, include_policy=False, include_decisions=True) -> InputHashResult
	•	InputHashResult.input_hash と InputHashResult.inputs（Path配列）を返す。

出力ファイル
	•	生成しない（ハッシュ文字列を返す）。
	•	ただし上位ツールがこの input_hash を OUTPUT/*.yaml のフィールドに書く（例：bundle_doc / skeleton）。

⸻

jcs.py

役割
	•	最小の **JCS（RFC 8785の趣旨に沿った canonical JSON）**シリアライズ。
	•	dict/list/str/bool/null/int のみ許可し、キーは文字列のみ。
	•	json.dumps(sort_keys=True, separators=(",",":")) で決定的文字列にする。

使い方（最小）
	•	API：dumps(obj) -> str
	•	topology edge_id / contract dep_id などの決定的ID生成に使われている。

出力ファイル
	•	生成しない。

⸻

ledger.py

役割
	•	“Topology ledger v0.1” を （簡易）YAML/JSONとして読み込み、スキーマ検証して TopologyInput に変換する。
	•	役割としては「外部入力（ledger）→ 安全な内部表現」。
	•	validateでは以下を強制：
	•	version: topology-ledger-v0.1
	•	profile: topology
	•	nodeの id（RELID）重複禁止、kind 必須、bindは @Kind.RELID 形式のみ
	•	edgeの from/to が node を参照していること
	•	direction語彙の閉集合
	•	contract_refs の非空・ユニーク・CONTRACT.* 形式
	•	edgeのPK重複（from,to,direction,contract_refs）禁止
	•	output.topology_v2_path を指定する場合、OUTPUT配下に制限

使い方（最小）
	•	読み込み：load_ledger(path) -> dict
	•	検証：validate_ledger(data, output_root: Path) -> (TopologyInput|None, diagnostics)
	•	diagnosticsが空なら TopologyInput が返る。

出力ファイル
	•	ledger自体は入力。
	•	TopologyInput.output_path が設定される可能性がある（ただし実際に書くのは run.py）。

⸻

lint.py

役割
	•	topology profile の .sdsl2 を 軽量lintする（Diagnosticsをjsonで出すCLIも含む）。
	•	やっていることは “SDSL全文パース” ではなく、アノテーションメタデータの抽出・必須キー・語彙・参照整合をチェックするゲート。

主なチェック（コードから）
	•	@File の存在、先頭、重複、profile=topology、id_prefix必須
	•	許容kindの閉集合：File/DocMeta/Node/Edge/Rule
	•	Node：idのRELID、重複、kind必須、Nodeにcontract_refsが来たらエラー
	•	Rule：bind必須
	•	Edge：必須フィールド（id/from/to/direction/contract_refs）、direction語彙、from/toが既存Node参照、contract_refsの形式、非空、ユニーク、PK重複禁止

使い方（最小）
	•	ライブラリ：lint_text(text: str, path: Path) -> list[Diagnostic]
	•	CLI：python -m sdslv2_builder.lint --input <file-or-dir> 相当（このファイル自身にもmainあり）
	•	失敗時は diagnostics をstderrに JSON で出す。

出力ファイル
	•	生成しない（診断の標準出力/標準エラーのみ）。

⸻

op_yaml.py

役割
	•	最小のYAML/JSON I/Oユーティリティ。
	•	load_yaml(path)：.jsonならjson、他は簡易YAMLパーサ
	•	dump_yaml(data)：dict/list/scalar を簡易YAMLとして出力
	•	いくつかのL2ツール（skeleton/conformance など）がこれに依存。

使い方（最小）
	•	読み：load_yaml(Path("x.yaml")) -> Any
	•	書き：dump_yaml(obj) -> str

出力ファイル
	•	直接は生成しない（文字列を返す）。
	•	上位が Path.write_text(dump_yaml(...)) で OUTPUT/*.yaml を作る用途。

⸻

refs.py

役割
	•	参照トークンの型とパーサ。
	•	InternalRef: @Kind.RELID（kindは閉集合）
	•	ContractRef: CONTRACT.*
	•	SSOTRef: SSOT.*
	•	書式検証を共通化し、誤入力を早期に弾く。

使い方（最小）
	•	parse_internal_ref("@Node.NODE_A") -> InternalRef|None
	•	parse_contract_ref("CONTRACT.foo") -> ContractRef|None
	•	parse_ssot_ref("SSOT.bar") -> SSOTRef|None

出力ファイル
	•	生成しない。

⸻

run.py

役割（CLI）
	•	ledger（Topology ledger v0.1）を入力として、
	1.	load_ledger で読み
	2.	validate_ledger で検証し
	3.	build_topology_model でモデル化し
	4.	write_topology で .sdsl2 を生成し
	5.	OUTPUT配下にファイルとして書く
	•	“tool-driven authoring” の topology側の実行器。

使い方（最小）

CLI：
	•	python -m sdslv2_builder.run --ledger <ledger.yaml> --out-dir OUTPUT
	•	--out-dir は 必ずディレクトリ名がOUTPUT でないと即死（E_OUTPUT_DIR_INVALID）

出力ファイル
	•	既定の出力先：
	•	OUTPUT/<id_prefix>/topology.sdsl2
	•	ledger側で output.topology_v2_path が指定されていればそれを優先（ただし OUTPUT 配下に限定）。

出力内容（概要）
	•	@File { profile:"topology", id_prefix:"..." }
	•	@Node {...} 群（ソート済み）
	•	@Edge {...} 群（決定的edge_id、ソート済み）

⸻

topology.py

役割
	•	ledger由来の TopologyInput を、決定性のある TopologyModel に変換する。
	•	EdgeInput のPK（from/to/direction/contract_refs）をJCSで固めてsha256し、決定的な edge_id = E_<16hex> を生成。

使い方（最小）
	•	build_topology_model(topology_input: TopologyInput) -> TopologyModel
	•	compute_edge_id(edge_input: EdgeInput) -> str

出力ファイル
	•	生成しない（モデルを返す）。
	•	実ファイル化は writer.py / run.py 側。

⸻

writer.py

役割
	•	TopologyModel を topology profile の .sdsl2 テキストとして出力する writer。
	•	決定性のために：
	•	ノード：rel_idソート
	•	エッジ：from/to/direction/contract_refsでソート
	•	contract_refs を ["CONTRACT.x", ...] 形式で出す。

使い方（最小）
	•	write_topology(model: TopologyModel) -> str

出力ファイル
	•	生成しない（文字列を返す）。
	•	run.py がこれをファイルに書く。

SDSLv2 builder tools END

==================================

==================================
Other Scripts

通常の運用で必須：
	1.	gate_a_check.py
	•	SDSL2ファイルの「最低限の形式・禁止事項・基礎整合」を落とす一次ゲートになりやすい。
	•	これが通らないと以降の工程（L1/L2生成や昇格）が概ね成立しない、という位置づけになる。

	2.	addendum_check.py
	•	“addendum（手動追記・例外・補遺）”のルール/ポリシー準拠を担保するチェックとして、CIに組み込まれやすい。
	•	特に「例外や補足情報を正式運用する」プロジェクトでは必須級になります。

	3.	diff_gate.py
	•	変更差分単位で「許可される変更だけ」を通すためのゲートとして運用されやすい。
	•	SDSL2はSSOT運用になり安い、「差分を縛る」ゲートは実務上ほぼ必須になります。


	必須（この repo の実運用上、外しにくい）
	•	oi_run_v0_1.py
実行オーケストレータ。これを回す運用なら、下記が強制的に必須になります（失敗で止まるため）。
	•	check_spec_locks.py
oi_run の最初に実行される＝仕様ロックに違反すると最初に落ちる。運用上は必須ゲート扱い。
	•	check_error_catalog.py
エラーカタログと diagnostics goldens の突合をゲートにしている。これも必須ゲート扱い。
	•	gate_a_check.py
「前段ゲート」。最低限のゲート（構文/基本ルール/基礎整合）として、後段以前に落とす意図が明確。
	•	determinism_check.py
manifest ベースで determinism を要求しているので、再現性が品質要件として必須になっている構図。
	•	gate_b_check.py
L0–L2運用における“意味的なリント”に近い位置づけで、落としどころがかなり実務的。
	•	diff_gate.py
最終段で差分の許容範囲を縛る。SSOT運用ではここが最後の安全弁になりやすく、実務上必須になりがち。



	Other Scripts ENDS
==================================
