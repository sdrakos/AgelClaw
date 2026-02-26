# Context

Two types of context: **local** (dependency injection for your code) and **agent/LLM** (what the model sees).

## Local Context (RunContextWrapper)

Pass any Python object as context. Available in tools, hooks, guardrails.

```python
from dataclasses import dataclass
from agents import Agent, RunContextWrapper, Runner, function_tool

@dataclass
class UserInfo:
    name: str
    uid: int

@function_tool
async def fetch_user_age(wrapper: RunContextWrapper[UserInfo]) -> str:
    """Fetch user's age."""
    return f"{wrapper.context.name} is 47 years old"

agent = Agent[UserInfo](name="Assistant", tools=[fetch_user_age])

result = await Runner.run(agent, "What is the user's age?", context=UserInfo(name="John", uid=123))
```

**Rules:**
- All agents, tools, hooks in a run must share the same context type
- Context is NOT sent to the LLM
- First param `RunContextWrapper[T]` is auto-injected (excluded from tool schema)

## ToolContext (Extended Metadata)

```python
from agents.tool_context import ToolContext

@function_tool
def get_weather(ctx: ToolContext[MyContext], city: str) -> str:
    print(f"Tool: {ctx.tool_name}, Call ID: {ctx.tool_call_id}, Args: {ctx.tool_arguments}")
    return f"Sunny in {city}"
```

`ToolContext` extends `RunContextWrapper` with: `tool_name`, `tool_call_id`, `tool_arguments`.

## Making Data Available to the LLM

1. **Instructions** (static or dynamic): always-relevant info
2. **Input messages**: add context as user/system messages
3. **Function tools**: on-demand data retrieval
4. **Retrieval/web search**: hosted tools for external data
