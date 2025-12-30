#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.lint import _capture_metadata, _parse_metadata_pairs, _split_list_items
from sdslv2_builder.refs import INTERNAL_REF_RE, parse_contract_ref, parse_internal_ref, parse_ssot_ref


CONTRACT_KINDS = {
    "File",
    "DocMeta",
    "Structure",
    "Interface",
    "Function",
    "Const",
    "Type",
    "Dep",
    "Rule",
}

TOPOLOGY_KINDS = {
    "File",
    "DocMeta",
    "Node",
    "Edge",
    "Rule",
}


def iter_sdsl_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*.sdsl2") if p.is_file())


def _diag(diags: list[Diagnostic], code: str, message: str, expected: str, got: str, path: str) -> None:
    diags.append(Diagnostic(code=code, message=message, expected=expected, got=got, path=path))


def _parse_list(value: str) -> list[str] | None:
    value = value.strip()
    if not (value.startswith("[") and value.endswith("]")):
        return None
    return _split_list_items(value)


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def _collect_entries(lines: list[str]) -> list[dict]:
    entries: list[dict] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.lstrip().startswith("@"):
            i += 1
            continue
        kind = line.lstrip().split(None, 1)[0][1:]
        brace_idx = line.find("{")
        if brace_idx == -1:
            i += 1
            continue
        meta, end_line = _capture_metadata(lines, i, brace_idx)
        pairs = _parse_metadata_pairs(meta)
        kv = {k: v for k, v in pairs}
        entries.append({"kind": kind, "kv": kv, "line": i})
        i = end_line + 1
    return entries


def _extract_profile(entries: list[dict], diags: list[Diagnostic]) -> str | None:
    for entry in entries:
        if entry["kind"] == "File":
            profile = entry["kv"].get("profile")
            if profile:
                return _strip_quotes(profile)
            _diag(
                diags,
                "E_PROFILE_INVALID",
                "profile must be contract or topology",
                "contract|topology",
                str(profile),
                json_pointer("file_header", "profile"),
            )
            return None
    _diag(diags, "E_FILE_HEADER_MISSING", "Missing @File header", "@File", "missing", json_pointer())
    return None


def _build_anchor_set(entries: list[dict]) -> set[str]:
    anchors: set[str] = set()
    for entry in entries:
        rel_id = entry["kv"].get("id")
        if rel_id:
            rel_id = _strip_quotes(rel_id)
            anchors.add(f"@{entry['kind']}.{rel_id}")
    return anchors


def _check_bind(
    value: str | None,
    anchors: set[str],
    diags: list[Diagnostic],
    path: str,
) -> None:
    if not value:
        _diag(diags, "E_RULE_BIND_REQUIRED", "bind is required", "@Kind.RELID", "missing", path)
        return
    parsed = parse_internal_ref(value)
    if not parsed:
        _diag(diags, "E_BIND_TARGET_NOT_FOUND", "bind must be InternalRef", "@Kind.RELID", value, path)
        return
    if parsed.to_string() not in anchors:
        _diag(
            diags,
            "E_BIND_TARGET_NOT_FOUND",
            "bind target not found",
            "existing InternalRef",
            parsed.to_string(),
            path,
        )


def check_file(path: Path) -> list[Diagnostic]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    entries = _collect_entries(lines)
    diags: list[Diagnostic] = []

    profile = _extract_profile(entries, diags)
    if profile is None:
        return diags

    anchors = _build_anchor_set(entries)

    decl_index = 0
    dep_index = 0
    rule_index = 0
    edge_index = 0
    node_index = 0

    for entry in entries:
        kind = entry["kind"]
        kv = entry["kv"]

        if profile == "contract" and kind not in CONTRACT_KINDS:
            _diag(
                diags,
                "E_PROFILE_KIND_FORBIDDEN",
                "Kind not allowed in contract profile",
                "File,DocMeta,Structure,Interface,Function,Const,Type,Dep,Rule",
                kind,
                json_pointer("annotations", str(entry["line"])),
            )
            continue
        if profile == "topology" and kind not in TOPOLOGY_KINDS:
            _diag(
                diags,
                "E_PROFILE_KIND_FORBIDDEN",
                "Kind not allowed in topology profile",
                "File,DocMeta,Node,Edge,Rule",
                kind,
                json_pointer("annotations", str(entry["line"])),
            )
            continue

        if kind == "Rule":
            _check_bind(kv.get("bind"), anchors, diags, json_pointer("rules", str(rule_index), "bind"))
            rule_index += 1

        if profile == "contract":
            if kind == "Dep":
                to_val = kv.get("to")
                if to_val:
                    if to_val.strip().startswith("["):
                        _diag(
                            diags,
                            "E_TOKEN_PLACEMENT_VIOLATION",
                            "dep to must be InternalRef or ContractRef",
                            "@Kind.RELID or CONTRACT.*",
                            to_val,
                            json_pointer("deps", str(dep_index), "to"),
                        )
                    else:
                        raw = _strip_quotes(to_val)
                        if not (parse_internal_ref(raw) or parse_contract_ref(raw)):
                            _diag(
                                diags,
                                "E_TOKEN_PLACEMENT_VIOLATION",
                                "dep to must be InternalRef or ContractRef",
                                "@Kind.RELID or CONTRACT.*",
                                raw,
                                json_pointer("deps", str(dep_index), "to"),
                            )
                dep_index += 1

            refs_val = kv.get("refs")
            if refs_val is not None:
                items = _parse_list(refs_val)
                if items is None:
                    _diag(
                        diags,
                        "E_BIND_TARGET_NOT_FOUND",
                        "refs must be InternalRef list",
                        "[@Kind.RELID]",
                        refs_val,
                        json_pointer("decls", str(decl_index), "refs"),
                    )
                else:
                    for idx, item in enumerate(items):
                        token = _strip_quotes(item)
                        if not parse_internal_ref(token):
                            _diag(
                                diags,
                                "E_BIND_TARGET_NOT_FOUND",
                                "refs must be InternalRef list",
                                "@Kind.RELID",
                                token,
                                json_pointer("decls", str(decl_index), "refs", str(idx)),
                            )

            contract_val = kv.get("contract")
            if contract_val is not None:
                items = _parse_list(contract_val)
                if items is None:
                    _diag(
                        diags,
                        "E_CONTRACT_REFS_INVALID",
                        "contract must be ContractRef list",
                        '["CONTRACT.*"]',
                        contract_val,
                        json_pointer("decls", str(decl_index), "contract"),
                    )
                else:
                    for idx, item in enumerate(items):
                        token = _strip_quotes(item)
                        if not parse_contract_ref(token):
                            _diag(
                                diags,
                                "E_CONTRACT_REFS_INVALID",
                                "contract must be ContractRef list",
                                "CONTRACT.*",
                                token,
                                json_pointer("decls", str(decl_index), "contract", str(idx)),
                            )

            ssot_val = kv.get("ssot")
            if ssot_val is not None:
                items = _parse_list(ssot_val)
                if items is None:
                    _diag(
                        diags,
                        "E_TOKEN_PLACEMENT_VIOLATION",
                        "ssot must be SSOTRef list",
                        '["SSOT.*"]',
                        ssot_val,
                        json_pointer("decls", str(decl_index), "ssot"),
                    )
                else:
                    for idx, item in enumerate(items):
                        token = _strip_quotes(item)
                        if not parse_ssot_ref(token):
                            _diag(
                                diags,
                                "E_TOKEN_PLACEMENT_VIOLATION",
                                "ssot must be SSOTRef list",
                                "SSOT.*",
                                token,
                                json_pointer("decls", str(decl_index), "ssot", str(idx)),
                            )

            if kind in {"Structure", "Interface", "Function", "Const", "Type"}:
                decl_index += 1

            if profile == "contract" and "contract_refs" in kv:
                _diag(
                    diags,
                    "E_TOKEN_PLACEMENT_VIOLATION",
                    "contract_refs not allowed in contract profile",
                    "contract or @Dep.to",
                    "contract_refs",
                    json_pointer("decls", str(decl_index), "contract_refs"),
                )

        if profile == "topology":
            if kind == "Node":
                if "contract_refs" in kv:
                    _diag(
                        diags,
                        "E_TOKEN_PLACEMENT_VIOLATION",
                        "contract_refs only allowed on edges",
                        "Edge.contract_refs",
                        "Node.contract_refs",
                        json_pointer("nodes", str(node_index), "contract_refs"),
                    )
                node_index += 1
            if kind == "Edge":
                refs_val = kv.get("contract_refs")
                if refs_val is not None:
                    items = _parse_list(refs_val)
                    if items is None:
                        _diag(
                            diags,
                            "E_CONTRACT_REFS_INVALID",
                            "contract_refs must be a list",
                            "list of CONTRACT.*",
                            refs_val,
                            json_pointer("edges", str(edge_index), "contract_refs"),
                        )
                    else:
                        if not items:
                            _diag(
                                diags,
                                "E_EDGE_CONTRACT_REFS_EMPTY",
                                "contract_refs must be non-empty",
                                "non-empty list",
                                "empty",
                                json_pointer("edges", str(edge_index), "contract_refs"),
                            )
                        for idx, item in enumerate(items):
                            token = _strip_quotes(item)
                            if not parse_contract_ref(token):
                                _diag(
                                    diags,
                                    "E_CONTRACT_REFS_INVALID",
                                    "contract_refs items must be CONTRACT.* tokens",
                                    "CONTRACT.*",
                                    token,
                                    json_pointer("edges", str(edge_index), "contract_refs", str(idx)),
                                )
                edge_index += 1

    return diags


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", action="append", required=True, help="File or directory path.")
    args = ap.parse_args()

    files: list[Path] = []
    for raw in args.input:
        files.extend(iter_sdsl_files(Path(raw)))

    if not files:
        print("E_INPUT_NOT_FOUND: no .sdsl2 files", file=sys.stderr)
        return 2

    all_diags: list[Diagnostic] = []
    for path in files:
        all_diags.extend(check_file(path))

    if all_diags:
        payload = [d.to_dict() for d in all_diags]
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
