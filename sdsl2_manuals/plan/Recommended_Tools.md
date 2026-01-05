# LLM-Centric Toolchain (L0 -> L1 -> L2)

Scope: Recommend a minimal toolchain to raise resolution from draft to L2 with guardrails.
Non-scope: Tool implementation; full policy specification.

Definitions
- Proposer: Draft-focused agent.
- Decider: Decision proposal agent.
- Promoter: Diff-only promotion agent.

Rules
1) Role Separation (MUST)
- Proposer writes only drafts/, ledger/, OUTPUT/ (Derived). MUST NOT modify sdsl2/ or decisions/.
- Decider writes proposals for decisions/edges.yaml and evidence coverage. MUST NOT modify SSOT.
- Promoter outputs unified diff only. MUST NOT auto-apply. MUST NOT perform meaning-changing migrations.

2) Human Approval Gates (MUST)
- Review set is fixed: Context Pack/Bundle Doc, Gate Summary, unified diff.
- Human action is approve or send back only.
- Gate Summary MUST include readiness/evidence-coverage status per decision_id.
- Gate Summary MUST include drift-check status.
- ledger/ is non-SSOT derived input/output; it MUST NOT be a Promote input.

3) Stage Workflows (SHOULD)
L0
- LLM: ledger, Draft, edgeintent diff from Intent YAML for non-SSOT preview.
- Tools: context-pack-gen, ledger-builder, draft-builder, draft-lint, edgeintent-diff, manual+addendum lint (sdsl2/ only).
- Human: diff approval.

L1
- LLM: Evidence, decisions draft, readiness loop, promote diff.
- Tools: evidence-builder, evidence-lint, decisions-builder, readiness-check, drift-check, promote-diff, token-registry-check.
- Human: decisions approval covers EdgeDecision tuple (id,from,to,direction,contract_refs) and evidence readiness; promote diff approval.

L2
- LLM: contract SSOT boundary spec, invariants/authz, OUTPUT skeletons, maintain exceptions/freshness.
- Tools: contract-sdsl-lint, context-pack-gen, bundle-doc-gen, determinism-check, freshness-check (if persisted), exception-lint, implementation-skeleton-gen, conformance-check.
- Human: exception approval and contract boundary confirmation.

4) Guardrails (MUST)
- FS isolation: Proposer writes only drafts/, ledger/, OUTPUT/; Decider MAY write decisions/edges.yaml and decisions/evidence.yaml; sdsl2/ is diff-only.
- decisions/* MUST be written only by Decider; builder tools MUST run under Decider.
- decisions/edges.yaml and decisions/evidence.yaml MUST be updated and approved as a single unit.
- Diff-only: SSOT changes MUST be unified diff and applied by humans or approved CI; decisions changes MUST be gated and approved per repo policy.
- Gate-driven state: FAIL -> fix loop; DIAG -> policy decides approve or continue; PASS -> next stage.

5) Minimum Required Tools (MUST)
- context-pack-gen / bundle-doc-gen
- drift-check
- edgeintent-diff

6) Tool Glossary (SHOULD)
- context-pack-gen: Generates Context Pack from SSOT Graph Facts; output for LLM input.
- bundle-doc-gen: Appends Supplementary Sections to Context Pack; output is Bundle Doc.
- ledger-builder: Structures free text into ledger/ (non-SSOT notes/questions).
- draft-builder: Converts inputs into Draft schema under drafts/.
- draft-lint: Validates Draft schema and constraints.
- edgeintent-diff: Produces unified diff to OUTPUT/intent_preview.sdsl2; no auto-apply.
- manual+addendum lint: Validates Manual/Addendum conformance for SSOT changes.
- evidence-builder: Maps decisions to Evidence items in decisions/evidence.yaml.
- evidence-lint: Validates Evidence schema, locator/hash, and coverage.
- decisions-builder: Generates EdgeDecision proposals in decisions/edges.yaml.
- readiness-check: Enforces Promotion Readiness (decisions + evidence).
- drift-check: Compares SSOT and decisions for drift/mismatch.
- promote-diff: Produces unified diff for @EdgeIntent -> @Edge promotion.
- token-registry-check: Validates SSOT.* and CONTRACT.* tokens against registries.
- contract-sdsl-lint: Validates contract profile SDSL for Manual compliance.
- determinism-check: Re-runs tools and compares outputs for identical results.
- freshness-check: Verifies persisted outputs match current inputs.
- exception-lint: Validates exception schema, expiry, and caps.
- implementation-skeleton-gen: Generates OUTPUT skeletons from contracts/invariants.
- conformance-check: Checks implementation against contract/invariants.
