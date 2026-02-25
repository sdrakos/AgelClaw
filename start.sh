#!/bin/bash
# AgelClaw Agent Launcher (Linux / macOS)
cd "$(dirname "$0")"

# Check if python3 is available
if ! command -v python3 &> /dev/null; then
    echo ""
    echo "  ============================================="
    echo "    Python 3 is not installed"
    echo "  ============================================="
    echo ""
    echo "  AgelClaw requires Python 3.11 or newer."
    echo ""
    echo "  Install it:"
    echo "    macOS:  brew install python@3.12"
    echo "    Ubuntu: sudo apt install python3.12 python3.12-venv"
    echo "    Fedora: sudo dnf install python3.12"
    echo ""
    exit 1
fi

python3 launcher.py
