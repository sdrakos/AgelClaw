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

import click

from agelclaw import __version__


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
        if prompt:
            # Single-shot mode: agelclaw -p "question"
            from agelclaw.cli import single_query
            asyncio.run(single_query(prompt))
        else:
            # Pure interactive mode
            from agelclaw.cli import main as cli_main
            asyncio.run(cli_main())


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
def web(production):
    """Start the web UI + API server (:8000)."""
    from agelclaw.api_server import app, API_PORT
    import uvicorn

    sys.argv = ["agelclaw-web"]
    if production:
        sys.argv.append("--production")

    uvicorn.run(app, host="0.0.0.0", port=API_PORT)


@main.command()
def telegram():
    """Start the Telegram bot."""
    from agelclaw.telegram_bot import main as telegram_main
    telegram_main()


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
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade",
         "--force-reinstall", "--no-deps",
         "git+https://github.com/sdrakos/AgelClaw.git"],
        capture_output=False,
    )
    click.echo()
    if result.returncode == 0:
        # Show new version
        from importlib.metadata import version as get_version
        try:
            new_ver = get_version("agelclaw")
        except Exception:
            new_ver = "unknown"
        click.echo(f"AgelClaw updated successfully! (v{new_ver})")
    else:
        click.echo("Update failed. Check your internet connection and try again.")


if __name__ == "__main__":
    main()
