from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8", symlink_code: str = "E_ATOMIC_WRITE_SYMLINK") -> None:
    tmp_path: Path | None = None
    try:
        if path.exists() and path.is_symlink():
            raise ValueError(symlink_code)
        with tempfile.NamedTemporaryFile("w", encoding=encoding, delete=False, dir=path.parent) as tmp:
            tmp.write(text)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = Path(tmp.name)
        if path.exists() and path.is_symlink():
            raise ValueError(symlink_code)
        os.replace(tmp_path, path)
    finally:
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
