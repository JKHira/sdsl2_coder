# Gate Responsibility Map Notes (Draft)

Scope:
- Summarize current gate responsibilities and tool coverage for L0/L1/L2.
- Record missing gate tooling required by SDSL2_CI_Gates_Spec.md.

Non-scope:
- Tool implementation details.
- Any changes to docs, policy, or CI.

Definitions:
- Manual Gate: SDSLv2_Manual.md validation (SDSL2_CI_Gates_Spec.md).
- Addendum Gate: Addendum rules with policy severity (SDSL2_CI_Gates_Spec.md).
- Operational Gate: Draft/Evidence/Intent/Exception checks (SDSL2_CI_Gates_Spec.md).
- Drift Gate: SSOT vs decisions mismatch (SDSL2_CI_Gates_Spec.md).
- Determinism/Freshness Gate: Deterministic outputs and persisted output freshness.
- SSOT: sdsl2/** only.
- Explicit Inputs: decisions/** and policy/** where applicable.

Rules:
- Gate order MUST follow SDSL2_CI_Gates_Spec.md:
  - Manual Gate -> Addendum Gate -> Operational Gate -> Drift Gate -> Determinism/Freshness Gate.
- Manual Gate MUST be enforced by `scripts/gate_a_check.py`.
- Addendum Gate MUST be enforced by `scripts/addendum_check.py` (policy-based severity).
- Operational Gate MUST include the checks listed in SDSL2_CI_Gates_Spec.md.
- Drift Gate MUST compare SSOT vs decisions using SDSL2_Decisions_Spec.md scope rules.
- Determinism/Freshness Gate MUST validate persisted outputs when present.

Gate -> Tool Mapping (Current Repo):
- Manual Gate:
  - `scripts/gate_a_check.py`
  - Wrapper: `L0_builder/manual_addendum_lint.py` (runs Gate A then Addendum).
- Addendum Gate:
  - `scripts/addendum_check.py`
  - Wrapper: `L0_builder/manual_addendum_lint.py`
- Operational Gate (implemented):
  - DRAFT-SCHEMA:
    - `L0_builder/draft_lint.py` (drafts/*.yaml)
    - Intent lint is embedded in `L0_builder/edgeintent_diff.py` via `intent_schema.normalize_intent`
  - EVIDENCE-COVERAGE:
    - `L1_builder/evidence_lint.py` (schema + locator + content_hash + coverage)
    - `L1_builder/readiness_check.py` (contract_ref coverage by decision_id)
  - READINESS-CHECK:
    - `L1_builder/readiness_check.py`
  - L2-EXCEPTION-CHECK:
    - `L2_builder/exception_lint.py` (requires --today)
  - DETERMINISM (tool outputs only):
    - `scripts/determinism_check.py` (manifest-based; repo tooling)
- Operational Gate (missing tools):
  - NO-SSOT-PROMOTION: no tool found (planned).
  - TOKEN-REGISTRY: no tool found (planned).
  - SCHEMA-MIGRATION: no tool found (planned).
  - EVIDENCE-REPAIR: no tool found (planned).
- Drift Gate:
  - No drift check tool found (planned).
- Determinism/Freshness Gate:
  - `scripts/determinism_check.py` (determinism for tool outputs)
  - `L2_builder/freshness_check.py` (bundle_doc freshness)
  - `L2_builder/conformance_check.py` (implementation_skeleton vs contract SSOT)

Repo-Specific Gates (not in SDSL2_CI_Gates_Spec.md):
- `scripts/gate_b_check.py` (semantic lint; token placement and binding rules)
- `scripts/diff_gate.py` (write allowlist; final safety gate)
- `scripts/oi_run_v0_1.py` (current orchestrator: spec locks -> error catalog -> Gate A -> determinism -> Gate B -> diff gate)

Non-normative Example:
- L1 CI order (target):
  - Manual Gate (gate_a_check.py)
  - Addendum Gate (addendum_check.py)
  - Operational Gate (decisions_lint.py + evidence_lint.py + readiness_check.py + DRAFT-SCHEMA checks)
  - Drift Gate (missing tool)
  - Determinism/Freshness Gate (determinism_check.py and freshness_check.py when outputs are persisted)

Sources:
- `sdsl2_manuals/ope_addendum/SDSL2_CI_Gates_Spec.md`
- `sdsl2_manuals/Operatoon_flow.md`
- `coder_planning/tools_doc.md`
- `scripts/gate_a_check.py`
- `scripts/addendum_check.py`
- `scripts/gate_b_check.py`
- `scripts/determinism_check.py`
- `scripts/diff_gate.py`
- `scripts/oi_run_v0_1.py`
- `L0_builder/manual_addendum_lint.py`
- `L0_builder/draft_lint.py`
- `L0_builder/edgeintent_diff.py`
- `L1_builder/decisions_lint.py`
- `L1_builder/evidence_lint.py`
- `L1_builder/readiness_check.py`
- `L2_builder/exception_lint.py`
- `L2_builder/freshness_check.py`
- `L2_builder/conformance_check.py`
