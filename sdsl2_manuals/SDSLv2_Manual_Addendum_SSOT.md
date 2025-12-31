# SDSL v2 Addendum SSOT (L0/L1/L2)

Status:
- Applies only when repository policy enables it.
- Does not change SDSLv2_Manual.md grammar or rules.

## Authority and Precedence
- SDSLv2_Manual.md is the SSOT for syntax/semantics.
- This addendum adds authoring/CI restrictions only.
- Manual violations remain handled by the core gates.

## Stage Declaration
- @File.stage is the primary stage signal.
- Allowed values: "L0", "L1", "L2".
- If omitted, default is L2.
- Stage rules apply to topology profile by default.
- Contract profile should omit stage unless policy allows it.

## Intent Layer (@EdgeIntent)
- Topology profile only. AnnotationOnly. Not Graph Facts.
- Required keys: id, from, to (refs are @Node).
- Optional keys: direction, channel, note, owner, contract_hint.
- Forbidden keys: contract_refs, contract.
- contract_hint is free text and MUST NOT include CONTRACT.* tokens.

## Placeholder Vocabulary
- None: missing value (null literal).
- TBD: planned, undecided (Ident).
- Opaque: intentionally abstracted (Ident).
- Placeholders are forbidden in SDSL statements.
- Placeholders are allowed only in Context Pack outputs.

## Rule Catalog (Defaults)
- ADD_STAGE_INVALID: @File.stage not in {L0,L1,L2} -> FAIL.
- ADD_STAGE_IN_CONTRACT_PROFILE: @File.stage in contract -> FAIL (unless policy allows).
- ADD_EDGEINTENT_PROFILE: @EdgeIntent in non-topology -> FAIL.
- ADD_EDGEINTENT_KEYS: @EdgeIntent missing id/from/to -> FAIL.
- ADD_EDGEINTENT_FORBIDDEN_KEYS: @EdgeIntent has contract_refs/contract -> FAIL.
- ADD_EDGEINTENT_CONTRACT_HINT_TOKENS: contract_hint contains CONTRACT.* -> FAIL.
- ADD_EDGEINTENT_UNKNOWN_KEYS: unknown keys -> FAIL (policy may downgrade).
- ADD_L0_EDGE_FORBIDDEN: @Edge or @Flow.edges in L0 -> FAIL.
- ADD_L0_TERMINAL_FORBIDDEN: @Terminal in L0 -> FAIL (unless policy allows).
- ADD_L1_EDGEINTENT_FORBIDDEN: @EdgeIntent in L1 -> DIAG (upgradeable).
- ADD_L2_EDGEINTENT_FORBIDDEN: @EdgeIntent in L2 -> FAIL.
- ADD_PLACEHOLDER_IN_SDSL: None/TBD/Opaque in SDSL -> FAIL.
- ADD_L0_KIND_FORBIDDEN: kind not in {File,Node,EdgeIntent} in L0 -> FAIL.
- ADD_EDGEINTENT_ID_INVALID: id not RELID -> FAIL.
- ADD_EDGEINTENT_FROM_TO_INVALID: from/to not @Node ref -> FAIL.
- ADD_EDGEINTENT_DIRECTION_INVALID: direction not in closed set -> FAIL.
- ADD_STAGE_BELOW_REPO_MIN: stage below repo_min_stage -> FAIL.
- ADD_MIXED_STAGES_FORBIDDEN: mixed stages when allow_mixed_stages=false -> FAIL.
- ADD_METADATA_DUPLICATE_KEY: duplicate metadata key -> FAIL.
- ADD_FILE_HEADER_UNREADABLE: addendum could not read @File header -> DIAG.
- ADD_POLICY_NOT_FOUND: policy file missing -> DIAG.
- ADD_POLICY_MULTIPLE_FOUND: multiple policy files found -> FAIL.
- ADD_POLICY_PARSE_FAILED: policy file parse error -> FAIL.
- ADD_POLICY_SCHEMA_INVALID: policy root not an object -> FAIL.

## Repository Policy (Out of Band)
- policy_path from CI is authoritative.
- If policy_path is not set, use .sdsl/policy.yaml.
- If multiple policy files are found -> FAIL.
- If no policy file is found, addendum.enabled is treated as false.
- Always emit ADD_POLICY_NOT_FOUND as DIAG when policy is missing.

Suggested defaults:
```yaml
addendum:
  enabled: true
stage_policy:
  allow_l0_terminal: false
  l0_kind_mode: fail
  l1_edgeintent_mode: diag
  edgeintent_unknown_keys: fail
  allow_mixed_stages: true
  repo_min_stage: "L1"
  allow_contract_stage: false
manual_policy:
  manual_mode: strict
  manual_lint_level: error
```

## Diagnostics
- Addendum diagnostics use Diagnostic(code/message/expected/got/path).
- Code prefix: ADD_*
- Separate catalog from core errors to avoid spec conflicts.

## CI Integration (Out of Band)
- Order: spec locks -> error catalog -> Gate A -> addendum checks -> determinism -> Gate B -> diff gate.
- No auto-fix in CI.
