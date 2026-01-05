from interpreter import interpreter
import subprocess

# トークン節約: 余計な実行手順をモデルに渡さない
# （公式設定に記載あり。空文字 or False が可能）
interpreter.llm.execution_instructions = ""

# 安全寄り: 自動実行しない
interpreter.auto_run = False

# システム指示（モデルに渡る）
interpreter.custom_instructions = """
You are operating tools for SDSLv2 generation. Follow these rules strictly:
- NEVER edit .sdsl2 files directly. Use Builder/Writer tools only.
- Treat the repository as read-only. Only /repo/OUTPUT may be written.
- NEVER modify scripts/, sdslv2_builder/, docs/, or coder_planning/.
- NEVER run auto-approve flags (e.g., -y / --auto_run) unless the user explicitly asks.
- Do not install packages or use network downloads.
- Use only approved commands in this repo (oi_run_v0_1.py, addendum/context_pack tests, determinism).
- Show diffs (git diff --name-only, git diff) before requesting any write.
- If a command fails, stop and ask for guidance.

Basic usage (when asked to run a tool):
- Always run scripts via python, never chmod or execute directly.
- In Docker, paths must use /repo/... (not /Volumes/...).
- Example tests:
  - python /repo/scripts/addendum_test.py --manifest /repo/tests/addendum_manifest.json
  - python /repo/scripts/context_pack_test.py --manifest /repo/tests/context_pack_manifest.json
- Example context pack output:
  - python /repo/scripts/context_pack_extract.py --input /repo/tests/inputs/addendum/L1_ok.sdsl2 --target @Node.NODE_A --hops 1
- Full gate run:
  - python /repo/scripts/oi_run_v0_1.py

Builder usage (Topology):
1) Create or update a ledger YAML under /repo/OUTPUT/<CASE>/topology_ledger.yaml.
2) Run:
   - python -m sdslv2_builder.run --ledger /repo/OUTPUT/<CASE>/topology_ledger.yaml --out-dir /repo/OUTPUT
3) Inspect:
   - /repo/OUTPUT/<CASE>/topology.sdsl2
4) Do not edit .sdsl2 by hand. Fix the ledger and re-run.

Builder usage (Contract):
1) Use the existing contract builder script(s) in /repo/scripts/.
2) Run the contract golden check for a case:
   - python /repo/scripts/contract_golden_check.py --emit-stdout --case <CASE> --golden /repo/tests/goldens/<CASE>/contract.sdsl2
3) Do not edit .sdsl2 by hand. Fix the builder script or inputs and re-run.

Ledger template (Topology v0.1):
version: topology-ledger-v0.1
schema_revision: 1
file_header:
  profile: topology
  id_prefix: P0_T_EXAMPLE
nodes: []
edges: []

Formatting hints (YAML):
- Use block indentation (2 spaces). Do not mix flow and block styles.
- Each node must include both id and kind.
- Keep keys as simple scalars; avoid inline comments.

How to write the ledger (example):
version: topology-ledger-v0.1
schema_revision: 1
file_header:
  profile: topology
  id_prefix: P0_T_EXAMPLE
nodes:
  - id: NODE_A
    kind: component
  - id: NODE_B
    kind: component
edges: []

Error handling:
- If a command fails, read stderr and ask for guidance.
- Do not guess missing fields. Fix inputs and re-run.

Diff gate:
- Before any write, show: git diff --name-only and git diff.
- Only OUTPUT/ is allowed to change.

Important subprocess rule:
- When using subprocess.run(command_list), command_list[0] must be "python" (or sys.executable). NEVER "".
""".strip()


def system_instruction():
    return interpreter.custom_instructions.strip()


def task_instruction():
    text = """
    次の作業をツールで実行してください。推論は禁止。明示されている要素のみを使う。

    対象：
    /repo/C_T/Topology/P1_ORCHESTRATION_CORE_SDSL_TOPOLOGY.md の全て

    やること：
    1) 先頭～182行の中に出てくる @Structure.<RELID> をすべて抽出
    2) それらを Node として topology ledger (v0.1) を作成
       - 出力先: /repo/OUTPUT/P1_T_ORCHESTRATION_CORE_L0/topology_ledger.yaml
       - id_prefix: P1_T_ORCHESTRATION_CORE_L0
       - edges: []（空）
       - source.evidence_note に 必要なことを記述すること
    3) Builderで sdsl2 を生成：
       python -m sdslv2_builder.run --ledger /repo/OUTPUT/P1_T_ORCHESTRATION_CORE_L0/topology_ledger.yaml --out-dir /repo/OUTPUT
    4) 生成された /repo/OUTPUT/P1_T_ORCHESTRATION_CORE_L0/topology.sdsl2

    注意：
    - /repo 以外のパスは使わない
    - chmod は不要（python で実行）
    - 失敗したら止まって報告する
    - 各 Node に kind: component を必ず入れる
    - 完全に抽出を正確に実行すること。
    """
    return text.strip()


def run_context_pack_extract_example():
    """
    例: context_pack_extract.py を subprocess で実行する。
    注意: これは関数定義のみで、プロファイル読み込み時には実行されません。
    """
    command = [
        "python",
        "/repo/scripts/context_pack_extract.py",
        "--input",
        "/repo/tests/inputs/addendum/L1_ok.sdsl2",
        "--target",
        "@Node.NODE_A",
        "--hops",
        "1",
    ]

    result = subprocess.run(command, capture_output=True, text=True)

    print("Captured stdout:")
    print(result.stdout)
    print("Captured stderr:")
    print(result.stderr)
    print("Return code:", result.returncode)
