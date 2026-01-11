# 実装返し前定義

実装開始に必要な“最小十分”な定義を、Topology / Contract / SSOT TypeScript kernel の3つに分け、相互参照とゲートで検証可能な形（ID体系・入出力・不変条件・生成物）として整理して提示します。

以下は「実際にコーディングを開始できる（＝L2で実装に降りられる）」状態と判断するために、SDSL2 Topology / Contract / SSOT TypeScript kernel に 少なくとも何が定義されているべきかを、相互整合とゲート検証可能性を前提に整理したものです。ここでいう “少なくとも” は、後から拡張しても破綻しない **最小十分（minimal sufficient）**のセットです。

⸻

1) SDSL2 Topology に最低限必要な定義

Topology は「システム境界と依存関係の“事実（graph facts）”」を確定させ、後段（L1/L2）が迷わず実装単位へ落とせるようにする責務です。最低限、次が必要です。

A. 境界の確定に必要な Node 定義

各 Node（サービス/コンポーネント/ジョブ/ストレージ等）について、最低限これが確定しているべきです。
	•	安定 ID（rel_id）
	•	後段が参照する主キー。変更ルール（rename扱い等）も含めて運用可能な粒度。
	•	Node の種別（kind）（例: service, job, db, queue, external, library）
	•	kind がないと Edge の解釈（同期/非同期、責務境界、デプロイ境界）が曖昧になります。
	•	責務の一文要約
	•	仕様書としてでなくてもよいが、実装者が “この箱は何をするか” を誤らない最低限の意味。
	•	インターフェースの入口/出口の概略
	•	例: HTTP API / gRPC / batch input / topic subscribe / DB read/write
	•	詳細な schema でなくてよいが、通信形態が確定している必要があります。

B. 依存関係の確定に必要な Edge 定義

Edge は「結線が実在すること」を確定させます。最低限：
	•	from / to / direction（閉じた語彙）
	•	通信形態/カテゴリ（同期呼び出し、イベント、データ参照、ファイル連携等）
	•	directionだけだと実装の形が分岐しすぎます。
	•	contract_refs（必須）
	•	「この接続はどの契約（Contract）に根拠があるか」を必ず持つ。
	•	ここが曖昧だと「TopologyはあるがContractが追随していない」状態になり、統合フローが破綻します。

C. L0/L1/L2 進行に必要なファイルメタ

あなたの文脈（stage必須）に沿うと、最低限：
	•	@File.profile:"topology"
	•	@File.id_prefix:"..."（ID衝突防止）
	•	@File.stage:"L0" | "L1" | "L2"（運用で使うなら必須。少なくとも L0 生成物が自動で満たせること）

D. Topology 側の「不変条件（ゲートで落とせること）」

実装開始の準備ができていると言うには、Topology に以下の検証可能性が必要です。
	•	Node ID が一意
	•	Edge の (from,to,direction,category等) が重複しない
	•	contract_refs が空でない、かつ CONTRACT.* トークンとして妥当
	•	許容される kind と属性が profile に適合している（contract/topology分離）

⸻

2) SDSL2 Contract に最低限必要な定義

Contract は「Topology の結線を成立させる“約束事（schema/規約/制約）”」を確定させ、実装者が迷わずインターフェースを作れる状態にする責務です。最低限、次が必要です。

A. Contract トークン（CONTRACT.*）の確定
	•	CONTRACT トークンの命名と安定性
	•	Topology の各 Edge が参照する CONTRACT. が存在すること*
	•	“参照先がない contract_refs” が残ると、トポロジーは通っても実装は開始できません。

B. インターフェースの最低限の形（Interface/Function/Type）

「詳細な完全スキーマ」までは不要ですが、少なくとも実装者がスタブを切れる粒度が必要です。
	•	Interface（提供側の入口）
	•	endpoint 群の存在（名前・概要・同期/非同期の別）
	•	Function（操作単位）
	•	入力/出力の型が存在する（仮でも良いが placeholder は禁止ルールに従う）
	•	Type（最低限のデータ構造）
	•	リクエスト/レスポンス/イベント payload の骨格
	•	エラー/例外の取り扱いの枠
	•	例: error code の集合、リトライ可否など（最小でよいが “未定” のまま放置しない）

C. 依存関係の意味づけ（Dep / Rule の最低限）
	•	Dep: 「どの契約がどれに依存するか」（例: 共通Type、共通Auth）
	•	Rule: 少なくとも bind が成立し、ルールがどの宣言に効くか追跡できること
	•	bind が欠けると、仕様が“浮いて”しまい、後段で揉めます。

D. Contract 側の「不変条件（ゲートで落とせること）」
	•	profile=contract に許される kind のみ
	•	token placement（contract_refs は topology にのみ、contract側は contract / @Dep.to を使う等）に整合
	•	placeholders（None/TBD/Opaque）を禁止するなら、ここでも検出可能
	•	参照（InternalRef/ContractRef/SSOTRef）が正規形

⸻

3) SSOT TypeScript kernel に最低限必要な定義

SSOT kernel は「実装を生成/検証/運用するための“真実の型と規約（runtime + definitions）”」を提供する中核です。ここが薄いと、SDSL2 が整っていても実装が収束しません。最低限、次が必要です。

A. トークン体系（SSOT.* / CONTRACT.* / InternalRef）の型定義
	•	**ブランド型（branded types）**で区別できること
	•	SSOTRef, ContractRef, InternalRef の混入をコンパイル時に防ぐ。
	•	正規表現・パーサ（parse/validate）と toString 正規化
	•	token placement の制約をコードで表現できる（少なくとも検証関数として）

B. 共通スキーマ（生成物の構造）とバージョニング

実装開始に必要な最重要ポイントです。
	•	出力アーティファクトのスキーマ定義
	•	例: ssot_registry.json, contract_registry.json, 生成される ledger / decisions / evidence の構造
	•	“何を生成し、どこに置き、何をもって正とするか” が TS 側で型として固定されている必要があります。
	•	schema_version と migration 戦略の型
	•	L1/L2 ゲートが「どの版を想定しているか」を明確化する。

C. 正規化・決定性（determinism）のユーティリティ
	•	canonical sort（キー順、配列順）
	•	stable serialization（JSON/YAMLの順序、改行、エスケープ）
	•	input_hash 計算の仕様（対象ファイル集合の宣言と計算）

D. ルート/権限モデル（project_root と allowed write roots）

あなたの「Authority and Write Rules」を TS 側でも矛盾なく扱える必要があります。
	•	ProjectRoot の概念（cwd依存を排除）
	•	AllowedWriteRoot（drafts / OUTPUT 等）と検証
	•	symlink / traversal の検査を共通化（Python側と二重実装なら仕様一致が必要）

E. エラーモデル（Diagnostic）と JSON Pointer
	•	Diagnostic { code, message, expected, got, path } の型
	•	JSON Pointer のエスケープ規則を統一
	•	“どのゲートがどの code を出すか” のカタログ化の足場（将来でよいが、最低限型は必要）