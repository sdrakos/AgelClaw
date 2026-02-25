---
name: openai-agents-sdk
description: >-
  Build AI agent applications using the OpenAI Agents SDK (openai-agents-python).
  Use when creating agents, multi-agent systems, sub-agents, tools, handoffs,
  guardrails, voice pipelines, realtime agents, MCP integrations, or any
  OpenAI agent workflow. Triggers on "openai agent", "agents sdk", "sub-agent",
  "multi-agent", "agent handoff", "voice agent", "realtime agent".
---

# OpenAI Agents SDK

Build production agent applications with `openai-agents`. This skill covers the full SDK:
agents, tools, handoffs, context, guardrails, streaming, sessions, MCP, voice, and realtime.

## Quick Start

```bash
pip install openai-agents
# Optional extras:
pip install "openai-agents[litellm]"    # Non-OpenAI models
pip install "openai-agents[voice]"      # Voice pipeline
pip install "openai-agents[viz]"        # Visualization
pip install "openai-agents[sqlalchemy]" # SQLAlchemy sessions
```

## Core Pattern

```python
from agents import Agent, Runner, function_tool

@function_tool
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Sunny in {city}"

agent = Agent(
    name="Assistant",
    instructions="You are helpful.",
    model="gpt-4.1",  # or "gpt-5.2" for higher quality
    tools=[get_weather],
)

result = await Runner.run(agent, "What's the weather in Tokyo?")
print(result.final_output)
```

## Skill Structure

For detailed API reference on each topic, read the corresponding reference file:

| Topic | Reference File | When to Use |
|-------|---------------|-------------|
| Agent config | `references/agents.md` | Agent params, output_type, cloning, hooks, tool_use_behavior |
| Running agents | `references/running.md` | Runner.run, run_sync, run_streamed, max_turns, conversations |
| Tools | `references/tools.md` | function_tool, FunctionTool, agents-as-tools, timeouts, errors |
| Handoffs | `references/handoffs.md` | Agent delegation, input filters, handoff callbacks |
| Context | `references/context.md` | RunContextWrapper, dependency injection, ToolContext |
| Multi-agent | `references/multi-agent.md` | Orchestration patterns (LLM vs code), manager/handoff patterns |
| Guardrails | `references/guardrails.md` | Input/output/tool guardrails, tripwires |
| Streaming | `references/streaming.md` | run_streamed, stream_events, raw events, progress |
| Sessions | `references/sessions.md` | SQLiteSession, SQLAlchemySession, AdvancedSQLiteSession, branching |
| MCP | `references/mcp.md` | MCP server integration (stdio, HTTP, hosted), tool filtering |
| Human-in-loop | `references/hitl.md` | Tool approval, RunState serialization, resume |
| Models | `references/models.md` | OpenAI, LiteLLM, custom providers, model mixing |
| Voice | `references/voice.md` | VoicePipeline, STT/TTS, audio streaming |
| Realtime | `references/realtime.md` | RealtimeAgent, WebSocket, SIP, low-latency voice |
| Results & Usage | `references/results.md` | RunResult, usage tracking, new_items |
| Starter templates | `scripts/` | Ready-to-run agent templates |

## Architecture Decision Guide

### Single Agent
Use when: one domain, simple task.
```python
agent = Agent(name="Helper", instructions="...", tools=[...])
result = await Runner.run(agent, input)
```

### Multi-Agent with Handoffs
Use when: distinct specializations, user-facing routing.
```python
triage = Agent(name="Triage", handoffs=[billing_agent, support_agent])
```

### Multi-Agent with Agents-as-Tools (Manager Pattern)
Use when: orchestrator controls sub-agents, needs results back.
```python
manager = Agent(name="Manager", tools=[
    specialist.as_tool(tool_name="specialist", tool_description="..."),
])
```

### Code Orchestration
Use when: deterministic flow, parallel execution, cost control.
```python
r1, r2 = await asyncio.gather(
    Runner.run(agent_a, input_a),
    Runner.run(agent_b, input_b),
)
```

## Key Patterns

### Structured Output
```python
from pydantic import BaseModel
class Answer(BaseModel):
    summary: str
    confidence: float

agent = Agent(name="Analyst", output_type=Answer)
result = await Runner.run(agent, "Analyze this data")
print(result.final_output.summary)  # typed access
```

### Conversation Persistence (Sessions)
```python
from agents import SQLiteSession
session = SQLiteSession("conv_123")
r1 = await Runner.run(agent, "Hello", session=session)
r2 = await Runner.run(agent, "Follow up", session=session)  # has history
```

### Dynamic Instructions
```python
def instructions(ctx: RunContextWrapper[MyCtx], agent: Agent) -> str:
    return f"User is {ctx.context.name}. Help them."
agent = Agent(name="Personal", instructions=instructions)
```

### Human-in-the-Loop
```python
@function_tool(needs_approval=True)
async def delete_record(id: int) -> str: ...

result = await Runner.run(agent, input)
if result.interruptions:
    state = result.to_state()
    state.approve(result.interruptions[0])
    result = await Runner.run(agent, state)
```

### Streaming
```python
result = Runner.run_streamed(agent, "Tell me a story")
async for event in result.stream_events():
    if event.type == "raw_response_event":
        # token-by-token
    elif event.type == "run_item_stream_event":
        # tool calls, messages
```

## Critical Notes

- Default model: `gpt-4.1`. Upgrade to `gpt-5.2` for quality.
- All agents/tools in a run share the same context type.
- `Runner.run()` is async; `Runner.run_sync()` for sync code.
- `max_turns` prevents infinite loops. Handle `MaxTurnsExceeded`.
- Tool functions: use `@function_tool` decorator, docstring becomes description.
- First param can be `RunContextWrapper` or `ToolContext` (auto-injected, not in schema).
- Handoffs appear as `transfer_to_<agent_name>` tools to the LLM.
- Sessions: `SQLiteSession` for dev, `SQLAlchemySession` for production.
- `reset_tool_choice=True` (default) prevents tool-calling loops.
