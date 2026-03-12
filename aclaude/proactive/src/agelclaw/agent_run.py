"""
Agent Runner (local development)
==================================
Starts all services concurrently using the src/agelclaw modules directly.

Usage:
    python src/agelclaw/agent_run.py              # Start all
    python src/agelclaw/agent_run.py --no-telegram  # Without Telegram bot
    python src/agelclaw/agent_run.py --no-daemon    # Without daemon
    python src/agelclaw/agent_run.py --no-api       # Without API server
"""

import os
import socket
import subprocess
import sys
import signal
import time
from pathlib import Path

# Remove CLAUDECODE env var — prevents "nested session" error when
# agent_run.py is started from a Claude Code terminal. Without this,
# claude.exe refuses to launch in child processes (exit code 1).
os.environ.pop("CLAUDECODE", None)

SRC_DIR = Path(__file__).resolve().parent  # src/agelclaw/


def _port_in_use(port: int) -> bool:
    """Check if a port is already in use (service already running)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0

SERVICES = {
    "api_server": {
        "module": "agelclaw.api_server",
        "label": "API Server (:8000)",
        "flag": "--no-api",
        "port": 8000,
    },
    "daemon": {
        "module": "agelclaw.daemon",
        "label": "Daemon (:8420)",
        "flag": "--no-daemon",
        "port": 8420,
    },
    "telegram": {
        "module": "agelclaw.telegram_bot",
        "label": "Telegram Bot",
        "flag": "--no-telegram",
        "port": None,
    },
}

processes: dict[str, subprocess.Popen] = {}
shutting_down = False


def start_service(name: str, module: str, label: str):
    proc = subprocess.Popen(
        [sys.executable, "-m", module],
        cwd=str(SRC_DIR.parent.parent),  # proactive/ root
    )
    processes[name] = proc
    print(f"  [{label}] started (PID {proc.pid})")


def shutdown(signum=None, frame=None):
    global shutting_down
    if shutting_down:
        return
    shutting_down = True

    print("\nShutting down...")
    for name, proc in processes.items():
        label = SERVICES[name]["label"]
        if proc.poll() is None:
            proc.terminate()
            print(f"  [{label}] terminated (PID {proc.pid})")

    deadline = time.time() + 5
    for name, proc in processes.items():
        remaining = max(0.1, deadline - time.time())
        try:
            proc.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            proc.kill()
            print(f"  [{SERVICES[name]['label']}] killed (PID {proc.pid})")

    print("All services stopped.")
    sys.exit(0)


def main():
    args = set(sys.argv[1:])

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print("=" * 50)
    print("  AgelClaw Agent System (local dev)")
    print("=" * 50)

    for name, info in SERVICES.items():
        if info["flag"] in args:
            print(f"  [{info['label']}] skipped ({info['flag']})")
            continue
        # Skip if already running on its port
        port = info.get("port")
        if port and _port_in_use(port):
            print(f"  [{info['label']}] already running on :{port}, skipping")
            continue
        start_service(name, info["module"], info["label"])

    if not processes:
        print("No services to run.")
        return

    print(f"\n{len(processes)} services running. Press Ctrl+C to stop.\n")

    while not shutting_down:
        time.sleep(2)
        all_dead = True
        for name, proc in list(processes.items()):
            if proc.poll() is not None:
                label = SERVICES[name]["label"]
                code = proc.returncode
                print(f"  [{label}] exited (code {code}), restarting...")
                start_service(name, SERVICES[name]["module"], label)
            else:
                all_dead = False

        if all_dead:
            print("All services exited.")
            break


if __name__ == "__main__":
    main()
