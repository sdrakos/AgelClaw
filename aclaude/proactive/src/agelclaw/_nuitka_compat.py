"""
Nuitka Compiled-Mode Compatibility
====================================
Detects whether AgelClaw is running as a Nuitka-compiled executable and
provides helpers for resolving paths to Python, the main exe, and CLI commands.

In dev mode (pip install -e .), every function returns the standard
sys.executable / [sys.executable, "-m", ...] values — zero behavior change.
"""

import sys
from pathlib import Path

def _detect_compiled() -> bool:
    """Detect Nuitka compiled mode via multiple signals."""
    # Nuitka sets __compiled__ on each compiled module (not on sys)
    if "__compiled__" in globals():
        return True
    # Some Nuitka versions set sys.frozen
    if getattr(sys, "frozen", False):
        return True
    # Fallback: check if exe name is AgelClaw (not python)
    stem = Path(sys.executable).stem.lower()
    if stem.startswith("agelclaw"):
        return True
    return False

IS_COMPILED: bool = _detect_compiled()


def get_python_exe() -> str:
    """Return path to a real Python interpreter.

    Compiled: looks for bundled python-embed/python.exe next to the exe.
    Dev: returns sys.executable (the current Python).
    """
    if IS_COMPILED:
        app_dir = Path(sys.executable).parent
        embed_python = app_dir / "python-embed" / "python.exe"
        if embed_python.exists():
            return str(embed_python)
    return sys.executable


def get_agelclaw_exe() -> str:
    """Return path to the AgelClaw main executable.

    Compiled: returns sys.executable (AgelClaw.exe).
    Dev: returns sys.executable (python).
    """
    if IS_COMPILED:
        return sys.executable
    return sys.executable


def get_agelclaw_daemon_cmd() -> list[str]:
    """Return command list to start the daemon subprocess.

    Compiled: [<install_dir>/AgelClaw.exe, daemon]
    Dev: [sys.executable, -m, agelclaw, daemon]
    """
    if IS_COMPILED:
        app_dir = Path(sys.executable).parent
        exe = app_dir / "AgelClaw.exe"
        return [str(exe), "daemon"]
    return [sys.executable, "-m", "agelclaw", "daemon"]


def get_mem_cli_cmd() -> list[str]:
    """Return command prefix for agelclaw-mem calls.

    Compiled: [<install_dir>/AgelClaw-Mem.exe]
    Dev: [sys.executable, -m, agelclaw.mem_cli]
    """
    if IS_COMPILED:
        app_dir = Path(sys.executable).parent
        mem_exe = app_dir / "AgelClaw-Mem.exe"
        return [str(mem_exe)]
    return [sys.executable, "-m", "agelclaw.mem_cli"]
