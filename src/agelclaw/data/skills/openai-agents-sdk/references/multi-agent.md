# Multi-Agent Orchestration

## Two Approaches

### 1. LLM-Driven Orchestration
Agent decides flow autonomously using tools + handoffs.

```python
triage = Agent(
    name="Triage",
    instructions="Route to specialist agents as needed.",
    handoffs=[billing_agent, support_agent, refund_agent],
    tools=[WebSearchTool(), get_account_info],
)
result = await Runner.run(triage, user_input)
```

**Best practices:**
- Invest in quality prompts
- Monitor and iterate
- Design focused specialist agents
- Build evaluation pipelines

### 2. Code-Driven Orchestration
Deterministic flow controlled by your code.

**Sequential chaining:**
```python
r1 = await Runner.run(researcher, "Find info about X")
r2 = await Runner.run(writer, f"Write article based on: {r1.final_output}")
```

**Parallel execution:**
```python
r1, r2, r3 = await asyncio.gather(
    Runner.run(agent_a, input_a),
    Runner.run(agent_b, input_b),
    Runner.run(agent_c, input_c),
)
```

**Conditional routing (structured output):**
```python
class Decision(BaseModel):
    route: str  # "billing" | "support"

router = Agent(name="Router", output_type=Decision)
result = await Runner.run(router, user_input)

if result.final_output.route == "billing":
    final = await Runner.run(billing_agent, user_input)
else:
    final = await Runner.run(support_agent, user_input)
```

**Evaluation loop:**
```python
for attempt in range(3):
    result = await Runner.run(writer, task)
    eval_result = await Runner.run(evaluator, result.final_output)
    if eval_result.final_output.quality >= 8:
        break
    task = f"Improve: {eval_result.final_output.feedback}\n\n{result.final_output}"
```

## Pattern: Manager with Sub-Agents as Tools

```python
manager = Agent(
    name="Manager",
    instructions="Coordinate specialists to solve the user's problem.",
    tools=[
        researcher.as_tool(tool_name="research", tool_description="Research a topic"),
        coder.as_tool(tool_name="write_code", tool_description="Write code"),
        reviewer.as_tool(tool_name="review", tool_description="Review work"),
    ],
)
```

## Pattern: Triage with Handoffs

```python
triage = Agent(
    name="Triage",
    instructions="Identify user need and hand off to the right specialist.",
    handoffs=[
        handoff(billing, tool_description_override="For billing questions"),
        handoff(support, tool_description_override="For technical support"),
    ],
)
```
