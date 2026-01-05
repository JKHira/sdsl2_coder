# SDSL2 Policy Specification

Scope: Define policy.yaml schema and closed key set.
Non-scope: CI implementation; semantics beyond referenced specs.

## Definitions
- Policy File: Repository operational configuration (policy.yaml).
- Gate Severity: FAIL | DIAG | IGNORE.
- Closed Set: Keys outside this spec are forbidden.

## Rules
- Policy file location and loading rules MUST follow SDSL2_Operational_Addendum_Spec.md and SDSLv2_Manual_Addendum_SSOT.md.
- policy.yaml MUST follow Common Operational YAML Conventions (SDSLv2_Manual_Addendum_Core.md).
- policy.yaml MUST be a map. Unknown keys MUST be treated as FAIL.
- Key semantics are defined by the referenced specs; if a key is omitted, defaults apply in those specs.
- Gate Severity values MUST be uppercase; mode enums MUST be lowercase as listed.
- If policy.yaml is missing, addendum.enabled is false and policy schema validation is skipped; CI emits DIAG (see SDSL2_Operational_Addendum_Spec.md).

### Closed Set (Top-Level Keys)
- addendum
- stage_policy
- manual_policy
- drift
- dod
- gates
- schema
- graph_facts
- context_pack

### addendum
- enabled: true | false
  - See SDSLv2_Manual_Addendum_SSOT.md.

### stage_policy
- allow_l0_terminal: true | false
- l0_kind_mode: "fail" | "diag"
- l1_edgeintent_mode: "fail" | "diag"
- edgeintent_unknown_keys: "fail" | "diag"
- allow_mixed_stages: true | false
- repo_min_stage: "L0" | "L1" | "L2"
- allow_contract_stage: true | false
  - See SDSLv2_Manual_Addendum_SSOT.md.

### manual_policy
- manual_mode: "strict" | "permissive"
- manual_lint_level: "error" | "warn"
- Reserved for Manual Gate tooling.
- Manual violations are always FAIL; manual_policy MUST NOT downgrade Manual errors.

### drift
- allow_missing_decisions_l0: true | false
- migration_window_l1: true | false
- allow_manual_edges: true | false
  - See SDSL2_Stage_DoD_and_Exception_Policy_Spec.md.

### dod
- require_evidence_l1: true | false
- require_evidence_l2: true | false
- l2_exception_cap: integer
- l2_exception_scope_cap: integer
  - See SDSL2_Stage_DoD_and_Exception_Policy_Spec.md.

### gates
- draft_schema: FAIL | DIAG | IGNORE
- evidence_coverage: FAIL | DIAG | IGNORE
- no_ssot_promotion: FAIL | DIAG | IGNORE
- readiness_check: FAIL | DIAG | IGNORE
- schema_migration: FAIL | DIAG | IGNORE
- evidence_repair: FAIL | DIAG | IGNORE
- determinism: FAIL | DIAG | IGNORE
- token_registry: FAIL | DIAG | IGNORE
- l2_exception_check: FAIL | DIAG | IGNORE
  - See SDSL2_CI_Gates_Spec.md.

### schema
- migration_window_days: integer
  - See SDSL2_CI_Gates_Spec.md.

### graph_facts
- duplicate_mode: "strict" | "migration"
- Repository selection for Manual R6 (see SDSLv2_Manual.md).
- graph_facts.duplicate_mode MUST be present; omission is FAIL.

### context_pack
- allow_open_todo_extensions: true | false
- allow_supplementary_extensions: true | false
  - See SDSL2_ContextPack_BundleDoc_Spec.md.
