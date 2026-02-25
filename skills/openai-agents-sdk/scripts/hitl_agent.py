"""
Human-in-the-Loop Agent Template
=================================
Demonstrates tool approval flow with state serialization.

Usage:
    pip install openai-agents
    export OPENAI_API_KEY=sk-...
    python hitl_agent.py
"""

import asyncio
from agents import Agent, Runner, RunState, function_tool


# ── Tools with Approval ──────────────────────────────
@function_tool(needs_approval=True)
async def delete_record(record_id: str) -> str:
    """Delete a record permanently.

    Args:
        record_id: The ID of the record to delete.
    """
    return f"Record {record_id} deleted permanently."


async def needs_review_for_large_amounts(ctx, params, call_id) -> bool:
    """Only require approval for transfers over $100."""
    amount = float(params.get("amount", 0))
    return amount > 100


@function_tool(needs_approval=needs_review_for_large_amounts)
async def transfer_funds(from_account: str, to_account: str, amount: float) -> str:
    """Transfer funds between accounts.

    Args:
        from_account: Source account ID.
        to_account: Destination account ID.
        amount: Amount to transfer.
    """
    return f"Transferred ${amount:.2f} from {from_account} to {to_account}"


@function_tool
async def check_balance(account_id: str) -> str:
    """Check account balance (no approval needed).

    Args:
        account_id: The account to check.
    """
    return f"Account {account_id} balance: $1,234.56"


# ── Agent ─────────────────────────────────────────────
agent = Agent(
    name="Banking Assistant",
    instructions="""You help with banking operations.
Some operations require human approval before executing.""",
    tools=[delete_record, transfer_funds, check_balance],
)


# ── Approval Loop ────────────────────────────────────
async def main():
    result = await Runner.run(agent, "Transfer $500 from ACC-001 to ACC-002")

    while result.interruptions:
        print("\n--- Approval Required ---")
        state = result.to_state()

        for interruption in result.interruptions:
            print(f"Tool: {interruption.name}")
            print(f"Args: {interruption.arguments}")
            answer = input("Approve? [y/N]: ").strip().lower()

            if answer in ("y", "yes"):
                state.approve(interruption)
                print("Approved.")
            else:
                state.reject(interruption)
                print("Rejected.")

        result = await Runner.run(agent, state)

    print(f"\nResult: {result.final_output}")


if __name__ == "__main__":
    asyncio.run(main())
