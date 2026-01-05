from __future__ import annotations

from pathlib import Path
from typing import Any

from .addendum_policy import PolicyResult, load_addendum_policy

GATE_SEVERITIES = {"FAIL", "DIAG", "IGNORE"}


def load_policy(policy_path: Path | None, project_root: Path) -> PolicyResult:
    return load_addendum_policy(policy_path, project_root)


def get_gate_severity(policy: dict[str, Any], gate_key: str, default: str = "FAIL") -> str:
    gates = policy.get("gates", {})
    if isinstance(gates, dict):
        raw = gates.get(gate_key)
        if isinstance(raw, str):
            value = raw.strip().upper()
            if value in GATE_SEVERITIES:
                return value
    return default if default in GATE_SEVERITIES else "FAIL"
