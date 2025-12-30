# SDSLv2 Coder (v0.1)

## Open Interpreter entry point
Run the v0.1 wrapper:
```
python scripts/oi_run_v0_1.py
```

Allow extra write paths (if required):
```
python scripts/oi_run_v0_1.py --allow some/output/path/
```

Notes:
- Guard order (v0.1): spec lock -> error catalog -> Gate A -> determinism -> Gate B -> diff gate.
- Must be a git repository (diff gate enforces allowlist).
- Safe mode and sandboxed execution are recommended.
- Do not use auto-approve flags (e.g., -y). v0.1 requires manual approval.

Details: `docs/open_interpreter_v0_1.md`
