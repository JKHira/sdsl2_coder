from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True)
class InputHashResult:
    input_hash: str
    inputs: list[Path]


def _normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _rel_path(root: Path, path: Path) -> str:
    rel = path.resolve().relative_to(root.resolve())
    return rel.as_posix()


def _content_hash(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    normalized = _normalize_text(text)
    return sha256(normalized.encode("utf-8")).hexdigest()


def _validate_path(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"INPUT_HASH_MISSING:{path}")
    if path.is_symlink():
        raise ValueError(f"INPUT_HASH_SYMLINK:{path}")


def _ssot_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for profile in ["contract", "topology"]:
        base = root / "sdsl2" / profile
        if not base.exists():
            continue
        for path in base.rglob("*.sdsl2"):
            if path.is_file():
                files.append(path)
    return sorted(files)


def _base_inputs(root: Path, include_decisions: bool) -> list[Path]:
    inputs = _ssot_files(root)
    if include_decisions:
        decisions = root / "decisions" / "edges.yaml"
        _validate_path(decisions)
        inputs.append(decisions)
    return sorted(inputs, key=lambda p: _rel_path(root, p))


def compute_input_hash(
    root: Path,
    extra_inputs: list[Path] | None = None,
    include_policy: bool = False,
    include_decisions: bool = True,
) -> InputHashResult:
    inputs = _base_inputs(root, include_decisions)
    if include_policy:
        for policy_path in [root / ".sdsl" / "policy.yaml", root / "policy" / "exceptions.yaml"]:
            if policy_path.exists():
                _validate_path(policy_path)
                inputs.append(policy_path)
    if extra_inputs:
        for path in extra_inputs:
            _validate_path(path)
            inputs.append(path)
    inputs = sorted(dict.fromkeys(inputs), key=lambda p: _rel_path(root, p))

    parts: list[str] = []
    for path in inputs:
        rel = _rel_path(root, path)
        digest = _content_hash(path)
        parts.append(f"{rel}\n{digest}\n")
    payload = "".join(parts)
    digest = sha256(payload.encode("utf-8")).hexdigest()
    return InputHashResult(input_hash=f"sha256:{digest}", inputs=inputs)
