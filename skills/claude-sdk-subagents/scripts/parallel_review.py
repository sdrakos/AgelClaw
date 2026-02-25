"""
Parallel Review — 3 Subagents
===============================
Security scanner + test runner + style checker running in parallel.

Usage:
    pip install claude-agent-sdk
    python parallel_review.py
"""

import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition


async def main():
    async for message in query(
        prompt="Do a comprehensive review of the project: security, tests, and style",
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Grep", "Glob", "Bash", "Task"],
            agents={
                "security-scanner": AgentDefinition(
                    description="Security vulnerability scanner. Use for security analysis.",
                    prompt="""You are a security expert. Analyze code for:
- SQL injection, XSS, CSRF vulnerabilities
- Hardcoded secrets and credentials
- Insecure dependencies
- Authentication/authorization flaws
Provide severity ratings and remediation steps.""",
                    tools=["Read", "Grep", "Glob"],
                    model="sonnet",
                ),
                "test-runner": AgentDefinition(
                    description="Test execution specialist. Use to run and analyze test suites.",
                    prompt="""Run tests and analyze results:
- Execute test suites
- Identify failing tests and root causes
- Check coverage gaps
- Suggest missing test cases""",
                    tools=["Bash", "Read", "Grep"],
                    model="sonnet",
                ),
                "style-checker": AgentDefinition(
                    description="Code style and linting specialist. Use for style/formatting issues.",
                    prompt="""Check code quality:
- Naming conventions and consistency
- Code formatting and structure
- Documentation completeness
- Dead code and unused imports""",
                    tools=["Read", "Grep", "Glob"],
                    model="haiku",  # lighter model for style checks
                ),
            },
        ),
    ):
        # Track subagent invocations
        if hasattr(message, "content") and message.content:
            for block in message.content:
                if getattr(block, "type", None) == "tool_use" and block.name == "Task":
                    agent_type = block.input.get("subagent_type", "unknown")
                    print(f"\n>>> Spawning subagent: {agent_type}")

        if hasattr(message, "result"):
            print(f"\n{'='*60}")
            print(message.result)


if __name__ == "__main__":
    asyncio.run(main())
