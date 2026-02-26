# Multiple Subagents & Parallel Execution

## Why Parallel Subagents?

Multiple subagents run concurrently, dramatically speeding up complex workflows.
Each maintains separate context — specialized tasks don't pollute each other.

## Python: Multiple Subagents

```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition

async def main():
    async for message in query(
        prompt="Do a full code review of the project",
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Grep", "Glob", "Bash", "Task"],
            agents={
                "security-scanner": AgentDefinition(
                    description="Security vulnerability scanner. Use for security analysis.",
                    prompt="""You are a security expert. Analyze code for:
- SQL injection, XSS, CSRF vulnerabilities
- Hardcoded secrets and credentials
- Insecure dependencies
- Authentication/authorization flaws""",
                    tools=["Read", "Grep", "Glob"],
                ),
                "test-runner": AgentDefinition(
                    description="Test execution specialist. Use to run and analyze tests.",
                    prompt="""Run tests and analyze results. Report:
- Failing tests with root cause
- Coverage gaps
- Flaky test patterns""",
                    tools=["Bash", "Read", "Grep"],
                ),
                "style-checker": AgentDefinition(
                    description="Code style and linting specialist. Use for style/formatting issues.",
                    prompt="Check code style, formatting, naming conventions, and documentation.",
                    tools=["Read", "Grep", "Glob"],
                ),
            },
        ),
    ):
        if hasattr(message, "result"):
            print(message.result)

asyncio.run(main())
```

Claude decides which subagents to invoke and can run them in parallel automatically.

## Dynamic Agent Factory

Create agents dynamically based on runtime conditions:

```python
from claude_agent_sdk import AgentDefinition

def create_reviewer(focus: str, strict: bool = False) -> AgentDefinition:
    return AgentDefinition(
        description=f"{focus} code reviewer",
        prompt=f"You are a {'strict' if strict else 'balanced'} {focus} reviewer. "
               f"Focus exclusively on {focus} concerns.",
        tools=["Read", "Grep", "Glob"],
        model="opus" if strict else "sonnet",
    )

# Build agents dict dynamically
agents = {
    "security-reviewer": create_reviewer("security", strict=True),
    "perf-reviewer": create_reviewer("performance"),
    "api-reviewer": create_reviewer("API design"),
}
```

## Context Isolation Benefits

Each subagent:
- Has its own conversation context (doesn't see other subagents' work)
- Can explore dozens of files without cluttering main conversation
- Returns only the relevant findings to the main agent
- Runs independently — failure in one doesn't affect others
