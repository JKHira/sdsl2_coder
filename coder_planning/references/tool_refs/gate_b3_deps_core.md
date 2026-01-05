# Gate B3 Core (@Dep from Ledger Evidence Only)

Purpose:
- Generate @Dep statements using ledger evidence only (no inference).

Inputs:
- B2-normalized .sdsl2 (contract profile only).
- Ledger YAML/JSON with declaration evidence fields:
  - evidence_refs_internal
  - evidence_refs_contract
  - evidence_refs_ssot

Core behaviors:
1) Resolve decl sites
   - Scan annotation groups and declaration heads.
   - Use @Anchor { id:"RELID" } to map rel_id -> line.

2) Evidence map
   - Read ledger.declarations entries keyed by (anchor_kind, rel_id).
   - Validate evidence lists are lists of strings.
   - Missing/invalid evidence -> REQ_DEP_EVIDENCE_INVALID.

3) Dep generation (deterministic)
   - For each decl with evidence:
     - Internal refs -> @Dep to internal target.
     - Contract tokens -> @Dep to "CONTRACT.X".
   - SSOT refs attached via ssot:[SSOT.X] only if valid.
   - Self-reference is dropped with MIG_DEP_SELF_REFERENCE.

4) ID rule
   - DEP_<from_rel_id>_<hash12> using sha256(from_ref->to_norm).

5) Duplicate handling
   - Duplicate dep targets -> REQ_DEP_DUPLICATE.
   - Unresolved internal ref -> REQ_DEP_UNRESOLVED_INTERNAL_REF.

Outputs:
- In-place or output file with inserted @Dep blocks.
- Per-file diagnostics YAML.
