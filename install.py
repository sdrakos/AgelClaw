#!/usr/bin/env python3
"""
One-Click Installer
===================
Sets up the agent system:
1. Check Python version
2. Install Python dependencies
3. Build React UI (if Node available)
4. Create required directories
5. Run setup wizard

Usage:
    python install.py
"""

import subprocess
import sys
from pathlib import Path

PROACTIVE_DIR = Path(__file__).resolve().parent
REACT_DIR = PROACTIVE_DIR / "react-claude-chat"


def check_python():
    """Check Python 3.11+."""
    v = sys.version_info
    print(f"Python {v.major}.{v.minor}.{v.micro}")
    if v < (3, 11):
        print("ERROR: Python 3.11+ required")
        sys.exit(1)
    print("  OK")


def install_deps():
    """Install Python dependencies."""
    print("\nInstalling Python dependencies...")
    req_file = PROACTIVE_DIR / "requirements.txt"
    if not req_file.exists():
        print(f"  WARNING: {req_file} not found")
        return
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
        cwd=str(PROACTIVE_DIR),
    )
    if result.returncode != 0:
        print("  WARNING: Some dependencies failed to install")
    else:
        print("  OK")


def build_react():
    """Build React UI if Node.js is available."""
    if not REACT_DIR.exists():
        print("\nReact UI directory not found, skipping frontend build")
        return

    # Check if npm is available
    try:
        subprocess.run(["npm", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("\nnpm not found, skipping frontend build")
        print("  Install Node.js to build the React UI")
        return

    print("\nInstalling frontend dependencies...")
    subprocess.run(["npm", "install"], cwd=str(REACT_DIR))

    print("Building React UI...")
    result = subprocess.run(["npm", "run", "build"], cwd=str(REACT_DIR))
    if result.returncode == 0:
        print("  OK — React build ready")
    else:
        print("  WARNING: React build failed (you can still use the API)")


def create_dirs():
    """Create required directories."""
    print("\nCreating directories...")
    for d in ["data", "logs", "reports"]:
        (PROACTIVE_DIR / d).mkdir(exist_ok=True)
        print(f"  {d}/")
    print("  OK")


def run_wizard():
    """Run the setup wizard."""
    print("\n" + "=" * 50)
    subprocess.run([sys.executable, str(PROACTIVE_DIR / "setup_wizard.py")])


def main():
    print("=" * 50)
    print("  AgelClaw Agent — Installer")
    print("=" * 50)
    print()

    check_python()
    install_deps()
    create_dirs()
    build_react()
    run_wizard()


if __name__ == "__main__":
    main()
