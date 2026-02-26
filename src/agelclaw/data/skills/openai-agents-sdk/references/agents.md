# Agent Configuration

## Agent Parameters

```python
from agents import Agent, ModelSettings

agent = Agent(
    name="My Agent",              # Required: identifier
    instructions="System prompt",  # str or callable(ctx, agent) -> str
    model="gpt-4.1",              # Model name or Model object
    model_settings=ModelSettings(  # Optional model config
        temperature=0.7,
        tool_choice="auto",       # "auto"|"required"|"none"|"<tool_name>"
        extra_args={"service_tier": "flex"},
    ),
    tools=[...],                  # List of tools
    mcp_servers=[...],            # MCP server instances
    handoffs=[...],               # Agent or Handoff objects
    output_type=MyModel,          # Pydantic model for structured output
    reset_tool_choice=True,       # Prevent tool-call loops (default)
    tool_use_behavior="run_llm_again",  # See below
    prompt={                      # OpenAI platform prompt template
        "id": "pmpt_123",
        "version": "1",
        "variables": {"style": "haiku"},
    },
)
```

## Structured Output

```python
from pydantic import BaseModel

class CalendarEvent(BaseModel):
    name: str
    date: str
    participants: list[str]

agent = Agent(
    name="Calendar extractor",
    instructions="Extract calendar events from text",
    output_type=CalendarEvent,
)
```

## Dynamic Instructions

```python
def dynamic_instructions(
    context: RunContextWrapper[UserContext], agent: Agent[UserContext]
) -> str:
    return f"User: {context.context.name}. Help them."

agent = Agent[UserContext](name="Personal", instructions=dynamic_instructions)
```

## Cloning

```python
pirate = Agent(name="Pirate", instructions="Write like a pirate", model="gpt-5.2")
robot = pirate.clone(name="Robot", instructions="Write like a robot")
```

## Tool Use Behavior

Controls what happens after tools execute:

- `"run_llm_again"` (default): Tools run, LLM processes results
- `"stop_on_first_tool"`: Stop after first tool call, return output directly
- `StopAtTools(stop_at_tool_names=["tool_a"])`: Stop only for specific tools
- Custom callable: `(ctx, tool_results) -> ToolsToFinalOutputResult`

```python
from agents.agent import StopAtTools, ToolsToFinalOutputResult

# Stop at specific tools
agent = Agent(
    tools=[get_weather, sum_numbers],
    tool_use_behavior=StopAtTools(stop_at_tool_names=["get_weather"]),
)

# Custom handler
def custom_handler(ctx, tool_results):
    for result in tool_results:
        if "sunny" in (result.output or ""):
            return ToolsToFinalOutputResult(is_final_output=True, final_output=result.output)
    return ToolsToFinalOutputResult(is_final_output=False, final_output=None)

agent = Agent(tools=[get_weather], tool_use_behavior=custom_handler)
```

## Lifecycle Hooks

```python
from agents import AgentHooks

class MyHooks(AgentHooks):
    async def on_start(self, context, agent): ...
    async def on_end(self, context, agent, output): ...
    async def on_handoff(self, context, agent, source): ...
    async def on_tool_start(self, context, agent, tool): ...
    async def on_tool_end(self, context, agent, tool, result): ...
```
