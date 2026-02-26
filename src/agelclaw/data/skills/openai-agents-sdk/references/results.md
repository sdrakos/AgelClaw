# Results & Usage

## RunResult Properties

```python
result = await Runner.run(agent, "Hello")

result.final_output       # str or output_type instance
result.last_agent          # Agent that produced the output
result.new_items           # List[RunItem] generated during run
result.to_input_list()     # Convert to input for next run
result.last_response_id    # Latest model response ID
result.raw_responses       # List[ModelResponse]
result.input               # Original input
result.interruptions       # Pending tool approvals (HITL)

# Guardrail results
result.input_guardrail_results
result.output_guardrail_results
result.tool_input_guardrail_results
result.tool_output_guardrail_results

# Type casting
result.final_output_as(MyModel, validate=True)

# Memory optimization
result.release_agents()
```

## RunItem Types

- `MessageOutputItem` — LLM text messages
- `ToolCallItem` — Tool invocations
- `ToolCallOutputItem` — Tool responses
- `HandoffCallItem` — Handoff invocations
- `HandoffOutputItem` — Completed handoffs
- `ReasoningItem` — LLM reasoning

## Usage Tracking

```python
result = await Runner.run(agent, "Hello")
usage = result.context_wrapper.usage

print(f"Requests: {usage.requests}")
print(f"Input tokens: {usage.input_tokens}")
print(f"Output tokens: {usage.output_tokens}")
print(f"Total tokens: {usage.total_tokens}")

# Per-request breakdown
for i, req in enumerate(usage.request_usage_entries):
    print(f"Request {i+1}: {req.input_tokens} in, {req.output_tokens} out")
```

## Usage in Hooks

```python
from agents import RunHooks

class MyHooks(RunHooks):
    async def on_agent_end(self, context, agent, output):
        u = context.usage
        print(f"{agent.name}: {u.requests} requests, {u.total_tokens} tokens")
```

## Usage with Sessions

Each `Runner.run()` returns usage for that specific execution only.
Previous messages re-fed as context affect input token counts.

## Visualization

```bash
pip install "openai-agents[viz]"
```

```python
from agents.extensions.visualization import draw_graph

draw_graph(triage_agent)              # Display in notebook
draw_graph(triage_agent).view()       # Open in window
draw_graph(triage_agent, filename="agent_graph")  # Save PNG
```

## REPL (Interactive Testing)

```python
from agents import Agent, run_demo_loop

agent = Agent(name="Assistant", instructions="You are helpful.")
await run_demo_loop(agent)  # Interactive terminal chat
```
