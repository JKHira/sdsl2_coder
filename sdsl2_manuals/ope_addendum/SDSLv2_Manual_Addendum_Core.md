# SDSL v2 Addendum Core: Staged Resolution (L0/L1/L2)

## Status and Scope (Optional Normative)

This addendum applies only to repositories that explicitly adopt it.
It does not change SDSL v2.0 grammar or any rule in SDSLv2_Manual.md.

## Authority and Precedence

- SDSLv2_Manual.md is the SSOT and read-only.
- This addendum may impose additional authoring/CI restrictions for adopting
  repositories, but does not alter the meaning of any Manual construct.
- Add semantics only where the Manual is silent.
- Conflicts must be recorded in Conflicts and resolved before use.

## Definitions

- Stage: L0, L1, L2.
- Intent Layer: planning-only; not Graph Facts.
- Graph Facts: see Manual 9.4.
- Context Pack: normalized subset of C&T for LLM.

## File-Level Stage Declaration

- @File MAY include stage:"L0" | "L1" | "L2".
- If omitted, default is L2.
- For topology profile files, stage omission is always treated as L2 for
  validation (it does not imply L0/L1).
- This addendum is topology-stage oriented. @File.stage MAY appear in any
  profile, but stage-based authoring restrictions apply only to
  profile:"topology" unless explicitly stated.
- For adopting repositories, stage is REQUIRED for topology files validated
  under L0 or L1.
- Contract profile SHOULD omit stage unless a repository policy says otherwise.

## Intent Layer (@EdgeIntent)

- Topology profile only. AnnotationOnly. Not a Graph Fact.
- Required keys: id, from, to (@Node refs).
- Optional keys: direction (canonical), channel (string or repo-defined closed set),
  note (string), owner (string or repo-defined closed set),
  contract_hint (string; non-binding).
- @EdgeIntent MUST NOT include contract_refs or contract.
- contract_hint MUST NOT include "CONTRACT.*" tokens or placeholders.
- contract_hint MUST be free text and MUST NOT be machine-interpreted.
- Promotion to @Edge is manual rewrite only; no inference.

## Placeholder Vocabulary (Closed Set)

- None: null literal = missing value.
- TBD: Ident = planned, undecided.
- Opaque: Ident = intentionally abstracted, not scheduled to fill.

Representation:

- Use exact spellings: None, TBD, Opaque.
- TBD/Opaque MUST be Ident (not String).
- Placeholders MAY appear only in allowed placements.
- Placeholders MUST NOT appear in Manual-constrained fields
  (contract_refs, contract, refs, bind, ssot, @File.id_prefix).

Allowed placements (closed set):

- Context Pack output fields only.

## Gate Classification (General)

- Rules are classified per repository as FAIL/DIAG/IGNORE.
- Any Manual rule violation -> FAIL (all levels).

## Repository Policy (Out of Band)

- This addendum defines no syntax for repository policy.
- Gate classification, migration windows, and exceptions (e.g., allow_l0_terminal:T)
  MUST be declared in CI/lint configuration.

## Context Pack Extraction (Canonical)

- Scope: target component plus 1-2 hop neighbors.
- Hop traversal uses the undirected graph of Graph Facts (from/to), ignoring
  direction.
- Section order (fixed):
  1) Header (target, profile, stage)
  2) Nodes
  3) Edges (Graph Facts only)
  4) Contracts (contract_refs only)
  5) Authz
  6) Invariants
  7) Open TODO
- Edges include: from, to, direction, channel, contract_refs.
- Contracts list: unique contract_refs only (no bodies).
- Completeness: missing required items are emitted as None or TBD in Open TODO.
  None = missing; TBD = planned but undecided.
- EdgeIntent MAY be listed under Open TODO.
- ID normalization: use canonical ids when available; otherwise relative ids.
- Output ordering: stable lexical order by canonical id when present, else
  by rel_id.
- De-duplication: by canonical key (canon_id if present else rel_id).
- Direction is emitted as a canonical quoted string (for example, "req").
- Edges are sorted by (from_id, to_id, direction, channel, joined_contract_refs)
  where *_id uses canon_id if present else rel_id.
- joined_contract_refs is the contract_refs list joined by "|" after lexical sort; tokens MUST NOT contain "|".
- Contracts are sorted lexically by token string.

### Context Pack Minimal Example (Non-normative)

Context Pack
Header:
  target: @Node.CONTROLLER
  profile: topology
  stage: L1
Nodes:
  - rel_id: CONTROLLER, canon_id: P0_T_EXAMPLE_CONTROLLER
  - rel_id: EXECUTOR, canon_id: P0_T_EXAMPLE_EXECUTOR
Edges:
  - from: @Node.CONTROLLER, to: @Node.EXECUTOR, direction: "req",
    channel: None, contract_refs: ["CONTRACT.SignedControlCommand"]
Contracts:
  - "CONTRACT.SignedControlCommand"
Open TODO:
  - missing_invariants: TBD
  - edge_intent: @EdgeIntent { from:@Node.CONTROLLER, to:@Node.LOGGER,
    note:"audit path" }

## Conflicts

- None recorded.

## Common Operational YAML Conventions

Scope: Common conventions for operational YAML artifacts in this repository.
Non-scope: SDSLv2 grammar or semantics.

Definitions
- Operational YAML Artifact: drafts/*.yaml, decisions/edges.yaml, decisions/contracts.yaml,
  decisions/evidence.yaml, policy/exceptions.yaml, .sdsl/policy.yaml, decisions/decision_log.yaml.

Rules
- Operational YAML Artifacts MUST be YAML block style only (no flow style).
- Operational YAML Artifacts MUST be UTF-8 and LF-normalized.
