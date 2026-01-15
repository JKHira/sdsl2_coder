Scope: Define the YAML input format for contract rule insertion (contract_rule_builder).
Non-scope: Rule semantics, enforcement logic, or automatic inference.

Definitions
- Rule Input: A YAML file that declares @Rule entries to be added to a target contract file.
- Target: A repo-relative path to a single contract `.sdsl2` file.
- Rule ID: A RELID used as @Rule.id.

Rules
1) File
- The input MUST be valid YAML.
- The input MUST be an object with keys `schema_version`, `target`, `rules`.
- `schema_version` MUST be a non-empty string.
- `target` MUST be a repo-relative path under `sdsl2/contract/`.
- `rules` MUST be a list of Rule objects.

2) Rule Object
- `id` MUST be a RELID.
- `bind` MUST be an InternalRef (`@Kind.RELID`).
- `refs` MAY be omitted; if present, it MUST be a list of InternalRef strings.
- `contract` MAY be omitted; if present, it MUST be a list of `CONTRACT.*` tokens.
- `ssot` MAY be omitted; if present, it MUST be a list of `SSOT.*` tokens.
- `refs`, `contract`, `ssot` SHOULD be sorted and de-duplicated.

3) Determinism
- The same input MUST always produce the same diff output.
- Duplicate Rule IDs are forbidden.

Non-normative Example
```yaml
schema_version: "1.0"
target: "sdsl2/contract/P0_C_ORDER_FLOW.sdsl2"
rules:
  - id: "AUTHZ_API"
    bind: "@Interface.API"
    contract:
      - "CONTRACT.ORDER_SUBMIT"
  - id: "INVARIANT_ORDER_SUBMIT"
    bind: "@Type.ORDER_SUBMIT"
    contract:
      - "CONTRACT.ORDER_SUBMIT"
```
