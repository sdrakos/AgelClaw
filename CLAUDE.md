# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

**AgelClaw v3.1.0** — a self-evolving autonomous assistant with multi-provider support (Claude + OpenAI), persistent memory, skills, and subagents.

**The detailed CLAUDE.md lives in `aclaude/CLAUDE.md`.** That is the primary working directory. This file covers the repo-wide layout only.

## Repository Layout

```
AGENTI_SDK/
├── aclaude/                      # ← Primary working directory (has its own CLAUDE.md)
│   ├── proactive/src/agelclaw/   # Python package source (always edit here, not proactive/*.py)
│   ├── proactive/react-claude-chat/  # React chat UI
│   ├── .Claude/Skills/           # Claude Code skills for this project
│   └── CLAUDE.md                 # Detailed dev guide (architecture, design decisions, commands)
├── Book_for_Agentic/             # Book/documentation project
└── Various standalone scripts    # claude.py, agent.py, etc. (experiments, not part of package)
```

## Quick Start

```bash
cd aclaude/proactive
pip install -e ".[all]"    # editable install with all extras
agelclaw init              # create project dir (~/.agelclaw/)
agelclaw setup             # interactive config wizard
agelclaw web               # Web UI :8000 + daemon :8420
```

## Key Rule

Source code lives in `proactive/src/agelclaw/`. Legacy flat files at `proactive/*.py` are older copies — **always edit under `proactive/src/agelclaw/`**.

No test suite, linting, or CI/CD for code quality. GitHub Actions CI builds release artifacts only.

See `aclaude/CLAUDE.md` for full architecture, design decisions, CLI reference, and configuration.
