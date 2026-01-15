# L0 Builder Toolchain

Purpose: minimal L0 toolchain aligned with `sdsl2_manuals/plan/Recommended_Tools.md`.
This folder contains thin wrappers plus a status map.

## Tools (L0 minimal set)

Ready
- `context_pack_gen.py` -> Context Pack generator (SSOT topology only, OUTPUT/context_pack.yaml).
- `manual_addendum_lint.py` -> Manual Gate (Gate A) + Addendum lint (wraps scripts).
- `draft_builder.py` -> Normalize/fill Draft YAML and write canonical output.
- `intent_builder.py` -> Normalize/fill Intent YAML under drafts/intent.
- `draft_lint.py` -> Draft schema validation.
- `ledger_builder.py` -> Build topology ledger from a node list.
- `topology_resolution_lint.py` -> Topology resolution lint for required fields (L0 safety).
- `resolution_profile_lint.py` -> Validate resolution profile structure (policy/resolution_profile.yaml).
- `resolution_gap_report.py` -> Emit resolution gaps to OUTPUT/resolution_gaps.yaml.
- `edgeintent_diff.py` -> Intent preview diff generator (stdout unified diff against OUTPUT/intent_preview.sdsl2 only; no auto-apply).
- `topology_enricher.py` -> Diff-only topology enrichment for @Node summary/io fields.
- `topology_channel_builder.py` -> Diff-only topology enrichment for @Edge channel fields.
- `intent_template_gen.py` -> Generate drafts/intent skeletons from topology.

Planned (not implemented yet)
- (none)

## Repository root layout (authoritative)

Drafts live at the repository root (`drafts/`). If you need isolation, use a separate
repo or worktree (do not nest a project root inside another repo).

```
repo_root/
  drafts/
  drafts/ledger/
  decisions/
  OUTPUT/
  sdsl2/  # SSOT (contract/topology)
```

Pass `--project-root <repo_root>` to L0 tools (defaults to repo root).

## Quickstart (L0)

Generate Context Pack:

```bash
python L0_builder/context_pack_gen.py \
  --input /repo/sdsl2/topology/P1_T_ORCHESTRATION_CORE_L0.sdsl2 \
  --target @Node.NODE_A \
  --hops 1 \
  --out /repo/OUTPUT/context_pack.yaml \
  --project-root /repo
```

Manual + Addendum lint:

```bash
python L0_builder/manual_addendum_lint.py \
  --input /repo/sdsl2/topology \
  --policy-path /repo/.sdsl/policy.yaml \
  --project-root /repo
```

Draft lint/build:

```bash
python L0_builder/draft_lint.py --input /repo/drafts/example.yaml --project-root /repo
python L0_builder/draft_builder.py --input /repo/drafts/example.yaml --project-root /repo \
  --scope-from /repo/sdsl2/topology/P1_T_ORCHESTRATION_CORE_L0.sdsl2
```

Draft builder prerequisites:
- `--scope-from` must point to `sdsl2/topology/*.sdsl2` under the same project root.
Notes:
- L0 input_hash uses SSOT only; decisions are not required.
- Intent YAML input is restricted to `drafts/intent/*.yaml` (use `intent_builder.py`).

Topology resolution lint / gap report:

```bash
python L0_builder/topology_resolution_lint.py --input /repo/sdsl2/topology --project-root /repo
python L0_builder/resolution_gap_report.py --input /repo/sdsl2/topology --project-root /repo
```

EdgeIntent diff:

```bash
python L0_builder/edgeintent_diff.py \
  --input /repo/sdsl2/topology/P1_T_ORCHESTRATION_CORE_L0.sdsl2 \
  --draft /repo/drafts/intent/example_intent.yaml \
  --project-root /repo
```

Topology enricher (diff-only):

```bash
python L0_builder/topology_enricher.py \
  --input /repo/sdsl2/topology \
  --map /repo/drafts/ledger/node_enrich.yaml \
  --project-root /repo
```

Topology channel builder (diff-only):

```bash
python L0_builder/topology_channel_builder.py \
  --input /repo/sdsl2/topology \
  --map /repo/drafts/ledger/edge_channels.yaml \
  --project-root /repo
```
Notes:
- stdout is JSON-only (tool result envelope); diff is written to `OUTPUT/topology_channel.patch` by default.

Intent template generator:

```bash
python L0_builder/intent_template_gen.py \
  --input /repo/sdsl2/topology/P1_T_ORCHESTRATION_CORE_L0.sdsl2 \
  --project-root /repo
```

Ledger builder:

```bash
python L0_builder/ledger_builder.py \
  --nodes /repo/drafts/ledger/nodes.txt \
  --id-prefix P0_T_EXAMPLE \
  --out /repo/drafts/ledger/topology_ledger.yaml \
  --project-root /repo
```

Ledger builder (extract @Structure tokens):

```bash
python L0_builder/ledger_builder.py \
  --extract-structures-from /repo/C_T/Topology/P1_ORCHESTRATION_CORE_SDSL_TOPOLOGY.md \
  --allow-structure-nodes \
  --line-start 1 --line-end 182 \
  --id-prefix P1_T_ORCHESTRATION_CORE_L0 \
  --out /repo/drafts/ledger/topology_ledger.yaml \
  --project-root /repo
```

Notes
- context_pack_gen input_hash uses SSOT only (no decisions).
- context_pack_gen `--out` must be OUTPUT/context_pack.yaml (or `--out -` for stdout).
- Derived outputs should remain under `OUTPUT/`.
- resolution_gap_report writes under `OUTPUT/` (default: OUTPUT/resolution_gaps.yaml).
- Ledger outputs should remain under `drafts/ledger/`.
- Ledger inputs are exclusive: use `--nodes` or `--extract-structures-from` (not both).
- Placeholders (None/TBD/Opaque) are forbidden in SDSL statements.
- topology_enricher emits unified diffs only (stdout or `--out`); it does not apply changes.
- intent_template_gen supports `--dry-run` to print YAML (single input only).
