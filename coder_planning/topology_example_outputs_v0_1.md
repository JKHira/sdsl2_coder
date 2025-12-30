# Topology Example Outputs v0.1

## Example 1: P4 Operation (node-only)
- Case ID: `P4_T_OPERATION`
- Ledger: `tests/ledgers/P4_T_OPERATION_NODEONLY/topology_ledger.yaml`
- Golden output: `tests/goldens/P4_T_OPERATION/topology.sdsl2`
- Repro command: `python3 -m sdslv2_builder.run --ledger tests/ledgers/P4_T_OPERATION_NODEONLY/topology_ledger.yaml --out-dir OUTPUT`
- Source SSOT: `C_T/Topology/P4_OPERATION_SDSL_TOPOLOGY.md`
- Scope: @Structure tags only; edges are intentionally omitted (no explicit edge facts in SSOT).
- Notes: Node kind is set to "component" for all extracted nodes in v0.1.

Operational entrypoint: see `README.md` (Open Interpreter Quickstart).
