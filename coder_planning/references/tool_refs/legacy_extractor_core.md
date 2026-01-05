# Legacy Extractor Core (Deterministic Ledger Build)

Purpose:
- Deterministic extraction of declaration anchors and evidence into a ledger.
- No heuristics or inference; strict adjacency rules.

Core behaviors to reuse:
1) Parse surface selection
   - If fenced code blocks exist, only capture supported languages:
     ts, typescript, sdsl, sdsl2.
   - Otherwise parse the whole file as-is.

2) Closed-set tag scanning
   - Anchor tags: DocMeta, Structure, Interface, Class, Function, Const, Type.
   - Evidence tags: Rule, SSOTRef.
   - Tags found in comments or inline (non-comment) are recorded.

3) Strict adjacency attribution
   - A tag applies ONLY to the next non-blank, non-comment line.
   - A blank line breaks adjacency (unattributed).
   - Decl head must be one of: enum/struct/interface/class/C/const/type/f.

4) Evidence extraction (closed-set only)
   - Internal refs: @Kind.RELID or @Kind::CANON_ID (Kind must be anchor kind).
   - External tokens: CONTRACT.X / SSOT.X (upper token only).
   - Invalid tokens/refs produce diagnostics.

5) ID normalization
   - rel_id = strip legacy_id_prefix if present; else fallback to UPPER_SNAKE(decl_name).
   - Invalid or empty rel_id -> UNNAMED_<KIND>_<n>.

6) Deterministic ordering
   - Sort by evidence line, then decl_kind, then decl_name.

7) Ledger output shape (minimal)
   - file_header: profile/scope/domain/module/id_prefix
   - declarations: anchor_kind, rel_id, canon_id, evidence refs
   - diagnostics + diagnostic_details

Useful diagnostics:
- MIG_LEGACY_TAG_UNATTRIBUTABLE
- MIG_RELID_INVALID_FORMAT
- MIG_DUPLICATE_RELID
- MIG_EVIDENCE_EMPTY / MIG_EVIDENCE_TOKEN_NONCANON
