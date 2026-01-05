# L0 Builder Toolchain

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

Generate Context Pack:

```bash
python L0_builder/context_pack_gen.py \
  --input /repo/tests/inputs/addendum/L1_ok.sdsl2 \
  --target @Node.NODE_A \
  --hops 1 \
  --out /repo/project_x/OUTPUT/context_pack.yaml \
  --project-root /repo/project_x
```

Manual + Addendum lint:

```bash
python L0_builder/manual_addendum_lint.py \
  --input /repo/project_x/OUTPUT/P1_T_ORCHESTRATION_CORE_L0/topology.sdsl2 \
  --policy-path /repo/.sdsl/policy.yaml \
  --project-root /repo/project_x
```

Draft lint/build:

```bash
python L0_builder/draft_lint.py --input /repo/project_x/drafts/example.yaml --project-root /repo/project_x
python L0_builder/draft_builder.py --input /repo/project_x/drafts/example.yaml --project-root /repo/project_x \
  --scope-from /repo/project_x/sdsl2/topology/P1_T_ORCHESTRATION_CORE_L0.sdsl2
```

Draft builder prerequisites:
- `project_x/decisions/edges.yaml` must exist (empty is OK).
- `--scope-from` must point to `sdsl2/topology/*.sdsl2` under the same project root.

EdgeIntent diff:

```bash
python L0_builder/edgeintent_diff.py \
  --input /repo/project_x/OUTPUT/P1_T_ORCHESTRATION_CORE_L0/topology.sdsl2 \
  --draft /repo/project_x/drafts/example.yaml \
  --project-root /repo/project_x
```

Ledger builder:

```bash
python L0_builder/ledger_builder.py \
  --nodes /repo/project_x/ledger/nodes.txt \
  --id-prefix P0_T_EXAMPLE \
  --out /repo/project_x/ledger/topology_ledger.yaml \
  --project-root /repo/project_x
```

Ledger builder (extract @Structure tokens):

```bash
python L0_builder/ledger_builder.py \
  --extract-structures-from /repo/project_x/C_T/Topology/P1_ORCHESTRATION_CORE_SDSL_TOPOLOGY.md \
  --allow-structure-nodes \
  --line-start 1 --line-end 182 \
  --id-prefix P1_T_ORCHESTRATION_CORE_L0 \
  --out /repo/project_x/ledger/topology_ledger.yaml \
  --project-root /repo/project_x
```

Notes
- Outputs should remain under `OUTPUT/`.
- Placeholders (None/TBD/Opaque) are forbidden in SDSL statements.
