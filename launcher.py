#!/usr/bin/env python3
"""
One-Click Launcher for AgelClaw Agent
======================================
Full auto-installer: creates virtual environment, installs dependencies,
copies bundled skills, starts the API server, and opens the browser.
Works on Windows, Linux, and macOS — zero terminal knowledge needed.

Usage:
    python launcher.py          # Default (port from config.yaml)
    python launcher.py --port 8000
"""

import os
import sys
import time
import shutil
import signal
import subprocess
import webbrowser
from pathlib import Path

PROACTIVE_DIR = Path(__file__).resolve().parent
REQUIREMENTS_FILE = PROACTIVE_DIR / "requirements.txt"
REACT_DIST = PROACTIVE_DIR / "react-claude-chat" / "dist"
STAMP_FILE = PROACTIVE_DIR / "data" / ".deps_installed"
VENV_DIR = PROACTIVE_DIR / ".venv"
BUNDLED_SKILLS = PROACTIVE_DIR / "skills"
CONFIG_FILE = PROACTIVE_DIR / "config.yaml"
CONFIG_EXAMPLE = PROACTIVE_DIR / "config.yaml.example"

# Track child processes for cleanup
_children: list[subprocess.Popen] = []


def _venv_python() -> str:
    """Return path to the venv Python executable."""
    if sys.platform == "win32":
        return str(VENV_DIR / "Scripts" / "python.exe")
    return str(VENV_DIR / "bin" / "python3")


def print_banner():
    print()
    print("=" * 50)
    print("   AgelClaw Agent - One-Click Launcher")
    print("=" * 50)
    print()


def check_python():
    """Ensure Python 3.11+."""
    v = sys.version_info
    if v < (3, 11):
        print(f"[ERROR] Python 3.11+ required, found {v.major}.{v.minor}.{v.micro}")
        print("  Download: https://www.python.org/downloads/")
        sys.exit(1)
    print(f"[OK] Python {v.major}.{v.minor}.{v.micro}")


def create_venv():
    """Create virtual environment if it doesn't exist."""
    if VENV_DIR.exists() and Path(_venv_python()).exists():
        print("[OK] Virtual environment exists")
        return

    print("[...] Creating virtual environment (.venv)...")
    result = subprocess.run(
        [sys.executable, "-m", "venv", str(VENV_DIR)],
        cwd=str(PROACTIVE_DIR),
    )
    if result.returncode != 0:
        print("[ERROR] Failed to create virtual environment")
        sys.exit(1)
    print("[OK] Virtual environment created")


def install_deps():
    """Install pip dependencies in .venv if requirements.txt is newer than last install."""
    if not REQUIREMENTS_FILE.exists():
        print("[SKIP] No requirements.txt found")
        return

    STAMP_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Check if deps are already installed and up-to-date
    if STAMP_FILE.exists():
        req_mtime = REQUIREMENTS_FILE.stat().st_mtime
        stamp_mtime = STAMP_FILE.stat().st_mtime
        if stamp_mtime >= req_mtime:
            print("[OK] Dependencies up to date")
            return

    vpy = _venv_python()
    print("[...] Installing dependencies (this may take a minute)...")
    result = subprocess.run(
        [vpy, "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE), "-q"],
        cwd=str(PROACTIVE_DIR),
    )
    if result.returncode != 0:
        print("[ERROR] Failed to install dependencies")
        sys.exit(1)

    STAMP_FILE.write_text(str(time.time()), encoding="utf-8")
    print("[OK] Dependencies installed")


def ensure_dirs():
    """Create data/logs/reports dirs if missing."""
    for name in ("data", "logs", "reports"):
        d = PROACTIVE_DIR / name
        d.mkdir(parents=True, exist_ok=True)
    print("[OK] Data directories ready")


def copy_skills():
    """Copy bundled skills to ../.Claude/Skills/ (runtime location)."""
    if not BUNDLED_SKILLS.exists():
        print("[SKIP] No bundled skills directory")
        return

    # Skills go one level up from proactive/ into .Claude/Skills/
    runtime_skills = PROACTIVE_DIR.parent / ".Claude" / "Skills"
    runtime_skills.mkdir(parents=True, exist_ok=True)

    copied = 0
    for skill_dir in sorted(BUNDLED_SKILLS.iterdir()):
        if not skill_dir.is_dir():
            continue
        dest = runtime_skills / skill_dir.name
        if dest.exists():
            continue  # Don't overwrite user-modified skills
        shutil.copytree(str(skill_dir), str(dest))
        copied += 1

    if copied:
        print(f"[OK] Installed {copied} skills")
    else:
        print("[OK] All skills already installed")


def copy_config():
    """Copy config.yaml.example to config.yaml on first run."""
    if CONFIG_FILE.exists():
        print("[OK] config.yaml found")
        return

    if CONFIG_EXAMPLE.exists():
        shutil.copy2(str(CONFIG_EXAMPLE), str(CONFIG_FILE))
        print("[OK] Created config.yaml from template (first run)")
        print("     >> Open Settings in the UI to add your API keys")
    else:
        print("[WARN] No config.yaml.example found — create config.yaml manually")


def start_server(port: int) -> subprocess.Popen:
    """Start api_server.py using the .venv Python."""
    server_script = PROACTIVE_DIR / "api_server.py"
    if not server_script.exists():
        print(f"[ERROR] {server_script} not found")
        sys.exit(1)

    vpy = _venv_python()
    print(f"[...] Starting API server on port {port}...")
    creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        [vpy, str(server_script)],
        cwd=str(PROACTIVE_DIR),
        creationflags=creation_flags,
    )
    _children.append(proc)
    return proc


def wait_for_server(port: int, timeout: int = 30) -> bool:
    """Poll /api/health until the server is ready."""
    import urllib.request
    import urllib.error

    url = f"http://localhost:{port}/api/health"
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(0.5)
    return False


def open_browser(port: int):
    """Open the default browser to the server URL."""
    url = f"http://localhost:{port}"
    print(f"[...] Opening browser: {url}")
    webbrowser.open(url)


def get_port() -> int:
    """Get port from config.yaml or command-line."""
    # Check --port argument
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--port" and i < len(sys.argv) - 1:
            try:
                return int(sys.argv[i + 1])
            except ValueError:
                pass

    # Read from config.yaml
    if CONFIG_FILE.exists():
        try:
            # Use simple parsing to avoid importing yaml before venv deps
            text = CONFIG_FILE.read_text(encoding="utf-8")
            for line in text.splitlines():
                if line.strip().startswith("api_port:"):
                    return int(line.split(":", 1)[1].strip())
        except Exception:
            pass

    return 8000


def cleanup(*_args):
    """Gracefully stop all child processes."""
    print("\n[...] Shutting down...")
    for proc in _children:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    print("[OK] All services stopped. Goodbye!")
    sys.exit(0)


def main():
    print_banner()

    # Step 1: Check Python 3.11+
    check_python()

    # Step 2: Create virtual environment
    create_venv()

    # Step 3: Install dependencies in .venv
    install_deps()

    # Step 4: Create data/logs/reports dirs
    ensure_dirs()

    # Step 5: Copy bundled skills
    copy_skills()

    # Step 6: Copy config.yaml.example on first run
    copy_config()

    # Step 7: Start API server
    port = get_port()
    server_proc = start_server(port)

    # Step 8: Wait for /api/health
    if wait_for_server(port):
        print(f"[OK] Server is ready at http://localhost:{port}")
    else:
        print(f"[WARN] Server may not be ready yet (timeout). Check logs.")

    # Step 9: Open browser
    open_browser(port)

    # Step 10: Keep running (Ctrl+C to stop)
    signal.signal(signal.SIGINT, cleanup)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, cleanup)

    print()
    print("-" * 50)
    print(f"  Server running at http://localhost:{port}")
    print("  Press Ctrl+C to stop all services")
    print("-" * 50)
    print()

    try:
        while True:
            if server_proc.poll() is not None:
                print(f"[ERROR] Server process exited with code {server_proc.returncode}")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()


if __name__ == "__main__":
    main()
