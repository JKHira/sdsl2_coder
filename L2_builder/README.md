# L2 Builder Tools

Scope: Minimal L2 tools for contract lint, context pack/bundle doc, exceptions, and conformance checks.
Non-scope: Auto-apply, migrations, or any SSOT edits (diff-only only where specified).

## Tools
- contract_sdsl_lint.py: Manual/Addendum checks for contract profile SDSL.
- context_pack_gen.py: Deterministic Context Pack output to OUTPUT/context_pack.yaml.
- bundle_doc_gen.py: Bundle Doc from Context Pack plus provenance section.
- exception_lint.py: L2 exception file validator (policy/exceptions.yaml).
- implementation_skeleton_gen.py: Contract-based OUTPUT/implementation_skeleton.yaml.
- conformance_check.py: Validates skeleton matches current contract SSOT.
- freshness_check.py: Verifies bundle_doc provenance input_hash/source_rev.

## Paths and Authority
- SSOT is read-only under sdsl2/.
- Derived outputs are written only under OUTPUT/.
- Exceptions are read from policy/exceptions.yaml (non-SSOT).

## Notes
- Bundle Doc provenance uses Supplementary Section "provenance" and appends
  input_hash as a string in provenance.inputs to satisfy input_hash requirements.
- exception_lint.py requires --today (YYYY-MM-DD) to keep results deterministic.
- These tools are intended to be run under the L2 stage after L1 is complete.
