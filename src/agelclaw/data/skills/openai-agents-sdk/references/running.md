# Running Agents

## Three Run Methods

```python
from agents import Agent, Runner

agent = Agent(name="Assistant", instructions="You are helpful.")

# 1. Async (recommended)
result = await Runner.run(agent, "Hello")

# 2. Sync wrapper
result = Runner.run_sync(agent, "Hello")

# 3. Streaming
result = Runner.run_streamed(agent, "Hello")
async for event in result.stream_events():
    ...
```

## The Agent Loop

1. Call LLM with current agent + input
2. If `final_output` → loop ends
3. If handoff → update agent, restart loop
4. If tool calls → execute, append results, restart loop
5. If `max_turns` exceeded → raise `MaxTurnsExceeded`

## Run Parameters

```python
result = await Runner.run(
    agent,
    input="Hello",            # str or list of messages
    context=my_context,       # Injected into tools/hooks
    max_turns=10,             # Safety limit
    session=my_session,       # Conversation persistence
    run_config=RunConfig(...),# Global overrides
    previous_response_id=id,  # Server-managed conversations
    conversation_id=conv_id,  # OpenAI conversation
)
```

## RunConfig Options

```python
from agents import RunConfig

config = RunConfig(
    model="gpt-5.2",                    # Override model globally
    model_settings=ModelSettings(...),   # Override temperature etc.
    input_guardrails=[...],             # Global input guardrails
    output_guardrails=[...],            # Global output guardrails
    handoff_input_filter=my_filter,     # Global handoff filter
    tracing_disabled=False,             # Disable tracing
    tool_error_formatter=my_formatter,  # Custom tool error messages
)
```

## Conversation Management

### Manual (stateless)
```python
result = await Runner.run(agent, "First message")
# Build next input from previous result
new_input = result.to_input_list() + [{"role": "user", "content": "Follow up"}]
result = await Runner.run(agent, new_input)
```

### Sessions (automatic persistence)
```python
from agents import SQLiteSession

session = SQLiteSession("conv_123")
r1 = await Runner.run(agent, "Hello", session=session)
r2 = await Runner.run(agent, "Follow up", session=session)  # history included
```

### Server-Managed (conversation_id)
```python
from openai import AsyncOpenAI
client = AsyncOpenAI()
conversation = await client.conversations.create()

result = await Runner.run(agent, "Hello", conversation_id=conversation.id)
```

### Server-Managed (previous_response_id)
```python
result = await Runner.run(
    agent, "Hello",
    previous_response_id=None,
    auto_previous_response_id=True,
)
# result.last_response_id auto-chains next call
```

## Error Handling

```python
from agents import RunErrorHandlerInput, RunErrorHandlerResult

def on_max_turns(data: RunErrorHandlerInput[None]) -> RunErrorHandlerResult:
    return RunErrorHandlerResult(
        final_output="Turn limit reached. Please narrow your request.",
        include_in_history=False,
    )

result = Runner.run_sync(
    agent, "Complex task",
    max_turns=3,
    error_handlers={"max_turns": on_max_turns},
)
```

## Call Model Input Filter

Edit model input before each LLM call:

```python
from agents.run import CallModelData, ModelInputData

def trim_history(data: CallModelData[None]) -> ModelInputData:
    return ModelInputData(
        input=data.model_data.input[-5:],
        instructions=data.model_data.instructions,
    )

config = RunConfig(call_model_input_filter=trim_history)
```

## Exceptions

| Exception | When |
|-----------|------|
| `MaxTurnsExceeded` | Agent exceeded max_turns |
| `ModelBehaviorError` | LLM produced invalid output |
| `ToolTimeoutError` | Tool exceeded timeout |
| `UserError` | SDK misuse |
| `InputGuardrailTripwireTriggered` | Input guardrail fired |
| `OutputGuardrailTripwireTriggered` | Output guardrail fired |
