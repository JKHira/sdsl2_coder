#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import sys
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sdslv2_builder.io_atomic import atomic_write_text


RELID_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
STRUCTURE_TOKEN_RE = re.compile(r"@Structure\.([A-Z][A-Z0-9_]{2,63})")


def _read_nodes(path: Path) -> tuple[list[str], list[str]]:
    nodes: list[str] = []
    invalid: list[str] = []
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if stripped == "" or stripped.startswith("#"):
            continue
        if not RELID_RE.match(stripped):
            invalid.append(f"line {idx}: {stripped}")
            continue
        nodes.append(stripped)
    return nodes, invalid


def _extract_structures(path: Path, line_start: int | None, line_end: int | None) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    start = max(1, line_start or 1)
    end = line_end or len(lines)
    if start > end or start < 1 or end > len(lines):
        return []
    subset = lines[start - 1 : end]
    seen: set[str] = set()
    nodes: list[str] = []
    for line in subset:
        for match in STRUCTURE_TOKEN_RE.finditer(line):
            rel_id = match.group(1)
            if rel_id not in seen:
                seen.add(rel_id)
                nodes.append(rel_id)
    return nodes


def _yaml_quote(value: str) -> str:
    value = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{value}"'


def _dump_ledger(
    id_prefix: str,
    stage: str | None,
    nodes: list[str],
    kind: str,
    evidence_note: str | None,
) -> str:
    lines: list[str] = []
    lines.append("version: topology-ledger-v0.1")
    lines.append("schema_revision: 1")
    lines.append("file_header:")
    lines.append("  profile: topology")
    lines.append(f"  id_prefix: {_yaml_quote(id_prefix)}")
    if stage:
        lines.append(f"  stage: {_yaml_quote(stage)}")
    lines.append("nodes:")
    for node_id in nodes:
        lines.append(f"  - id: {_yaml_quote(node_id)}")
        lines.append(f"    kind: {_yaml_quote(kind)}")
    lines.append("edges: []")
    if evidence_note:
        lines.append("source:")
        lines.append(f"  evidence_note: {_yaml_quote(evidence_note)}")
    lines.append("")
    return "\n".join(lines)


def _resolve_path(base: Path, raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = (base / path).absolute()
    return path


def _has_symlink_parent(path: Path, stop: Path) -> bool:
    for parent in [path, *path.parents]:
        if parent == stop:
            break
        if parent.is_symlink():
            return True
    return False


def _ensure_allowed(path: Path, project_root: Path) -> bool:
    allowed = [project_root / "drafts" / "ledger"]
    for root in allowed:
        try:
            path.resolve().relative_to(root.resolve())
            return True
        except ValueError:
            continue
    print("E_LEDGER_BUILDER_OUTPUT_OUTSIDE_DRAFTS", file=sys.stderr)
    return False


def _ensure_input_under(path: Path, project_root: Path) -> bool:
    try:
        path.resolve().relative_to(project_root.resolve())
    except ValueError:
        print("E_LEDGER_BUILDER_INPUT_OUTSIDE_PROJECT", file=sys.stderr)
        return False
    return True


def _ensure_file_path(path: Path, label: str) -> bool:
    if path.exists() and path.is_dir():
        print(f"E_{label}_IS_DIRECTORY", file=sys.stderr)
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nodes", default=None, help="Text file with one RELID per line")
    ap.add_argument("--extract-structures-from", default=None, help="Source file to extract @Structure.<RELID>")
    ap.add_argument("--allow-structure-nodes", action="store_true", help="Allow @Structure tokens as Node ids")
    ap.add_argument("--line-start", type=int, default=None, help="Start line (1-based, inclusive)")
    ap.add_argument("--line-end", type=int, default=None, help="End line (1-based, inclusive)")
    ap.add_argument("--id-prefix", required=True, help="Topology id_prefix")
    ap.add_argument("--stage", default="L0", help="Topology stage (L0/L1/L2)")
    ap.add_argument("--kind", default="component", help="Node kind")
    ap.add_argument("--evidence-note", default="", help="Evidence note")
    ap.add_argument("--out", required=True, help="Output ledger path")
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root); outputs must stay under drafts/ledger/",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    ledger_root = project_root / "drafts" / "ledger"
    if ledger_root.is_symlink() or _has_symlink_parent(ledger_root, project_root):
        print("E_LEDGER_BUILDER_LEDGER_ROOT_SYMLINK", file=sys.stderr)
        return 2

    if not args.nodes and not args.extract_structures_from:
        print("E_LEDGER_BUILDER_INPUT_MISSING", file=sys.stderr)
        return 2
    if args.nodes and args.extract_structures_from:
        print("E_LEDGER_BUILDER_INPUT_CONFLICT", file=sys.stderr)
        return 2

    nodes: list[str] = []
    if args.nodes:
        nodes_path = _resolve_path(project_root, args.nodes)
        if not _ensure_input_under(nodes_path, project_root):
            return 2
        if nodes_path.is_symlink() or _has_symlink_parent(nodes_path, project_root):
            print("E_LEDGER_BUILDER_NODES_SYMLINK", file=sys.stderr)
            return 2
        if not nodes_path.exists():
            print("E_LEDGER_BUILDER_NODES_NOT_FOUND", file=sys.stderr)
            return 2
        nodes, invalid = _read_nodes(nodes_path)
        if invalid:
            print("E_LEDGER_BUILDER_INVALID_NODE_ID", file=sys.stderr)
            for entry in invalid:
                print(f"  - {entry}", file=sys.stderr)
            return 2

    if args.extract_structures_from:
        if not args.allow_structure_nodes:
            print("E_LEDGER_BUILDER_STRUCTURE_NODES_FORBIDDEN", file=sys.stderr)
            return 2
        source_path = _resolve_path(project_root, args.extract_structures_from)
        if not _ensure_input_under(source_path, project_root):
            return 2
        if source_path.is_symlink() or _has_symlink_parent(source_path, project_root):
            print("E_LEDGER_BUILDER_SOURCE_SYMLINK", file=sys.stderr)
            return 2
        if not source_path.exists():
            print("E_LEDGER_BUILDER_SOURCE_NOT_FOUND", file=sys.stderr)
            return 2
        extracted = _extract_structures(source_path, args.line_start, args.line_end)
        nodes = extracted if extracted else nodes

    if not nodes:
        print("E_LEDGER_BUILDER_NODES_EMPTY", file=sys.stderr)
        return 2

    evidence = args.evidence_note or None
    if not evidence and args.extract_structures_from:
        start = args.line_start or 1
        end = args.line_end or "EOF"
        evidence = f"lines {start}-{end} only / @Structure tokens only / no edges"

    if not args.id_prefix.strip():
        print("E_LEDGER_BUILDER_ID_PREFIX_EMPTY", file=sys.stderr)
        return 2
    if args.stage and args.stage not in {"L0", "L1", "L2"}:
        print("E_LEDGER_BUILDER_STAGE_INVALID", file=sys.stderr)
        return 2
    if not args.kind.strip():
        print("E_LEDGER_BUILDER_KIND_EMPTY", file=sys.stderr)
        return 2

    content = _dump_ledger(args.id_prefix, args.stage, nodes, args.kind, evidence)
    out_path = _resolve_path(project_root, args.out)
    if not _ensure_allowed(out_path, project_root):
        return 2
    if not _ensure_file_path(out_path, "LEDGER_OUTPUT"):
        return 2
    if out_path.is_symlink():
        print("E_LEDGER_BUILDER_OUTPUT_SYMLINK", file=sys.stderr)
        return 2
    if _has_symlink_parent(out_path, project_root):
        print("E_LEDGER_BUILDER_OUTPUT_SYMLINK_PARENT", file=sys.stderr)
        return 2
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        atomic_write_text(out_path, content, symlink_code="E_LEDGER_BUILDER_OUTPUT_SYMLINK")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"E_LEDGER_BUILDER_WRITE_FAILED:{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
