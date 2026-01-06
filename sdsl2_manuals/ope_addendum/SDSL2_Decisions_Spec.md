# SDSL2 Decisions Input Specification

Scope: Define explicit decision inputs for Promote.
Non-scope: Grammar/semantics changes; tool implementation details.

## Definitions
- Explicit Inputs: Human-reviewed decision files under decisions/ used by Promote.
- Decision Scope: The target area a decision applies to (file, id_prefix, or component).
- RelId: Relative id used in SDSL2 files (no canonical ids).

## Rules
- Explicit Inputs MUST live under decisions/.
- Decisions files MUST follow Common Operational YAML Conventions (SDSLv2_Manual_Addendum_Core.md).
- Placeholders (None/TBD/Opaque) are forbidden in decisions files.
- Decisions MUST NOT contain canonical ids. RelId only.
- Evidence Map decisions/evidence.yaml MUST follow SDSL2_Decision_Evidence_Spec.md and is required for Promotion Readiness.
- Promotion Readiness MUST include evidence coverage for contract_refs (see SDSL2_Decision_Evidence_Spec.md).
- Promotion Readiness MUST require a matching Intent YAML edge_intents_proposed entry with the same scope (kind/value) and id/from/to under drafts/intent/ (see SDSL2_Intent_YAML_Spec.md). If an Intent entry exists with the same scope+id but different from/to, readiness FAIL.
- scope keys: kind, value.
- scope.kind: "file" | "id_prefix" | "component".
- scope.value:
  - file: repo-relative topology .sdsl2 path.
  - id_prefix: target topology id_prefix.
  - component: @Node rel_id in target topology.
  - component rel_id MUST be globally unique across sdsl2/topology/**/*.sdsl2; if not unique or missing, decisions_lint MUST FAIL.
- For scope.kind:"component", Promote applies only when from == value or to == value.
- Decisions for topology edges MUST be stored in decisions/edges.yaml.
- Decisions for contract structures/rules MUST be stored in decisions/contracts.yaml.
- decisions/edges.yaml top-level keys: schema_version, provenance, scope, edges.
- schema_version MUST be non-empty string.
- provenance keys: author, reviewed_by, source_link (all non-empty strings).
- provenance.source_link MUST be repo-relative path or artifact id.
- edges MUST be a list of EdgeDecision items.
- EdgeDecision.id MUST be unique within edges. Duplicate is FAIL.
- edges MUST be sorted lexically by id.
- The tuple (from,to,direction) MUST be unique within edges. Duplicate is FAIL.

## EdgeDecision (for decisions/edges.yaml)
- EdgeDecision MUST be a map with keys: id, from, to, direction, contract_refs.
- id/from/to MUST be RelId strings.
- from/to MUST refer to @Node rel_id values in the target topology scope.
- direction MUST be one of the canonical values in Manual 7.10.
- contract_refs MUST be a non-empty list of ContractRef tokens (Manual 9.3).
- contract_refs MUST be sorted lexically and de-duplicated.

## Contract Decisions (for decisions/contracts.yaml)
- decisions/contracts.yaml top-level keys: schema_version, provenance, scope, structures, rules.
- provenance keys and constraints are the same as decisions/edges.yaml.
- scope.kind: "file" | "id_prefix".
- scope.value:
  - file: repo-relative sdsl2/contract/*.sdsl2 path.
  - id_prefix: RELID (UPPER_SNAKE_CASE).
- structures MUST be a list of StructureDecision { id, decl | decl_lines }.
- StructureDecision.id MUST be RELID; decl is a non-empty string.
- decl_lines MAY be used instead of decl; it is a list of line strings or {line:<text>} objects; lines joined with "\\n".
- structures MUST be sorted by id and de-duplicated.
- rules MUST be a list of RuleDecision { id, bind, refs, contract, ssot }.
- RuleDecision.id MUST be RELID; bind and refs MUST be InternalRef.
- contract MUST be a list of CONTRACT.* tokens; ssot MUST be a list of SSOT.* tokens.
- refs/contract/ssot MUST be sorted and de-duplicated; rules MUST be sorted by id and de-duplicated.

## Promotion Constraints
- Promote MUST NOT create Graph Facts without Explicit Inputs (see Manual 9.4).
- If an EdgeDecision matches an existing @Edge with the same (from,to,direction,contract_refs), Promote is a no-op for that item.
- Otherwise, Promote MUST insert a new @Edge for that decision.
- Promote MUST NOT read Intent YAML; only decisions/ are inputs.
- READINESS-CHECK is the authoritative enforcement for Promotion Readiness requirements.
- READINESS-CHECK MUST be required as a PR/merge gate; local bypass MAY be allowed.
