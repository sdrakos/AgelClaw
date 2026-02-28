# Resuming Subagents

Resumed subagents retain their full conversation history (all tool calls, results, reasoning)
and pick up exactly where they stopped.

## Flow

1. **First run**: capture `session_id` + `agentId`
2. **Resume**: pass `resume=session_id` and reference the `agentId` in prompt

## Python

```python
import asyncio
import json
import re
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition

def extract_agent_id(text: str) -> str | None:
    """Extract agentId from Task tool result text."""
    match = re.search(r"agentId:\s*([a-f0-9-]+)", text)
    return match.group(1) if match else None

async def main():
    agent_id = None
    session_id = None

    # Define the subagent
    agents = {
        "analyzer": AgentDefinition(
            description="Codebase analyzer for architecture review.",
            prompt="Analyze code structure, patterns, and architecture.",
            tools=["Read", "Grep", "Glob"],
        ),
    }

    # Step 1: First invocation
    async for message in query(
        prompt="Use the analyzer agent to review the codebase architecture",
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Grep", "Glob", "Task"],
            agents=agents,
        ),
    ):
        if hasattr(message, "session_id"):
            session_id = message.session_id
        if hasattr(message, "content"):
            content_str = json.dumps(message.content, default=str)
            extracted = extract_agent_id(content_str)
            if extracted:
                agent_id = extracted
        if hasattr(message, "result"):
            print(message.result)

    # Step 2: Resume with follow-up question
    if agent_id and session_id:
        async for message in query(
            prompt=f"Resume agent {agent_id} and list the top 3 most complex modules",
            options=ClaudeAgentOptions(
                allowed_tools=["Read", "Grep", "Glob", "Task"],
                resume=session_id,   # Same session!
                agents=agents,       # Same agent definitions!
            ),
        ):
            if hasattr(message, "result"):
                print(message.result)

asyncio.run(main())
```

## TypeScript

```typescript
import { query, type SDKMessage } from "@anthropic-ai/claude-agent-sdk";

function extractAgentId(message: SDKMessage): string | undefined {
  if (!("message" in message)) return undefined;
  const content = JSON.stringify(message.message.content);
  const match = content.match(/agentId:\s*([a-f0-9-]+)/);
  return match?.[1];
}

const agents = {
  "analyzer": {
    description: "Codebase analyzer for architecture review.",
    prompt: "Analyze code structure, patterns, and architecture.",
    tools: ["Read", "Grep", "Glob"],
  },
};

let agentId: string | undefined;
let sessionId: string | undefined;

// First invocation
for await (const message of query({
  prompt: "Use the analyzer agent to review the codebase",
  options: { allowedTools: ["Read", "Grep", "Glob", "Task"], agents },
})) {
  if ("session_id" in message) sessionId = message.session_id;
  const extracted = extractAgentId(message);
  if (extracted) agentId = extracted;
  if ("result" in message) console.log(message.result);
}

// Resume
if (agentId && sessionId) {
  for await (const message of query({
    prompt: `Resume agent ${agentId} and list the top 3 issues`,
    options: {
      allowedTools: ["Read", "Grep", "Glob", "Task"],
      resume: sessionId,
      agents,
    },
  })) {
    if ("result" in message) console.log(message.result);
  }
}
```

## Resume Rules

- **Same session**: pass `resume=session_id` — a new `query()` without `resume` starts fresh
- **Same agents**: pass identical `agents` dict in both calls
- **Transcript persistence**: subagent transcripts stored separately from main conversation
  - Unaffected by main conversation compaction
  - Persist across session restarts
  - Auto-cleaned after `cleanupPeriodDays` (default: 30 days)
