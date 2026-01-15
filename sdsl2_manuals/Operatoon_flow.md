
1. 全体像：この運用が解決したいこと

このレポジトリ運用は、SDSL2 を「書きやすく」するためというより、“確定していないもの” と “確定したもの” を混ぜないことによって、次を同時に実現するために設計されています。
	•	SSOT（sdsl2/ 配下）：確定したグラフ事実・契約・参照（トークン）のみを保持し、CI で常に厳密に検証できる
	•	非SSOT（drafts/, decisions/, .sdsl/, policy/ など）：未確定・審査中・証拠付け・例外などを置き、意思決定プロセスを追跡できる
	•	派生出力（OUTPUT/）：LLM やレビュー支援のための要約（Context Pack / Bundle Doc）や、TS の配布境界 JSON を決定論的に再生成できる

つまり、流れとしては：
	1.	L0 で「形（ノード）」と「意図（Intent）」を集める
	2.	L1 で「インターフェース（Edge＋contract_refs）を確定」させ、Topology SSOT を“グラフ事実”として成立させる
	3.	L2 で「振る舞い（invariants/authz）まで確定」させ、運用上の DoD を満たす
並行して、Contract SSOT を整備し、トークン参照を閉じる（Registry で欠落を許さない）。
※TS SSOT kernel は進行中（definitions/runtime/registry は導入済み）。

⸻

2. アーティファクト階層：どこに何が置かれ、何が“権威”か

運用を理解する鍵は、まず「置き場所＝権威境界」です。

2.1 権威（Authority）の三層

A) SSOT（確定情報の唯一の置き場所）
	•	sdsl2/topology/**/*.sdsl2：Graph Facts（@Edge） を含む確定トポロジ
	•	sdsl2/contract/**/*.sdsl2：境界スキーマ・不変条件・認可などの Contract（境界仕様）

ここだけが SDSL2 の authoritative parse surface です（CI はここだけを SSOT として解析）。

B) Explicit Inputs（Promote が読む「人間レビュー済みの確定入力」）
	•	decisions/edges.yaml：@Edge を作るための明示決定（id/from/to/direction/contract_refs）
	•	decisions/contracts.yaml：Contract Structure/Rule を確定する明示決定
	•	（ただし）decisions/evidence.yaml は「証拠マップ」であり、Promote の入力ではない（後述）

Explicit Inputs は “SSOT ではないが、Promote が参照して SSOT を更新する根拠” です。
ここが「人間審査に耐えた確定入力」という位置づけになります。
Contract SSOT も decisions/contracts.yaml → contract_promote（diff-only）で昇格します。

C) Draft / Intent / Evidence / Exceptions（非SSOT、意思決定の足場）
	•	drafts/*.yaml：検討中の提案（questions/conflicts/候補など）
	•	drafts/ledger/*.yaml：ノード骨格などの作業用 ledger（非SSOT）
	•	drafts/intent/*.yaml：Edge の“意図”を表す Intent YAML（L0/L1 の下書き）
	•	decisions/evidence.yaml：決定の証拠（Evidence Map）
	•	.sdsl/policy.yaml：ゲート運用の設定（FAIL/DIAG/IGNORE 等）
	•	policy/exceptions.yaml：L2 での例外（期限付き・上限付き）

これらは SSOT に昇格してはいけない領域で、CI の「品質ゲート」には使われますが、Graph Facts そのものにはならない、という扱いです。

D) Derived Outputs（派生出力：保存しても権威にならない）
	•	OUTPUT/intent_preview.sdsl2
	•	OUTPUT/context_pack.yaml
	•	OUTPUT/bundle_doc.yaml
	•	OUTPUT/decisions_needed.yaml
	•	OUTPUT/diagnostics_summary.yaml
	•	OUTPUT/resolution_gaps.yaml
	•	OUTPUT/implementation_skeleton.yaml
	•	OUTPUT/ssot/ssot_registry.json
	•	OUTPUT/ssot/contract_registry.json
	•	OUTPUT/ssot/ssot_definitions.json
	•	OUTPUT/ssot/ssot_registry_map.json

※OUTPUT/ssot/ssot_registry.json と OUTPUT/ssot/contract_registry.json は token_registry_gen で生成（現運用）。
OUTPUT/ssot/ssot_definitions.json は build_ssot_definitions で生成（現運用）。

これらは 必ず再生成できることが要求され、手編集は禁止です。保存する場合は source_rev と input_hash で “この入力集合から生成した” が追跡できる必要があります。
intent_preview は cache 扱い（非SSOT・非権威）とし、必要時に再生成する前提で運用します。

⸻

3. L0 → L1 → L2 の実運用フロー（人とツールの動き）

ここからが本題で、実際にどう進めると “最終形” に収束するかです。
全体を、現場で起きるタスクの粒度に合わせて説明します。

⸻

3.1 L0：骨格（Nodes）＋意図（Intent）を「SSOT外」に集約する段階

L0 のゴール
	•	Topology SSOT はまだ “グラフ事実（@Edge）” を持たない（または持てない）
	•	代わりに、何を繋ぎたいか を Intent として集め、曖昧さも含めて記録する
	•	ここでは「完全な正しさ」より「収集と分類」が優先されます
	•	Draft/Intent の input_hash は SSOT のみ（decisions は含めない）

ここで作られる／更新されるファイル
	1.	Topology SSOT（最小）

	•	sdsl2/topology/<something>.sdsl2
	•	内容：@File(stage:"L0") と @Node 群
	•	まだ Edge は入れない（= グラフ事実を作らない）

	2.	Intent YAML（意図の保管場所）

	•	drafts/intent/<scope別>.yaml
	•	内容：edge_intents_proposed と必要なら nodes_proposed/questions/conflicts

	3.	Draft（検討の論点と未確定情報）

	•	drafts/<something>.yaml
	•	内容：質問、衝突、contract 候補など（“候補” はここに置く）

	4.	Evidence Map（証拠の下準備）

	•	decisions/evidence.yaml
	•	「後で決定を確定するときに必要になる証拠」を先に紐づけておく
※ここで重要なのは、Evidence は “将来の Readiness の材料” であり、Promote の入力ではない点です。

	5.	Intent Preview（レビュー用の派生出力）

	•	OUTPUT/intent_preview.sdsl2
	•	Intent YAML から決定論的に生成し、SSOT には反映しない

	6.	Resolution Gap Report（欠落診断の派生出力）

	•	OUTPUT/resolution_gaps.yaml
	•	Topology の必須フィールド不足を機械的に列挙する（SSOT には反映しない）
	•	manual_addendum_lint は topology_resolution_lint / resolution_gap_report を実行する（skip フラグで除外可）

曖昧さ（Ambiguity）は、L0/L1 の“吸収剤”として扱う

L0 では、設計・実装・既存コードの状況が揃わず、次が頻出します。
	•	そもそも接続があるか不明（A1）
	•	接続はあるが direction が不明（A2）
	•	接続はあるが contract_refs が不明（A3/A4）
	•	根拠が足りない、検証できない（A5）

ここで大切なのは「未確定を SSOT に持ち込まない」ことで、曖昧さは drafts/ や drafts/intent/、decisions/evidence.yaml にルーティングされます。
結果として、L0 の SSOT は “ノード骨格として常に正しい” 状態を維持しやすくなります。

⸻

3.2 L1：決定（Decisions）を確定し、Promote で Graph Facts（@Edge）へ昇格させる段階

L1 のゴール
	•	Topology SSOT に @Edge が入り、Graph Facts として確定する
	•	各 Edge は contract_refs を持ち、インターフェース形状が決まる（Interface Shaping）
	•	ここから先は「意図」ではなく「決定」が中心になります

L1 への遷移で起きること（運用上の“芯”）

L1 の中核は、次の三点セットです。
	1.	Intent が揃う（drafts/intent）
	2.	決定が揃う（decisions/edges.yaml）
	3.	証拠が揃う（decisions/evidence.yaml）
→ これが揃うと READINESS-CHECK が PASSし、Promote が安全に回せます

Edge Intent と Contract Map の明示入力
	•	edge_intents_proposed は intent_edge_builder（明示入力YAML）で生成し、diff-only で intent に反映する
	•	contract_map は contract_map_builder（明示入力YAML）で生成し、drafts/contract_map.yaml に diff-only で反映する
	•	drafts/contract_map.yaml は Draft スキーマ対象外のため、Operational Gate の draft_lint / schema_migration_check では検証対象にしない

Operational Gate は、duplicate_key_lint / draft_lint / intent_lint / schema_migration_check / decisions_lint / evidence_lint / evidence_repair / readiness_check /
contract_resolution_lint / contract_token_bind_check / no_ssot_promotion_check / token_registry_check を順に実行し、policy の gate severity で FAIL/DIAG/IGNORE を決めます。
contract_resolution_lint / contract_token_bind_check は policy 未指定時は DIAG が既定です。
（determinism_check は manifest 指定時のみ）
no_ssot_promotion_check は sdsl2/ と decisions/ 配下への非SSOT混入や symlink を遮断します。
token_registry_check は UNRESOLVED#/ を暫定許容し、publish 時は UNRESOLVED#/ を FAIL にします（段階的厳格化）。

(1) Intent YAML を “決定の前提” として揃える
Intent YAML は Promote の入力ではありませんが、Readiness の条件として機能します。
つまり L1 では「決定した Edge が、事前に意図として提出されている」ことを確認し、意図と決定がズレていれば止めます。
これにより、“決定だけ先に暴走する” 事故を防ぎます。
intent_lint により Intent YAML のスキーマ、並び順、未知キーなどを機械的に検証します。

(2) decisions/edges.yaml で “確定入力” を作る
	•	decisions/edges.yaml に、EdgeDecision を記入します
	•	ここが「Promote が読む唯一の材料」です
	•	ここまで来ると、曖昧さ（候補・未承認・不確実）は decisions に入れず、drafts 側に残す運用になります

(3) decisions/evidence.yaml で “contract_refs の根拠” を閉じる
L1 では、Edge を SSOT に昇格させるだけでなく、contract_refs の根拠が追える状態が求められます（ポリシーで require_evidence_l1 が true の場合は特に）。
	•	Evidence は「どのファイルのどの範囲が、どの決定（decision_id）と token を支持するか」を固定化する
	•	locator + content_hash によって「後で内容が変わったら検知できる」ようにする
	•	evidence_template_gen は claims 骨格を生成し、evidence_hash_helper は content_hash を算出・検証する
	•	evidence_repair は content_hash の再計算結果を diff-only で提示する

補助出力（任意）
	•	next_actions_gen で OUTPUT/decisions_needed.yaml と OUTPUT/diagnostics_summary.yaml を生成し、Bundle Doc の補助情報として使う

Promote：決定 → SSOT への“唯一の昇格路”

Promote は、次を厳密に守る道具として設計されています。
	•	入力：decisions/edges.yaml（のみ）
	•	出力：unified diff（パッチ）
	•	反映：CI が勝手に書き換えず、人間がパッチをレビューして適用する

この “diff で出す” という形は、SSOT を自動で書き換えて監査不能になる事態を避けるためです。
Promote により、Topology SSOT は以下の変化をします。
	•	@Edge が挿入される（決定論的順序で）
	•	もし @File.stage:"L0" だった場合、Edge 追加と同時に stage が “L1” に更新される
	•	以後、L1 では @EdgeIntent は SSOT から排除され（Intent YAML に置く）、SSOT は Graph Facts のみを持つ形に整理されます

Diff の適用手順（共通）
	•	diff-only ツールは unified diff を stdout または --out に出力するだけで、SSOT/decisions を直接書き換えません
	•	適用前の確認: git apply --check <patch>
	•	適用: git apply <patch>
	•	適用後は該当 lint / gate を再実行して整合を確認する

⸻

3.3 L2：振る舞い（Invariants/Authz）と例外管理まで含めて“運用品質”を完成させる段階

L2 のゴール
	•	トポロジが決まっただけではなく、境界の振る舞い制約（invariants）や認可（authz）が整備される
	•	例外（exceptions）がある場合も、期限・上限・出口条件つきで管理される
	•	CI の DoD（Definition of Done）で L2 として合格する

ここで重要なのは、L2 は “より厳格” というより、未確定を例外として可視化し、期限付きで焼き切る段階だという点です。
未整備を放置する代わりに、policy/exceptions.yaml に「何が未達で、いつまでに、どう出口を作るか」を持たせます。

L2 の派生出力（非SSOT）
	•	implementation_skeleton_gen で OUTPUT/implementation_skeleton.yaml を生成する

L2 の実行順（l2_gate_runner）
	•	Operational Gate（L1）→ Contract SDSL lint（contract_sdsl_lint）→ Drift（drift_check）→ Exception（exception_lint）→（publish 時）SSOT kernel（ssot_kernel_lint）/ registry consistency（ssot_registry_consistency_check）/ Conformance（conformance_check）/ Freshness（freshness_check）
	•	exception_lint は policy の severity（FAIL/DIAG/IGNORE）を適用する

⸻

4. 並行して完成させる：Contract SSOT と TS SSOT kernel（Definitions/Runtime＋Registry）

Topology の L0/L1/L2 と並行して、最終完成形に不可欠なのが Contract と TS SSOT kernel です。ここを “いつ・どう閉じるか” が実運用では重要になります。

⸻

4.1 Contract SSOT：境界スキーマと不変条件の権威
	•	sdsl2/contract/**/*.sdsl2 が権威
	•	ここは「データテーブルの重複」や「TS の定数のコピー」を置く場所ではなく、**境界で守るべき形（schema）と制約（invariants/authz）**を置く場所です

Topology の contract_refs は、Contract 側の境界仕様（および allowlist/registry）により「参照が存在する」ことを保証され、L2 ではさらに「その参照が意味的にも整備されている」状態へ進めます。
Contract の確定入力は decisions/contracts.yaml とし、contract_promote が diff-only で SSOT へ昇格します。

⸻

4.2 TS SSOT kernel：Definition と Runtime を分離し、JSON 配布境界を固定化する

ssot_kernel_builder/ に definitions/runtime とビルドスクリプトを置き、OUTPUT/ssot/ssot_definitions.json を生成する。

TS 側は、SDSL2 と同列の SSOT ではなく、別ドメインの権威として扱われます（相互依存を禁止しているのがポイントです）。

4.2.1 ファイル（概念）と出力（必須）
	•	TS 側のソース：
	•	ssot_kernel_builder/ssot_definitions.ts：const / types / enums / interfaces（定義のみ）
	•	ssot_kernel_builder/ssot_runtime.ts：guards / builders / validators（実行時のみ）
	•	L2_builder/ssot_kernel_source_lint.py：definitions/runtime の許容構文を検査（ssot_kernel_source）
	•	TS の派生出力（配布境界）：
	•	OUTPUT/ssot/ssot_definitions.json
	•	OUTPUT/ssot/ssot_registry.json
	•	OUTPUT/ssot/contract_registry.json

Registry 自体は token_registry_gen で生成し、decisions の registry_map で対応付けする。
publish では l2_gate_runner --publish --build-ssot を使い、definitions 出力と registry を先に確定させる。
project_root と kernel_root が異なる場合は --kernel-root を指定する。

Registry Map（明示入力）
	•	decisions/contract_registry_map.yaml
	•	decisions/ssot_registry_map.yaml
	•	L1 では UNRESOLVED#/ を許容（DIAG）、L2 publish では UNRESOLVED#/ を禁止（FAIL）
	•	L1 では token_registry_gen に --contract-map / --ssot-map を指定して生成する
	•	L2 publish では build_ssot_definitions / contract_definitions_gen で OUTPUT/ssot/*_registry_map.json を確定し、token_registry_gen は map 未指定で生成する
	•	contract_registry_map の target は OUTPUT/ssot/contract_definitions.json#/tokens/CONTRACT.* を基準に解決する

ここで “完成形” に向かう進化として重要なのは、非TSコンシューマは TS ソースを直接 import しないことです。
必ず JSON（配布境界）か、そこから生成したバインディングを使います。

4.2.2 Registry が“参照の穴”を塞ぐ

SDSL2 は TS 定義を直接参照しません。参照は SSOT.* / CONTRACT.* トークンで行い、
それが Registry（ssot_registry.json / contract_registry.json）に存在することを CI で保証します。
	•	SDSL2 側：ssot:["SSOT.XYZ"], contract:["CONTRACT.ABC"] のようにトークン参照
	•	Registry：token -> <path>#/<json_pointer> の対応を持つ
	•	CI：SDSL2 が使った SSOT.* / CONTRACT.* が Registry にないと FAIL
	•	UNRESOLVED#/ は pre-publish では許容し、publish では FAIL
	•	非コアの SSOT.* は ssot_definitions.ts で kind:"ref" のまま暫定可（Registry で解決される限り publish は通す）。権威が確定したら rule/table へ昇格して map を更新する

この構造により、「SDSL2 と TS の結合」が ソースコード結合ではなく、明示トークン＋レジストリ結合になり、最終状態での決定性が高まります。

⸻

5. CI が“流れ”を保証する：Gate Order と、成果物が進化するタイミング

運用が回り続けるのは、CI が「各段階で許される未確定」を定義し、それ以外を止めるからです。
ゲートは概ね次の役割分担です。
	1.	Manual / Addendum：SDSL と staged rules の違反を止める
	2.	Operational Gate：draft/intent/decisions/evidence の健全性＋duplicate_key/contract_resolution/contract_token_bind/schema_migration/evidence_repair/no_ssot_promotion/token_registry を順に検証
	3.	Drift：SSOT と decisions の不整合を止める
	4.	Exception：例外の期限・上限・出口条件を強制する（L2）
	5.	Determinism/Freshness：OUTPUT 等の派生物が “今の入力から再現できるか” を止める（publish、ssot_kernel_source/ssot_kernel/registry consistency を含む）

ここで実務的に最も効くのは次です。
	•	L0：Missing Decisions を policy で DIAG 扱いにでき、移行中でも回しやすい
	•	L1：readiness/no_ssot_promotion/token_registry が揃わないと FAIL（＝確定に進む）
	•	L2：例外は許すが、期限・上限・出口条件を強制する（＝未確定を凍結せず燃やし切る）

⸻

6. 最終形（完成状態）とは何か：L2 の先にある “確定的な三点セット”

この運用の「完成」は、単に stage が L2 になったことではなく、次が同時に成立している状態です。

6.1 確定的 Topology SSOT
	•	sdsl2/topology/** に Graph Facts（@Edge）が揃い、decisions/ との drift がない
	•	Intent は drafts/intent に残ってもよいが、SSOT を汚さない
	•	Context Pack / Bundle Doc を生成しても内容が順序含め決定論的

6.2 確定的 Contract SSOT
	•	CONTRACT.* が参照されるだけでなく、境界スキーマ／不変条件／認可の形として整備されている
	•	Evidence が要求されるポリシーの場合、それが coverage と検証可能性を満たす
	•	SSOT.* / CONTRACT.* の参照が Registry で解決でき、token_registry_check が PASS

6.3 TS SSOT kernel の完成（進行中）
	•	Definitions と Runtime が分離され、Topology/Contract に依存しない
	•	ssot_definitions.json（配布境界）と ssot_registry.json / contract_registry.json（参照辞書）が生成され、SDSL2 の参照がすべて解決できる
	•	ssot_registry_map.json で token -> target を固定する
	•	非TSコンシューマが TS ソース import をしていない（JSON で統一）

⸻

7. 実務での“典型的な進め方”を 1本の流れに落とす（チェックリスト）

最後に、現場での手順を「何ができたら次へ行くか」という運用の言葉に直します。
	1.	L0開始

	•	Topology SSOT に Node 骨格を作る（L0）
	•	繋ぎたいものを Intent YAML に集める
	•	曖昧さは drafts/ と evidence に逃がし、SSOT には入れない

	2.	L1準備（確定の準備）

	•	Intent と proposals をレビューして、EdgeDecision を decisions/edges.yaml に確定させる
	•	contract_refs の根拠を decisions/evidence.yaml に揃える（要求ポリシーなら必須）
	•	evidence_template_gen で骨格を作り、evidence_hash_helper で content_hash を確定する
	•	Operational Gate（readiness/no_ssot_promotion/token_registry など）が PASS するまで差分を詰める

	3.	Promote（SSOTへ昇格）

	•	Promote の diff を生成し、人間がレビューして適用
	•	Topology SSOT が @Edge を持ち、stage が L1 になる
	•	drift が解消される（SSOT と decisions が一致）
	•	Contract は decisions/contracts.yaml → contract_promote の diff を適用して確定

	4.	Contract と TS の“参照穴”を閉じる

	•	CONTRACT.* の整備（Contract SSOT と allowlist/registry）
	•	token_registry_gen で Registry を生成し、token_registry_check で参照の解決を保証
	•	SSOT.* の target は ssot_registry_map.json で固定し、publish では未解決を FAIL

	5.	L2（振る舞いと例外の焼き切り）

	•	invariants/authz を Contract 側で固める
	•	未達がある場合は exceptions を期限付きで管理し、DoD を PASS_WITH_EXCEPTIONS で運用
	•	OUTPUT が保存される運用なら freshness/determinism を PASS で維持

⸻

8. 設定と実行手順（最小）

ここでは「初期設定」と「最小の実行順」を定義します。詳細は各 builder の README を参照してください。

8.1 設定（必須/推奨）
	•	project_root はリポジトリルートを指す（すべてのツールで共通）
	•	OUTPUT/ は派生出力専用（手編集しない）
	•	policy/.sdsl 関連の主要ファイル
		•	.sdsl/policy.yaml：Operational Gate の severity 設定
		•	policy/resolution_profile.yaml：Topology L0 の required/vocab/pattern
		•	policy/contract_resolution_profile.yaml：Contract L1 の required/rules/error_model
		•	policy/ssot_kernel_profile.yaml：SSOT kernel coverage の required_paths/required_artifacts
		•	policy/exceptions.yaml：L2 exceptions（期限・上限・出口条件）
	•	L2 は --today (YYYY-MM-DD) を必須とし、publish は --publish を付ける
	•	kernel_root が project_root と異なる場合は --kernel-root を指定する

8.2 実行手順（最小）
	L0（骨格と意図）
		1) Manual/Addendum lint
			python3 L0_builder/manual_addendum_lint.py --input sdsl2/topology --policy-path .sdsl/policy.yaml --project-root <repo>
		2) Draft/Intent 整備
			python3 L0_builder/draft_lint.py --input drafts --project-root <repo>
			python3 L0_builder/draft_builder.py --input drafts/<draft>.yaml --project-root <repo> --scope-from sdsl2/topology/<topology>.sdsl2
			python3 L0_builder/intent_builder.py --input drafts/intent --project-root <repo>
		3) Topology 解像度チェック
			python3 L0_builder/topology_resolution_lint.py --input sdsl2/topology --project-root <repo>
			python3 L0_builder/resolution_gap_report.py --input sdsl2/topology --project-root <repo>
		4) 任意：Intent Preview
			python3 L0_builder/edgeintent_diff.py --input sdsl2/topology/<topology>.sdsl2 --draft drafts/intent/<intent>.yaml --project-root <repo>

	L1（決定と昇格）
		1) Operational Gate
			python3 L1_builder/operational_gate.py --project-root <repo> --decisions-path decisions/edges.yaml --evidence-path decisions/evidence.yaml
		2) Promote（diff-only）
			python3 L1_builder/promote.py --project-root <repo> --out OUTPUT/promote.patch
		3) Contract Promote（diff-only）
			python3 L1_builder/contract_promote.py --project-root <repo> --out OUTPUT/contract_promote.patch

	L2（例外・完成度・配布境界）
		1) SSOT kernel definitions（必要時）
			python3 ssot_kernel_builder/build_ssot_definitions.py --project-root <repo>
		2) Registry 生成
			python3 L2_builder/token_registry_gen.py --project-root <repo>
		3) L2 Gate（publish なし）
			python3 L2_builder/l2_gate_runner.py --today 2024-01-01 --project-root <repo>
		4) L2 Gate（publish）
			python3 L2_builder/l2_gate_runner.py --today 2024-01-01 --publish --project-root <repo>
		5) 任意：Bundle/Implementation
			python3 L2_builder/bundle_doc_gen.py --project-root <repo>
			python3 L2_builder/implementation_skeleton_gen.py --project-root <repo>
