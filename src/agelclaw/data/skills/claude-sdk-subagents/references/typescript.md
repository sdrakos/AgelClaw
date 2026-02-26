# TypeScript Examples

## Single Subagent

```typescript
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "Review the authentication module for security issues",
  options: {
    allowedTools: ["Read", "Grep", "Glob", "Task"],
    agents: {
      "code-reviewer": {
        description: "Expert code reviewer. Use for quality and security reviews.",
        prompt: `You are a code review specialist.
Focus on security vulnerabilities, performance issues, and best practices.`,
        tools: ["Read", "Grep", "Glob"],
        model: "sonnet",
      },
    },
  },
})) {
  if ("result" in message) console.log(message.result);
}
```

## Multiple Subagents

```typescript
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "Do a full review of the project",
  options: {
    allowedTools: ["Read", "Grep", "Glob", "Bash", "Task"],
    agents: {
      "security-scanner": {
        description: "Security vulnerability scanner.",
        prompt: "Find security vulnerabilities in the codebase.",
        tools: ["Read", "Grep", "Glob"],
      },
      "test-runner": {
        description: "Test execution specialist.",
        prompt: "Run tests and analyze results. Report failures clearly.",
        tools: ["Bash", "Read", "Grep"],
      },
      "style-checker": {
        description: "Code style and linting specialist.",
        prompt: "Check code style, formatting, and naming conventions.",
        tools: ["Read", "Grep", "Glob"],
      },
    },
  },
})) {
  if ("result" in message) console.log(message.result);
}
```

## Dynamic Agent Factory (TypeScript)

```typescript
import { query, type AgentDefinition } from "@anthropic-ai/claude-agent-sdk";

function createReviewer(
  focus: string,
  strict: boolean = false
): AgentDefinition {
  return {
    description: `${focus} code reviewer`,
    prompt: `You are a ${strict ? "strict" : "balanced"} ${focus} reviewer.`,
    tools: ["Read", "Grep", "Glob"],
    model: strict ? "opus" : "sonnet",
  };
}

for await (const message of query({
  prompt: "Review this PR for security issues",
  options: {
    allowedTools: ["Read", "Grep", "Glob", "Task"],
    agents: {
      "security-reviewer": createReviewer("security", true),
      "perf-reviewer": createReviewer("performance"),
    },
  },
})) {
  if ("result" in message) console.log(message.result);
}
```

## Read-Only Analysis Agent

```typescript
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "Analyze the architecture of this codebase",
  options: {
    allowedTools: ["Read", "Grep", "Glob", "Task"],
    agents: {
      "code-analyzer": {
        description: "Static code analysis and architecture review",
        prompt: `You are a code architecture analyst. Analyze code structure,
identify patterns, and suggest improvements without making changes.`,
        tools: ["Read", "Grep", "Glob"],
      },
    },
  },
})) {
  if ("result" in message) console.log(message.result);
}
```

## TypeScript-Specific Notes

- Agent config uses camelCase: `allowedTools`, not `allowed_tools`
- `AgentDefinition` is a plain object type, not a class
- Access content via `message.message.content` (wrapped `SDKAssistantMessage`)
- Use `"result" in message` to check for final result
