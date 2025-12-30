from __future__ import annotations

import json
from typing import Any


def _validate(obj: Any) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str):
                raise ValueError("JCS_KEY_NOT_STRING")
            _validate(v)
        return
    if isinstance(obj, list):
        for item in obj:
            _validate(item)
        return
    if isinstance(obj, (str, bool, type(None), int)):
        return
    raise ValueError(f"JCS_UNSUPPORTED_TYPE: {type(obj).__name__}")


def dumps(obj: Any) -> str:
    """
    Minimal RFC 8785 (JCS) serializer for strings/lists/dicts/bool/null/int.
    Uses json.dumps with sorted keys and no extra whitespace.
    """
    _validate(obj)
    return json.dumps(
        obj,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
