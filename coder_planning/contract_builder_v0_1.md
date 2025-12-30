# ContractBuilder v0.1 Usage Guide

## 1. Scope / Non-goals
- v0.1 uses Builder -> Writer only. Hand-written SDSL is not supported.
- Contract CLI expansion is deferred to v0.2+.
- Contract ledger input is not part of v0.1 (Builder only).
- Topology generation is separate; do not mix profiles.

## 2. Quickstart
Minimal example:

```python
from sdslv2_builder.contract import ContractBuilder
from sdslv2_builder.contract_writer import write_contract
from sdslv2_builder.refs import parse_internal_ref

b = ContractBuilder()
b.file("P0_C_EXAMPLE")
b.structure("BASIC", decl="struct Basic {}\n", bind=parse_internal_ref("@Interface.API"))
text = write_contract(b.build())
print(text)
```

Reference cases (golden sources):
- FULL: `python3 scripts/contract_golden_check.py --case FULL --golden tests/goldens/P0_C_FULL/contract.sdsl2`
- MIN: `python3 scripts/contract_golden_check.py --case MIN --golden tests/goldens/P0_C_MIN/contract.sdsl2`
- ESCAPE: `python3 scripts/contract_golden_check.py --case ESCAPE --golden tests/goldens/P0_C_ESCAPE/contract.sdsl2`
- ORDERING: `python3 scripts/contract_golden_check.py --case ORDERING --golden tests/goldens/P0_C_ORDER/contract.sdsl2`

Operational entrypoint: see `README.md` (Open Interpreter Quickstart).

## 3. API Surface (v0.1)
Builder entry:
- `file(id_prefix: str) -> ContractBuilder`

Anchors:
- `doc_meta(id, title?, desc?, refs?, ssot?)`
- `structure(id, decl, title?, desc?, refs?, contract?, ssot?, bind?)`
- `interface(...)`, `function(...)`, `const(...)`, `type_alias(...)`
- `dep(from_ref, to, ssot?)` (bind is auto-set to from_ref)
- `rule(id, bind, refs?, contract?, ssot?)` (bind required)

Type requirements:
- `InternalRef` for bind/refs: `parse_internal_ref("@Kind.RELID")`
- `ContractRef` for contract: `parse_contract_ref("CONTRACT.*")`
- `SSOTRef` for ssot: `parse_ssot_ref("SSOT.*")`
- Raw strings are rejected.

## 4. Validation & Error Model
- Builder raises `BuilderError` and returns JSON diagnostics:
  `[{code,message,expected,got,path}]`
- `path` is JSON Pointer (RFC 6901):
  - `~` -> `~0`, `/` -> `~1`
- Example failure snapshots live in `tests/goldens/**/diagnostics.json`.

## 5. Determinism Contract
- Success cases are validated by `scripts/determinism_check.py`.
- Contract success cases are SSOT via `tests/determinism_manifest.json`.
- Determinism means:
  1) Golden match
  2) Re-run hash equality (same output twice)
- Failure cases are compared against diagnostics snapshots.

## 6. Closed Set v0.1
Enforced by `sdslv2_builder/closed_set_contract_v0_1.py`.

Allowed kinds:
- `@File`, `@DocMeta`, `@Structure`, `@Interface`, `@Function`, `@Const`, `@Type`, `@Dep`, `@Rule`

Rules:
- `@Dep.to` must be `InternalRef` or `ContractRef`
- Any Closed Set change requires a spec bump (v0.2+).

## 7. Canonicalization (JCS)
- Any contract hash must use JCS (RFC 8785).
- `@Dep` uses `sha256(JCS({from,to}))` for the hash suffix.
- Changes to canonicalization are breaking in v0.1.

## 8. FAQ / Troubleshooting
- `E_ID_FORMAT_INVALID`: use `UPPER_SNAKE_CASE` for ids and id_prefix.
- `E_RULE_BIND_REQUIRED`: `@Rule` must have `bind`.
- `E_BIND_TARGET_NOT_FOUND`: use `parse_internal_ref(...)` for refs/bind.
- `E_CONTRACT_REFS_INVALID`: use `parse_contract_ref(...)` for contract tokens.
- Golden mismatch: regenerate only when you intend a spec bump.

## Files of Record
- `coder_planning/builder_writer_api_v0_1.md`
- `coder_planning/errors_v0_1.md`
- `sdslv2_builder/closed_set_contract_v0_1.py`
