# Context for Intent‑YAML Proposal (for Spec Author)

## Where We Are Now
We built an L0 toolchain that is intentionally conservative:
- **SSOT** lives in `sdsl2/` and must remain read‑only (diff‑only changes).
- **LLM outputs** are confined to `drafts/`, `ledger/`, and `OUTPUT/` under a per‑project root.
- **Gate A (Manual)** rejects any syntax not allowed in topology, and is always FAIL on violations.
- **Addendum** defines L0/L1/L2 staging rules and placeholder restrictions.

We can already run the L0 loop:
1) Build a topology ledger (v0.1) from explicit inputs.
2) Generate `.sdsl2` via the Builder.
3) Normalize a Draft (`draft_builder`).
4) Produce unified diff for `@EdgeIntent` (`edgeintent_diff`).

## The Issue We Hit
We attempted to apply the `@EdgeIntent` diff to the topology SSOT file and run Gate A.
**Gate A fails** because `@EdgeIntent` is not an allowed kind in topology profile by the Manual.
This is expected: Gate A enforces Manual rules strictly and cannot be “temporarily relaxed” without violating SSOT authority.

So the current L0 workflow is blocked if we try to store Intent inside SSOT.

## The Proposed Resolution
**Move Intent to a non‑SSOT YAML file** instead of embedding it in `.sdsl2`.
Example filenames:
- `drafts/edgeintent.yaml`
- `drafts/intent.yaml`

Why this is better:
- No new parser: YAML is already used for Drafts, Evidence, Decisions.
- Full alignment with:
  - Addendum (L0/L1/L2)
  - Ambiguity Routing (A1–A5)
  - Draft Spec (intent is non‑SSOT)
- Clear separation: **LLM writes intent**, humans approve, SSOT stays clean.
- Keeps “diff‑only” and “no inference” principles intact.

Downside:
- Intent is not inside SDSL files; but this is safer and consistent with the current authority model.

## What We Need Next
We need a **formal spec decision** for this new Intent YAML artifact:
1) **File name and location** (default `drafts/edgeintent.yaml`).
2) **Schema** (likely reuse or subset of Draft Spec’s `edge_intents_proposed`).
3) **Lint rules** (no placeholders, RELID validation, canonical sort order).
4) **Tooling changes**:
   - `edgeintent_diff` should read intent YAML and output unified diff, but not apply it.
   - Promote should only consume **Decisions**, not Intent YAML (intent remains non‑SSOT).

## Why This Matters
If we keep Intent inside `.sdsl2`:
- Gate A will always fail.
- SSOT authority is violated.
- The “LLM writes only non‑SSOT” boundary collapses.

The YAML‑intent approach preserves authority boundaries and keeps the L0/L1/L2 pipeline deterministic and safe.
