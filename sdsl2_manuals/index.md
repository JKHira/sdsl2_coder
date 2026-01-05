# SDSL2 Manuals Index

Scope: List manuals and addenda under sdsl2_manuals/ with relative paths and roles.
Non-scope: Full summaries or normative rules.

Definitions
- Manual: Core syntax and semantics SSOT.
- Addendum: Operational or stage restrictions layered on the Manual.

Rules
- Paths are relative to sdsl2_manuals/.
- One line per file, concise role only.
- Paths under ope_addendum/ are listed without the prefix.

Files
- `SDSLv2_Manual.md` - Core grammar/semantics SSOT (all stages).

- `ope_addendum/` - Addenda and operational specs listed below in the dir.
- `SDSL2_Minimal_Lifecycle_Example.md` - Draft to L2 steps (L0-L2).
- `SDSLv2_Manual_Addendum_Core.md` - Stage framework, placeholders, context pack order (all stages).
- `SDSLv2_Manual_Addendum_L0.md` - L0 allowed/forbidden kinds (L0).
- `SDSLv2_Manual_Addendum_L1.md` - L1 allowed/forbidden kinds (L1).
- `SDSLv2_Manual_Addendum_L2.md` - L2 rules (L2).
- `SDSLv2_Manual_Addendum_SSOT.md` - SSOT addendum and policy defaults (all stages).
- `SDSL2_Operational_Addendum_Spec.md` - Operational authority/precedence and repo restrictions (all stages).
- `SDSL2_SSOT_File_Layout_Spec.md` - SSOT file layout and parse surface (all stages).
- `SDSL2_SSOT_Domain_Model.md` - SSOT domain split with TS kernel/registry (all stages).
- `SDSL2_Authority_and_Artifacts_Spec.md` - Authority boundaries and artifact classes (all stages).
- `SDSL2_ContextPack_BundleDoc_Spec.md` - Context Pack/Bundle Doc output rules (all stages).
- `SDSL2_Decisions_Spec.md` - Decisions input schema for Promote (L1 focus).
- `SDSL2_Decision_Draft_Spec.md` - Draft (non-SSOT) proposal schema (L0->L1).
- `SDSL2_Intent_YAML_Spec.md` - Intent YAML (non-SSOT) for edge intents (L0-L1).
- `SDSL2_Decision_Evidence_Spec.md` - Evidence map schema and coverage rules (L1 focus).
- `SDSL2_Ambiguity_Routing_Spec.md` - Ambiguity routing across Draft/Evidence/Decisions (L0-L1).
- `SDSL2_Policy_Spec.md` - policy.yaml schema and closed key set (all stages).
- `SDSL2_InputHash_Spec.md` - input_hash normalization and input set rules (all stages).
- `SDSL2_Promote_Spec.md` - Promote behavior and patch constraints (L0->L1).
- `SDSL2_CI_Gates_Spec.md` - CI gate order, drift, freshness (all stages).
- `SDSL2_Stage_DoD_and_Exception_Policy_Spec.md` - Stage DoD and exception policy (L0-L2).
