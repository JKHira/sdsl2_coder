# v0.2 Triggers and Locks

Purpose:
- Define when a v0.2 spec bump is required.
- Define which files are locked and how to generate spec locks.

## Spec bump triggers (判定可能)
- Error catalog: add/remove a code, or change meaning of message/expected/got/path.
- Closed Set: add/remove/alter allowed kinds, keys, token placement rules.
- Token placement: allow CONTRACT/SSOT in a new field or disallow existing field.
- Deterministic output: change ID rules (JCS payload, hash length), required fields, canonical order, or writer formatting that affects diff.
- Gate C: introduce transform/auto-fix rules or change existing transform behavior.
- Input schema: ledger schema changes (new required fields, new top-level keys, type changes).
- CLI/output contract: new commands or flags that change output format or semantics.

## Non-triggers (no bump)
- Documentation updates that do not change locked specs.
- New examples/goldens that do not change spec rules.
- New tests or CI wiring that do not change output semantics.

## Lock policy (v0.2)
- Create `spec_locks_v0_2.json` when v0.2 specs are finalized.
Lock files (expected list) are:
- coder_planning/builder_writer_api_v0_2.md
- coder_planning/errors_v0_2.md
- coder_planning/ledger_v0_2.md
- coder_planning/ledger_format/closed_set_v0_2.md
- coder_planning/ledger_format/topology_ledger_v0_2.md
- coder_planning/gate_c_policy_v0_2.md (if Gate C transform is adopted)
- CI must fail if any locked file hash changes without a spec bump.

## Diff gate alignment
- If new input sources are added (e.g., Contract ledger), update diff gate allowlist at the same time.
- Keep allowlist changes tied to the v0.2 spec bump.
