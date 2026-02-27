"""
CLI Entry Point
================
Click-based CLI for the agelclaw command.

Usage:
    agelclaw init [dir]
    agelclaw setup
    agelclaw daemon
    agelclaw web
    agelclaw telegram
    agelclaw status
    agelclaw chat
"""

import os
import sys
import socket
import subprocess

import click

from agelclaw import __version__


# ── Daemon auto-start helpers ────────────────────────────

def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def _ensure_daemon(daemon_port: int) -> subprocess.Popen | None:
    """Start the daemon if it's not already running. Returns the Popen or None."""
    if _port_in_use(daemon_port):
        click.echo(f"  Daemon already running on :{daemon_port}")
        return None

    click.echo(f"  Starting daemon on :{daemon_port} ...")
    creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        [sys.executable, "-m", "agelclaw", "daemon"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags,
    )
    click.echo(f"  Daemon started (pid {proc.pid})")
    return proc


def _stop_daemon(proc: subprocess.Popen | None):
    """Terminate a daemon subprocess if it's still running."""
    if proc and proc.poll() is None:
        click.echo("  Stopping daemon ...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name="agelclaw")
@click.option("--home", envvar="AGELCLAW_HOME", default=None,
              help="Override project directory (sets AGELCLAW_HOME).")
@click.option("-p", "--prompt", default=None,
              help="Single-shot: answer a prompt and exit.")
@click.pass_context
def main(ctx, home, prompt):
    """AgelClaw — Self-evolving AI agent with persistent memory and skills."""
    if home:
        os.environ["AGELCLAW_HOME"] = str(home)
        from agelclaw.project import reset_project_dir
        reset_project_dir()

    # No subcommand → interactive chat (like `claude`)
    if ctx.invoked_subcommand is None:
        import asyncio
        from agelclaw.core.config import load_config
        cfg = load_config()
        daemon_proc = _ensure_daemon(cfg.get("daemon_port", 8420))

        try:
            if prompt:
                # Single-shot mode: agelclaw -p "question"
                from agelclaw.cli import single_query
                asyncio.run(single_query(prompt))
            else:
                # Pure interactive mode
                from agelclaw.cli import main as cli_main
                asyncio.run(cli_main())
        finally:
            _stop_daemon(daemon_proc)


@main.command()
@click.argument("directory", required=False, default=None)
def init(directory):
    """Initialize a new AgelClaw project directory."""
    from agelclaw.project import init_project
    path = init_project(directory)
    click.echo(f"Project initialized at: {path}")
    click.echo()
    click.echo("Next steps:")
    click.echo("  agelclaw setup       — Configure API keys and settings")
    click.echo("  agelclaw telegram    — Start Telegram bot")
    click.echo("  agelclaw web         — Start web UI + API")


@main.command()
def setup():
    """Interactive setup wizard for API keys and settings."""
    from agelclaw.setup_wizard import main as wizard_main
    wizard_main()


@main.command()
def daemon():
    """Start the background task daemon (:8420)."""
    import asyncio
    from agelclaw.daemon import run_daemon
    asyncio.run(run_daemon())


@main.command()
@click.option("--production/--dev", default=True,
              help="Serve React build (production) or proxy to Vite (dev).")
@click.option("--no-open", is_flag=True, default=False,
              help="Don't open browser automatically.")
@click.option("--no-daemon", is_flag=True, default=False,
              help="Don't auto-start the daemon (run web only).")
def web(production, no_open, no_daemon):
    """Start the web UI + API server (:8000) and daemon (:8420)."""
    from agelclaw.api_server import app, API_PORT
    from agelclaw.core.config import load_config
    import threading
    import webbrowser
    import uvicorn

    cfg = load_config()
    daemon_port = cfg.get("daemon_port", 8420)
    daemon_proc = None

    sys.argv = ["agelclaw-web"]
    if production:
        sys.argv.append("--production")

    if not no_daemon:
        daemon_proc = _ensure_daemon(daemon_port)

    if not no_open:
        def _open_browser():
            import time
            time.sleep(1.5)
            webbrowser.open(f"http://localhost:{API_PORT}")
        threading.Thread(target=_open_browser, daemon=True).start()

    try:
        uvicorn.run(app, host="0.0.0.0", port=API_PORT)
    finally:
        _stop_daemon(daemon_proc)


@main.command()
@click.option("--no-daemon", is_flag=True, default=False,
              help="Don't auto-start the daemon.")
def telegram(no_daemon):
    """Start the Telegram bot and daemon (:8420)."""
    from agelclaw.core.config import load_config
    from agelclaw.telegram_bot import main as telegram_main

    daemon_proc = None
    if not no_daemon:
        cfg = load_config()
        daemon_proc = _ensure_daemon(cfg.get("daemon_port", 8420))

    try:
        telegram_main()
    finally:
        _stop_daemon(daemon_proc)


@main.command()
def status():
    """Show daemon status and task statistics."""
    import json
    from urllib.request import urlopen, Request
    from urllib.error import URLError

    from agelclaw.core.config import load_config
    cfg = load_config()
    daemon_port = cfg.get("daemon_port", 8420)

    click.echo("AgelClaw Status")
    click.echo("=" * 40)

    # Check daemon
    try:
        req = Request(f"http://localhost:{daemon_port}/status")
        resp = urlopen(req, timeout=3)
        data = json.loads(resp.read().decode())
        click.echo(f"  Daemon: running on :{daemon_port}")
        click.echo(f"  State: {data.get('state', '?')}")
        running = data.get("running_tasks", {})
        if running:
            click.echo(f"  Running tasks: {len(running)}")
            for tid, info in running.items():
                click.echo(f"    #{tid}: {info.get('title', '?')}")
        click.echo(f"  Last cycle: {data.get('last_cycle', 'never')}")
    except (URLError, OSError):
        click.echo(f"  Daemon: not running (port {daemon_port})")

    click.echo()

    # Task stats from memory
    try:
        from agelclaw.memory import Memory
        mem = Memory()
        stats = mem.get_task_stats()
        click.echo("  Task Statistics:")
        for key, val in stats.items():
            click.echo(f"    {key}: {val}")
    except Exception as e:
        click.echo(f"  Tasks: error loading ({e})")


@main.command()
def chat():
    """Interactive CLI chat with the agent."""
    import asyncio
    from agelclaw.cli import main as cli_main
    asyncio.run(cli_main())


@main.command()
def update():
    """Update AgelClaw to the latest version."""
    import subprocess

    click.echo(f"Current version: {__version__}")
    click.echo("Checking for updates...")
    click.echo()

    pip_url = "git+https://github.com/sdrakos/AgelClaw.git"

    # Try normal install first
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade",
         "--force-reinstall", "--no-deps", pip_url],
        capture_output=True, text=True,
    )

    # If .exe locked, retry with --user
    if result.returncode != 0 and "WinError 32" in (result.stderr or ""):
        click.echo("  Retrying with --user (exe is locked)...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade",
             "--force-reinstall", "--no-deps", "--user", pip_url],
            capture_output=False,
        )

    elif result.returncode != 0:
        # Show the error output
        if result.stdout:
            click.echo(result.stdout)
        if result.stderr:
            click.echo(result.stderr)

    click.echo()
    if result.returncode == 0:
        from importlib.metadata import version as get_version
        try:
            new_ver = get_version("agelclaw")
        except Exception:
            new_ver = "unknown"
        click.echo(f"AgelClaw updated successfully! (v{new_ver})")
    else:
        click.echo("Update failed. Check your internet connection and try again.")


@main.command()
@click.option("--version", "rel_version", default=None,
              help=f"Version to upload (default: {__version__})")
@click.option("--file", "extra_files", multiple=True,
              help="Extra file(s) to upload as release assets.")
def release(rel_version, extra_files):
    """Upload installer + assets to GitHub Release."""
    from agelclaw.release_upload import upload_release
    upload_release(version=rel_version, extra_files=list(extra_files) or None)


if __name__ == "__main__":
    main()
