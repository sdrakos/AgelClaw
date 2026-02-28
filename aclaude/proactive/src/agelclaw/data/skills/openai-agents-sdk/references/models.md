# Models

## Default Model
Default: `gpt-4.1`. Recommended upgrade: `gpt-5.2`.

### Override Default

```bash
export OPENAI_DEFAULT_MODEL=gpt-5.2
```

```python
result = await Runner.run(agent, "Hello", run_config=RunConfig(model="gpt-5.2"))
```

## Two API Backends

- **OpenAIResponsesModel** (recommended): Responses API — supports all features
- **OpenAIChatCompletionsModel**: Chat Completions API — broader provider compatibility

```python
from agents.extensions.models.litellm_model import LitellmModel
from agents import OpenAIChatCompletionsModel

# Use Chat Completions explicitly
agent = Agent(
    model=OpenAIChatCompletionsModel(model="gpt-5-nano", openai_client=AsyncOpenAI()),
)
```

## LiteLLM (100+ Models)

```bash
pip install "openai-agents[litellm]"
```

```python
from agents.extensions.models.litellm_model import LitellmModel

agent = Agent(
    name="Claude Agent",
    model=LitellmModel(model="anthropic/claude-3-5-sonnet-20240620", api_key="..."),
    model_settings=ModelSettings(include_usage=True),  # Enable usage tracking
)

# Or use the shorthand prefix
agent = Agent(model="litellm/anthropic/claude-3-5-sonnet-20240620")
```

## Model Settings

```python
from agents import ModelSettings
from openai.types.shared import Reasoning

agent = Agent(
    model_settings=ModelSettings(
        temperature=0.7,
        tool_choice="auto",
        reasoning=Reasoning(effort="high"),  # For GPT-5.x
        verbosity="low",
        extra_args={"service_tier": "flex", "user": "user_123"},
    ),
)
```

## Mixing Models in One Workflow

```python
researcher = Agent(name="Researcher", model="gpt-5.2")
writer = Agent(name="Writer", model="gpt-4.1")
checker = Agent(
    name="Checker",
    model=LitellmModel(model="anthropic/claude-3-5-sonnet", api_key="..."),
)

orchestrator = Agent(
    name="Orchestrator",
    tools=[
        researcher.as_tool(tool_name="research", tool_description="Research topics"),
        writer.as_tool(tool_name="write", tool_description="Write content"),
        checker.as_tool(tool_name="check", tool_description="Check quality"),
    ],
)
```

## Custom Provider

```python
from agents import set_default_openai_client
from openai import AsyncOpenAI

client = AsyncOpenAI(base_url="https://my-provider.com/v1", api_key="...")
set_default_openai_client(client)
```

## Troubleshooting

- **Tracing 401**: `set_tracing_disabled(True)` or `set_tracing_export_api_key(...)`
- **Responses API not supported**: `set_default_openai_api("chat_completions")`
- **Structured output fails**: Use provider with JSON schema support
- **Pydantic warnings (LiteLLM)**: `export OPENAI_AGENTS_ENABLE_LITELLM_SERIALIZER_PATCH=true`
