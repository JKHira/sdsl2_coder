# sdslv2_builder (shared library)

Purpose: shared library for SDSLv2 tooling (L0/L1/L2 and scripts).
Non-scope: CLI tools (use L0_builder, L1_builder, L2_builder, or scripts).

## Modules (selected)
- `addendum_policy.py`: load `.sdsl/policy.yaml` and return policy + diagnostics.
- `closed_set_contract_v0_1.py`: validate ContractModel v0.1 (allowed kinds/refs).
- `contract.py`: ContractBuilder + ContractModel validation.
- `contract_writer.py`: deterministic SDSL contract writer.
- `context_pack.py`: extract Context Pack from topology `.sdsl2`.
- `draft_schema.py`: normalize/validate draft YAML.
- `intent_schema.py`: normalize/validate intent YAML.
- `errors.py`: Diagnostic, json_pointer, BuilderError.
- `input_hash.py`: deterministic input hash + input enumeration.
- `io_atomic.py`: atomic_write_text with symlink guard.
- `jcs.py`: JSON canonicalization (stable hashing).
- `ledger.py`: load/validate topology ledger (YAML/JSON).
- `lint.py`: SDSL annotation/metadata parsing helpers.
- `op_yaml.py`: minimal YAML loader (duplicate key tracking) + dump.
- `policy_utils.py`: load policy + gate severity helpers.
- `refs.py`: parse/validate InternalRef / ContractRef / SSOTRef.
- `run.py`: CLI helper to build topology from ledger into OUTPUT/.
- `schema_versions.py`: schema version constants.
- `topology.py` / `writer.py`: topology model + deterministic writer.

## Usage (minimal)
- Build topology from ledger: `python3 -m sdslv2_builder.run --ledger drafts/ledger/topology_ledger.yaml --out-dir OUTPUT`

## Notes
- This package is shared; changes affect all stages.
- Prefer shared helpers (json_pointer, input_hash, io_atomic) to keep outputs consistent.
