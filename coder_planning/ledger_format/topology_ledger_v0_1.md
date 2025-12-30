# Topology Ledger Format v0.1

Purpose:
- SSOT input for topology Graph Facts (@Node, @Edge).
- Deterministic Builder input (no inference).

File format:
- YAML or JSON only.
- Top-level object must be a dictionary.

YAML subset (v0.1):
- Spaces-only indentation (2 spaces recommended).
- Block mappings and block sequences only.
- Double-quoted strings or plain scalars; true/false/null, numbers.
- No inline comments, anchors/aliases, multiline strings, or flow-style collections (except empty []/{}).

Required top-level keys:
```
version: topology-ledger-v0.1
schema_revision: 1
file_header:
  profile: topology
  id_prefix: P0_T_EXAMPLE
nodes: []
edges: []
```

Optional top-level keys:
- source: { input_path, evidence_note }
- output: { topology_v2_path }

## Node entry
```
- id: EXECUTOR
  kind: component
  bind: "@Structure.EXECUTOR_IMPL"   # optional
```
Rules:
- id is RELID (uppercase snake).
- kind is a closed set defined by the project (examples: component, service, adapter).
- bind is optional internal ref string.

## Edge entry (required contract_refs)
```
- from: CONTROLLER
  to: EXECUTOR
  direction: req
  contract_refs: ["CONTRACT.SignedControlCommand"]
```
Rules:
- from/to must reference existing Node ids in the same ledger.
- direction is one of: pub, sub, req, rep, rw, call.
- contract_refs must be non-empty list of CONTRACT.* tokens.
- Duplicate edges (same PK) are REQ errors.

Edge PK (for deterministic ID generation):
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

## Validation summary (Builder)
- Missing contract_refs on any edge is REQ.
- Any token outside allowed placement is REQ.
- Unresolved Node refs are REQ.
- Duplicate edges (same PK) are REQ.
- Output order is deterministic (Writer responsibility).

## Scope (v0.1)
- Flow/Terminal are deferred to v0.2.
- channel/topic are deferred to v0.2.
