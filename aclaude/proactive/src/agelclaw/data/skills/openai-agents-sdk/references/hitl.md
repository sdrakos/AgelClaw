# Human-in-the-Loop (HITL)

## Marking Tools for Approval

```python
from agents import function_tool

# Always require approval
@function_tool(needs_approval=True)
async def cancel_order(order_id: int) -> str:
    return f"Cancelled order {order_id}"

# Conditional approval
async def requires_review(ctx, params, call_id) -> bool:
    return "refund" in params.get("subject", "").lower()

@function_tool(needs_approval=requires_review)
async def send_email(subject: str, body: str) -> str:
    return f"Sent '{subject}'"
```

`needs_approval` works on: `function_tool`, `Agent.as_tool`, `ShellTool`, `ApplyPatchTool`, MCP servers.

## Approval Flow

1. Model emits tool call → runner checks `needs_approval`
2. If approval needed → run pauses, `result.interruptions` populated
3. Serialize: `state = result.to_state()`
4. Approve/reject: `state.approve(interruption)` / `state.reject(interruption)`
5. Resume: `result = await Runner.run(agent, state)`

## Complete Example

```python
from agents import Agent, Runner, RunState, function_tool

async def needs_oakland_approval(ctx, params, call_id) -> bool:
    return "Oakland" in params.get("city", "")

@function_tool(needs_approval=needs_oakland_approval)
async def get_temperature(city: str) -> str:
    return f"Temperature in {city} is 20°C"

agent = Agent(
    name="Weather assistant",
    instructions="Answer weather questions.",
    tools=[get_temperature],
)

async def main():
    result = await Runner.run(agent, "Temperature in Oakland?")

    while result.interruptions:
        state = result.to_state()

        # Serialize for storage (DB, queue, etc.)
        serialized = state.to_string()
        # ... later, deserialize
        state = await RunState.from_string(agent, serialized)

        for interruption in result.interruptions:
            approved = input(f"Approve {interruption.name}? [y/N]: ").lower() == "y"
            if approved:
                state.approve(interruption, always_approve=False)
            else:
                state.reject(interruption)

        result = await Runner.run(agent, state)

    print(result.final_output)
```

## Serialization Methods

```python
state = result.to_state()

# JSON
json_data = state.to_json()
state = await RunState.from_json(agent, json_data)

# String
string_data = state.to_string()
state = await RunState.from_string(agent, string_data)

# Exclude sensitive context
json_data = state.to_json(context_override=None)
```

## Durable Workflow Integrations
- **Temporal**: Durable, long-running workflows
- **Restate**: Lightweight durable agents
- **DBOS**: Reliable agents with progress preservation
