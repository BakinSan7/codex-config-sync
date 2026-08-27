# Claude Code agents

Put reviewed Claude Code subagent definitions here as Markdown files with
frontmatter, then list each file name in the `claude_agents` table of
`manifests/portable-files.json` under `common`, `windows`, or `macos`.

Listed files install to `$CLAUDE_HOME/agents/` (`~/.claude/agents/` by
default). See `examples/example-claude-agent.md` for the expected shape.

Mark an agent `common` only when every command and tool it references exists
on both systems.
