# SDSL v2 Addendum Tooling Plan (L0/L1/L2)

## Scope

Out-of-band CI/lint policy for Addendum Core + L0/L1/L2.
No changes to SDSLv2_Manual.md or grammar.
Addendum rules apply only when enabled by repository policy.

## Inputs

- draft/SDSLv2_Manual_Addendum_Core.md
- draft/SDSLv2_Manual_Addendum_L0.md
- draft/SDSLv2_Manual_Addendum_L1.md
- draft/SDSLv2_Manual_Addendum_L2.md
- SDSLv2_Manual.md (manual rules)

## Outputs

1) Rule catalog with default actions (FAIL/DIAG/IGNORE)
2) Repository policy config (out-of-band)
3) Lint checks aligned to catalog
4) Minimal fixture set (L0/L1/L2 + Context Pack)

## Rule Catalog (Defaults)

- STAGE_INVALID (all): @File.stage not in {L0,L1,L2} -> FAIL.
- MANUAL_VIOLATION (all): any Manual rule violation -> FAIL or DIAG per
  manual_lint_level.
- STAGE_IN_CONTRACT_PROFILE (contract): @File.stage present -> FAIL (unless
  policy allows).

- EDGEINTENT_PROFILE (all): @EdgeIntent in non-topology profile -> FAIL.
- EDGEINTENT_KEYS (all): @EdgeIntent missing id/from/to -> FAIL.
- EDGEINTENT_FORBIDDEN_KEYS (all): @EdgeIntent has contract_refs or contract -> FAIL.
- EDGEINTENT_CONTRACT_HINT_TOKENS (all): contract_hint has "CONTRACT.*" or
  placeholders -> FAIL.
- EDGEINTENT_UNKNOWN_KEYS (all): keys outside allowed set -> FAIL (upgradeable).

- L0_EDGE_FORBIDDEN (L0): @Edge or @Flow.edges -> FAIL.
- L0_TERMINAL_FORBIDDEN (L0): @Terminal -> FAIL (unless repo policy allows).
- L1_EDGEINTENT_FORBIDDEN (L1): @EdgeIntent -> DIAG (upgradeable).
- L2_EDGEINTENT_FORBIDDEN (L2): @EdgeIntent -> FAIL.

- PLACEHOLDER_IN_SDSL (all): None/TBD/Opaque in SDSL statements -> FAIL.
  Trigger only when AST Value is Null or Ident with exact token; do not match
  inside strings/comments/raw block bodies.
  This addendum introduces no allowed placeholder placements in SDSL, therefore
  any AST-level placeholder occurrence in parsed SDSL is a violation.

## Repository Policy (Out of Band)

Suggested config keys (non-normative):

```yaml
addendum:
  enabled: true
stage_policy:
  allow_l0_terminal: false
  l1_edgeintent_mode: diag   # diag | fail
  edgeintent_unknown_keys: fail   # diag | fail
  allow_mixed_stages: true        # true | false
  repo_min_stage: "L1"            # L0 | L1 | L2
  allow_contract_stage: false     # false | true
migration_window:
  l1_edgeintent_deadline: "2025-12-31"
manual_policy:
  manual_mode: strict             # strict | migration
  manual_lint_level: error        # error | warn
  appendix_m_enabled: false       # false | true

repo_min_stage meaning:

- For topology profile files, @File.stage MUST be >= repo_min_stage.
- If allow_mixed_stages is true, this check applies only to the target subset
  selected by CI (git diff base..head; changed files).
manual_policy meaning:

- strict: apply all Manual rules as errors.
- migration: allow legacy Appendix M rules where applicable.
- manual_lint_level: error -> FAIL, warn -> DIAG.

policy discovery (normative):

- policy_path from CI config is the single authoritative location.
- If policy_path is not set, use .sdsl/policy.yaml.
- If multiple policy files are found -> FAIL.
- If no policy file is found, treat addendum.enabled as false.
```

## Context Pack Tests (Minimal)

- L0_ok: @Node + @EdgeIntent only.
- L0_fail_edge: @Edge present -> FAIL.
- L0_fail_terminal: @Terminal present -> FAIL (unless allowed).
- L1_ok: @Edge with contract_refs.
- L1_diag_edgeintent: @EdgeIntent present -> DIAG/FAIL by policy.
- L2_fail_placeholder: None/TBD/Opaque in SDSL -> FAIL.
- Context Pack golden: normalized output order + direction quoting.

## Implementation Steps (Minimal)

1) Implement rule checks in lint layer.
2) Add policy file reader (out-of-band).
3) Wire CI to fail on FAIL rules; report DIAG.
4) Add fixtures + golden file for Context Pack.
