from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .errors import Diagnostic, json_pointer
from .refs import parse_contract_ref, parse_internal_ref


RELID_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
DIRECTION_VOCAB = {"pub", "sub", "req", "rep", "rw", "call"}
ALLOWED_KINDS = {"File", "DocMeta", "Node", "Edge", "EdgeIntent", "Rule"}


def _print_diagnostics(diags: list[Diagnostic]) -> None:
    payload = [d.to_dict() for d in diags]
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)


def _capture_metadata(lines: list[str], start_line: int, start_col: int) -> tuple[str, int]:
    depth = 0
    in_string: str | None = None
    escaped = False
    out: list[str] = []
    for li in range(start_line, len(lines)):
        line = lines[li]
        j = start_col if li == start_line else 0
        while j < len(line):
            ch = line[j]
            if in_string is not None:
                out.append(ch)
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == in_string:
                    in_string = None
                j += 1
                continue
            if ch in ('"', "'"):
                in_string = ch
                out.append(ch)
                j += 1
                continue
            if ch == "/" and j + 1 < len(line) and line[j + 1] == "/":
                break
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            out.append(ch)
            j += 1
            if depth == 0:
                return "".join(out), li
        if depth > 0:
            out.append("\n")
    return "", start_line


def _parse_metadata_pairs(meta: str) -> list[tuple[str, str]]:
    meta = meta.strip()
    if not (meta.startswith("{") and meta.endswith("}")):
        return []
    inner = meta[1:-1]
    pairs: list[tuple[str, str]] = []
    i = 0
    in_string: str | None = None
    escaped = False
    depth_brace = 0
    depth_bracket = 0
    depth_paren = 0
    while i < len(inner):
        while i < len(inner) and inner[i] in " \t\r\n,":
            i += 1
        if i >= len(inner):
            break
        key_start = i
        while i < len(inner) and (inner[i].isalnum() or inner[i] == "_"):
            i += 1
        key = inner[key_start:i]
        if not key:
            break
        while i < len(inner) and inner[i].isspace():
            i += 1
        if i >= len(inner) or inner[i] != ":":
            break
        i += 1
        val_start = i
        in_string = None
        escaped = False
        depth_brace = 0
        depth_bracket = 0
        depth_paren = 0
        while i < len(inner):
            ch = inner[i]
            if in_string is not None:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == in_string:
                    in_string = None
                i += 1
                continue
            if ch in ('"', "'"):
                in_string = ch
                i += 1
                continue
            if ch == "{":
                depth_brace += 1
            elif ch == "}":
                if depth_brace > 0:
                    depth_brace -= 1
            elif ch == "[":
                depth_bracket += 1
            elif ch == "]":
                if depth_bracket > 0:
                    depth_bracket -= 1
            elif ch == "(":
                depth_paren += 1
            elif ch == ")":
                if depth_paren > 0:
                    depth_paren -= 1
            if depth_brace == 0 and depth_bracket == 0 and depth_paren == 0 and ch == ",":
                break
            i += 1
        value = inner[val_start:i].strip()
        pairs.append((key, value))
        if i < len(inner) and inner[i] == ",":
            i += 1
    return pairs


def _split_list_items(value: str) -> list[str]:
    value = value.strip()
    if not (value.startswith("[") and value.endswith("]")):
        return []
    inner = value[1:-1]
    items: list[str] = []
    i = 0
    in_string: str | None = None
    escaped = False
    start = 0
    while i < len(inner):
        ch = inner[i]
        if in_string is not None:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_string:
                in_string = None
            i += 1
            continue
        if ch in ('"', "'"):
            in_string = ch
            i += 1
            continue
        if ch == ",":
            items.append(inner[start:i].strip())
            i += 1
            start = i
            continue
        i += 1
    tail = inner[start:].strip()
    if tail:
        items.append(tail)
    return items


def _diag(diags: list[Diagnostic], code: str, message: str, expected: str, got: str, path: str) -> None:
    diags.append(Diagnostic(code=code, message=message, expected=expected, got=got, path=path))


def lint_text(text: str, path: Path) -> list[Diagnostic]:
    diags: list[Diagnostic] = []
    lines = text.splitlines()
    file_lines = [idx for idx, line in enumerate(lines) if line.lstrip().startswith("@File")]

    first_stmt = None
    for idx, line in enumerate(lines):
        if line.strip() == "" or line.lstrip().startswith("//"):
            continue
        first_stmt = idx
        break

    if not file_lines:
        _diag(diags, "E_FILE_HEADER_MISSING", "Missing @File header", "@File", "missing", json_pointer())
    else:
        if first_stmt is not None and file_lines[0] != first_stmt:
            _diag(
                diags,
                "E_FILE_HEADER_NOT_FIRST",
                "@File must be first non-blank statement",
                "first statement",
                "later statement",
                json_pointer(),
            )
        if len(file_lines) > 1:
            _diag(
                diags,
                "E_FILE_HEADER_DUPLICATE",
                "Duplicate @File header",
                "single @File",
                "multiple",
                json_pointer(),
            )

    profile = None
    id_prefix = None
    if file_lines:
        line = lines[file_lines[0]]
        brace_idx = line.find("{")
        if brace_idx != -1:
            meta, _ = _capture_metadata(lines, file_lines[0], brace_idx)
            pairs = _parse_metadata_pairs(meta)
            for key, value in pairs:
                if key == "profile":
                    profile = value.strip().strip('"')
                if key == "id_prefix":
                    id_prefix = value.strip().strip('"')
        if profile != "topology":
            _diag(
                diags,
                "E_PROFILE_INVALID",
                "profile must be topology",
                "topology",
                str(profile),
                json_pointer("file_header", "profile"),
            )
        if not id_prefix:
            _diag(
                diags,
                "E_ID_FORMAT_INVALID",
                "id_prefix required",
                "non-empty string",
                str(id_prefix),
                json_pointer("file_header", "id_prefix"),
            )

    node_ids: set[str] = set()
    edge_pks: set[tuple[str, str, str, tuple[str, ...]]] = set()
    node_index = 0
    edge_index = 0
    rule_index = 0

    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.lstrip().startswith("@"):
            i += 1
            continue
        kind = line.lstrip().split(None, 1)[0][1:]
        if kind not in ALLOWED_KINDS:
            _diag(
                diags,
                "E_PROFILE_KIND_FORBIDDEN",
                "Kind not allowed in topology profile",
                "File,DocMeta,Node,Edge,Rule",
                kind,
                json_pointer("annotations", str(i)),
            )
        brace_idx = line.find("{")
        if brace_idx == -1:
            i += 1
            continue
        meta, end_line = _capture_metadata(lines, i, brace_idx)
        pairs = _parse_metadata_pairs(meta)
        i = end_line + 1

        kv = {k: v for k, v in pairs}
        if kind == "Node":
            rel_id = kv.get("id", "").strip('"')
            if not rel_id or not RELID_RE.match(rel_id):
                _diag(
                    diags,
                    "E_ID_FORMAT_INVALID",
                    "Node id must be RELID",
                    "UPPER_SNAKE_CASE",
                    rel_id,
                    json_pointer("nodes", str(node_index), "id"),
                )
            if rel_id in node_ids:
                _diag(
                    diags,
                    "E_ID_DUPLICATE",
                    "Duplicate node id",
                    "unique id",
                    rel_id,
                    json_pointer("nodes", str(node_index), "id"),
                )
            node_ids.add(rel_id)
            kind_value = kv.get("kind", "").strip('"')
            if not kind_value:
                _diag(
                    diags,
                    "E_LEDGER_REQUIRED_FIELD_MISSING",
                    "Node kind is required",
                    "non-empty string",
                    kind_value,
                    json_pointer("nodes", str(node_index), "kind"),
                )
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
            continue

        if kind == "Rule":
            bind_value = kv.get("bind", "")
            if not bind_value:
                _diag(
                    diags,
                    "E_RULE_BIND_REQUIRED",
                    "@Rule requires bind",
                    "bind:@Kind.RELID",
                    "missing",
                    json_pointer("rules", str(rule_index), "bind"),
                )
            rule_index += 1
            continue

        if kind != "Edge":
            continue

        missing = [key for key in ("id", "from", "to", "direction", "contract_refs") if key not in kv]
        if missing:
            _diag(
                diags,
                "E_EDGE_MISSING_FIELD",
                "Edge missing required fields",
                "id/from/to/direction/contract_refs",
                ",".join(missing),
                json_pointer("edges", str(edge_index)),
            )

        edge_id = kv.get("id", "").strip('"')
        if edge_id and not RELID_RE.match(edge_id):
            _diag(
                diags,
                "E_ID_FORMAT_INVALID",
                "Edge id must be RELID",
                "E_<hash>",
                edge_id,
                json_pointer("edges", str(edge_index), "id"),
            )

        from_val = kv.get("from", "")
        to_val = kv.get("to", "")
        direction = kv.get("direction", "").strip('"')
        if direction and direction not in DIRECTION_VOCAB:
            _diag(
                diags,
                "E_EDGE_DIRECTION_INVALID",
                "Edge direction invalid",
                "pub|sub|req|rep|rw|call",
                direction,
                json_pointer("edges", str(edge_index), "direction"),
            )

        from_ref = parse_internal_ref(from_val)
        to_ref = parse_internal_ref(to_val)
        if from_val and (not from_ref or from_ref.kind != "Node"):
            _diag(
                diags,
                "E_EDGE_FROM_TO_INVALID",
                "Edge from must be @Node.RELID",
                "@Node.RELID",
                from_val,
                json_pointer("edges", str(edge_index), "from"),
            )
        if to_val and (not to_ref or to_ref.kind != "Node"):
            _diag(
                diags,
                "E_EDGE_FROM_TO_INVALID",
                "Edge to must be @Node.RELID",
                "@Node.RELID",
                to_val,
                json_pointer("edges", str(edge_index), "to"),
            )
        from_id = from_ref.rel_id if from_ref and from_ref.kind == "Node" else ""
        to_id = to_ref.rel_id if to_ref and to_ref.kind == "Node" else ""
        if from_id and from_id not in node_ids:
            _diag(
                diags,
                "E_EDGE_FROM_TO_UNRESOLVED",
                "Edge from must reference existing node",
                "existing node id",
                from_id,
                json_pointer("edges", str(edge_index), "from"),
            )
        if to_id and to_id not in node_ids:
            _diag(
                diags,
                "E_EDGE_FROM_TO_UNRESOLVED",
                "Edge to must reference existing node",
                "existing node id",
                to_id,
                json_pointer("edges", str(edge_index), "to"),
            )

        refs_raw = kv.get("contract_refs", "")
        items = _split_list_items(refs_raw) if refs_raw else []
        if refs_raw and refs_raw.strip().startswith("[") and refs_raw.strip().endswith("]"):
            pass
        elif "contract_refs" in kv:
            _diag(
                diags,
                "E_CONTRACT_REFS_INVALID",
                "contract_refs must be a list",
                "list of CONTRACT.*",
                refs_raw,
                json_pointer("edges", str(edge_index), "contract_refs"),
            )

        if items == [] and "contract_refs" in kv:
            _diag(
                diags,
                "E_EDGE_CONTRACT_REFS_EMPTY",
                "contract_refs must be non-empty",
                "non-empty list",
                "empty",
                json_pointer("edges", str(edge_index), "contract_refs"),
            )

        tokens: list[str] = []
        token_seen: set[str] = set()
        for idx_item, raw in enumerate(items):
            raw = raw.strip()
            if raw.startswith('"') and raw.endswith('"'):
                token = raw[1:-1]
            else:
                token = raw
            if not parse_contract_ref(token):
                _diag(
                    diags,
                    "E_CONTRACT_REFS_INVALID",
                    "contract_refs items must be CONTRACT.* tokens",
                    "CONTRACT.*",
                    token,
                    json_pointer("edges", str(edge_index), "contract_refs", str(idx_item)),
                )
                continue
            if token in token_seen:
                _diag(
                    diags,
                    "E_CONTRACT_REFS_INVALID",
                    "contract_refs must be unique",
                    "unique list",
                    token,
                    json_pointer("edges", str(edge_index), "contract_refs"),
                )
                continue
            token_seen.add(token)
            tokens.append(token)

        pk_tokens = tuple(sorted(tokens))
        pk = (from_id, to_id, direction, pk_tokens)
        if pk in edge_pks:
            _diag(
                diags,
                "E_EDGE_DUPLICATE",
                "Duplicate edge (same PK)",
                "unique PK",
                f"{from_id}->{to_id}",
                json_pointer("edges", str(edge_index)),
            )
        edge_pks.add(pk)
        edge_index += 1

    return diags


def iter_sdsl_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*.sdsl2") if p.is_file())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to .sdsl2 file or directory.")
    args = ap.parse_args()

    path = Path(args.input)
    files = iter_sdsl_files(path)
    if not files:
        print("E_INPUT_NOT_FOUND: no .sdsl2 files", file=sys.stderr)
        return 2

    all_diags: list[Diagnostic] = []
    for file_path in files:
        text = file_path.read_text(encoding="utf-8")
        all_diags.extend(lint_text(text, file_path))

    if all_diags:
        _print_diagnostics(all_diags)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
