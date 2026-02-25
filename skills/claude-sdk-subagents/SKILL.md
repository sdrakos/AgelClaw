---
name: claude-sdk-subagents
description: >-
  Build multi-agent systems using the Claude Agent SDK's subagents feature.
  Use when creating subagents, spawning child agents, delegating tasks to
  specialized agents, running agents in parallel, restricting agent tools,
  resuming agents, or building orchestrator/worker patterns with the Anthropic
  Claude Agent SDK (Python or TypeScript). Triggers on subagent, child agent,
  agent delegation, parallel agents, AgentDefinition, Task tool, multi-agent
  workflow, agent orchestration.
---

# Claude SDK Subagents

Subagents are separate Claude instances spawned via the `Task` tool to handle focused subtasks
with isolated context, parallel execution, and restricted tool access.

## Core Rules

1. `Task` MUST be in `allowed_tools` / `allowedTools`
2. Subagents CANNOT spawn their own subagents (never put `Task` in a subagent's tools)
3. Claude auto-delegates based on `description` — or force it: `"Use the X agent to..."`
4. Built-in `general-purpose` subagent is always available when `Task` is allowed

## Quick Start (Python)

```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition

async def main():
    async for message in query(
        prompt="Review the auth module for security issues",
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Grep", "Glob", "Task"],
            agents={
                "code-reviewer": AgentDefinition(
                    description="Code review specialist. Use for quality and security reviews.",
                    prompt="You are a code review specialist. Find vulnerabilities and suggest fixes.",
                    tools=["Read", "Grep", "Glob"],
                    model="sonnet",
                ),
            },
        ),
    ):
        if hasattr(message, "result"):
            print(message.result)

asyncio.run(main())
```

## AgentDefinition

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `description` | `string` | Yes | When to use this agent — Claude matches tasks to this |
| `prompt` | `string` | Yes | System prompt defining role and behavior |
| `tools` | `string[]` | No | Omit = inherits all. Specify to restrict |
| `model` | `'sonnet'`\|`'opus'`\|`'haiku'`\|`'inherit'` | No | Defaults to main model |

## Tool Restriction Patterns

| Use Case | Tools | Why |
|----------|-------|-----|
| Read-only analysis | `Read`, `Grep`, `Glob` | Safe: can't modify or execute |
| Test execution | `Bash`, `Read`, `Grep` | Can run commands + read results |
| Code modification | `Read`, `Edit`, `Write`, `Grep`, `Glob` | Full read/write, no shell |
| Full access | _(omit `tools`)_ | Inherits everything from parent |

## Reference Files

| Topic | File | When to Read |
|-------|------|-------------|
| Multiple subagents & parallel | `references/parallel.md` | Multi-agent setups, factory patterns |
| Resume & session persistence | `references/resume.md` | Resuming subagents, capturing session/agent IDs |
| Event detection | `references/events.md` | Detecting subagent invocation and messages |
| TypeScript examples | `references/typescript.md` | All patterns in TypeScript |
| Filesystem agents | `references/filesystem.md` | `.claude/agents/` markdown-based agents |
| Troubleshooting | `references/troubleshooting.md` | Common issues and solutions |

## Starter Templates

| Template | File | Description |
|----------|------|-------------|
| Single subagent | `scripts/single_subagent.py` | Minimal working example |
| Parallel review | `scripts/parallel_review.py` | 3 subagents running in parallel |
| Resume flow | `scripts/resume_subagent.py` | Capture + resume a subagent |
