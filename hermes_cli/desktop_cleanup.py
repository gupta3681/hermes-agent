"""Cleanup-only paths for legacy desktop installations."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

APP_ID = "com.nousresearch.hermes"
DESKTOP_ENTRY_NAME = f"{APP_ID}.desktop"
LEGACY_DESKTOP_ENTRY_NAME = "hermes.desktop"


def _xdg_data_home() -> Path:
    raw = os.environ.get("XDG_DATA_HOME")
    return Path(raw).expanduser() if raw and raw.strip() else Path.home() / ".local" / "share"


def desktop_entry_path() -> Path:
    return _xdg_data_home() / "applications" / DESKTOP_ENTRY_NAME


def refresh_desktop_databases(applications_dir: Path) -> list[str]:
    """Reindex the menu caches. Run each tool only when it exists."""
    ran: list[str] = []

    update_db = shutil.which("update-desktop-database")
    if update_db and _run_quiet([update_db, str(applications_dir)]):
        ran.append("update-desktop-database")

    # Plasma 6 first, then Plasma 5. Only one of them is ever installed.
    for tool in ("kbuildsycoca6", "kbuildsycoca5"):
        resolved = shutil.which(tool)
        if resolved:
            if _run_quiet([resolved, "--noincremental"]):
                ran.append(tool)
            break

    return ran


def _run_quiet(cmd: list[str], *, timeout: int = 60, on_error: Optional[bool] = False, **kwargs) -> Optional[bool]:
    """Exit-status success of a silenced subprocess; ``on_error`` when it could not be run at all."""
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=timeout,
            **kwargs,
        )
    except (OSError, subprocess.SubprocessError):
        return on_error
    return result.returncode == 0
