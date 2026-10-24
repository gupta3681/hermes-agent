"""Interpreter admission for executable CLI wrappers, independent of desktop integration."""

import os
import sys
from pathlib import Path
from typing import Optional


def _shebang_tokens(shebang: str) -> list[str]:
    return shebang[2:].strip().split()


def _read_head(path: Path, size: int = 4096) -> Optional[bytes]:
    try:
        with open(path, "rb") as fh:
            return fh.read(size)
    except OSError:
        return None


def _needs_interpreter(bin_path: Path) -> bool:
    """Whether ``bin_path`` is a Python script whose shebang escapes the running venv.

    Native binaries (uv shim, PyInstaller, distro package) and shell wrappers (the installer's
    bash launcher execs the venv python itself) never need one.
    """
    head = _read_head(bin_path, 256)
    if head is None or not head.startswith(b"#!"):
        return False
    shebang = head.decode("utf-8", errors="replace").splitlines()[0].strip()
    if "python" not in shebang.lower():
        return False
    return _shebang_escapes_running_env(shebang)


def _shebang_escapes_running_env(shebang: str) -> bool:
    """Whether a python shebang resolves OUTSIDE the running interpreter's directory.

    Compares PATH COMPONENTS, never substrings: ``<venv>/bin-extra/python`` is not inside
    ``<venv>/bin``. ``env`` shebangs ALWAYS escape — ``env`` resolves through the DE's cold PATH,
    not the shell that installed the venv — except the rare ``env -S <abs-interpreter>`` form,
    which is judged by its absolute target.

    Tokenizes the shebang (interpreter path plus any flags) and compares PATH COMPONENTS, never substrings:
    ``<venv>/bin-extra/python`` is not inside ``<venv>/bin`` even though it starts with it
    (sibling-directory confusion; independently surfaced in nosliwhtes' #92122 hardening ``b96427d0`` —
    reimplemented here with two extensions).
    The comparison uses the LEXICAL interpreter directory (abspath, not resolve()): on uv venvs the resolved
    parent is the base interpreter's dir, which makes a valid ``.venv/bin/python`` shebang look foreign
    (#94443 review case 1). Both sides use the SAME case operation (``.lower()``): interpreter paths
    legitimately carry uppercase (conda env names, usernames, uv's ephemeral build dirs) and an asymmetric
    compare would flag the venv's own console script as foreign.
    """
    tokens = _shebang_tokens(shebang)
    if not tokens:
        return True  # bare "#!python": resolves via PATH
    interp = Path(tokens[0])
    if interp.name in ("env", "env.exe"):
        rest = [t for t in tokens[1:] if not t.startswith("-")]
        if not (rest and Path(rest[0]).is_absolute()):
            return True
        interp = Path(rest[0])
    running_dir = os.path.dirname(os.path.abspath(sys.executable)).lower()
    return str(interp.parent).lower() != running_dir
