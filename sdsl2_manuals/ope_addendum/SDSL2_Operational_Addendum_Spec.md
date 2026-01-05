# SDSL2 Operational Addendum Specification

Scope: Define operational addendum scope and authority.
Non-scope: Grammar/semantics changes; edits to SDSLv2_Manual.md.

## Definitions
- Manual: SDSLv2_Manual.md (syntax/semantics SSOT).
- Core Addendum: SDSLv2_Manual_Addendum_Core.md.
- Operational Addendum: Tooling/CI rules outside Manual/Core.
- Conflict: Rule that overrides/weakens Manual/Addenda.

## Authority and Precedence
- Manual is the only SSOT for syntax and semantics.
- Addenda add operational restrictions only.
- Precedence order (highest first):
  1) SDSLv2_Manual.md
  2) Manual Addenda (Core, L0/L1/L2, SSOT) in sdsl2_manuals/
  3) Repository Operational Specs (this spec + sdsl2_manuals/ope_addendum/*)
- Within Repository Operational Specs, precedence is lexical by normalized relative path unless explicitly stated in sdsl2_manuals/ope_addendum/Conflicts.md.
- Conflicts MUST be recorded with id+resolution in sdsl2_manuals/ope_addendum/Conflicts.md; unresolved conflicts are FAIL.
- CI MUST load Conflicts.md when the addendum is enabled.

## References (Normative)
Operational rules in this repository MUST reference the following specs:
- SDSLv2_Manual.md
- sdsl2_manuals/SDSLv2_Manual_Addendum_Core.md
- sdsl2_manuals/SDSLv2_Manual_Addendum_L0.md
- sdsl2_manuals/SDSLv2_Manual_Addendum_L1.md
- sdsl2_manuals/SDSLv2_Manual_Addendum_L2.md
- sdsl2_manuals/ope_addendum/SDSLv2_Manual_Addendum_SSOT.md
- sdsl2_manuals/ope_addendum/ (files below)
  - SDSL2_SSOT_File_Layout_Spec.md
  - SDSL2_Authority_and_Artifacts_Spec.md
  - SDSL2_ContextPack_BundleDoc_Spec.md
  - SDSL2_SSOT_Domain_Model.md
  - SDSL2_Decisions_Spec.md
  - SDSL2_Decision_Draft_Spec.md
  - SDSL2_Decision_Evidence_Spec.md
  - SDSL2_Intent_YAML_Spec.md
  - SDSL2_Ambiguity_Routing_Spec.md
  - SDSL2_Policy_Spec.md
  - SDSL2_InputHash_Spec.md
  - SDSL2_Stage_DoD_and_Exception_Policy_Spec.md

## Policy Configuration
- policy.yaml is authoritative for operational gating and addendum enablement.
- If policy_path is provided by CI, it MUST be used. Otherwise use .sdsl/policy.yaml.
- If multiple policy files are found, CI MUST FAIL.
- If policy.yaml is missing, addendum.enabled is treated as false and CI MUST emit DIAG.
- policy.yaml MUST NOT override or weaken Manual rules.
- policy.yaml MAY only configure gate classification and explicitly-defined extension toggles; it MUST NOT change any normative schema/closed set defined by specs.
- policy schema and key set are defined in SDSL2_Policy_Spec.md.

## CI Requirements (Operational)
- CI SHOULD require checks: DRAFT-SCHEMA, EVIDENCE-COVERAGE, NO-SSOT-PROMOTION, L2-EXCEPTION-CHECK, READINESS-CHECK, TOKEN-REGISTRY, DETERMINISM.
- CI SHOULD enforce deterministic execution (containerized or locked runtime).
- Manual/Addendum lint MUST target SSOT parse surface (sdsl2/ only); OUTPUT/ and drafts/ are excluded.

## Operational Inputs (Non-SSOT)
- drafts/ (including drafts/intent/ Intent YAML), decisions/evidence.yaml, and policy/exceptions.yaml are operational inputs and MUST NOT be parsed as SSOT.
- policy/ is an operational input root (non-SSOT).
- Drafts/Evidence/Intent YAML/Exceptions are CI inputs only; MUST NOT be used by Promote.
- Drafts/Evidence/Intent YAML/Exceptions MAY be used by Operational Gate checks.
- Draft/Evidence checks are quality gates only; MUST NOT change SSOT meaning.

## Repository Restrictions (Operational)
- @Flow and @Flow.edges are forbidden in profile:"topology" SSOT files under sdsl2/topology/. Use @Edge only.
- @EdgeIntent is forbidden in profile:"topology" SSOT files under sdsl2/topology/; Intent YAML MUST be stored under drafts/intent/.
- Changes under decisions/ MUST be protected by CODEOWNERS or protected branch rules.

## Conflicts
- Operational rules MUST NOT redefine token placement, Graph Facts semantics, or any Manual rule.
- If an Operational rule conflicts with any Manual/Addendum rule, the Operational rule is invalid and MUST be removed or revised.
