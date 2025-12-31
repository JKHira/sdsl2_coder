# Builder/Writer API v0.1 (Candidate)

Scope:
- Topology is ledger-only SSOT.
- Flow/Terminal are deferred to v0.2.
- channel/topic are deferred to v0.2.
- @Rule requires bind in all cases.
- title/desc allowed but never synthesized.

## Core Types

RelId:
- Regex: ^[A-Z][A-Z0-9_]{2,63}$

InternalRef:
- type: { kind: str, rel_id: str, absolute: bool = false }
- encoding: "@Kind.RELID"
- raw strings are rejected; use parse_internal_ref(...)
- kind must be a v0.1 Closed Set kind (File, DocMeta, Structure, Interface, Function, Const, Type, Dep, Rule, Node, Edge).

ContractRef:
- type: { token: str } where token matches ^CONTRACT\.[A-Za-z0-9_.-]+$

SSOTRef:
- type: { token: str } where token matches ^SSOT\.[A-Za-z0-9_.-]+$

Error payload (required fields):
- code, message, expected, got, path (JSON Pointer)
- JSON Pointer escaping: "~" -> "~0", "/" -> "~1"

## ContractBuilder (profile: contract)

file(id_prefix: str) -> ContractBuilder
- Sets @File { profile:"contract", id_prefix:"..." }

doc_meta(id: str, title: str?, desc: str?, refs: InternalRef[]?, ssot: SSOTRef[]?)

structure(id: str, decl: str, title: str?, desc: str?, refs: InternalRef[]?, contract: ContractRef[]?, ssot: SSOTRef[]?, bind: InternalRef?)
interface(id: str, decl: str, ...)
function(id: str, decl: str, ...)
const(id: str, decl: str, ...)
type_alias(id: str, decl: str, ...)

rule(id: str, bind: InternalRef, refs: InternalRef[]?, contract: ContractRef[]?, ssot: SSOTRef[]?)
- bind is always required (attached/detachedの区別なし).

dep(from_ref: InternalRef, to: InternalRef | ContractRef, ssot: SSOTRef[]?)
- bind is not accepted from callers; Builder sets bind = from_ref.
- id is computed as "DEP_<from_rel_id>_<hash12>" (sha256(JCS({from,to}))).
- Any hash input in contract uses JCS canonicalization; changes are breaking in v0.1.

Validation (examples):
- E_PROFILE_KIND_FORBIDDEN, E_ID_FORMAT_INVALID, E_RULE_BIND_REQUIRED
- E_TOKEN_PLACEMENT_VIOLATION, E_CONTRACT_REFS_INVALID

## TopologyBuilder (profile: topology)

file(id_prefix: str) -> TopologyBuilder
- Sets @File { profile:"topology", id_prefix:"..." }

node(id: str, kind: str, bind: InternalRef?)

edge(from_id: str, to_id: str, direction: str, contract_refs: ContractRef[])
- id is computed by Builder and always emitted by Writer.
- contract_refs must be non-empty CONTRACT.* list.

rule(id: str, bind: InternalRef, refs: InternalRef[]?, contract: ContractRef[]?, ssot: SSOTRef[]?)

Validation (examples):
- E_EDGE_MISSING_FIELD, E_EDGE_DIRECTION_INVALID, E_EDGE_CONTRACT_REFS_EMPTY
- E_EDGE_FROM_TO_UNRESOLVED, E_EDGE_DUPLICATE

Edge ID (deterministic):
```
pk = {
  from, to, direction,
  contract_refs: sorted+dedup
}
edge_id = "E_" + sha256(canonical_json(pk))[:16].upper()
```
canonical_json:
- RFC 8785 (JCS) compliant.
- contract_refs sorted by Unicode codepoint, then deduped before JCS.

## Writer (deterministic serializer)

write_contract(model) -> str
write_topology(model) -> str
write_to_output(model, path) -> None
- Output must be under OUTPUT/ (enforced by caller).
- Writer does not validate semantics (no inference).
- Writer may assert:
  - model.profile matches write_* target
  - id fields contain no newline characters
  - output ends with newline

Deterministic ordering:
- Contract: @File -> @DocMeta -> Declarations -> @Dep -> @Rule
  - Declarations order: Structure, Interface, Function, Const, Type
  - Within each group: sort by id (lexicographic)
- Topology: @File -> @DocMeta -> @Node -> @Edge -> @Rule
  - @Node sort: id lexicographic
- @Edge sort: (from,to,direction,contract_refs[]) lexicographic (tuple comparison)
  - @Rule sort: id lexicographic

Key order (metadata):
- Common: id, bind, title, desc, refs, contract, ssot
- @Node: id, kind, bind
- @Edge: id, from, to, direction, contract_refs
