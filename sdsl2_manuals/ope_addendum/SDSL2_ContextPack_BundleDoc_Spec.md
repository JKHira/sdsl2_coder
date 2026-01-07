# SDSL2 Context Pack and Bundle Doc Specification

Scope: Define Context Pack and Bundle Doc outputs.
Non-scope: Grammar/semantics changes; tool implementation.

## Definitions
- Authority/precedence: Manual is SSOT; Addendum Core is SSOT for ordering; this spec adds output rules only.
- Context Pack: Deterministic summary from Graph Facts + allowed metadata.
- Bundle Doc: Context Pack plus Supplementary Sections.
- Supplementary Section: Post-Context Pack section with fixed keys.
- Open TODO: Structured missing items in Context Pack.
- Derived Output: Non-authoritative artifact.

## Rules
- Context Pack order and determinism MUST follow SDSLv2_Manual_Addendum_Core.md.
- Context Pack sections MUST be: Header, Nodes, Edges, Contracts, Authz, Invariants, Open TODO.
- Context Pack uses Graph Facts only; Edges MUST come only from @Edge; EdgeIntent ids MUST appear only under Open TODO.edge_intents; @EdgeIntent statements MUST NOT appear in Context Pack (see SDSL2_Operational_Addendum_Spec.md).
- Bundle Doc MUST embed the full Context Pack first and unchanged; Supplementary Sections MAY follow only.
- Persisted outputs (if any) MUST be stored only at OUTPUT/context_pack.yaml and OUTPUT/bundle_doc.yaml (closed set).
- Persisted Context Pack MUST include Supplementary: provenance (generator, source_rev, inputs). No other Supplementary sections are allowed in context_pack.yaml.
- Context Pack input_hash MUST be computed from SSOT files only (no Explicit Inputs).
- Bundle Doc provenance input_hash MUST follow the same SSOT-only rule by default; include Explicit Inputs only when explicitly requested by tooling.
- Supplementary Sections MUST use delimiter `---` and heading `Supplementary: <key>`.
- Supplementary Sections MUST be YAML block style; no flow style; no prose.
- Supplementary Section maps MUST use schema key order; strings MUST be double-quoted (Supplementary Sections only).
- Supplementary Section keys (order) are closed: decisions_needed, provenance, diagnostics_summary, links, decision_log.
- Supplementary Sections MUST appear in the above order when present.
- Open TODO MUST be a map; empty lists MUST be `[]`; empty Open TODO MUST be `{}`.
- Open TODO keys (closed): edge_intents, missing_contract_defs, missing_invariants, missing_authz.
- decisions_needed MUST appear only as a Supplementary Section.
- Open TODO value types (closed):
  - edge_intents: list of string ids, sorted.
  - missing_*: None | TBD | Opaque | list of string ids, sorted.
- missing_* list elements MUST be string identifiers only.
- None/TBD/Opaque semantics follow SDSLv2_Manual_Addendum_Core.md; emit as exact double-quoted strings "None", "TBD", "Opaque".
- Unknown Supplementary/Open TODO keys are errors unless policy allows extensions.
- Extension toggles: policy.context_pack.allow_open_todo_extensions, policy.context_pack.allow_supplementary_extensions.

## Context Pack Section Types (Minimal)
- Header keys: target, profile, stage.
  - profile: "topology" | "contract".
  - stage: "L0" | "L1" | "L2".
- Nodes: list of NodeSummary { rel_id, canon_id }; canon_id is string if present else "None".
- Edges: list of EdgeSummary { from, to, direction, channel, contract_refs }.
  - direction is canonical quoted string; channel is None|string; contract_refs is non-empty list of ContractRef tokens.
- Contracts: list of ContractRef tokens.
- Authz/Invariants: list of strings (identifiers or refs).
- Nodes sorted by (canon_id if present else rel_id) and de-duplicated by the same key.
- Edges sorted and de-duplicated per Addendum Core edge sort key.
- Contracts/Authz/Invariants sorted lexically and de-duplicated.

## Supplementary Section Minimal Schemas
- decisions_needed: list of DecisionNeed { id, summary, scope }.
  - scope: topology | contract | ssot | tooling.
  - keys order: id, summary, scope.
- provenance: map { generator, source_rev, inputs } in that order; inputs is list of strings.
- diagnostics_summary: map { errors, diagnostics } in that order; lists of diagnostic codes.
- links: list of Link { label, href } in that order; href is repo-relative path or artifact id.
- decision_log: list of DecisionEntry { id, when, who, summary } in that order; when is YYYY-MM-DD.
