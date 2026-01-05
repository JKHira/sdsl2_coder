[FINDING 1]
File: L1_builder/token_registry_check.py
Location: _collect_tokens_from_files()
Category: A
Trigger: Run token_registry_check when any sdsl2/**/*.sdsl2 file has a malformed annotation (e.g., @Edge without "{") or duplicate metadata keys.
Impact: The tool throws an uncaught ValueError and crashes instead of emitting diagnostics, breaking the gate.
Proof:
  • _parse_annotations raises ValueError on missing "{" or duplicate metadata keys.
  • _collect_tokens_from_files calls _parse_annotations without try/except.
  • main() does not catch ValueError from _collect_tokens_from_files, so the exception escapes.
Minimal fix:
  • Catch ValueError around _parse_annotations and emit a Diagnostic with exit 2.

[FINDING 2]
File: L1_builder/evidence_repair.py
Location: main() diff generation and return path
Category: G
Trigger: decisions/evidence.yaml contains a content_hash that does not match the current source content.
Impact: evidence_repair exits 0 even when it detects mismatches, so Operational Gate passes and stale evidence is not signaled.
Proof:
  • When actual != content_hash, item["content_hash"] is updated and changed=True.
  • After diff generation, the code returns 0 regardless of changed.
  • operational_gate treats evidence_repair as a gate and only fails on nonzero exit; evidence_lint does not verify content_hash correctness.
Minimal fix:
  • Return exit 2 (or emit a Diagnostic) when changed=True so gate severity can be applied.

[FINDING 3]
File: L1_builder/evidence_repair.py
Location: main() handling of --out
Category: B
Trigger: Run evidence_repair with --out set to a path under sdsl2/ or decisions/ (e.g., sdsl2/topology/repair.patch).
Impact: The tool writes a diff file into SSOT/decisions roots, violating the OUTPUT-only write boundary and polluting SSOT.
Proof:
  • out_path is only checked with _ensure_inside(project_root); no OUTPUT/ restriction is enforced.
  • There is no denylist for sdsl2/ or decisions/ output roots.
  • out_path.write_text writes the diff to the user-supplied path.
Minimal fix:
  • Enforce OUTPUT/ (or stdout-only) for --out; reject sdsl2/ and decisions/ paths.

[FINDING 4]
File: L2_builder/token_registry_gen.py
Location: _write_registry()
Category: B
Trigger: Run token_registry_gen with --ssot-out or --contract-out pointing inside sdsl2/ or decisions/.
Impact: Registry files can be written into SSOT/decisions areas, violating authority boundaries and SSOT file layout rules.
Proof:
  • _write_registry only checks that the path is inside project_root and ends with .json.
  • No enforcement of OUTPUT/ssot prefix despite CLI help stating fixed output.
  • out_parent.mkdir(...) and path.write_text(...) execute for any in-project path.
Minimal fix:
  • Enforce OUTPUT/ssot as the only allowed output root for both registries.

[FINDING 5]
File: L1_builder/schema_migration_check.py
Location: _collect_yaml_files() and main() path handling
Category: E
Trigger: Place a symlinked directory under drafts/ or pass --decisions-path (or other path args) pointing outside project_root.
Impact: The tool reads YAML outside project_root, allowing external files to affect schema_migration results (authority boundary violation).
Proof:
  • _collect_yaml_files uses rglob without symlink or parent-symlink checks.
  • main() resolves explicit paths but never enforces _ensure_inside or symlink checks for decisions/evidence/contracts/exceptions.
  • _load_schema_version reads any resolved file without containment validation.
Minimal fix:
  • Add _ensure_inside and symlink-parent checks for all inputs; skip or fail on symlinked paths.
