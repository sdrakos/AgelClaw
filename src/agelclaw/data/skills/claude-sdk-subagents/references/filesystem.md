# Filesystem-Based Agents

Alternative to programmatic `AgentDefinition`: define agents as `.md` files.

## Directory Structure

```
.claude/
  agents/
    code-reviewer.md       # Agent name = filename (without .md)
    security-scanner.md
    test-runner.md
```

## Agent File Format

Each `.md` file is the agent's system prompt. The filename becomes the agent name.

Example `code-reviewer.md`:
```markdown
You are a code review specialist with expertise in security, performance, and best practices.

When reviewing code:
- Identify security vulnerabilities
- Check for performance issues
- Verify adherence to coding standards
- Suggest specific improvements

Be thorough but concise in your feedback.
```

## Precedence

- Programmatic definitions (`agents={}`) take precedence over filesystem agents with the same name
- Filesystem agents load at startup only — restart session after creating new files

## When to Use Filesystem Agents

- **Complex prompts**: avoid Windows command-line length limits (8191 chars)
- **Reuse across projects**: place in user-level `~/.claude/agents/`
- **Team sharing**: commit to `.claude/agents/` in the repo
- **Non-SDK use**: works with Claude Code CLI directly (not just SDK)

## When to Use Programmatic Agents

- **Dynamic configuration**: factory patterns, runtime conditions
- **Tool restrictions**: `tools` field only available programmatically
- **Model override**: `model` field only available programmatically
- **Self-contained**: everything in one script, no external files
