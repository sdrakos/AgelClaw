# Streaming

## Basic Streaming

```python
from agents import Agent, Runner

agent = Agent(name="Assistant", instructions="You are helpful.")

result = Runner.run_streamed(agent, "Tell me 5 jokes")
async for event in result.stream_events():
    ...
```

## Event Types

### 1. Raw Response Events (token-by-token)

```python
from openai.types.responses import ResponseTextDeltaEvent

async for event in result.stream_events():
    if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
        print(event.data.delta, end="", flush=True)
```

### 2. Run Item Events (high-level progress)

```python
from agents import ItemHelpers

async for event in result.stream_events():
    if event.type == "run_item_stream_event":
        if event.item.type == "tool_call_item":
            print("Tool called")
        elif event.item.type == "tool_call_output_item":
            print(f"Tool output: {event.item.output}")
        elif event.item.type == "message_output_item":
            print(f"Message: {ItemHelpers.text_message_output(event.item)}")
```

### 3. Agent Updated Events (handoffs)

```python
async for event in result.stream_events():
    if event.type == "agent_updated_stream_event":
        print(f"Agent changed to: {event.new_agent.name}")
```

## Complete Example

```python
import asyncio
from openai.types.responses import ResponseTextDeltaEvent
from agents import Agent, Runner, function_tool, ItemHelpers

@function_tool
def how_many_jokes() -> int:
    return random.randint(1, 10)

agent = Agent(
    name="Joker",
    instructions="First call how_many_jokes, then tell that many jokes.",
    tools=[how_many_jokes],
)

result = Runner.run_streamed(agent, "Hello")
async for event in result.stream_events():
    if event.type == "raw_response_event":
        if isinstance(event.data, ResponseTextDeltaEvent):
            print(event.data.delta, end="", flush=True)
    elif event.type == "run_item_stream_event":
        if event.item.type == "tool_call_item":
            print("\n[Tool called]")
        elif event.item.type == "tool_call_output_item":
            print(f"[Tool output: {event.item.output}]")
```

## Result After Streaming

`RunResultStreaming` contains full run info once streaming completes — same as `RunResult`.
