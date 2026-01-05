# SDSL2 Decision Draft Specification

Scope: Define non-SSOT Draft artifacts for intent/proposal capture.
Non-scope: Grammar/semantics changes; Promote inputs; auto SSOT updates.

## Definitions
- Draft Root: Repository root directory that stores Draft Artifacts.
- Draft Artifact: YAML file under Draft Root that contains proposals only.
- Schema Version: Draft schema version in MAJOR.MINOR form.

## Rules
- Draft Root MUST be drafts/ at repository root.
- Drafts are non-SSOT and MUST NOT be used by Promote or Drift.
- Draft files MUST NOT be symlinks; symlinks FAIL.
- Intent YAML is defined in SDSL2_Intent_YAML_Spec.md and is a Draft Artifact with a restricted key set.
- Drafts MUST follow Common Operational YAML Conventions (SDSLv2_Manual_Addendum_Core.md).
- schema_version MUST be non-empty MAJOR.MINOR; readers accept same MAJOR only.
- MINOR compatibility MUST be additive optional fields only; no meaning change.
- MAJOR mismatch is incompatible; any allowance is via SCHEMA-MIGRATION gate.
- migrate MUST be structural/normalization-only and diff-only (no auto-apply in CI).
- migrate MUST NOT change meaning (no deletion or summarization of proposal fields).
- Drafts SHOULD be regenerated when schema_version changes.
- input_hash MUST be computed from SSOT files only (no Explicit Inputs) and follow SDSL2_InputHash_Spec.md.

### Draft Top-Level Schema (Closed Set)
- Top-level keys: schema_version, source_rev, input_hash, generator_id, scope, nodes_proposed, edge_intents_proposed, contract_candidates, questions, conflicts.
- scope MUST follow decisions/edges.yaml scope rules (see SDSL2_Decisions_Spec.md).
- Placeholders (None/TBD/Opaque) are forbidden.
- Graph Facts and @Edge creation are forbidden.

### nodes_proposed
- nodes_proposed MUST be a list of NodeProposal items.
- NodeProposal MUST be a map with keys: id, kind (kind optional).
- NodeProposal.id MUST be a RelId string.
- nodes_proposed MUST be sorted lexically by id.

### edge_intents_proposed
- edge_intents_proposed MUST be a list of EdgeIntentProposal items.
- EdgeIntentProposal MUST be a map with keys: id, from, to, direction, channel, note.
- id/from/to MUST be RelId strings.
- direction MAY be omitted; if present it MUST be one of the canonical values in Manual 7.10.
- channel MAY be omitted; if present it MUST be a string.
- note MAY be omitted; if present it MUST be a string.
- edge_intents_proposed MUST be sorted lexically by id.

### contract_candidates
- contract_candidates MUST be a list of ContractCandidate items.
- ContractCandidate MUST be a map with keys: edge_id, tokens.
- edge_id MUST be an EdgeIntentProposal id.
- tokens MUST be a non-empty list of "CONTRACT.*" string tokens only.
- tokens MUST be sorted lexically and de-duplicated.
- contract_candidates are proposals only and never decisions.

### questions / conflicts
- questions MUST be a list of strings, sorted lexically.
- conflicts MUST be a list of strings, sorted lexically.
