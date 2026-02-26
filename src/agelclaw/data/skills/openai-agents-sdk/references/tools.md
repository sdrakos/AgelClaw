# Tools

## Tool Types

1. **Hosted tools**: WebSearchTool, FileSearchTool, CodeInterpreterTool, ImageGenerationTool, HostedMCPTool, ShellTool
2. **Function tools**: `@function_tool` decorated Python functions
3. **Agents as tools**: `agent.as_tool(...)` for sub-agent invocation
4. **Local runtime**: ComputerTool, ShellTool (local), ApplyPatchTool

## Function Tools (@function_tool)

```python
from agents import function_tool, RunContextWrapper
from typing import Any

@function_tool
async def fetch_weather(city: str) -> str:
    """Fetch weather for a city.

    Args:
        city: The city name.
    """
    return f"Sunny in {city}"

@function_tool(name_override="read_data")
def read_file(ctx: RunContextWrapper[Any], path: str, directory: str | None = None) -> str:
    """Read file contents.

    Args:
        path: File path.
        directory: Optional directory.
    """
    return "<contents>"
```

**Key rules:**
- Docstring → tool description. Args section → parameter descriptions.
- First param can be `RunContextWrapper` or `ToolContext` (auto-injected, excluded from schema)
- Supports sync and async functions
- Return types: str, Pydantic model, ToolOutputImage, ToolOutputFileContent, ToolOutputText

## Custom FunctionTool

```python
from pydantic import BaseModel
from agents import FunctionTool, RunContextWrapper

class FunctionArgs(BaseModel):
    username: str
    age: int

async def run_function(ctx: RunContextWrapper[Any], args: str) -> str:
    parsed = FunctionArgs.model_validate_json(args)
    return f"{parsed.username} is {parsed.age}"

tool = FunctionTool(
    name="process_user",
    description="Process user data",
    params_json_schema=FunctionArgs.model_json_schema(),
    on_invoke_tool=run_function,
)
```

## Pydantic Field Constraints

```python
from typing import Annotated
from pydantic import Field

@function_tool
def score(value: Annotated[int, Field(ge=0, le=100, description="Score 0-100")]) -> str:
    return f"Score: {value}"
```

## Agents as Tools

```python
specialist = Agent(name="Specialist", instructions="...")

manager = Agent(
    name="Manager",
    tools=[
        specialist.as_tool(
            tool_name="ask_specialist",
            tool_description="Ask the specialist a question",
        ),
    ],
)
```

### Structured Input
```python
from pydantic import BaseModel, Field

class TranslationInput(BaseModel):
    text: str = Field(description="Text to translate")
    target: str = Field(description="Target language")

tool = translator.as_tool(
    tool_name="translate",
    tool_description="Translate text",
    parameters=TranslationInput,
    include_input_schema=True,
)
```

### Custom Output Extraction
```python
async def extract_json(run_result):
    for item in reversed(run_result.new_items):
        if isinstance(item, ToolCallOutputItem) and item.output.startswith("{"):
            return item.output
    return "{}"

tool = data_agent.as_tool(
    tool_name="get_data",
    tool_description="Get JSON data",
    custom_output_extractor=extract_json,
)
```

### Streaming Sub-Agent Events
```python
from agents import AgentToolStreamEvent

async def on_stream(event: AgentToolStreamEvent):
    print(f"[{event['agent'].name}] {event['event'].type}")

tool = sub_agent.as_tool(
    tool_name="helper",
    tool_description="...",
    on_stream=on_stream,
)
```

### Conditional Tool Enabling
```python
def is_enabled(ctx: RunContextWrapper[MyCtx], agent: AgentBase) -> bool:
    return ctx.context.feature_flag

tool = sub_agent.as_tool(
    tool_name="optional_tool",
    tool_description="...",
    is_enabled=is_enabled,  # bool or callable
)
```

## Timeouts

```python
@function_tool(timeout=2.0)
async def slow_lookup(query: str) -> str:
    await asyncio.sleep(10)
    return f"Result for {query}"

# Behaviors:
# timeout_behavior="error_as_result" (default) - returns error message to model
# timeout_behavior="raise_exception" - raises ToolTimeoutError
```

## Error Handling

```python
def my_error_handler(ctx: RunContextWrapper[Any], error: Exception) -> str:
    return "Internal error. Try again."

@function_tool(failure_error_function=my_error_handler)
def flaky_tool(data: str) -> str:
    raise ValueError("oops")
```

## Hosted Tools

```python
from agents import Agent, WebSearchTool, FileSearchTool, CodeInterpreterTool, ImageGenerationTool

agent = Agent(
    name="Research",
    tools=[
        WebSearchTool(),
        FileSearchTool(vector_store_ids=["vs_123"]),
        CodeInterpreterTool(),
        ImageGenerationTool(),
    ],
)
```

## ShellTool (Hosted Container)

```python
from agents import ShellTool

agent = Agent(
    name="Container Agent",
    tools=[
        ShellTool(environment={
            "type": "container_auto",
            "network_policy": {"type": "disabled"},
        })
    ],
)
```
