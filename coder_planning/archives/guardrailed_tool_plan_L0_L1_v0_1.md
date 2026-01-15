Scope: Plan guardrailed tools for L0/L1 that remove manual edits in normal operations.
Non-scope: New tools beyond the L0/L1 set in this plan.

Definitions
- Manual Touchpoint: A file authored by hand because no tool exists for it.
- Guardrail: A hard constraint that prevents unsafe writes, path drift, or non-determinism.
- TSF: Token Save Format (JSON Lines, one token per line).
- Token: A single plan record for a tool or touchpoint.

Rules
1) All new tools MUST be diff-only or write only to drafts/ or OUTPUT/.
2) Tools MUST reject symlink paths and paths outside project_root.
3) Tools MUST be deterministic (stable ordering, stable serialization, LF line endings).
4) Tools MUST emit JSON Diagnostics on failure.
5) Tools MUST accept --project-root and resolve relative paths under it.

L0 Manual Touchpoints and Tool Plan
- Touchpoint: Topology node summary/io fields added by hand after ledger->topology.
  - Tool: topology_enricher
  - Input: sdsl2/topology/*.sdsl2
  - Output: unified diff only (no auto-apply)
  - Guardrail: MUST not invent graph facts; only fill summary/io for existing @Node entries.
  - Flexibility: allow per-node overrides via drafts/intent or a CSV/YAML map.
- Touchpoint: drafts/intent template authored by hand.
  - Tool: intent_template_gen
  - Input: sdsl2/topology/*.sdsl2 + target node list
  - Output: drafts/intent/*.yaml (canonical order)
  - Guardrail: MUST not create edges; only intent skeletons.

L1 Manual Touchpoints and Tool Plan
- Touchpoint: decisions/edges.yaml authored by hand.
  - Tool: decisions_from_intent_gen
  - Input: drafts/intent/*.yaml + sdsl2/topology/*.sdsl2
  - Output: decisions/edges.yaml (canonical order)
  - Guardrail: MUST only use explicit intents; no inference or synthesis.
  - Flexibility: allow select-by-scope and allow omit (no edge) entries.
- Touchpoint: decisions/evidence.yaml content_hash filling by hand.
  - Tool: evidence_fill_gen
  - Input: decisions/evidence.yaml + source files
  - Output: diff-only patch that updates content_hash
  - Guardrail: MUST only update content_hash fields; no structural edits.
- Touchpoint: contract skeleton for referenced CONTRACT.* tokens.
  - Tool: contract_scaffold_gen
  - Input: decisions/edges.yaml + contract_resolution_profile.yaml
  - Output: diff-only patch for sdsl2/contract/*.sdsl2
  - Guardrail: MUST only add minimal stubs (Type/Function/Rule) required by profile.

Universal Guardrails
- Output location MUST be OUTPUT/ or drafts/ unless tool is diff-only.
- Tool MUST enforce canonical ordering and forbid placeholders if target schema forbids them.
- Tool MUST record generator_id, source_rev, input_hash in outputs when the target format includes provenance fields.
- Tools that write files MUST provide --dry-run; diff-only tools output to stdout by default.

Implementation Status
- topology_enricher: implemented (diff-only; placeholder overrides rejected).
- intent_template_gen: implemented (drafts/intent output; supports --dry-run).
- decisions_from_intent_gen: implemented (diff-only; provenance.source_link records gen/rev/input).
- evidence_fill_gen: implemented (diff-only; source_rev updates; duplicate key guard).
- contract_scaffold_gen: implemented (diff-only; @DocMeta desc records gen/rev/input).

Metadata Placement Decisions (v0.1)
- decisions: record `gen/rev/input` in `provenance.source_link` as `gen:<id>;rev:<rev>;input:<hash>`.
- evidence: record `gen` in `source_rev` as `<gitrev>|gen:<id>`; `input_hash` remains in top-level.
- contract: record metadata in `@DocMeta.desc` as `gen:<id>;rev:<rev>;input:<hash>`.

Token Save Records (TSF)
{"token_id":"TOOL.TOPOLOGY_ENRICHER","kind":"tool.plan","scope":"L0","source":"coder_planning/guardrailed_tool_plan_L0_L1_v0_1.md","status":"implemented"}
{"token_id":"TOOL.INTENT_TEMPLATE_GEN","kind":"tool.plan","scope":"L0","source":"coder_planning/guardrailed_tool_plan_L0_L1_v0_1.md","status":"implemented"}
{"token_id":"TOOL.DECISIONS_FROM_INTENT_GEN","kind":"tool.plan","scope":"L1","source":"coder_planning/guardrailed_tool_plan_L0_L1_v0_1.md","status":"implemented"}
{"token_id":"TOOL.EVIDENCE_FILL_GEN","kind":"tool.plan","scope":"L1","source":"coder_planning/guardrailed_tool_plan_L0_L1_v0_1.md","status":"implemented"}
{"token_id":"TOOL.CONTRACT_SCAFFOLD_GEN","kind":"tool.plan","scope":"L1","source":"coder_planning/guardrailed_tool_plan_L0_L1_v0_1.md","status":"implemented"}
