# SDSLv2 Coder (v0.1)

This repo provides a **tool-driven SDSLv2 authoring system**:
LLMs operate the tools, not the language. Output is generated only through
Builder/Writer paths and validated by deterministic gates.

## System Composition (Core vs. Support)

Core (SSOT logic):
- `sdslv2_builder/` — Builder/Writer/Validator, canonicalization, refs, errors.

Support tooling (execution + CI harness):
- `scripts/` — run/lint wrappers, diff gate, determinism checks, addendum checks.
- `tests/` — fixtures, manifests, goldens.
- `OUTPUT/` — generated artifacts only.

Docs/Specs:
- `coder_planning/` — locked specs and plans.
- `sdsl2_manuals/` — addendum SSOT and staged rules.

## Key Principles (v0.1)
- **Only tool output**: no raw `.sdsl2` edits.
- **Determinism**: same input => same output (golden + hash).
- **Closed sets**: kinds/keys/tokens are versioned.
- **No inference**: graph facts come from explicit inputs.

## Local Verification (CI parity)
Run from repo root:
```
python scripts/check_spec_locks.py --locks spec_locks_v0_1.json
python scripts/check_error_catalog.py --errors coder_planning/archives/errors_v0_1.md --diagnostics-glob "tests/goldens/**/diagnostics.json"
python scripts/gate_a_check.py --input OUTPUT --input tests/goldens
python scripts/addendum_test.py --manifest tests/addendum_manifest.json
python scripts/context_pack_test.py --manifest tests/context_pack_manifest.json
python scripts/determinism_check.py --manifest tests/determinism_manifest.json
python scripts/gate_b_check.py --input OUTPUT --input tests/goldens
```

Golden updates (explicit only):
```
python scripts/addendum_test.py --manifest tests/addendum_manifest.json --update
python scripts/context_pack_test.py --manifest tests/context_pack_manifest.json --update
```

## L0/L1/L2 Addendum (Out-of-band)
Enable via policy:
- `.sdsl/policy.yaml` (default) or CI-specified policy path

Checks:
- `python scripts/addendum_test.py --manifest tests/addendum_manifest.json`

## L2 Tools (project_root)
Minimal L2 tooling lives in `L2_builder/`.

Example run (project_x):
```
python3 L2_builder/token_registry_gen.py --project-root project_x
python3 L2_builder/contract_sdsl_lint.py --input sdsl2/contract --project-root project_x
python3 L2_builder/context_pack_gen.py --input sdsl2/topology/MINIMAL_L0.sdsl2 --target @Node.NODE_A --project-root project_x
python3 L2_builder/bundle_doc_gen.py --project-root project_x
python3 L2_builder/implementation_skeleton_gen.py --project-root project_x
python3 L2_builder/conformance_check.py --project-root project_x
python3 L2_builder/freshness_check.py --project-root project_x
python3 L2_builder/exception_lint.py --project-root project_x --today 2024-01-03
python3 L2_builder/l2_gate_runner.py --project-root project_x --today 2024-01-03 --publish
```
Notes:
- To avoid ADD_POLICY_NOT_FOUND DIAG, add a minimal `.sdsl/policy.yaml` (see `sdsl2_manuals/ope_addendum/SDSL2_Policy_Spec.md`).
- L2 outputs are fixed under `OUTPUT/` (context_pack.yaml, bundle_doc.yaml, implementation_skeleton.yaml).
- Registries are fixed under `OUTPUT/ssot/` and validated by token_registry_check in L1.

## References (Operational Gate / UNRESOLVED)
- L1 Operational Gate flow: `sdsl2_manuals/Operatoon_flow.md` and `sdsl2_manuals/ope_addendum/SDSL2_CI_Gates_Spec.md`.
- `--fail-on-unresolved` usage and behavior: `coder_planning/tools_doc.md`.

## Context Pack (Addendum output)
Deterministic extraction from topology facts:
- `python scripts/context_pack_test.py --manifest tests/context_pack_manifest.json`
- `python scripts/context_pack_extract.py --input <file.sdsl2> --target @Node.X --hops 1`

## Docker (Local OI)
Read-only repo + writable OUTPUT (recommended):
```bash
docker run --rm -it --name oi \
  -v "/Volumes/SSD/Dev_Projects/SDSL2_Coder:/repo:ro" \
  -v "/Volumes/SSD/Dev_Projects/SDSL2_Coder/OUTPUT:/repo/OUTPUT:rw" \
  -v "/Volumes/SSD/Dev_Projects/SDSL2_Coder/oi_llm_instruction.py:/root/.config/open-interpreter/profiles/oi_llm_instruction.py:ro" \
  -w /repo \
  openinterpreter:latest \
  interpreter --profile oi_llm_instruction.py \
  --model ollama/qwen2.5-coder:32b --api_base http://host.docker.internal:11434 --safe_mode ask
```


Auto-run (unsafe; use only if you accept full execution):
```bash
docker run --rm -it --name oi \
  -v "/Volumes/SSD/Dev_Projects/SDSL2_Coder:/repo:ro" \
  -v "/Volumes/SSD/Dev_Projects/SDSL2_Coder/OUTPUT:/repo/OUTPUT:rw" \
  -v "/Volumes/SSD/Dev_Projects/SDSL2_Coder/oi_llm_instruction.py:/root/.config/open-interpreter/profiles/oi_llm_instruction.py:ro" \
  -w /repo \
  openinterpreter:latest \
  interpreter --profile oi_llm_instruction.py --model ollama/qwen2.5-coder:32b --api_base http://host.docker.internal:11434 --auto_run

```

## Docker 再ビルド
dockerfile に変更があった場合
```bash
docker build --no-cache -t openinterpreter:latest /Volumes/SSD/Dev_Projects/oi_docker
```

## System Message / Custom Instructions
CLI flags:
- `--custom_instructions "..."` (recommended)
- `--system_message "..."` (use only if you intend to replace the default)

Profile file (mounted into the container):
- place `oi_llm_instruction.py` under `/root/.config/open-interpreter/profiles/`
- run with `--profile oi_llm_instruction.py`

## Quick Test (Context Pack)
Prepared test case (L1_ok):
```
python scripts/context_pack_test.py --manifest tests/context_pack_manifest.json
```

Manual diff check:
```
python scripts/context_pack_extract.py --input tests/inputs/addendum/L1_ok.sdsl2 --target @Node.NODE_A --hops 1 > /tmp/context_pack.txt
diff -u /tmp/context_pack.txt tests/goldens/addendum/context_pack_L1_ok.txt
```

## Open Interpreter Entry Point
Run the v0.1 wrapper:
```
python scripts/oi_run_v0_1.py
```

Allow extra write paths (if required):
```
python scripts/oi_run_v0_1.py --allow some/output/path/
```

Notes:
- Guard order (v0.1): spec lock -> error catalog -> Gate A -> addendum -> determinism -> Gate B -> diff gate.
- Must be a git repository (diff gate enforces allowlist).
- Safe mode and sandboxed execution are recommended.
- Do not use auto-approve flags (e.g., -y). v0.1 requires manual approval.

Details: `docs/open_interpreter_v0_1.md`
