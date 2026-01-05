# SDSL2 Stage DoD and Exception Policy (Operational)

Scope: Define stage DoD and exception handling for topology.
Non-scope: Manual/Addenda changes; new syntax/semantics.

## Definitions
- Stage: "L0" | "L1" | "L2".
- Stage DoD: A topology file state where required gate results are met.
- Gate status: PASS | DIAG | FAIL.
- DoD Status: PASS | PASS_WITH_EXCEPTIONS | FAIL.
- Missing Decisions / Manual Edge: Drift mismatch cases defined in SDSL2_CI_Gates_Spec.md.
- Drift mismatch: See SDSL2_CI_Gates_Spec.md Drift Rules.
- Exception File: policy/exceptions.yaml (non-SSOT).

## Rules
- Authority/precedence: Manual > Addenda > Repository Operational Specs; this spec is operational only.
- Applicability: Stage DoD applies only to profile:"topology".
- Drift mismatch definition MUST follow SDSL2_CI_Gates_Spec.md; no redefinition here.
- Stage DoD uses gate order from SDSL2_CI_Gates_Spec.md.

### L0 DoD
- Manual Gate: PASS.
- Addendum Gate: L0 rules PASS.
- Operational Gate: PASS or DIAG. FAIL blocks DoD.
- Drift Gate: Missing Decisions MAY be DIAG or IGNORE by policy; any drift mismatch is FAIL.

### L1 DoD
- Manual Gate: PASS.
- Addendum Gate: L1 rules PASS.
- Operational Gate: PASS.
- If policy.dod.require_evidence_l1 = true, EVIDENCE-COVERAGE MUST be PASS for L1 DoD.
- Drift Gate: PASS.
- Determinism/Freshness Gate: PASS if derived outputs are persisted; MAY be skipped by policy otherwise.

### L2 DoD
- Manual Gate: PASS.
- Addendum Gate: L2 rules PASS.
- Operational Gate: PASS.
- If policy.dod.require_evidence_l2 = true, EVIDENCE-COVERAGE MUST be PASS for L2 DoD.
- Drift Gate: PASS.
- Determinism/Freshness Gate: PASS if derived outputs are persisted; MAY be skipped by policy otherwise.

### Exceptions (policy-controlled)
- Exceptions MAY only affect Operational Gate severities and MUST NOT affect Drift Gate.
- Manual or Addendum violations are always FAIL and cannot be downgraded.

#### Missing Decisions
- L0: Missing Decisions -> DIAG by default; MAY be IGNORE if policy.drift.allow_missing_decisions_l0 = true.
- L1: Missing Decisions -> FAIL; MAY be DIAG only if policy.drift.migration_window_l1 = true.
- L2: Missing Decisions -> FAIL.

#### Manual Edges
- L1/L2: Manual Edge -> FAIL by default.
- If policy.drift.allow_manual_edges = true, Manual Edge -> DIAG and CI MUST emit DRIFT_MANUAL_EDGE.
- Note: Even when downgraded to DIAG, Manual Edges prevent L1/L2 DoD because Drift Gate is not PASS.

#### Partial Migration
- Mixed stages across topology files are allowed only if policy.stage_policy.allow_mixed_stages = true (see SDSLv2_Manual_Addendum_SSOT.md).
- If false, Operational Gate MUST FAIL on mixed stages.

### L2 Exception Policy (Quality Gate Only)
- Exception File MUST be policy/exceptions.yaml and is non-SSOT.
- Exception File MUST follow Common Operational YAML Conventions (SDSLv2_Manual_Addendum_Core.md).
- Exception File top-level keys: schema_version, source_rev, input_hash, exceptions.
- schema_version MUST be non-empty string.
- input_hash MUST follow SDSL2_InputHash_Spec.md.
- exceptions MUST be a list of ExceptionEntry items.
- ExceptionEntry MUST be a map with keys: id, scope, targets, reason_code, owner, expires, exit_criteria, extend_count, progress_note.
- id MUST be unique across exceptions.
- scope MUST follow decisions/edges.yaml scope rules.
- targets MUST be non-empty list with closed set values: EVIDENCE-COVERAGE | DRAFT-SCHEMA | SCHEMA-MIGRATION.
- reason_code MUST be one of: LEGACY_MIGRATION | EXTERNAL_APPROVAL | SCHEMA_SYNC.
- owner MUST be a non-empty string.
- expires MUST be YYYY-MM-DD; expired exceptions FAIL.
- exit_criteria MUST be a non-empty string.
- extend_count MUST be 0 or 1; if 1, progress_note REQUIRED.
- progress_note MUST be omitted when extend_count == 0.
- Only one active exception per (scope, target) is allowed.
- Active exceptions per repo and per scope MUST NOT exceed policy.dod.l2_exception_cap and policy.dod.l2_exception_scope_cap.
- L2 DoD MUST be PASS_WITH_EXCEPTIONS when any active exception exists and MUST NOT be PASS.

#### Policy Keys (closed set)
- policy.drift.allow_missing_decisions_l0: true | false
- policy.drift.migration_window_l1: true | false
- policy.drift.allow_manual_edges: true | false
- policy.stage_policy.allow_mixed_stages: true | false
- policy.dod.require_evidence_l1: true | false
- policy.dod.require_evidence_l2: true | false
- policy.dod.l2_exception_cap: integer
- policy.dod.l2_exception_scope_cap: integer
