# Guardrails

## Three Types

### 1. Input Guardrails
Run on initial user input. Only fire if agent is the first agent.

```python
from agents import input_guardrail, GuardrailFunctionOutput, Agent, Runner

@input_guardrail
async def check_profanity(ctx, agent, input_data):
    has_profanity = "bad" in str(input_data).lower()
    return GuardrailFunctionOutput(
        output_info={"flagged": has_profanity},
        tripwire_triggered=has_profanity,
    )

agent = Agent(
    name="Assistant",
    input_guardrails=[check_profanity],
)

try:
    result = await Runner.run(agent, "bad input")
except InputGuardrailTripwireTriggered:
    print("Input blocked by guardrail")
```

**Execution modes:**
- Parallel (default): Best latency, agent may consume tokens before cancellation
- Blocking: Guardrail completes before agent starts

### 2. Output Guardrails
Run on final agent output. Only fire if agent is the last agent.

```python
from agents import output_guardrail, GuardrailFunctionOutput

@output_guardrail
async def check_output(ctx, agent, output):
    is_harmful = "harmful" in str(output).lower()
    return GuardrailFunctionOutput(
        output_info={"harmful": is_harmful},
        tripwire_triggered=is_harmful,
    )

agent = Agent(
    name="Assistant",
    output_guardrails=[check_output],
)
```

### 3. Tool Guardrails
Wrap function tools. Validate before/after tool execution.

```python
from agents import tool_input_guardrail, tool_output_guardrail

@tool_input_guardrail
async def validate_tool_input(ctx, agent, tool_call):
    # Can skip call, replace output, or trigger tripwire
    return GuardrailFunctionOutput(tripwire_triggered=False)

@tool_output_guardrail
async def validate_tool_output(ctx, agent, tool_output):
    return GuardrailFunctionOutput(tripwire_triggered=False)
```

## Tripwires
When `tripwire_triggered=True`, raises exception and halts agent execution immediately.

## Global Guardrails (via RunConfig)
```python
config = RunConfig(
    input_guardrails=[check_profanity],
    output_guardrails=[check_output],
)
result = await Runner.run(agent, input, run_config=config)
```
