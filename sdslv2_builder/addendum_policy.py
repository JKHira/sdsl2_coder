from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import Diagnostic, json_pointer
from .ledger import load_ledger


@dataclass(frozen=True)
class PolicyResult:
    policy: dict[str, Any]
    diagnostics: list[Diagnostic]


def _diag(code: str, message: str, expected: str, got: str, path: str) -> Diagnostic:
    return Diagnostic(code=code, message=message, expected=expected, got=got, path=path)


def _default_policy() -> dict[str, Any]:
    return {"addendum": {"enabled": False}}


def _find_default_policy(root: Path) -> list[Path]:
    candidates: list[Path] = []
    for name in ("policy.yaml", "policy.yml"):
        path = root / ".sdsl" / name
        if path.exists():
            candidates.append(path)
    return candidates


def load_addendum_policy(policy_path: Path | None, repo_root: Path) -> PolicyResult:
    diagnostics: list[Diagnostic] = []
    if policy_path is not None:
        if not policy_path.exists():
            diagnostics.append(
                _diag(
                    "ADD_POLICY_NOT_FOUND",
                    "policy file not found",
                    "existing file",
                    str(policy_path),
                    json_pointer("policy_path"),
                )
            )
            return PolicyResult(policy=_default_policy(), diagnostics=diagnostics)
        return _load_policy_file(policy_path, diagnostics)

    candidates = _find_default_policy(repo_root)
    if len(candidates) > 1:
        diagnostics.append(
            _diag(
                "ADD_POLICY_MULTIPLE_FOUND",
                "multiple policy files found",
                "single policy file",
                ",".join(str(p) for p in candidates),
                json_pointer("policy_path"),
            )
        )
        return PolicyResult(policy=_default_policy(), diagnostics=diagnostics)
    if not candidates:
        diagnostics.append(
            _diag(
                "ADD_POLICY_NOT_FOUND",
                "policy file not found",
                ".sdsl/policy.yaml",
                "missing",
                json_pointer("policy_path"),
            )
        )
        return PolicyResult(policy=_default_policy(), diagnostics=diagnostics)
    return _load_policy_file(candidates[0], diagnostics)


def _load_policy_file(path: Path, diagnostics: list[Diagnostic]) -> PolicyResult:
    try:
        data = load_ledger(path)
    except Exception as exc:  # pragma: no cover - defensive
        diagnostics.append(
            _diag(
                "ADD_POLICY_PARSE_FAILED",
                "policy file failed to parse",
                "valid YAML or JSON",
                str(exc),
                json_pointer("policy_path"),
            )
        )
        return PolicyResult(policy=_default_policy(), diagnostics=diagnostics)

    if not isinstance(data, dict):
        diagnostics.append(
            _diag(
                "ADD_POLICY_SCHEMA_INVALID",
                "policy root must be an object",
                "object",
                type(data).__name__,
                json_pointer(),
            )
        )
        return PolicyResult(policy=_default_policy(), diagnostics=diagnostics)

    return PolicyResult(policy=data, diagnostics=diagnostics)
