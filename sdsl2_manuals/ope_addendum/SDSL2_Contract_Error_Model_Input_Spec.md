Scope: Define the YAML input for contract_error_model_builder to generate ERROR_CODE and RETRY_POLICY string unions.
Non-scope: Inference, auto-editing SSOT, or non-deterministic generation.

Definitions
- Error Model Input: The YAML file consumed by contract_error_model_builder.
- Target: The contract .sdsl2 file to receive the error model types.
- String Union: A `type` declaration formed only by double-quoted string literals joined by `|`.

Rules
- Top-Level Object
  - `schema_version` MUST be `"1.0"`.
  - `target` MUST be a non-empty string path under `sdsl2/contract/`.
  - `error_code` MUST be an object with `values`.
  - `retry_policy` MUST be an object with `values`.
  - No other top-level keys are allowed.
- `error_code`
  - `values` MUST be a non-empty list of non-empty strings.
  - Items MUST be unique (no duplicates).
  - Items MUST NOT be placeholders (`None`, `TBD`, `Opaque`, case-insensitive).
  - Order MUST be preserved.
- `retry_policy`
  - `values` MUST be a non-empty list of non-empty strings.
  - Items MUST be unique (no duplicates).
  - Items MUST NOT be placeholders (`None`, `TBD`, `Opaque`, case-insensitive).
  - Order MUST be preserved.
- Output Shape (Deterministic)
  - The tool MUST generate `type ERROR_CODE = "..." | "..."` and `type RETRY_POLICY = "..." | "..."`.
  - The tool MUST be diff-only and MUST NOT modify files directly.

Non-normative Example
```yaml
schema_version: "1.0"
target: "sdsl2/contract/P0_C_ORDER_FLOW.sdsl2"
error_code:
  values:
    - "E_1001"
    - "E_1002"
retry_policy:
  values:
    - "NO_RETRY"
    - "RETRY_3"
```
