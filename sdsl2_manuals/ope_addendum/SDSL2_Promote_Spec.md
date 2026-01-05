# SDSL2 Promote Specification

Scope: Define deterministic Promote behavior and patch output.
Non-scope: Grammar/semantics changes; auto-apply.

## Definitions
- Promote: Tool step that upgrades Intent to Graph Facts using Explicit Inputs.
- Explicit Inputs: decisions/ files defined in SDSL2_Decisions_Spec.md.
- Patch: Unified diff output (no auto-apply).

## Rules
- Promote MUST use Explicit Inputs only; no inference.
- Output MUST be deterministic unified diff; no auto-apply in CI.
- Preserve formatting/comments; no reformatting; only new statements follow canonical style.
- Promote MUST emit @Edge only; @Flow/@Flow.edges are forbidden (see SDSL2_Operational_Addendum_Spec.md). If target file contains @Flow/@Flow.edges, FAIL.
- New @Edge MUST be canonical multi-line with canonical key order and trailing commas (Manual 7.x).
- If an EdgeDecision matches an existing @Edge with the same (from,to,direction,contract_refs), Promote is a no-op for that item.
- Otherwise, Promote MUST insert a new @Edge for that decision.
- Promote MUST NOT read Intent YAML; only decisions/ are inputs.
- Topology SSOT MUST NOT contain @EdgeIntent in this repository; if present, Promote MUST FAIL.
- New @Edge entries MUST be inserted into the @Edge run (contiguous @Edge statements) sorted lexically by id.
- If no @Edge run exists, insert after the last @Node and before the next non-@Node/@Edge statement (or at end of file).
- contract_refs MUST be emitted exactly as provided (Decisions spec requires sorted and de-duplicated).
- If @File.stage is "L0" and any @Edge is added, Promote MUST update @File.stage to "L1".
- If @File.stage is "L1" or "L2", Promote MUST NOT change stage.
- Conflicts (duplicate id, mismatched existing edge, or @Flow/@Flow.edges present) MUST be FAIL.
- Mismatch is defined as same id with different from/to/direction/contract_refs.
