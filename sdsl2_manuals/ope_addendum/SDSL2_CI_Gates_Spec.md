# SDSL2 CI Gates and Drift Policy

Scope: Define CI gate order, drift, and freshness rules.
Non-scope: Tool implementation details.

## Definitions
- Manual Gate: SDSLv2_Manual.md validation.
- Addendum Gate: Manual Addenda validation with policy-based severity.
- Operational Gate: Repository operational specs in sdsl2_manuals/ope_addendum/.
- Drift: Mismatch between SSOT, Explicit Inputs, and Derived Outputs.
- Freshness: Derived Outputs match the current SSOT and Explicit Inputs.
- Decision Log: Optional record of decisions.
- DRAFT-SCHEMA: Draft schema validation (see SDSL2_Decision_Draft_Spec.md).
- DUPLICATE-KEYS: YAML duplicate key detection for operational inputs.
- EVIDENCE-COVERAGE: Evidence validity and coverage checks (see SDSL2_Decision_Evidence_Spec.md).
- READINESS-CHECK: Promotion readiness enforcement (see SDSL2_Decisions_Spec.md).
- NO-SSOT-PROMOTION: Detect Draft/Evidence mixed into SSOT or decisions roots.
- SCHEMA-MIGRATION: Temporary allowance for schema_version transitions.
- EVIDENCE-REPAIR: Proposal-only evidence repair check.
- TOKEN-REGISTRY: SSOT.* and CONTRACT.* registry validation.
- L2-EXCEPTION-CHECK: L2 exception schema and expiry validation.
- DETERMINISM: Tooling determinism checks.

## Gate Order (Normative)
1) Manual Gate (FAIL on any violation)
2) Addendum Gate (FAIL/DIAG per policy)
3) Operational Gate (FAIL/DIAG per policy)
4) Drift Gate (FAIL/DIAG per policy)
5) Determinism/Freshness Gate (severity per Freshness Rules)

## Operational Gate Checks (Normative)
- DRAFT-SCHEMA
- DUPLICATE-KEYS
- EVIDENCE-COVERAGE
- READINESS-CHECK
- NO-SSOT-PROMOTION
- SCHEMA-MIGRATION
- EVIDENCE-REPAIR
- TOKEN-REGISTRY
- L2-EXCEPTION-CHECK
- DETERMINISM (tool outputs only; persisted outputs are checked in Determinism/Freshness Gate)

## Operational Gate Rules
- DRAFT-SCHEMA validates drafts/*.yaml with SDSL2_Decision_Draft_Spec.md and drafts/intent/*.yaml with SDSL2_Intent_YAML_Spec.md; symlinks under drafts/ or drafts/intent/ are FAIL; it reports MAJOR mismatch with a dedicated diagnostic code.
- DUPLICATE-KEYS validates that a mapping does not contain duplicate keys in operational YAML inputs; duplicates are DIAG by default and become FAIL when policy.gates.duplicate_keys=FAIL.
- EVIDENCE-COVERAGE validates Evidence schema, locator/content_hash correctness, scope match, and coverage.
- READINESS-CHECK is the authoritative enforcement for Promotion Readiness (Decisions + Evidence + Intent YAML), including scope match, duplicate Intent YAML detection, and stale Intent mismatches.
- NO-SSOT-PROMOTION FAILS if Draft/Evidence/Exception appear under sdsl2/ or decisions/, or via symlink; Exception File path != policy/exceptions.yaml is FAIL.
- policy/ is an operational input root; symlink inclusion from sdsl2/ or decisions/ is forbidden.
- SCHEMA-MIGRATION sets severity for MAJOR mismatch diagnostics; within policy.schema.migration_window_days -> DIAG, after expiry -> FAIL.
- EVIDENCE-REPAIR is proposal-only; multiple candidates for a single item is FAIL.
- TOKEN-REGISTRY validates "SSOT.*" and "CONTRACT.*" tokens against registries/allowlists.
- UNRESOLVED#/ targets are allowed pre-publish; publish MUST fail if any UNRESOLVED#/ remains.
- L2-EXCEPTION-CHECK validates exception schema, expiry, scope/target uniqueness, and policy caps.
- DETERMINISM checks normalization, stable ordering, and identical output on rerun under fixed environment.

## Drift Rules
- decisions -> SSOT not reflected: FAIL.
- A decision is reflected iff @Edge exists in scoped topology with matching (id,from,to,direction,contract_refs) after normalization (see SDSL2_Operational_Addendum_Spec.md; @Flow/@Flow.edges forbidden).
- SSOT -> decisions missing: @Edge in scope without matching EdgeDecision is drift mismatch (Missing Decisions/Manual Edge). Severity is policy-controlled (see SDSL2_Stage_DoD_and_Exception_Policy_Spec.md).
- Scope resolution/matching MUST follow SDSL2_Decisions_Spec.md.
- Graph Facts created via Promote MUST have Explicit Inputs (decisions/edges.yaml); Evidence Map MUST NOT affect Drift.
- Derived Outputs mismatch SSOT/Explicit Inputs: DIAG by default; FAIL if persisted outputs are present.

## Freshness Rules
- Persisted Derived Outputs paths/names MUST follow SDSL2_ContextPack_BundleDoc_Spec.md (and repo policy).
- Persisted Context Pack/Bundle Doc MUST include source_rev and input_hash.
- If persisted, source_rev/input_hash MUST match current SSOT + Explicit Inputs; mismatch FAIL.

## Addendum Severity
- policy.yaml MAY define FAIL/DIAG/IGNORE only where explicitly allowed by specs.
- Default severity for Operational Gate checks is FAIL unless overridden by policy.gates.*.
- DUPLICATE-KEYS defaults to DIAG unless overridden by policy.gates.duplicate_keys.
- Manual violations are always FAIL.

## Policy Keys (Closed Set)
- policy.gates.draft_schema: FAIL | DIAG | IGNORE
- policy.gates.duplicate_keys: FAIL | DIAG | IGNORE
- policy.gates.evidence_coverage: FAIL | DIAG | IGNORE
- policy.gates.no_ssot_promotion: FAIL | DIAG | IGNORE
- policy.gates.readiness_check: FAIL | DIAG | IGNORE
- policy.gates.schema_migration: FAIL | DIAG | IGNORE
- policy.gates.evidence_repair: FAIL | DIAG | IGNORE
- policy.gates.determinism: FAIL | DIAG | IGNORE
- policy.gates.token_registry: FAIL | DIAG | IGNORE
- policy.gates.l2_exception_check: FAIL | DIAG | IGNORE
- policy.schema.migration_window_days: integer

## Decision Log (Minimal)
- Drift checks MUST use SDSL2_Decisions_Spec.md scope resolution and matching rules as the only SSOT↔decisions mapping.
- If decisions/decision_log.yaml exists, it MUST follow Common Operational YAML Conventions (SDSLv2_Manual_Addendum_Core.md).
- It MUST be a list of entries with keys: id, when, who, summary (schema order).
- id MUST be unique; when MUST be YYYY-MM-DD.

## References
- SDSLv2_Manual.md
- sdsl2_manuals/SDSLv2_Manual_Addendum_Core.md
- sdsl2_manuals/ope_addendum/ (files below)
  - SDSL2_Operational_Addendum_Spec.md
  - SDSL2_Authority_and_Artifacts_Spec.md
  - SDSL2_ContextPack_BundleDoc_Spec.md
  - SDSL2_Decisions_Spec.md
  - SDSL2_Decision_Draft_Spec.md
  - SDSL2_Intent_YAML_Spec.md
  - SDSL2_Decision_Evidence_Spec.md
  - SDSL2_Policy_Spec.md
  - SDSL2_InputHash_Spec.md
  - SDSL2_Stage_DoD_and_Exception_Policy_Spec.md
