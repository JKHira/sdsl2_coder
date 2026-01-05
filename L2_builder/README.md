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
- `token_registry_gen.py`: Generate OUTPUT/ssot/ssot_registry.json and contract_registry.json.
- `l2_gate_runner.py`: Run L1 operational gate, drift_check, exception_lint, and (publish) conformance/freshness.

## Paths and Authority
- SSOT is read-only under sdsl2/.
- Derived outputs are written only under OUTPUT/.
- Exceptions are read from policy/exceptions.yaml (non-SSOT).
- Registries are fixed under OUTPUT/ssot/.

## Notes
- Bundle Doc provenance uses Supplementary Section "provenance" and appends
  input_hash as a string in provenance.inputs to satisfy input_hash requirements.
- exception_lint.py requires --today (YYYY-MM-DD) to keep results deterministic.
- token_registry_gen accepts optional map inputs and can emit UNRESOLVED#/ entries.
- l2_gate_runner uses --publish to enforce conformance/freshness and to fail on UNRESOLVED#/. 
