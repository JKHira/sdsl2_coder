Scope: Enforce Required_Resolution via deterministic tooling across L0/L1/L2 and close gaps by explicit inputs only.
Non-scope: Inference from prose/pseudo-code, auto-editing SSOT, or non-deterministic generation.

Definitions
- Resolution Gap: Missing/invalid fields required by Required_Resolution that prevent implementation-ready use.
- Explicit Input: Human-confirmed YAML/CSV/text that is the only allowed source for graph facts and contracts.
- Gate: A deterministic lint/check step that MUST block or DIAG based on policy.
- Tool Result Envelope: A machine-readable JSON object returned by every tool run.
- Promote: Diff-only projection of decisions into SSOT (no direct edits).

Rules
1) Authority and Inputs
- Graph Facts MUST be derived only from Explicit Input (no inference).
- Contract API/Type/Rule content MUST be derived only from Explicit Input.
- All edits MUST be diff-only outputs + explicit apply step.

2) Required Profiles (Hard Preconditions)
- L0 requires policy/resolution_profile.yaml.
- L1 requires policy/contract_resolution_profile.yaml.
- L2 requires policy/ssot_kernel_profile.yaml and ssot_definitions.json.
- Missing profile/definitions MUST be FAIL with a clear diagnostic.

3) Stage Gates (Ordering is Mandatory)
- L0 Gate Order: topology_resolution_lint -> resolution_gap_report -> manual_addendum_lint.
- L1 Gate Order: intent_lint -> decisions_lint -> evidence_lint -> readiness_check -> contract_* lints -> token_registry_check -> drift_check.
- L2 Gate Order (pre-publish): ssot_kernel_coverage_check -> context_pack_gen -> bundle_doc_gen -> implementation_skeleton_gen -> conformance_check -> freshness_check.
- L2 Gate Order (publish): l2_gate_runner --publish (includes ssot_kernel_source_lint, registry consistency, conformance, freshness).

4) Gap Closure Loop (Repeat Until Zero Gaps)
- If any gate outputs a Resolution Gap, the next step MUST be the specific tool that can fill that gap.
- Gaps MUST be closed by adding Explicit Input, not by direct edits to derived outputs.
- The loop ends only when all gates PASS (or DIAG where policy allows) and Required_Resolution fields are present.

5) Tooling Requirements to Reach Required_Resolution
- topology_channel_builder: Explicit Input -> Edge channel/category in decisions, then promote to topology.
- contract_api_builder: Explicit Input -> @Interface/@Function + request/response Type skeletons.
- contract_error_model_builder: Explicit Input -> ERROR_CODE / RETRY_POLICY string unions.
- contract_rule_builder: Explicit Input -> @Rule with bind and optional contract coverage.
- resolution_controller (optional): Orchestrates tool order and stops on hard gaps.

6) Interactive Tool Result Envelope (MUST)
- Every tool MUST return a JSON object to stdout (single line) with:
  - status: ok|diag|fail
  - tool: <name>
  - stage: L0|L1|L2
  - inputs: [paths]
  - outputs: [paths]
  - diff_paths: [paths]
  - diagnostics: {count:int, codes:[...]}
  - gaps: {missing:[...], invalid:[...]} (empty if none)
  - next_actions: ["tool:arg1=...", ...]
- Tools MUST include a concise human-readable summary in stderr, but stdout MUST be JSON-only.

7) Enforcement Points (Where Current Flow Leaks)
- topology_resolution_lint MUST be included in L1/L2 gates to enforce channel/category.
- contract_resolution_profile MUST be present in project_root to enforce rules and error model.
- ssot_kernel_source_lint MUST point to valid definitions/runtime paths; publish gate MUST fail otherwise.

8) Determinism
- All generators MUST compute input_hash from the same declared input set.
- Outputs MUST be stable (sorting, LF, no time-dependent fields unless explicitly in provenance).

Non-normative Example
Tool Result Envelope:
{
  "status":"diag",
  "tool":"topology_channel_builder",
  "stage":"L1",
  "inputs":["inputs/edge_channels.yaml"],
  "outputs":["OUTPUT/edge_channel.patch"],
  "diff_paths":["OUTPUT/edge_channel.patch"],
  "diagnostics":{"count":1,"codes":["E_CHANNEL_MISSING"]},
  "gaps":{"missing":["channel"],"invalid":[]},
  "next_actions":["tool:edge_channel_builder --input inputs/edge_channels.yaml"]
}
