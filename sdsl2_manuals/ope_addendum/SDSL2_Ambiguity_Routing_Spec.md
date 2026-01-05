# SDSL2 Ambiguity Routing Specification

Scope: Define routing rules for ambiguous inputs across Intent/Draft/Evidence/Decisions/SSOT.
Non-scope: Grammar/semantics; CI implementation.

## Definitions
- Ambiguity Type: Closed set A1-A5.
- Routing Target: Allowed storage location.
- Gate Outcome: Required CI result when unresolved.
- Draft: drafts/*.yaml conforming to SDSL2_Decision_Draft_Spec.md.
- Intent YAML: drafts/intent/*.yaml per SDSL2_Intent_YAML_Spec.md.

## Rules
- Ambiguities MUST be classified as A1-A5.
- Routing MUST follow this mapping; any other placement is forbidden.
- Routing MUST NOT create Graph Facts or Decisions (see Manual 9.4, R1-R7).
- Routing does not authorize automatic creation; Intent YAML entries MAY be authored only by humans or explicit tooling inputs per repo workflow.

### A1: Connection Existence Unknown
- Routing Target: Draft.questions or Draft.conflicts.
- MUST NOT create Intent YAML edge_intents_proposed entries or EdgeDecision.
- SHOULD record Bundle Doc Supplementary: decisions_needed (at least one item).
- Gate Outcome: No direct gate result; visibility via decisions_needed.

### A2: Connection Exists, Direction Unknown
- Routing Target: Intent YAML edge_intents_proposed with direction omitted.
- MUST NOT create EdgeDecision.
- Gate Outcome: Intent YAML handling follows SDSL2_Intent_YAML_Spec.md.

### A3: Connection Exists, contract_refs Unknown
- Routing Target: Intent YAML edge_intents_proposed (contract_refs are not allowed in this schema).
- MUST NOT create EdgeDecision.
- Gate Outcome: Intent YAML handling follows SDSL2_Intent_YAML_Spec.md.

### A4: Contract Candidates Exist but Unapproved
- Routing Target: Draft.contract_candidates only.
- MUST NOT create EdgeDecision based solely on candidates.
- Gate Outcome: If a Decision is created without evidence for chosen contract_refs, READINESS-CHECK MUST report not-ready (severity per policy; see SDSL2_CI_Gates_Spec.md).

### A5: Evidence Missing or Unverifiable
- Routing Target: decisions/evidence.yaml (Evidence Map).
- EdgeDecision MAY exist.
- A5a: Evidence entry missing (decision_id not present in Evidence Map).
- A5b: Evidence entry unverifiable (locator/hash mismatch).
- Gate Outcome: EVIDENCE-COVERAGE MUST report missing entry for A5a and unverifiable entry for A5b; READINESS-CHECK MUST report not-ready (severity per policy; see SDSL2_CI_Gates_Spec.md).
