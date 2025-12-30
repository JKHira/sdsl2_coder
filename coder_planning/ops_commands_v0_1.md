# v0.1 Fixed Commands and Diff Gate

## run (generation)

Command:
```
python -m sdslv2_builder.run --ledger <PATH> --out-dir OUTPUT
```

Args:
- --ledger: required (Topology ledger v0.1, YAML/JSON)
- --out-dir: required (must be OUTPUT; subdirectories allowed)

Output path:
- Default: OUTPUT/<id_prefix>/topology.sdsl2
- If ledger has output.topology_v2_path: must be under OUTPUT or error.

Golden reference (separate from OUTPUT):
- tests/goldens/<id_prefix>/topology.sdsl2
- Spec bumps add new golden files (e.g., topology.v0_2.sdsl2)

## lint (validation)

Command:
```
python -m sdslv2_builder.lint --input OUTPUT
```

Args:
- --input: file or directory
- If directory: recursively scan *.sdsl2
- v0.1 output extension is .sdsl2

## diff gate (required)

1) git status --porcelain
- Must show changes only under OUTPUT/

2) git diff --stat -- OUTPUT/
3) git diff -- OUTPUT/

Optional:
- git diff --name-only -- OUTPUT/
