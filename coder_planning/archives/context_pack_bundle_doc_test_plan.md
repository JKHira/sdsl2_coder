# Context Pack / Bundle Doc Test Plan

Scope: Define deferred tests for Context Pack and Bundle Doc outputs.
Non-scope: Generator changes; spec changes.

Definitions
- Context Pack: OUTPUT/context_pack.yaml only.
- Bundle Doc: OUTPUT/bundle_doc.yaml only.
- SSOT inputs: sdsl2/topology/**/*.sdsl2 and sdsl2/contract/**/*.sdsl2.

Rules
- Context Pack MUST include sections in fixed order and with required keys.
- Nodes MUST be sorted and de-duplicated by canon_id (fallback rel_id).
- Edges MUST be sorted by Addendum Core key and de-duplicated.
- Contracts/Authz/Invariants MUST be sorted and de-duplicated.
- Open TODO MUST be a map with closed keys and correct value types.
- Bundle Doc MUST embed Context Pack unchanged as the full prefix.
- Supplementary MUST use delimiter "---" and heading "Supplementary: <key>" only.
- Supplementary keys MUST be from the closed set and in correct order.
- Supplementary MUST be YAML block style with required key order and double-quoted strings.
- input_hash MUST be computed from SSOT only; no Explicit Inputs.
- Determinism MUST hold: regenerate twice and byte-compare outputs.

