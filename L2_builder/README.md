# L2 Builder Tools

Scope: Minimal L2 tools for contract lint, context pack/bundle doc, exceptions, registries, and conformance checks.
Non-scope: Auto-apply, migrations, or any SSOT edits (diff-only only where specified).

## Tools
- `contract_sdsl_lint.py`: Manual/Addendum checks for contract profile SDSL.
- `context_pack_gen.py`: Deterministic Context Pack output to OUTPUT/context_pack.yaml (provenance included).
- `bundle_doc_gen.py`: Bundle Doc from Context Pack plus provenance section.
- `implementation_skeleton_gen.py`: Contract-based OUTPUT/implementation_skeleton.yaml.
- `exception_lint.py`: L2 exception file validator (policy/exceptions.yaml).
- `conformance_check.py`: Validates skeleton matches current contract SSOT.
- `freshness_check.py`: Verifies bundle_doc provenance input_hash/source_rev.
- `ssot_kernel_coverage_check.py`: Validate SSOT kernel coverage against policy/ssot_kernel_profile.yaml.
- `ssot_kernel_lint.py`: SSOT kernel lint (publish-time).
- `ssot_registry_consistency_check.py`: Validate registry/SSOT consistency (publish-time).
- `token_registry_gen.py`: Generate OUTPUT/ssot/ssot_registry.json and contract_registry.json.
- `l2_gate_runner.py`: Run L1 operational gate, contract_sdsl_lint, drift_check, exception_lint, and (publish) conformance/freshness.

## Paths and Authority
- SSOT is read-only under sdsl2/.
- Derived outputs are written only under OUTPUT/.
- Exceptions are read from policy/exceptions.yaml (non-SSOT).
- Registries are fixed under OUTPUT/ssot/.

## Usage (minimal)
- L2 gate (pre-publish): `python3 L2_builder/l2_gate_runner.py --today 2024-01-01 --project-root /repo`
- L2 gate (publish): `python3 L2_builder/l2_gate_runner.py --today 2024-01-01 --publish --project-root /repo`
- Build SSOT definitions: `python3 ssot_kernel_builder/build_ssot_definitions.py --project-root /repo`
- Context Pack: `python3 L2_builder/context_pack_gen.py --input sdsl2/topology/P0_T_EXAMPLE_L2.sdsl2 --target @Node.EXAMPLE --project-root /repo`
- Bundle Doc: `python3 L2_builder/bundle_doc_gen.py --project-root /repo`
- Implementation skeleton: `python3 L2_builder/implementation_skeleton_gen.py --project-root /repo`
- Registries: `python3 L2_builder/token_registry_gen.py --project-root /repo`
- SSOT kernel coverage: `python3 L2_builder/ssot_kernel_coverage_check.py --project-root /repo`

## Notes
- Bundle Doc provenance uses Supplementary Section "provenance" and appends
  input_hash as a string in provenance.inputs to satisfy input_hash requirements.
- Bundle Doc/Freshness input_hash excludes decisions by default; use --include-decisions to opt in.
- exception_lint.py requires --today (YYYY-MM-DD) to keep results deterministic.
- l2_gate_runner.py requires --today (YYYY-MM-DD).
- ssot_kernel_lint.py reads OUTPUT/ssot/ssot_definitions.json; use --allow-missing for pre-publish.
- l2_gate_runner --publish expects OUTPUT/ssot/ssot_definitions.json and OUTPUT/ssot/ssot_registry.json to exist.
- ssot_kernel_coverage_check.py requires policy/ssot_kernel_profile.yaml to exist.
- token_registry_gen accepts optional map inputs and can emit UNRESOLVED#/ entries.
- ssot_definitions.json and ssot_registry_map.json are produced by ssot_kernel_builder/build_ssot_definitions.py.
- l2_gate_runner uses --publish to run ssot_kernel_lint, ssot_registry_consistency_check, conformance_check, and freshness_check. 
