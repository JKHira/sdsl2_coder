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

from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.op_yaml import load_yaml


PROFILE_REL_PATH = Path("policy") / "resolution_profile.yaml"


def _emit_diag(
    diags: list[Diagnostic],
    code: str,
    message: str,
    expected: str,
    got: str,
    path: str,
) -> None:
    diags.append(Diagnostic(code=code, message=message, expected=expected, got=got, path=path))


def _has_symlink_parent(path: Path, stop: Path) -> bool:
    for parent in [path, *path.parents]:
        if parent == stop:
            break
        if parent.is_symlink():
            return True
    return False


def _print_diags(diags: list[Diagnostic]) -> None:
    payload = [d.to_dict() for d in diags]
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)


def _read_str_list(
    value: object,
    diags: list[Diagnostic],
    path: str,
    label: str,
) -> None:
    if value is None:
        return
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
        _emit_diag(
            diags,
            "E_TOPO_RES_PROFILE_INVALID",
            f"{label} must be non-empty string list",
            "list[str]",
            str(value),
            path,
        )


def _read_pattern(
    value: object,
    diags: list[Diagnostic],
    path: str,
    label: str,
) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value.strip():
        _emit_diag(
            diags,
            "E_TOPO_RES_PROFILE_INVALID",
            f"{label} must be non-empty string",
            "string",
            str(value),
            path,
        )
        return
    try:
        re.compile(value)
    except re.error as exc:
        _emit_diag(
            diags,
            "E_TOPO_RES_PROFILE_INVALID",
            f"{label} regex invalid",
            "valid regex",
            str(exc),
            path,
        )


def _load_profile(path: Path, project_root: Path, diags: list[Diagnostic]) -> dict[str, object] | None:
    if not path.exists():
        _emit_diag(
            diags,
            "E_TOPO_RES_PROFILE_MISSING",
            "Resolution profile not found",
            str(PROFILE_REL_PATH),
            str(path),
            json_pointer("profile"),
        )
        return None
    try:
        path.resolve().relative_to(project_root.resolve())
    except ValueError:
        _emit_diag(
            diags,
            "E_TOPO_RES_PROFILE_OUTSIDE_PROJECT",
            "Resolution profile must be under project_root",
            "project_root/...",
            str(path),
            json_pointer("profile"),
        )
        return None
    if path.is_symlink() or _has_symlink_parent(path, project_root):
        _emit_diag(
            diags,
            "E_TOPO_RES_PROFILE_SYMLINK",
            "Resolution profile must not be symlink",
            "non-symlink",
            str(path),
            json_pointer("profile"),
        )
        return None
    try:
        data = load_yaml(path)
    except Exception as exc:
        _emit_diag(
            diags,
            "E_TOPO_RES_PROFILE_PARSE_FAILED",
            "Resolution profile parse failed",
            "valid YAML",
            str(exc),
            json_pointer("profile"),
        )
        return None
    if not isinstance(data, dict):
        _emit_diag(
            diags,
            "E_TOPO_RES_PROFILE_INVALID",
            "Resolution profile must be object",
            "object",
            type(data).__name__,
            json_pointer("profile"),
        )
        return None
    return data


def _validate_profile(data: dict[str, object], diags: list[Diagnostic]) -> None:
    schema_version = data.get("schema_version")
    if schema_version is not None and (not isinstance(schema_version, str) or not schema_version.strip()):
        _emit_diag(
            diags,
            "E_TOPO_RES_PROFILE_INVALID",
            "schema_version must be non-empty string",
            "string",
            str(schema_version),
            json_pointer("profile", "schema_version"),
        )

    node_cfg = data.get("node")
    if node_cfg is not None and not isinstance(node_cfg, dict):
        _emit_diag(
            diags,
            "E_TOPO_RES_PROFILE_INVALID",
            "node must be object",
            "object",
            type(node_cfg).__name__,
            json_pointer("profile", "node"),
        )
    if isinstance(node_cfg, dict):
        _read_str_list(node_cfg.get("required_fields"), diags, json_pointer("profile", "node", "required_fields"), "node.required_fields")
        _read_str_list(node_cfg.get("kind_vocab"), diags, json_pointer("profile", "node", "kind_vocab"), "node.kind_vocab")
        summary_cfg = node_cfg.get("summary")
        if summary_cfg is not None and not isinstance(summary_cfg, dict):
            _emit_diag(
                diags,
                "E_TOPO_RES_PROFILE_INVALID",
                "summary must be object",
                "object",
                type(summary_cfg).__name__,
                json_pointer("profile", "node", "summary"),
            )
        if isinstance(summary_cfg, dict):
            max_len = summary_cfg.get("max_len")
            if max_len is not None and (not isinstance(max_len, int) or max_len <= 0):
                _emit_diag(
                    diags,
                    "E_TOPO_RES_PROFILE_INVALID",
                    "summary.max_len must be positive int",
                    "positive int",
                    str(max_len),
                    json_pointer("profile", "node", "summary", "max_len"),
                )
            _read_pattern(
                summary_cfg.get("pattern"),
                diags,
                json_pointer("profile", "node", "summary", "pattern"),
                "summary.pattern",
            )
        io_cfg = node_cfg.get("io")
        if io_cfg is not None and not isinstance(io_cfg, dict):
            _emit_diag(
                diags,
                "E_TOPO_RES_PROFILE_INVALID",
                "io must be object",
                "object",
                type(io_cfg).__name__,
                json_pointer("profile", "node", "io"),
            )
        if isinstance(io_cfg, dict):
            _read_pattern(
                io_cfg.get("pattern"),
                diags,
                json_pointer("profile", "node", "io", "pattern"),
                "io.pattern",
            )

    edge_cfg = data.get("edge")
    if edge_cfg is not None and not isinstance(edge_cfg, dict):
        _emit_diag(
            diags,
            "E_TOPO_RES_PROFILE_INVALID",
            "edge must be object",
            "object",
            type(edge_cfg).__name__,
            json_pointer("profile", "edge"),
        )
    if isinstance(edge_cfg, dict):
        _read_str_list(edge_cfg.get("required_fields"), diags, json_pointer("profile", "edge", "required_fields"), "edge.required_fields")
        _read_str_list(edge_cfg.get("channel_vocab"), diags, json_pointer("profile", "edge", "channel_vocab"), "edge.channel_vocab")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root)",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    profile_path = project_root / PROFILE_REL_PATH

    diags: list[Diagnostic] = []
    data = _load_profile(profile_path, project_root, diags)
    if data is not None:
        _validate_profile(data, diags)
    if diags:
        _print_diags(diags)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
