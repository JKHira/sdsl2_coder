Scope: Define the ideal pre-implementation map state that lets an LLM implement without ambiguity.
Non-scope: Editing existing SDSL specs or changing tool behavior.

Definitions
- Code Plan Map (CPM): The complete, deterministic map of Topology + Contract + SSOT kernel + gate outputs required for implementation.
- Token Save Format (TSF): A line-oriented JSON format that persists CPM elements as tokens.
- Token: A single CPM unit (node, edge, contract decl, rule, kernel definition, runtime rule, gate check, artifact).
- Ready State: The state where CPM tokens are complete and L2 gates can pass without exceptions.

Rules
1) Token Save Format (TSF v1)
- TSF MUST be JSON Lines (one JSON object per line).
- Each token MUST include these keys: token_id, kind, scope, source, status.
- token_id MUST be unique and stable across runs.
- kind MUST be one of:
  - topology.node
  - topology.edge
  - contract.decl
  - contract.rule
  - ssot.definition
  - ssot.runtime
  - gate.check
  - artifact.output
- scope MUST be a stable path or ID that a tool can resolve (e.g., sdsl2/topology/*.sdsl2 or CONTRACT.*).
- source MUST reference the authoritative file path.
- status MUST be one of: defined, missing, invalid, pending.
- Optional keys MAY include: refs, requirements, diagnostics, notes, owner.

2) Topology completeness
- Every topology.node MUST define: id, kind, summary, io.
- Every topology.edge MUST define: from, to, direction, channel, contract_refs.
- Every topology.edge MUST reference only existing topology.node ids.
- Every topology.edge MUST reference only CONTRACT.* tokens.

3) Contract completeness
- Every contract.decl MUST be bound to a unique rel_id.
- Every contract.rule MUST have bind and MUST resolve to an existing decl.
- For each CONTRACT.* referenced by topology.edge, a contract.decl MUST exist.

4) SSOT kernel completeness
- ssot.definition MUST define token_rules and distribution_boundary.
- ssot.runtime MUST validate tokens using the same token_rules.
- artifact.output MUST include ssot_definitions.json and ssot_registry.json under OUTPUT/ssot/.

5) Gate completeness
- gate.check tokens MUST exist for L0/L1/L2 critical checks and MUST align to the toolchain:
  - L0: topology_resolution_lint, resolution_gap_report
  - L1: contract_resolution_lint, contract_rule_coverage_check, contract_error_model_lint
  - L2: ssot_kernel_coverage_check, ssot_kernel_lint, ssot_registry_consistency_check
- gate.check status MUST be defined before Ready State is declared.

6) Ready State (L2)
- All topology.node and topology.edge tokens MUST be defined with status=defined.
- All contract.decl and contract.rule tokens MUST be defined with status=defined.
- All ssot.definition and ssot.runtime tokens MUST be defined with status=defined.
- All gate.check tokens MUST be defined with status=defined.
- artifact.output tokens MUST be defined for all required outputs.

Examples (Non-normative)
```jsonl
{"token_id":"TP.NODE.ORDER_API","kind":"topology.node","scope":"@Node.ORDER_API","source":"sdsl2/topology/P0_T_ORDER_FLOW_L0.sdsl2","status":"defined"}
{"token_id":"TP.EDGE.ORDER_TO_INVENTORY","kind":"topology.edge","scope":"@Edge.ORDER_TO_INVENTORY","source":"sdsl2/topology/P0_T_ORDER_FLOW_L1.sdsl2","status":"defined","refs":["CONTRACT.ReserveInventory"]}
{"token_id":"CT.DECL.RESERVE_INVENTORY","kind":"contract.decl","scope":"CONTRACT.ReserveInventory","source":"sdsl2/contract/P0_C_ORDER_FLOW.sdsl2","status":"defined"}
{"token_id":"SSOT.DEF.REGISTRY","kind":"ssot.definition","scope":"OUTPUT/ssot/ssot_definitions.json","source":"ssot_kernel_builder/ssot_definitions.ts","status":"defined"}
```
