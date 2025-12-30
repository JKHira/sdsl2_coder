# Gate B1/B2 Core (Canonicalization + Token/Binding Checks)

Gate B1 (Canonical normalization):
- Quotes: convert simple single-quoted strings -> double-quoted.
- Literals: true/false/null -> T/F/None (only when in value positions).
- Types:
  - List[T] / list[T] / [T] -> T[]
  - Dict[K,V] / Map[K,V] -> d[K,V]
  - Set[T] -> set[T]
  - Apply in type spans after ":" or "->", and in "type X = ..." RHS.

Gate B2 (Binding + token placement):
- Detect profile from @File.profile (contract/topology).
- Parse annotation groups and decl heads; build target map from @Kind { id:"RELID" }.
- Token placement:
  - CONTRACT.* tokens allowed only in "contract" (contract profile) or "contract_refs" (topology).
  - SSOT.* tokens allowed only in "ssot".
  - @Dep.to can accept CONTRACT.* in contract profile.
- Detached annotations:
  - If references exist and no bind -> REQ_DETACHED_BIND_MISSING.
  - If bind points to unknown target -> REQ_DETACHED_BIND_TARGET_NOT_FOUND.
  - Multi-target bind unsupported -> REQ_MULTI_TARGET_RULE_UNSUPPORTED.

Output:
- Aggregated diagnostics YAML for batch runs.
- No inference; no mutation except B1 normalization.
