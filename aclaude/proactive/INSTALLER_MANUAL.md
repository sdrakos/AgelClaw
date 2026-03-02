# AgelClaw Windows Installer — Manual

## What This Is

A complete build pipeline that turns the AgelClaw Python package into a native Windows installer (`AgelClaw-Setup-3.1.0.exe`). End users install AgelClaw like any desktop app — no Python, no git, no pip required.

## How It Works (Architecture)

```
Source Code (Python)
       │
       ▼
   ┌───────────┐
   │  Nuitka    │  Compiles Python → native .exe + bundled dependencies
   │ --standalone│  Output: build/AgelClaw.dist/  (~60-100MB)
   └─────┬─────┘
         │
         ├── AgelClaw.exe          Main executable (CLI, Web, Telegram, Daemon)
         ├── AgelClaw-Mem.exe      Copy of AgelClaw.exe (filename-based dispatch → mem_cli)
         ├── python-embed/         Bundled Python 3.12 embeddable (~12MB)
         │   └── python.exe        For MCP server scripts that need a real interpreter
         ├── agelclaw/data/        React UI, skills, templates, MCP servers
         └── *.dll, *.pyd          Python runtime + compiled dependencies
         │
         ▼
   ┌───────────┐
   │ Inno Setup │  Wraps everything into a single setup wizard
   └─────┬─────┘
         │
         ▼
   AgelClaw-Setup-3.1.0.exe       Final installer (~80-100MB)
```

## What Gets Bundled

| Component | Source | Purpose |
|-----------|--------|---------|
| **AgelClaw.exe** | Nuitka compile of `cli_entry.py` | Main entry point — all CLI commands |
| **AgelClaw-Mem.exe** | Binary copy of AgelClaw.exe | Memory CLI (`agelclaw-mem` replacement) |
| **python-embed/** | Python.org embeddable zip | Real Python interpreter for MCP server scripts |
| **agelclaw/data/react_dist/** | Pre-built React app | Web UI served by FastAPI |
| **agelclaw/data/skills/** | 15 bundled skills | PDF, Excel, email, etc. |
| **agelclaw/data/templates/** | Config templates | config.yaml, persona files |
| **agelclaw/data/mcp_servers/** | Bundled MCP servers | memory-tools (auto-loaded) |

## What Does NOT Get Bundled

| Component | Why | How It's Handled |
|-----------|-----|------------------|
| **Claude Code CLI** (`claude.exe`) | 236MB, requires npm | Installed during setup via `npm install -g @anthropic-ai/claude-code` |
| **Node.js** | System dependency | Installer checks if npm exists; warns if missing |
| **Buypage** | Separate marketing site | Not part of the agent — hosted online |
| **API keys** | User-specific secrets | Configured via `agelclaw setup` after install |

## The _nuitka_compat.py Module

Central compatibility layer. Every function has two paths:

```python
IS_COMPILED = hasattr(sys, "__compiled__") or getattr(sys, "frozen", False)
```

| Function | Dev Mode (pip install -e .) | Compiled Mode (Nuitka exe) |
|----------|---------------------------|---------------------------|
| `get_python_exe()` | `sys.executable` (current Python) | `<install>/python-embed/python.exe` |
| `get_agelclaw_exe()` | `sys.executable` | `sys.executable` (AgelClaw.exe) |
| `get_agelclaw_daemon_cmd()` | `[python, -m, agelclaw, daemon]` | `[<install>/AgelClaw.exe, daemon]` |
| `get_mem_cli_cmd()` | `[python, -m, agelclaw.mem_cli]` | `[<install>/AgelClaw-Mem.exe]` |

**Zero dev-mode impact.** When `IS_COMPILED` is `False`, every function returns the same value as before the installer was added. The existing `pip install -e .` workflow is 100% unchanged.

## AgelClaw-Mem.exe — Filename-Based Dispatch

Instead of compiling two separate executables (wasteful), `AgelClaw-Mem.exe` is a byte-for-byte copy of `AgelClaw.exe`. At startup, `cli_entry.py` checks:

```python
if IS_COMPILED and Path(sys.executable).stem.lower() == "agelclaw-mem":
    from agelclaw.mem_cli import main as mem_main
    raise SystemExit(mem_main() or 0)
```

If the running exe is named `agelclaw-mem`, it dispatches directly to `mem_cli.main()` instead of the Click CLI. This only triggers in compiled mode — dev mode never matches because `sys.executable` is `python.exe`.

## Files Modified in Existing Codebase

| File | What Changed | Dev Impact |
|------|-------------|------------|
| `cli_entry.py` | Daemon spawn uses `get_agelclaw_daemon_cmd()`, AgelClaw-Mem dispatch at top of `main()` | None — returns same command list |
| `daemon.py` | Notification script uses `get_python_exe()` instead of `sys.executable` | None — returns `sys.executable` |
| `agent_config.py` | MCP server Python resolution uses `get_python_exe()` | None — returns `sys.executable` |
| `project.py` | Startup script uses direct exe path when compiled | None — uses existing `cd /d` approach |

## Files Created

| File | Purpose |
|------|---------|
| `src/agelclaw/_nuitka_compat.py` | Runtime compatibility layer (IS_COMPILED, path helpers) |
| `build_installer.py` | Build orchestrator (Nuitka + embed + Inno Setup) |
| `installer.iss` | Inno Setup script (wizard, PATH, shortcuts, Claude CLI) |
| `assets/icon.ico` | Application icon for exe and installer |

## Build Steps (Developer Machine)

### Prerequisites

```bash
# Python packages
pip install nuitka ordered-set zstandard

# Inno Setup 6 (download and install)
# https://jrsoftware.org/isdl.php
# Default: C:\Program Files (x86)\Inno Setup 6\
```

### Build

```bash
cd proactive

# Full build (Nuitka + Python embed + Inno Setup)
python build_installer.py

# Nuitka only (skip installer packaging)
python build_installer.py --skip-inno

# Re-package only (already compiled, just rebuild installer)
python build_installer.py --skip-nuitka

# Skip Python embeddable download (already cached)
python build_installer.py --skip-embed
```

### Build Output

```
proactive/
├── build/
│   ├── AgelClaw.dist/              # Nuitka standalone output
│   │   ├── AgelClaw.exe            # Main executable
│   │   ├── AgelClaw-Mem.exe        # Memory CLI (copy)
│   │   ├── python-embed/           # Bundled Python
│   │   │   └── python.exe
│   │   ├── agelclaw/data/          # Bundled data
│   │   └── *.dll, *.pyd            # Runtime libs
│   ├── installer/
│   │   └── AgelClaw-Setup-3.1.0.exe   # Final installer
│   └── python-embed-3.12.8.zip     # Cached download
```

### Verification

```bash
# Test compiled exe
build\AgelClaw.dist\AgelClaw.exe --version
build\AgelClaw.dist\AgelClaw.exe daemon          # Should start on :8420
build\AgelClaw.dist\AgelClaw-Mem.exe context      # Should print memory context

# Test installer on clean machine (no Python)
# 1. Run AgelClaw-Setup-3.1.0.exe
# 2. Open terminal: agelclaw --version
# 3. agelclaw setup → configure API keys
# 4. agelclaw web → should open browser on :8000
```

## What the Installer Does (End User Experience)

1. **Welcome screen** with AgelClaw branding
2. **Select install location** (default: `C:\Program Files\AgelClaw\`)
3. **Choose components:**
   - [x] Add AgelClaw to PATH
   - [ ] Desktop shortcut
   - [ ] Start daemon on login
   - [x] Install Claude Code CLI (requires Node.js)
4. **Install files** → copies AgelClaw.dist/ to install dir
5. **Post-install:**
   - Adds install dir to user PATH (registry)
   - Runs `npm install -g @anthropic-ai/claude-code` (if Node.js found)
   - Runs `AgelClaw.exe init` (creates `~/.agelclaw/` with config templates)
   - Optionally creates daemon auto-start .bat in Windows Startup folder
6. **Offers to launch setup wizard** (`agelclaw setup`)
7. **Start Menu shortcuts:**
   - AgelClaw CLI (opens terminal with interactive chat)
   - AgelClaw Web UI (starts web server + opens browser)
   - AgelClaw Setup Wizard
   - Uninstall AgelClaw

### Uninstaller

- Removes all files from install directory
- Removes install dir from PATH (registry cleanup)
- Removes Start Menu shortcuts
- Does NOT delete `~/.agelclaw/` (user data, config, memory database)

## Build Pipeline Summary

```
python build_installer.py
  │
  ├─ Step 1: Nuitka --standalone
  │   cli_entry.py → build/AgelClaw.dist/AgelClaw.exe
  │   (includes all Python deps, agelclaw package, bundled data)
  │
  ├─ Step 2: Copy AgelClaw.exe → AgelClaw-Mem.exe
  │   (same binary, different filename = different behavior)
  │
  ├─ Step 3: Download Python 3.12.8 embeddable
  │   python.org → build/AgelClaw.dist/python-embed/
  │   (for MCP server scripts that need a real Python)
  │
  └─ Step 4: Inno Setup (ISCC.exe installer.iss)
      build/AgelClaw.dist/ → build/installer/AgelClaw-Setup-3.1.0.exe
      (single file, ~80-100MB, ready for distribution)
```
