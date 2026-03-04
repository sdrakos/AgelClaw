"""
Nuitka Compiled-Mode Compatibility
====================================
Detects whether AgelClaw is running as a Nuitka-compiled executable and
provides helpers for resolving paths to Python, the main exe, and CLI commands.

Supports both Windows (.exe) and Linux (ELF binary) compiled modes.

In dev mode (pip install -e .), every function returns the standard
sys.executable / [sys.executable, "-m", ...] values — zero behavior change.
"""

import shutil
import sys
from pathlib import Path

IS_LINUX: bool = sys.platform.startswith("linux")
IS_WINDOWS: bool = sys.platform == "win32"


def _detect_compiled() -> bool:
    """Detect Nuitka compiled mode via multiple signals."""
    # Nuitka sets __compiled__ on each compiled module (not on sys)
    if "__compiled__" in globals():
        return True
    # Some Nuitka versions set sys.frozen
    if getattr(sys, "frozen", False):
        return True
    # Fallback: check if exe name is AgelClaw / agelclaw (not python)
    stem = Path(sys.executable).stem.lower()
    if stem.startswith("agelclaw"):
        return True
    return False

IS_COMPILED: bool = _detect_compiled()


def get_python_exe() -> str:
    """Return path to a real Python interpreter.

    Windows compiled: looks for bundled python-embed/python.exe next to the exe.
    Linux compiled: returns system python3 (no embed needed).
    Dev: returns sys.executable (the current Python).
    """
    if IS_COMPILED:
        if IS_WINDOWS:
            app_dir = Path(sys.executable).parent
            embed_python = app_dir / "python-embed" / "python.exe"
            if embed_python.exists():
                return str(embed_python)
        else:
            # Linux: use system python3
            system_python = shutil.which("python3") or shutil.which("python")
            if system_python:
                return system_python
    return sys.executable


def get_agelclaw_exe() -> str:
    """Return path to the AgelClaw main executable.

    Compiled (both platforms): returns sys.executable.
    Dev: returns sys.executable (python).
    """
    return sys.executable


def get_agelclaw_daemon_cmd() -> list[str]:
    """Return command list to start the daemon subprocess.

    Windows compiled: [<install_dir>/AgelClaw.exe, daemon]
    Linux compiled: [<install_dir>/agelclaw, daemon]
    Dev: [sys.executable, -m, agelclaw, daemon]
    """
    if IS_COMPILED:
        app_dir = Path(sys.executable).parent
        if IS_WINDOWS:
            exe = app_dir / "AgelClaw.exe"
        else:
            exe = app_dir / "agelclaw"
        return [str(exe), "daemon"]
    return [sys.executable, "-m", "agelclaw", "daemon"]


