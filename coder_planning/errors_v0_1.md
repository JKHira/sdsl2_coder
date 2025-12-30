# Error Codes v0.1 (Candidate)

Format:
- E_<CATEGORY>_<DETAIL>
- Always return: code, message, expected, got, path (JSON Pointer, when applicable).

Path examples:
- /edges/3/contract_refs
- /nodes/0/id

JSON Pointer escaping (RFC 6901):
- "~" -> "~0"
- "/" -> "~1"

## Ledger schema
- E_LEDGER_SCHEMA_INVALID
- E_LEDGER_REQUIRED_FIELD_MISSING
- E_LEDGER_FIELD_TYPE_INVALID
- E_LEDGER_UNKNOWN_FIELD

## Profile / Kind separation
- E_PROFILE_KIND_FORBIDDEN
- E_PROFILE_INVALID

## Binding
- E_RULE_BIND_REQUIRED
- E_BIND_TARGET_NOT_FOUND
- E_DEP_BIND_MUST_EQUAL_FROM

## Token placement
- E_TOKEN_PLACEMENT_VIOLATION
- E_CONTRACT_REFS_INVALID
- E_EDGE_CONTRACT_REFS_EMPTY

## Topology edge rules
- E_EDGE_MISSING_FIELD
- E_EDGE_DIRECTION_INVALID
- E_EDGE_FROM_TO_UNRESOLVED
- E_EDGE_DUPLICATE

## Document structure (Gate C)
- E_FILE_HEADER_MISSING
- E_FILE_HEADER_DUPLICATE
- E_FILE_HEADER_NOT_FIRST
- E_METADATA_OBJECT_INVALID

## ID rules
- E_ID_FORMAT_INVALID
- E_ID_DUPLICATE

## Writer / determinism
- E_OUTPUT_NONDETERMINISTIC

## Notes (v0.1)
- contract_refs error roles:
  - E_TOKEN_PLACEMENT_VIOLATION: wrong field placement
  - E_CONTRACT_REFS_INVALID: not list or non-CONTRACT.* elements
  - E_EDGE_CONTRACT_REFS_EMPTY: empty list
- E_OUTPUT_NONDETERMINISTIC should include fingerprint(expected/got) or ordering_key in details.
