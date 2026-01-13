#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from L1_builder.decisions_lint import parse_decisions_file
from sdslv2_builder.contract import ContractModel, Decl, DocMeta
from sdslv2_builder.contract_writer import write_contract
from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.input_hash import compute_input_hash
from sdslv2_builder.lint import _capture_metadata, _parse_metadata_pairs
from sdslv2_builder.op_yaml import load_yaml
from sdslv2_builder.refs import RELID_RE, parse_contract_ref

PROFILE_REL_PATH = Path("policy") / "contract_resolution_profile.yaml"
DECL_KINDS = {"Structure", "Interface", "Function", "Const", "Type"}
FILE_HEADER_RE = re.compile(r'@File\s*\{\s*profile\s*:\s*"contract"\s*,\s*id_prefix\s*:\s*"(?P<prefix>[^"]+)"')


def _diag(
    diags: list[Diagnostic],
    code: str,
    message: str,
    expected: str,
    got: str,
    path: str,
) -> None:
    diags.append(Diagnostic(code=code, message=message, expected=expected, got=got, path=path))


def _print_diags(diags: list[Diagnostic]) -> None:
    payload = [d.to_dict() for d in diags]
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)


def _resolve_path(base: Path, raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = (base / path).resolve()
    return path


def _has_symlink_parent(path: Path, stop: Path) -> bool:
    for parent in [path, *path.parents]:
        if parent == stop:
            break
        if parent.is_symlink():
            return True
    return False


def _git_rev(root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return "UNKNOWN"
    if proc.returncode != 0:
        return "UNKNOWN"
    return proc.stdout.strip() or "UNKNOWN"


def _strip_quotes(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _load_profile(project_root: Path, diags: list[Diagnostic]) -> dict[str, object] | None:
    path = (project_root / PROFILE_REL_PATH).resolve()
    if not path.exists():
        return None
    if path.is_symlink() or _has_symlink_parent(path, project_root):
        _diag(
            diags,
            "E_CONTRACT_SCAFFOLD_PROFILE_SYMLINK",
            "contract profile must not be symlink",
            "non-symlink",
            str(path),
            json_pointer("profile"),
        )
        return None
    try:
        data = load_yaml(path)
    except Exception as exc:
        _diag(
            diags,
            "E_CONTRACT_SCAFFOLD_PROFILE_PARSE_FAILED",
            "contract profile must be valid YAML",
            "valid YAML",
            str(exc),
            json_pointer("profile"),
        )
        return None
    if not isinstance(data, dict):
        _diag(
            diags,
            "E_CONTRACT_SCAFFOLD_PROFILE_INVALID",
            "contract profile must be object",
            "object",
            type(data).__name__,
            json_pointer("profile"),
        )
        return None
    return data


def _line_offsets(lines: list[str]) -> list[int]:
    offsets: list[int] = []
    pos = 0
    for line in lines:
        offsets.append(pos)
        pos += len(line) + 1
    return offsets


def _render_meta(pairs: list[tuple[str, str]], multiline: bool) -> str:
    if not multiline and len(pairs) <= 2:
        inner = ", ".join(f"{k}:{v}" for k, v in pairs)
        return f"{{ {inner} }}"
    lines = ["{"]
    for key, value in pairs:
        lines.append(f"  {key}:{value},")
    lines.append("}")
    return "\n".join(lines)


def _upsert_desc(meta: str, desc_value: str) -> str:
    pairs = _parse_metadata_pairs(meta)
    replaced = False
    rendered_pairs: list[tuple[str, str]] = []
    for key, value in pairs:
        if key == "desc":
            existing = _strip_quotes(value) or ""
            if desc_value in existing:
                new_desc = existing
            elif existing:
                new_desc = f"{existing} | {desc_value}"
            else:
                new_desc = desc_value
            rendered_pairs.append((key, f'"{_escape(new_desc)}"'))
            replaced = True
        else:
            rendered_pairs.append((key, value))
    if not replaced:
        rendered_pairs.append(("desc", f'"{_escape(desc_value)}"'))
    multiline = "\n" in meta
    return _render_meta(rendered_pairs, multiline)


def _upsert_doc_meta(text: str, desc_value: str, diags: list[Diagnostic]) -> tuple[str, bool]:
    lines = text.splitlines()
    offsets = _line_offsets(lines)
    first_statement = None
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "" or stripped.startswith("//"):
            continue
        first_statement = (idx, stripped)
        break
    if first_statement is None:
        _diag(
            diags,
            "E_CONTRACT_SCAFFOLD_FILE_HEADER_MISSING",
            "Missing @File header",
            '@File { profile:"contract" }',
            "missing",
            json_pointer("doc_meta"),
        )
        return text, False
    if not first_statement[1].startswith("@File"):
        _diag(
            diags,
            "E_CONTRACT_SCAFFOLD_FILE_HEADER_INVALID",
            "@File header must be first statement",
            '@File { profile:"contract" }',
            first_statement[1],
            json_pointer("doc_meta"),
        )
        return text, False
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "" or stripped.startswith("//"):
            continue
        if stripped.startswith("@DocMeta"):
            brace_idx = line.find("{")
            if brace_idx == -1:
                _diag(
                    diags,
                    "E_CONTRACT_SCAFFOLD_DOCMETA_INVALID",
                    "@DocMeta missing metadata object",
                    "{...}",
                    line.strip(),
                    json_pointer("doc_meta"),
                )
                return text, False
            meta, end_line = _capture_metadata(lines, idx, brace_idx)
            start_offset = offsets[idx] + brace_idx
            end_offset = start_offset + len(meta)
            new_meta = _upsert_desc(meta, desc_value)
            if new_meta == meta:
                return text, False
            new_text = text[:start_offset] + new_meta + text[end_offset:]
            return new_text, True
        if stripped.startswith("@File"):
            continue
    # No DocMeta found: insert after first non-empty/comment line (usually @File).
    insert_at = first_statement[0] + 1
    meta = _render_meta(
        [("id", '"DOC_META"'), ("desc", f'"{_escape(desc_value)}"')],
        multiline=False,
    )
    docmeta_line = f"@DocMeta {meta}"
    new_lines = lines[:insert_at] + [docmeta_line] + lines[insert_at:]
    return "\n".join(new_lines) + ("\n" if text.endswith("\n") else ""), True


def _collect_contract_decls(
    contract_root: Path,
    diags: list[Diagnostic],
) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {kind: set() for kind in DECL_KINDS}
    for path in sorted(contract_root.rglob("*.sdsl2")):
        if not path.is_file():
            continue
        if path.is_symlink() or _has_symlink_parent(path, contract_root):
            _diag(
                diags,
                "E_CONTRACT_SCAFFOLD_INPUT_SYMLINK",
                "contract file must not be symlink",
                "non-symlink",
                str(path),
                json_pointer("contract"),
            )
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            _diag(
                diags,
                "E_CONTRACT_SCAFFOLD_READ_FAILED",
                "contract file must be readable UTF-8",
                "readable UTF-8 file",
                str(exc),
                json_pointer("contract"),
            )
            continue
        file_diags: list[Diagnostic] = []
        meta_map = _extract_file_header_meta(lines, file_diags, str(path))
        if file_diags:
            diags.extend(file_diags)
            continue
        if not meta_map:
            continue
        profile = _strip_quotes(meta_map.get("profile"))
        if profile != "contract":
            _diag(
                diags,
                "E_CONTRACT_SCAFFOLD_FILE_PROFILE_INVALID",
                "profile must be contract",
                "contract",
                str(profile),
                json_pointer(str(path), "file_header", "profile"),
            )
            continue
        for idx, line in enumerate(lines):
            if not line.lstrip().startswith("@"):
                continue
            kind = line.lstrip().split(None, 1)[0][1:]
            if kind not in DECL_KINDS:
                continue
            brace_idx = line.find("{")
            if brace_idx == -1:
                continue
            meta, _ = _capture_metadata(lines, idx, brace_idx)
            pairs = _parse_metadata_pairs(meta)
            meta_map = {k: v for k, v in pairs}
            rel_id = _strip_quotes(meta_map.get("id"))
            if rel_id:
                found.setdefault(kind, set()).add(rel_id)
    return found


def _decl_stub(kind: str, rel_id: str, contract_ref: str | None) -> Decl:
    contract_refs = [contract_ref] if contract_ref else []
    if kind == "Type":
        decl = f'type {rel_id} = "UNSPECIFIED"'
    elif kind == "Structure":
        decl = f"struct {rel_id} {{\n}}"
    elif kind == "Interface":
        decl = f"interface {rel_id} {{\n}}"
    elif kind == "Const":
        decl = f'const {rel_id} = "UNSPECIFIED"'
    else:
        decl = f'type {rel_id} = "UNSPECIFIED"'
    return Decl(
        kind=kind,
        rel_id=rel_id,
        decl=decl,
        bind=None,
        title=None,
        desc=None,
        refs=[],
        contract=[parse_contract_ref(ref) for ref in contract_refs if parse_contract_ref(ref)],
        ssot=[],
    )


def _extract_file_header_meta(
    lines: list[str],
    diags: list[Diagnostic],
    path_ref: str,
) -> dict[str, str] | None:
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "" or stripped.startswith("//"):
            continue
        if not stripped.startswith("@File"):
            _diag(
                diags,
                "E_CONTRACT_SCAFFOLD_FILE_HEADER_INVALID",
                "@File header must be first statement",
                '@File { profile:"contract" }',
                stripped,
                json_pointer(path_ref, "file_header"),
            )
            return None
        brace_idx = line.find("{")
        if brace_idx == -1:
            _diag(
                diags,
                "E_CONTRACT_SCAFFOLD_FILE_HEADER_INVALID",
                "@File header missing metadata",
                "{...}",
                line.strip(),
                json_pointer(path_ref, "file_header"),
            )
            return None
        meta, _ = _capture_metadata(lines, idx, brace_idx)
        pairs = _parse_metadata_pairs(meta)
        return {k: v for k, v in pairs}
    _diag(
        diags,
        "E_CONTRACT_SCAFFOLD_FILE_HEADER_MISSING",
        "Missing @File header",
        '@File { profile:"contract" }',
        "missing",
        json_pointer(path_ref, "file_header"),
    )
    return None


def _extract_existing_prefix(text: str, diags: list[Diagnostic]) -> str | None:
    lines = text.splitlines()
    meta_map = _extract_file_header_meta(lines, diags, "file")
    if not meta_map:
        return None
    profile = _strip_quotes(meta_map.get("profile"))
    if profile and profile != "contract":
        _diag(
            diags,
            "E_CONTRACT_SCAFFOLD_FILE_PROFILE_INVALID",
            "profile must be contract",
            "contract",
            str(profile),
            json_pointer("file", "file_header", "profile"),
        )
        return None
    prefix = _strip_quotes(meta_map.get("id_prefix"))
    if not prefix:
        _diag(
            diags,
            "E_CONTRACT_SCAFFOLD_FILE_PREFIX_MISSING",
            "id_prefix required",
            "id_prefix",
            "missing",
            json_pointer("file", "file_header", "id_prefix"),
        )
        return None
    return prefix


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--decisions-path", default="decisions/edges.yaml", help="decisions/edges.yaml path")
    ap.add_argument("--out", required=True, help="Target contract .sdsl2 file")
    ap.add_argument("--id-prefix", required=True, help="@File id_prefix for new contract file")
    ap.add_argument("--generator-id", default="contract_scaffold_gen_v0_1", help="generator id")
    ap.add_argument("--project-root", default=None, help="Project root (defaults to repo root)")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    decisions_path = _resolve_path(project_root, args.decisions_path)
    if not decisions_path.exists():
        _print_diags(
            [
                Diagnostic(
                    code="E_CONTRACT_SCAFFOLD_DECISIONS_NOT_FOUND",
                    message="decisions file not found",
                    expected="existing file",
                    got=str(decisions_path),
                    path=json_pointer("decisions"),
                )
            ]
        )
        return 2
    if decisions_path.is_dir():
        _print_diags(
            [
                Diagnostic(
                    code="E_CONTRACT_SCAFFOLD_DECISIONS_IS_DIR",
                    message="decisions path must be file",
                    expected="file",
                    got=str(decisions_path),
                    path=json_pointer("decisions"),
                )
            ]
        )
        return 2
    if decisions_path.is_symlink() or _has_symlink_parent(decisions_path, project_root):
        _print_diags(
            [
                Diagnostic(
                    code="E_CONTRACT_SCAFFOLD_DECISIONS_SYMLINK",
                    message="decisions path must not be symlink",
                    expected="non-symlink",
                    got=str(decisions_path),
                    path=json_pointer("decisions"),
                )
            ]
        )
        return 2

    out_path = _resolve_path(project_root, args.out)
    contract_root = project_root / "sdsl2" / "contract"
    try:
        out_path.resolve().relative_to(contract_root.resolve())
    except ValueError:
        _print_diags(
            [
                Diagnostic(
                    code="E_CONTRACT_SCAFFOLD_OUT_NOT_CONTRACT",
                    message="out must be under sdsl2/contract",
                    expected="sdsl2/contract/...",
                    got=str(out_path),
                    path=json_pointer("out"),
                )
            ]
        )
        return 2
    if out_path.exists() and out_path.is_dir():
        _print_diags(
            [
                Diagnostic(
                    code="E_CONTRACT_SCAFFOLD_OUT_IS_DIR",
                    message="out must be file",
                    expected="file",
                    got=str(out_path),
                    path=json_pointer("out"),
                )
            ]
        )
        return 2
    if out_path.exists() and out_path.is_symlink():
        _print_diags(
            [
                Diagnostic(
                    code="E_CONTRACT_SCAFFOLD_OUT_SYMLINK",
                    message="out must not be symlink",
                    expected="non-symlink",
                    got=str(out_path),
                    path=json_pointer("out"),
                )
            ]
        )
        return 2
    if _has_symlink_parent(out_path, project_root):
        _print_diags(
            [
                Diagnostic(
                    code="E_CONTRACT_SCAFFOLD_OUT_SYMLINK_PARENT",
                    message="out parent must not be symlink",
                    expected="non-symlink",
                    got=str(out_path),
                    path=json_pointer("out"),
                )
            ]
        )
        return 2

    diags: list[Diagnostic] = []
    decisions, decision_diags = parse_decisions_file(decisions_path, project_root)
    if decision_diags:
        _print_diags(decision_diags)
        return 2
    profile = _load_profile(project_root, diags)
    profile_path = (project_root / PROFILE_REL_PATH).resolve()

    if diags:
        _print_diags(diags)
        return 2

    contract_refs: set[str] = set()
    for edge in decisions.get("edges", []):
        if not isinstance(edge, dict):
            continue
        refs = edge.get("contract_refs", [])
        if not isinstance(refs, list):
            continue
        for ref in refs:
            if isinstance(ref, str) and parse_contract_ref(ref):
                contract_refs.add(ref)

    if contract_root.is_symlink() or _has_symlink_parent(contract_root, project_root):
        _print_diags(
            [
                Diagnostic(
                    code="E_CONTRACT_SCAFFOLD_CONTRACT_ROOT_SYMLINK",
                    message="sdsl2/contract must not be symlink",
                    expected="non-symlink",
                    got=str(contract_root),
                    path=json_pointer("contract"),
                )
            ]
        )
        return 2

    try:
        extra_inputs = [decisions_path]
        if profile_path.exists():
            extra_inputs.append(profile_path)
        input_hash = compute_input_hash(
            project_root,
            include_decisions=False,
            extra_inputs=extra_inputs,
        )
    except (FileNotFoundError, ValueError, OSError, UnicodeDecodeError) as exc:
        _print_diags(
            [
                Diagnostic(
                    code="E_CONTRACT_SCAFFOLD_INPUT_HASH_FAILED",
                    message="input_hash calculation failed",
                    expected="valid inputs",
                    got=str(exc),
                    path=json_pointer("input_hash"),
                )
            ]
        )
        return 2

    generator_desc = f"gen:{args.generator_id};rev:{_git_rev(project_root)};input:{input_hash.input_hash}"

    existing = _collect_contract_decls(contract_root, diags)
    if diags:
        _print_diags(diags)
        return 2

    stubs: list[Decl] = []
    if profile:
        required = profile.get("required_declarations")
        if isinstance(required, list):
            for idx, item in enumerate(required):
                if not isinstance(item, dict):
                    continue
                kind = item.get("kind")
                rel_id = item.get("id")
                if kind not in DECL_KINDS or not isinstance(rel_id, str):
                    _diag(
                        diags,
                        "E_CONTRACT_SCAFFOLD_REQUIRED_INVALID",
                        "required_declarations entries must have kind/id",
                        "kind+id",
                        json.dumps(item, ensure_ascii=False),
                        json_pointer("profile", "required_declarations", str(idx)),
                    )
                    continue
                if not RELID_RE.match(rel_id):
                    _diag(
                        diags,
                        "E_CONTRACT_SCAFFOLD_REQUIRED_ID_INVALID",
                        "required_declarations id must be RELID",
                        "UPPER_SNAKE_CASE",
                        rel_id,
                        json_pointer("profile", "required_declarations", str(idx), "id"),
                    )
                    continue
                if rel_id in existing.get(kind, set()):
                    continue
                stubs.append(_decl_stub(kind, rel_id, None))

    for ref in sorted(contract_refs):
        token = ref.split("CONTRACT.", 1)[-1]
        if not RELID_RE.match(token):
            _diag(
                diags,
                "E_CONTRACT_SCAFFOLD_TOKEN_INVALID",
                "contract token must end with RELID to scaffold",
                "CONTRACT.UPPER_SNAKE_CASE",
                ref,
                json_pointer("contract_refs"),
            )
            continue
        already = any(token in existing.get(kind, set()) for kind in DECL_KINDS)
        if already:
            continue
        stubs.append(_decl_stub("Type", token, ref))

    if diags:
        _print_diags(diags)
        return 2
    if not stubs:
        _print_diags(
            [
                Diagnostic(
                    code="E_CONTRACT_SCAFFOLD_NO_CHANGE",
                    message="no contract stubs required",
                    expected="missing declarations",
                    got="none",
                    path=json_pointer("contract"),
                )
            ]
        )
        return 2

    model = ContractModel(
        id_prefix=args.id_prefix,
        doc_meta=DocMeta(
            rel_id="DOC_META",
            title=None,
            desc=generator_desc,
            refs=[],
            ssot=[],
        ),
        decls=stubs,
        deps=[],
        rules=[],
    )
    stub_text = write_contract(model)

    old_text = ""
    if out_path.exists():
        old_text = out_path.read_text(encoding="utf-8")
        header_diags: list[Diagnostic] = []
        existing_prefix = _extract_existing_prefix(old_text, header_diags)
        if header_diags:
            _print_diags(header_diags)
            return 2
        if existing_prefix and existing_prefix != args.id_prefix:
            _print_diags(
                [
                    Diagnostic(
                        code="E_CONTRACT_SCAFFOLD_PREFIX_MISMATCH",
                        message="existing file id_prefix differs",
                        expected=args.id_prefix,
                        got=existing_prefix,
                        path=json_pointer("out"),
                    )
                ]
            )
            return 2
        updated_text, changed = _upsert_doc_meta(old_text, generator_desc, diags)
        if diags:
            _print_diags(diags)
            return 2
        old_text = updated_text
        stub_lines = stub_text.splitlines()[1:]
        if stub_lines:
            new_text = old_text.rstrip() + "\n" + "\n".join(stub_lines) + "\n"
        else:
            new_text = old_text
    else:
        new_text = stub_text

    diff = difflib.unified_diff(
        old_text.splitlines(),
        new_text.splitlines(),
        fromfile=str(out_path),
        tofile=str(out_path),
        lineterm="",
    )
    output = "\n".join(diff)
    if not output:
        _print_diags(
            [
                Diagnostic(
                    code="E_CONTRACT_SCAFFOLD_NO_CHANGE",
                    message="no contract stubs required",
                    expected="missing declarations",
                    got="none",
                    path=json_pointer("contract"),
                )
            ]
        )
        return 2
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
