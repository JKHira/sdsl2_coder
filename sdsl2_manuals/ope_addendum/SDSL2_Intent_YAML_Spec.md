# SDSL2 Intent YAML Specification

Scope: Define non-SSOT Intent YAML artifacts for L0/L1.
Non-scope: Grammar/semantics changes; Promote inputs; auto-apply.

Definitions
- Intent YAML: Draft artifact that records edge intents outside SSOT.
- Intent Root: drafts/intent/ (closed set).

Rules
- Intent YAML files MUST be stored under drafts/intent/*.yaml (closed set).
- Intent YAML is non-SSOT and MUST NOT be parsed as SSOT.
- Intent YAML MUST NOT be used by Promote or Drift.
- Intent YAML files MUST NOT be symlinks; symlinks FAIL.
- Intent YAML MUST follow Common Operational YAML Conventions (SDSLv2_Manual_Addendum_Core.md).
- Intent YAML MUST follow SDSL2_Decision_Draft_Spec.md rules for scope, sorting, RelId, and edge_intents_proposed item schema.
- Allowed top-level keys (closed set): schema_version, source_rev, input_hash, generator_id, scope, nodes_proposed, edge_intents_proposed, questions, conflicts.
- edge_intents_proposed MUST be present.
- edge_intents_proposed.id MUST be unique within a file; duplicates FAIL.
- contract_candidates MUST NOT appear in Intent YAML.
- Placeholders (None/TBD/Opaque) are forbidden (see SDSL2_Decision_Draft_Spec.md).
- input_hash MUST be computed from SSOT files only (no Explicit Inputs).
- DRAFT-SCHEMA MUST validate drafts/intent/*.yaml using this spec.
- edgeintent-diff MUST read Intent YAML and output unified diff against OUTPUT/intent_preview.sdsl2 only; it MUST NOT target sdsl2/ or auto-apply.
- Intent YAML files MUST be enumerated in lexical path order; within the same scope, edge_intents_proposed.id MUST be unique across all Intent YAML files (duplicates FAIL).
