"""Stdlib-only validation of the source revision admitted to a build."""
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import tomllib


def git(source: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=source, text=True, encoding="utf-8").rstrip("\r\n")


def require_source(source: Path, commit: str) -> None:
    if git(source, "rev-parse", "HEAD") != commit:
        raise ValueError("preparation source checkout changed revision; prepare again")
    status = git(source, "status", "--porcelain", "--untracked-files=all")
    if status:
        raise ValueError(f"payload builds require a clean source checkout at the admitted revision:\n{status}")


def require_commit(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{40}", value):
        raise ValueError("Commit builds require an exact full 40-character SHA")
    return value


def output(argv: list[str], repo: Path | None = None) -> str:
    return subprocess.check_output(argv, cwd=repo, text=True, encoding="utf-8", timeout=60).strip()


def version_at(repo: Path | None, commit: str, *, run=output) -> str:
    require_commit(commit)
    document = tomllib.loads(run(["git", "show", f"{commit}:pyproject.toml"], repo))
    version = document["project"]["version"]
    if not isinstance(version, str) or not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", version):
        raise ValueError("Commit packaging requires project.version=X.Y.Z")
    return version
