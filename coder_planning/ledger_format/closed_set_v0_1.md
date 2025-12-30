# Closed Set v0.1 (Reference)

Scope:
- v0.1 is minimal and strict.
- Flow/Terminal are deferred to v0.2.
- channel/topic are deferred to v0.2.

## Allowed KINDS by profile

Contract profile:
- @File
- @DocMeta
- @Structure
- @Interface
- @Function
- @Const
- @Type
- @Dep
- @Rule

Topology profile:
- @File
- @DocMeta
- @Node
- @Edge
- @Rule

Forbidden (v0.1):
- Topology: @Flow, @Terminal
- Contract: @Node, @Edge, @Flow, @Terminal

## Allowed keys by KIND (v0.1)

@File:
- profile (required)
- id_prefix (required)

@DocMeta:
- id (required)
- title (optional)
- desc (optional)
- refs (optional, InternalRefs only)
- ssot (optional, SSOT tokens only)

@Structure / @Interface / @Function / @Const / @Type:
- id (required)
- bind (optional)
- title (optional)
- desc (optional)
- refs (optional, InternalRefs only)
- contract (optional, ContractRef tokens only)
- ssot (optional, SSOT tokens only)

@Dep (contract only):
- id (required)
- bind (required, InternalRef)
- from (required, InternalRef)
- to (required, InternalRef or ContractRef token)
- ssot (optional, SSOT tokens only)
 - bind must equal from (Builder enforces)

@Rule:
- id (required)
- bind (required in all cases)
- refs (optional, InternalRefs only)
- contract (optional, ContractRef tokens only)
- ssot (optional, SSOT tokens only)

@Node (topology only):
- id (required)
- kind (required, closed set)
- bind (optional, InternalRef)

@Edge (topology only):
- id (required, machine-derived)
- from (required, @Node.RELID)
- to (required, @Node.RELID)
- direction (required, one of pub/sub/req/rep/rw/call)
- contract_refs (required, ContractRef tokens only)

## Token placement (SSOT, v0.1)

ContractRef ("CONTRACT.*") allowed fields:
- contract:[...]
- contract_refs:[...]
- @Dep.to

SSOTRef ("SSOT.*") allowed fields:
- ssot:[...]

Forbidden:
- CONTRACT/SSOT tokens in refs or bind.
- contract_refs on @Flow (not in v0.1).
- contract on topology connection units.

## ID rules (v0.1)
- id values are RELID (UPPER_SNAKE_CASE).
- @Node/@Flow ids are human-named (no auto hash).
- @Edge id is machine-derived from PK (in Builder).

## Notes (v0.1)
- title/desc are allowed but must not be synthesized by Builder.
