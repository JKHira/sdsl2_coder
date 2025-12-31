# Addendum Adoption v0.1 (L0/L1/L2)

Goal:
- Adopt the addendum as an out-of-band lint/CI policy without changing the core manual.
- Keep rules deterministic and repo-policy driven.

## Scope (Decision)
- Apply addendum rules only when repository policy enables them.
- Topology profile is the primary target for stage rules.
- Contract profile keeps stage disabled by default.
- @File.stage is the primary stage signal (no SDSL tail tags).

## Core Rules (Summary)
- @File.stage allowed values: L0, L1, L2. Default is L2 if omitted.
- L0: @Node and @EdgeIntent only; @Edge/@Flow.edges forbidden; @Terminal forbidden by default.
- L1: @Edge/@Flow.edges allowed; @EdgeIntent forbidden (DIAG -> FAIL by policy).
- L2: full manual; @EdgeIntent forbidden; placeholders forbidden.
- @EdgeIntent: topology profile only, required keys (id/from/to), no contract_refs/contract.
- Placeholders (None/TBD/Opaque) are forbidden in SDSL statements (allowed only in Context Pack output).

## Policy (Out-of-Band)
- Use .sdsl/policy.yaml unless CI overrides policy_path.
- If no policy file exists, addendum checks are disabled.
  Emit ADD_POLICY_NOT_FOUND as DIAG to avoid silent no-ops.

Recommended defaults:
```yaml
addendum:
  enabled: true
stage_policy:
  allow_l0_terminal: false
  l1_edgeintent_mode: diag
  edgeintent_unknown_keys: fail
  allow_mixed_stages: true
  repo_min_stage: "L1"
  allow_contract_stage: false
manual_policy:
  manual_mode: strict
  manual_lint_level: error
```

## Integration (Execution)
- Implement addendum checks as a separate CI step (out-of-band).
- Run order: spec locks -> error catalog -> Gate A -> addendum checks -> determinism -> Gate B -> diff gate.
- Add fixtures for L0/L1/L2 and Context Pack outputs.
- SSOT is consolidated in `sdsl2_manuals/SDSLv2_Manual_Addendum_SSOT.md`.

## DoD
- Policy file exists and is referenced by CI.
- Addendum checks enforce stage/edgeintent/placeholder rules.
- Fixtures/goldens are added and pass in CI.
