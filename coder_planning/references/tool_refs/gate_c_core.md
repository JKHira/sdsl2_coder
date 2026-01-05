# Gate C Core (Finalizer + Deterministic Formatting)

Purpose:
- Finalize .sdsl2 with deterministic spacing and validations.
- No inference and no ledger access.

Core checks:
1) File header
   - @File must exist, be unique, and be the first non-comment statement.
2) Profile validation
   - profile in @File must be "contract" or "topology".
3) Token placement
   - CONTRACT.* / SSOT.* only in allowed fields.
   - @Dep.to can accept CONTRACT.* (quoted).
4) Metadata object validity
   - If metadata is complex and not parseable -> REQ_METADATA_OBJECT_INVALID (or MIG in non-strict).
5) Type forms
   - Reject: any, tuple[], d<...>
   - Normalize List/Dict/Set to canonical forms when enabled.
6) @Dep form
   - Required keys: id, bind, from, to.
   - to must be internal ref or quoted CONTRACT token.
   - Duplicates -> REQ_DEP_DUPLICATE.
   - Self-reference -> dropped with MIG.

Deterministic formatting:
- Normalize blank lines (single blank between statements).
- Group annotation blocks and decl bodies into statements.
- Preserve comments, reject inline block comments (REQ).
- Output always ends with newline.

Outputs:
- Finalized .sdsl2 and diagnostics YAML (per file).
