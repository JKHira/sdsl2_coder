# SDSL2 Authority and Artifact Classification

Scope: Define authority boundaries and artifact classes.
Non-scope: Grammar/semantics changes; tool implementation.

## Definitions
- Authority: The source of truth for a domain.
- SSOT: Authoritative SDSL2 files parsed from sdsl2/ (see SDSL2_SSOT_File_Layout_Spec.md).
- Explicit Inputs: Human-reviewed decision inputs used to promote topology and contract SSOT.
- Derived Outputs: Tool outputs such as Context Pack and Bundle Doc (see SDSL2_ContextPack_BundleDoc_Spec.md).
- Cache: Stored outputs for speed only; non-authoritative.
- Draft Artifact: Non-SSOT proposal under drafts/.
- Intent YAML: Non-SSOT draft artifact under drafts/intent/ (see SDSL2_Intent_YAML_Spec.md).
- Evidence Map: Non-SSOT decisions/evidence.yaml.
- Exception File: Non-SSOT policy/exceptions.yaml.
- input_hash: Deterministic hash of the input set defined by the producing spec (base is SSOT + Explicit Inputs unless overridden).
- source_rev: Git commit hash of the repository state used to generate an artifact.

## Rules
- SDSLv2_Manual.md is SSOT for syntax/semantics. Addenda add operational restrictions only.
- SDSL2 Topology SSOT is authoritative for Graph Facts. SDSL2 Contract SSOT is authoritative for boundary schemas/invariants. Global registries/tables are authoritative in TS SSOT Kernel Definitions (via Distribution Boundary).
- Graph Facts MUST exist only in SDSL2 Topology SSOT (see Manual 9.4).
- Explicit Inputs MAY justify promotion but MUST NOT be treated as Graph Facts.
- Draft Artifacts (including Intent YAML), Evidence Maps, and Exception Files are non-authoritative and MUST NOT be treated as SSOT or Explicit Inputs.
- Derived Outputs are non-authoritative. Saving them MUST NOT grant authority.
- If Derived Outputs are persisted, they MUST include source_rev and input_hash.
- If Draft Artifacts, Evidence Maps, or Exception Files are persisted, they MUST include source_rev and input_hash.
- input_hash MUST follow SDSL2_InputHash_Spec.md.
- Derived Outputs and Cache artifacts MUST NOT be manually edited. They MUST be reproducible from SSOT + Explicit Inputs.
- Caches are non-authoritative and disposable; if persisted, include source_rev and input_hash.
- Explicit Inputs MUST live under a fixed root (default: decisions/) and MUST be human-reviewed.
- Explicit Inputs include decisions/edges.yaml and decisions/contracts.yaml.
- If an artifact conflicts with SSOT, SSOT wins.
- Tool outputs SHOULD include generator_id.
- Migrated Draft/Evidence/Exception artifacts SHOULD include migrate_from and migrate_tool_version.

## References
- SDSL2_SSOT_File_Layout_Spec.md
- SDSL2_ContextPack_BundleDoc_Spec.md
- SDSL2_SSOT_Domain_Model.md
- SDSL2_Decision_Draft_Spec.md
- SDSL2_Decision_Evidence_Spec.md
- SDSL2_Intent_YAML_Spec.md
- SDSL2_InputHash_Spec.md
- SDSL2_Stage_DoD_and_Exception_Policy_Spec.md
