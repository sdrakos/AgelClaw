# Handoffs

Handoffs delegate tasks between specialized agents. They appear as `transfer_to_<agent_name>` tools to the LLM.

## Basic Handoff

```python
from agents import Agent, handoff

billing = Agent(name="Billing agent", instructions="Handle billing questions")
refund = Agent(name="Refund agent", instructions="Handle refunds")

triage = Agent(
    name="Triage agent",
    instructions="Route to billing or refund as needed",
    handoffs=[billing, handoff(refund)],  # Both forms work
)
```

## Customized Handoff

```python
from agents import handoff, RunContextWrapper

def on_handoff(ctx: RunContextWrapper[None]):
    print("Handoff triggered")

h = handoff(
    agent=target_agent,
    on_handoff=on_handoff,                          # Callback on handoff
    tool_name_override="route_to_specialist",       # Custom tool name
    tool_description_override="Route to specialist", # Custom description
    input_type=EscalationData,                      # Required input schema
    input_filter=my_filter,                         # Filter conversation history
    is_enabled=True,                                # bool or callable
)
```

## Handoff with Input Data

```python
from pydantic import BaseModel

class EscalationData(BaseModel):
    reason: str

async def on_handoff(ctx: RunContextWrapper[None], input_data: EscalationData):
    print(f"Escalation reason: {input_data.reason}")

h = handoff(agent=escalation_agent, on_handoff=on_handoff, input_type=EscalationData)
```

## Input Filters

Filter what conversation history the next agent sees:

```python
from agents.extensions import handoff_filters

h = handoff(
    agent=faq_agent,
    input_filter=handoff_filters.remove_all_tools,  # Remove tool history
)
```

## Recommended Prompt Pattern

```python
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX

billing = Agent(
    name="Billing",
    instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
    Handle billing inquiries.""",
)
```
