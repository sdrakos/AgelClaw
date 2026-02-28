"""
Streaming Chat Template
========================
Interactive chat with streaming output and session persistence.

Usage:
    pip install openai-agents
    export OPENAI_API_KEY=sk-...
    python streaming_chat.py
"""

import asyncio
from openai.types.responses import ResponseTextDeltaEvent
from agents import Agent, Runner, SQLiteSession, function_tool, ItemHelpers


@function_tool
def get_current_time() -> str:
    """Get the current date and time."""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


agent = Agent(
    name="Chat Assistant",
    instructions="You are a helpful assistant. Be concise.",
    model="gpt-4.1",
    tools=[get_current_time],
)


async def main():
    session = SQLiteSession("interactive_chat")
    print("Chat with the agent (type 'quit' to exit)\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("quit", "exit"):
            break
        if not user_input:
            continue

        print("Agent: ", end="", flush=True)
        result = Runner.run_streamed(agent, user_input, session=session)

        async for event in result.stream_events():
            if event.type == "raw_response_event":
                if isinstance(event.data, ResponseTextDeltaEvent):
                    print(event.data.delta, end="", flush=True)
            elif event.type == "run_item_stream_event":
                if event.item.type == "tool_call_item":
                    print(f"\n  [calling tool...]", end="", flush=True)
                elif event.item.type == "tool_call_output_item":
                    print(f"\n  [tool result: {event.item.output[:100]}]", end="", flush=True)

        print()  # newline after response
        usage = result.context_wrapper.usage
        print(f"  ({usage.total_tokens} tokens)\n")


if __name__ == "__main__":
    asyncio.run(main())
