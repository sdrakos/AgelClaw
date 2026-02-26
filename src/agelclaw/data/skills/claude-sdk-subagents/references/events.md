# Detecting Subagent Activity

## Python

```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition

async def main():
    async for message in query(
        prompt="Use the code-reviewer agent to review this codebase",
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Glob", "Grep", "Task"],
            agents={
                "code-reviewer": AgentDefinition(
                    description="Expert code reviewer.",
                    prompt="Analyze code quality and suggest improvements.",
                    tools=["Read", "Glob", "Grep"],
                ),
            },
        ),
    ):
        # Detect when subagent is spawned (Task tool_use block)
        if hasattr(message, "content") and message.content:
            for block in message.content:
                if getattr(block, "type", None) == "tool_use" and block.name == "Task":
                    print(f"Subagent invoked: {block.input.get('subagent_type')}")

        # Detect messages FROM inside a subagent
        if hasattr(message, "parent_tool_use_id") and message.parent_tool_use_id:
            print("  (running inside subagent)")

        # Final result
        if hasattr(message, "result"):
            print(message.result)

asyncio.run(main())
```

## TypeScript

```typescript
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "Use the code-reviewer agent to review this codebase",
  options: {
    allowedTools: ["Read", "Glob", "Grep", "Task"],
    agents: {
      "code-reviewer": {
        description: "Expert code reviewer.",
        prompt: "Analyze code quality and suggest improvements.",
        tools: ["Read", "Glob", "Grep"],
      },
    },
  },
})) {
  const msg = message as any;

  // Detect subagent invocation
  for (const block of msg.message?.content ?? []) {
    if (block.type === "tool_use" && block.name === "Task") {
      console.log(`Subagent invoked: ${block.input.subagent_type}`);
    }
  }

  // Messages from within a subagent
  if (msg.parent_tool_use_id) {
    console.log("  (running inside subagent)");
  }

  if ("result" in message) console.log(message.result);
}
```

## Message Structure Notes

- **Python**: content blocks accessed via `message.content` directly
- **TypeScript**: `SDKAssistantMessage` wraps the API message, so use `message.message.content`
- `parent_tool_use_id` is set on messages that originate from within a subagent's execution
- `session_id` appears on `ResultMessage` — capture it for resume flows
