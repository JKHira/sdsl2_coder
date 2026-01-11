#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from L2_builder.common import ROOT as REPO_ROOT, ensure_inside, has_symlink_parent, resolve_path
from sdslv2_builder.errors import Diagnostic, json_pointer

DEFAULT_DEFINITIONS = "ssot_kernel_builder/ssot_definitions.ts"
DEFAULT_RUNTIME = "ssot_kernel_builder/ssot_runtime.ts"
ALLOWED_RUNTIME_IMPORTS = {"./ssot_definitions", "./ssot_definitions.ts"}

IMPORT_FROM_RE = re.compile(
    r'^\s*import\s+(?:type\s+)?[^;]*?\s+from\s+["\']([^"\']+)["\']',
    re.MULTILINE,
)
IMPORT_SIDE_EFFECT_RE = re.compile(r'^\s*import\s+["\']([^"\']+)["\']', re.MULTILINE)


def _diag(diags: list[Diagnostic], code: str, message: str, expected: str, got: str, path: str) -> None:
    diags.append(Diagnostic(code=code, message=message, expected=expected, got=got, path=path))


def _print_diags(diags: list[Diagnostic]) -> None:
    payload = [d.to_dict() for d in diags]
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)


def _strip_strings_and_comments(text: str) -> str:
    out: list[str] = []
    in_string = False
    string_quote = ""
    escape = False
    in_line_comment = False
    in_block_comment = False
    i = 0
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
                out.append("\n")
            else:
                out.append(" ")
            i += 1
            continue
        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                out.append(" ")
                out.append(" ")
                i += 2
                continue
            if ch == "\n":
                out.append("\n")
            else:
                out.append(" ")
            i += 1
            continue
        if in_string:
            if escape:
                escape = False
                out.append(" ")
                i += 1
                continue
            if ch == "\\":
                escape = True
                out.append(" ")
                i += 1
                continue
            if ch == string_quote:
                in_string = False
            out.append(" ")
            i += 1
            continue

        if ch == "/" and nxt == "/":
            in_line_comment = True
            out.append(" ")
            out.append(" ")
            i += 2
            continue
        if ch == "/" and nxt == "*":
            in_block_comment = True
            out.append(" ")
            out.append(" ")
            i += 2
            continue
        if ch in {"'", '"', "`"}:
            in_string = True
            string_quote = ch
            out.append(" ")
            i += 1
            continue

        out.append(ch)
        i += 1

    return "".join(out)


def _collect_imports(text: str) -> list[str]:
    imports: list[str] = []
    for match in IMPORT_FROM_RE.finditer(text):
        imports.append(match.group(1))
    for match in IMPORT_SIDE_EFFECT_RE.finditer(text):
        imports.append(match.group(1))
    return imports


def _check_definitions(text: str, diags: list[Diagnostic]) -> None:
    stripped = _strip_strings_and_comments(text)
    if not re.search(r"\bexport\s+const\s+SSOT_DEFINITIONS\b", stripped):
        _diag(
            diags,
            "E_SSOT_KERNEL_SRC_DEF_ANCHOR_MISSING",
            "ssot_definitions.ts must export SSOT_DEFINITIONS",
            "export const SSOT_DEFINITIONS = { ... } as const;",
            "missing",
            json_pointer("definitions"),
        )
    if len(re.findall(r"\bexport\s+const\s+SSOT_DEFINITIONS\b", stripped)) > 1:
        _diag(
            diags,
            "E_SSOT_KERNEL_SRC_DEF_ANCHOR_DUPLICATE",
            "ssot_definitions.ts must export SSOT_DEFINITIONS once",
            "single export",
            "duplicate",
            json_pointer("definitions"),
        )
    if not re.search(r"\bas\s+const\b", stripped):
        _diag(
            diags,
            "E_SSOT_KERNEL_SRC_DEF_AS_CONST_MISSING",
            "ssot_definitions.ts must use 'as const'",
            "as const",
            "missing",
            json_pointer("definitions"),
        )

    disallowed = [
        "import",
        "require",
        "function",
        "class",
        "new",
        "if",
        "for",
        "while",
        "switch",
        "try",
        "catch",
        "throw",
        "return",
        "=>",
        "async",
        "await",
    ]
    for token in disallowed:
        if token == "=>":
            if "=>" in stripped:
                _diag(
                    diags,
                    "E_SSOT_KERNEL_SRC_DEF_RUNTIME_TOKEN",
                    "ssot_definitions.ts must not include runtime logic",
                    "no runtime tokens",
                    token,
                    json_pointer("definitions"),
                )
            continue
        if re.search(rf"\b{re.escape(token)}\b", stripped):
            _diag(
                diags,
                "E_SSOT_KERNEL_SRC_DEF_RUNTIME_TOKEN",
                "ssot_definitions.ts must not include runtime logic",
                "no runtime tokens",
                token,
                json_pointer("definitions"),
            )


def _check_runtime(text: str, diags: list[Diagnostic]) -> None:
    stripped = _strip_strings_and_comments(text)
    imports = _collect_imports(text)
    allowed_seen = False
    for spec in imports:
        if spec in ALLOWED_RUNTIME_IMPORTS:
            allowed_seen = True
            continue
        _diag(
            diags,
            "E_SSOT_KERNEL_SRC_RUNTIME_IMPORT_INVALID",
            "ssot_runtime.ts may import only from ssot_definitions",
            "import from ./ssot_definitions(.ts)",
            spec,
            json_pointer("runtime", "imports"),
        )
    if not imports or not allowed_seen:
        _diag(
            diags,
            "E_SSOT_KERNEL_SRC_RUNTIME_IMPORT_MISSING",
            "ssot_runtime.ts must import ssot_definitions",
            "import from ./ssot_definitions(.ts)",
            "missing",
            json_pointer("runtime", "imports"),
        )

    if re.search(r"\bSSOT_DEFINITIONS\b\s*=", stripped):
        _diag(
            diags,
            "E_SSOT_KERNEL_SRC_RUNTIME_REDEFINE",
            "ssot_runtime.ts must not re-define SSOT_DEFINITIONS",
            "no assignment",
            "SSOT_DEFINITIONS",
            json_pointer("runtime"),
        )
    if re.search(r"\bSSOT_META\b\s*=", stripped):
        _diag(
            diags,
            "E_SSOT_KERNEL_SRC_RUNTIME_REDEFINE",
            "ssot_runtime.ts must not re-define SSOT_META",
            "no assignment",
            "SSOT_META",
            json_pointer("runtime"),
        )

    disallowed = ["class", "enum", "namespace", "module"]
    for token in disallowed:
        if re.search(rf"\b{re.escape(token)}\b", stripped):
            _diag(
                diags,
                "E_SSOT_KERNEL_SRC_RUNTIME_TOKEN",
                "ssot_runtime.ts contains disallowed declaration",
                "no class/enum/namespace/module",
                token,
                json_pointer("runtime"),
            )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=str(REPO_ROOT), help="Project root.")
    ap.add_argument(
        "--kernel-root",
        default=None,
        help="Kernel source root for ssot_definitions.ts (defaults to project root).",
    )
    ap.add_argument("--definitions", default=DEFAULT_DEFINITIONS, help="Definitions TS path.")
    ap.add_argument("--runtime", default=DEFAULT_RUNTIME, help="Runtime TS path.")
    ap.add_argument("--allow-missing", action="store_true", help="Return OK if inputs missing.")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve()
    if args.kernel_root:
        raw_kernel = Path(args.kernel_root)
        kernel_root = (ROOT / raw_kernel).resolve() if not raw_kernel.is_absolute() else raw_kernel.resolve()
    else:
        kernel_root = project_root
    definitions_path = resolve_path(kernel_root, args.definitions)
    runtime_path = resolve_path(kernel_root, args.runtime)

    try:
        ensure_inside(REPO_ROOT, kernel_root, "E_SSOT_KERNEL_SRC_ROOT_OUTSIDE_REPO")
        ensure_inside(kernel_root, definitions_path, "E_SSOT_KERNEL_SRC_OUTSIDE_PROJECT")
        ensure_inside(kernel_root, runtime_path, "E_SSOT_KERNEL_SRC_OUTSIDE_PROJECT")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if kernel_root.is_symlink() or has_symlink_parent(kernel_root, REPO_ROOT):
        print("E_SSOT_KERNEL_SRC_ROOT_SYMLINK", file=sys.stderr)
        return 2

    expected_def = (kernel_root / DEFAULT_DEFINITIONS).resolve()
    expected_rt = (kernel_root / DEFAULT_RUNTIME).resolve()
    if definitions_path != expected_def or runtime_path != expected_rt:
        print("E_SSOT_KERNEL_SRC_PATH_INVALID", file=sys.stderr)
        return 2

    if not definitions_path.exists() or not runtime_path.exists():
        if args.allow_missing:
            return 0
        missing = []
        if not definitions_path.exists():
            missing.append("definitions")
        if not runtime_path.exists():
            missing.append("runtime")
        _print_diags([
            Diagnostic(
                code="E_SSOT_KERNEL_SRC_INPUT_NOT_FOUND",
                message="SSOT source files missing",
                expected="definitions + runtime",
                got=",".join(missing),
                path=json_pointer(),
            )
        ])
        return 2

    for path in (definitions_path, runtime_path):
        if path.is_dir():
            print("E_SSOT_KERNEL_SRC_INPUT_IS_DIRECTORY", file=sys.stderr)
            return 2
        if has_symlink_parent(path, kernel_root) or path.is_symlink():
            print("E_SSOT_KERNEL_SRC_INPUT_SYMLINK", file=sys.stderr)
            return 2

    try:
        definitions_text = definitions_path.read_text(encoding="utf-8")
        runtime_text = runtime_path.read_text(encoding="utf-8")
    except OSError as exc:
        _print_diags([
            Diagnostic(
                code="E_SSOT_KERNEL_SRC_READ_FAILED",
                message="SSOT source read failed",
                expected="readable files",
                got=str(exc),
                path=json_pointer(),
            )
        ])
        return 2

    diags: list[Diagnostic] = []
    _check_definitions(definitions_text, diags)
    _check_runtime(runtime_text, diags)

    if diags:
        _print_diags(diags)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
