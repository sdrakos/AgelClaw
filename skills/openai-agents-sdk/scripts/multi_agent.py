"""
Multi-Agent Template
====================
Demonstrates both orchestration patterns:
1. Handoffs (triage → specialist)
2. Agents-as-tools (manager → sub-agents)

Usage:
    pip install openai-agents
    export OPENAI_API_KEY=sk-...
    python multi_agent.py
"""

import asyncio
from dataclasses import dataclass
from agents import Agent, Runner, RunContextWrapper, function_tool, handoff


# ── Shared Context ────────────────────────────────────
@dataclass
class AppContext:
    user_id: str
    user_name: str


# ── Tools ─────────────────────────────────────────────
@function_tool
def get_order_status(ctx: RunContextWrapper[AppContext], order_id: str) -> str:
    """Check the status of an order.

    Args:
        order_id: The order ID to look up.
    """
    return f"Order {order_id} for {ctx.context.user_name}: shipped, arriving tomorrow."


@function_tool
def process_refund(ctx: RunContextWrapper[AppContext], order_id: str, reason: str) -> str:
    """Process a refund for an order.

    Args:
        order_id: The order ID.
        reason: Reason for refund.
    """
    return f"Refund processed for order {order_id}. Reason: {reason}"


@function_tool
def search_faq(query: str) -> str:
    """Search the FAQ knowledge base.

    Args:
        query: Search query.
    """
    return f"FAQ result for '{query}': Check our help center at help.example.com"


# ── Specialist Agents ────────────────────────────────
orders_agent = Agent[AppContext](
    name="Orders specialist",
    instructions="You handle order inquiries. Use get_order_status to look up orders.",
    tools=[get_order_status],
)

refunds_agent = Agent[AppContext](
    name="Refunds specialist",
    instructions="You handle refund requests. Use process_refund to issue refunds.",
    tools=[process_refund],
)

faq_agent = Agent[AppContext](
    name="FAQ specialist",
    instructions="You answer general questions using the FAQ.",
    tools=[search_faq],
)


# ── Pattern 1: Handoffs (Triage) ─────────────────────
triage_agent = Agent[AppContext](
    name="Triage",
    instructions="""You are the first point of contact for customers.
Determine the user's need and hand off to the right specialist:
- Order questions → Orders specialist
- Refund requests → Refunds specialist
- General questions → FAQ specialist""",
    handoffs=[orders_agent, refunds_agent, faq_agent],
)


# ── Pattern 2: Manager with Sub-Agents as Tools ──────
manager_agent = Agent[AppContext](
    name="Manager",
    instructions="""You coordinate specialist agents to solve customer problems.
Call the relevant tool for each sub-task. Combine results into a clear response.""",
    tools=[
        orders_agent.as_tool(
            tool_name="check_orders",
            tool_description="Check order status and delivery info",
        ),
        refunds_agent.as_tool(
            tool_name="handle_refund",
            tool_description="Process refund requests",
        ),
        faq_agent.as_tool(
            tool_name="search_faq",
            tool_description="Search FAQ for general questions",
        ),
    ],
)


# ── Run ───────────────────────────────────────────────
async def main():
    ctx = AppContext(user_id="user_123", user_name="Stefanos")

    print("=== Pattern 1: Handoffs (Triage) ===")
    result = await Runner.run(
        triage_agent,
        "I'd like a refund for order ORD-456",
        context=ctx,
    )
    print(f"Final agent: {result.last_agent.name}")
    print(f"Output: {result.final_output}\n")

    print("=== Pattern 2: Manager ===")
    result = await Runner.run(
        manager_agent,
        "Check order ORD-789 and also find info about return policies",
        context=ctx,
    )
    print(f"Output: {result.final_output}")


if __name__ == "__main__":
    asyncio.run(main())
