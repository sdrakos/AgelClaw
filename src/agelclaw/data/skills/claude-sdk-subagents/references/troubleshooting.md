# Troubleshooting

## Claude doesn't delegate to subagent

| Cause | Fix |
|-------|-----|
| `Task` not in `allowedTools` | Add `"Task"` to `allowed_tools` / `allowedTools` |
| Vague description | Write clear description: "Use for X when Y" |
| Claude handles it directly | Use explicit prompt: `"Use the X agent to..."` |

## Subagent not found

- Agent name in prompt must match the key in `agents={}` exactly
- Check for typos in both the dict key and the prompt reference

## Windows: long prompt failures

Command line limit is 8191 chars on Windows. Solutions:
- Keep subagent prompts concise
- Use filesystem agents (`.claude/agents/*.md`) for complex prompts
- The prompt content is in a file, bypassing CLI length limits

## Filesystem agents not loading

Agents in `.claude/agents/` load at session startup only.
- **Fix**: restart the Claude Code session after creating new agent files
- Programmatic agents don't have this limitation

## Subagent can't use a tool

- Check that the tool is in the subagent's `tools` list
- If `tools` is omitted, subagent inherits all parent tools
- Never include `Task` in a subagent's tools (can't spawn sub-subagents)

## Resume not working

- Must pass `resume=session_id` (not a new session)
- Must pass the same `agents` definitions in both calls
- The `agentId` comes from the Task tool result content (parse with regex)
- `session_id` comes from `ResultMessage` — check `hasattr(message, "session_id")`

## Streaming mode timeout on Windows

Per project memory: streaming mode (`--input-format stream-json`) has initialization timeouts
on Windows with the bundled claude.exe. Consider non-streaming `query(prompt="...", options=...)`
which uses `--print` mode as a workaround.
