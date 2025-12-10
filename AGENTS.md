# AGENTS.md

## About Agent Plugins

**Agent Plugins** is a universal plugin manager for AI coding agents. It provides a single canonical location (`~/.agent/`) for skills, commands, agents, and hooks, then syncs them to each supported AI agent's expected directory structure.

This file serves as a reference for supported agents and their folder structures, kept in sync with [GitHub Spec Kit](https://github.com/github/spec-kit).

---

## Build & Run

- **Install:** `uv tool install agent-plugins --from git+https://github.com/jasonkneen/agent-plugins.git`
- **Run:** `agent-plugins <command>` or `python -m agent_plugins`
- **Python:** >=3.11

## Code Style

- **Imports:** stdlib first, then third-party (typer, rich, yaml, httpx), no blank lines between groups
- **Types:** Use `typing` module (`Optional`, `Dict`, `List`, `Any`), annotate all function signatures
- **Naming:** `snake_case` for functions/variables, `SCREAMING_SNAKE_CASE` for constants
- **Formatting:** Section separators with `# ===...===` comment blocks
- **CLI:** Use `typer` with `rich` for output; short flags like `--force/-f`
- **Paths:** Use `pathlib.Path` throughout, never string paths
- **Errors:** Use `typer.Exit(1)` for CLI errors, Rich formatting `[red]Error:[/red]`
- **File I/O:** Context managers (`with open(...)`), JSON for config files

---

## Supported Agents

Folder structures sourced from: https://github.com/github/spec-kit/blob/main/AGENTS.md

| Agent | CLI Tool | Home Directory | Commands Dir | Format | Skills |
|-------|----------|----------------|--------------|--------|--------|
| Claude Code | `claude` | `~/.claude/` | `commands/` | Markdown | Yes |
| OpenCode | `opencode` | `~/.opencode/` | `command/` | Markdown | Yes |
| Codex CLI | `codex` | `~/.codex/` | `commands/` | Markdown | Yes |
| Gemini CLI | `gemini` | `~/.gemini/` | `commands/` | TOML | Yes |
| Cursor | `cursor-agent` | `~/.cursor/` | `commands/` | Markdown | Yes |
| Windsurf | N/A (IDE) | `~/.windsurf/` | `workflows/` | Markdown | Yes |
| GitHub Copilot | N/A (IDE) | `~/.github/` | `agents/` | Markdown | No |
| Qwen Code | `qwen` | `~/.qwen/` | `commands/` | TOML | Yes |
| Kilo Code | N/A (IDE) | `~/.kilocode/` | `rules/` | Markdown | Yes |
| Auggie CLI | `auggie` | `~/.augment/` | `rules/` | Markdown | Yes |
| CodeBuddy | `codebuddy` | `~/.codebuddy/` | `commands/` | Markdown | Yes |
| Roo Code | N/A (IDE) | `~/.roo/` | `rules/` | Markdown | Yes |
| Amazon Q | `q` | `~/.amazonq/` | `prompts/` | Markdown | Yes |
| Amp | `amp` | `~/.agents/` | `commands/` | Markdown | Yes |
| SHAI | `shai` | `~/.shai/` | `commands/` | Markdown | Yes |

## Command File Formats

### Markdown Format (Most Agents)

Used by: Claude, Cursor, OpenCode, Codex, Windsurf, Amazon Q, Amp, SHAI, etc.

```markdown
---
description: "Command description"
---

Command instructions here with $ARGUMENTS placeholder.
```

### TOML Format (Gemini, Qwen)

```toml
description = "Command description"

prompt = """
Command instructions here with {{args}} placeholder.
"""
```

## Directory Structure

Agent Plugins creates:

```
~/.agent/                           # Canonical location (source of truth)
├── config.json                     # Configuration
├── skills/                         # SKILL.md files (synced to all agents)
├── agents/                         # Agent definitions (Claude-style)
├── commands/                       # Slash commands
├── hooks/                          # Hook scripts
└── plugins/
    └── marketplaces/               # Cloned marketplace repos
```

Then creates symlinks (or junction points on Windows):

```
~/.claude/skills    → ~/.agent/skills
~/.claude/agents    → ~/.agent/agents
~/.claude/commands  → ~/.agent/commands
~/.claude/hooks     → ~/.agent/hooks
~/.opencode/skills  → ~/.agent/skills
~/.codex/skills     → ~/.agent/skills
~/.gemini/skills    → ~/.agent/skills
... (for all enabled agents)
```

## Adding New Agent Support

When adding a new agent, update `AGENT_CONFIG` in `src/agent_plugins/__init__.py`:

```python
"new-agent": {
    "name": "New Agent",
    "home": Path.home() / ".newagent",
    "project_dir": ".newagent",
    "skills_dir": "skills",
    "commands_dir": "commands",      # Agent-specific (could be rules/, prompts/, etc.)
    "agents_dir": None,
    "hooks_dir": None,
    "plugins_dir": None,
    "command_format": "markdown",    # or "toml"
    "install_url": "https://example.com/install",
    "requires_cli": True,
    "supports_plugins": False,
    "supports_skills": True,
    "supports_commands": True,
    "supports_agents": False,
    "supports_hooks": False,
},
```

Key fields:
- Use the **actual CLI tool name** as the key (what users type in terminal)
- `commands_dir`: Agent-specific directory name (`commands/`, `rules/`, `prompts/`, `workflows/`)
- `command_format`: `"markdown"` or `"toml"`
- `requires_cli`: `True` for CLI agents, `False` for IDE-based

---

## Keeping in Sync with Speckit

The `AGENT_CONFIG` in this project is kept in sync with [GitHub Spec Kit](https://github.com/github/spec-kit). When Speckit adds new agents or changes folder structures:

1. Check Speckit's `AGENTS.md` for the latest agent table
2. Update `AGENT_CONFIG` in `src/agent_plugins/__init__.py`
3. Update the table in this file
4. Run `agent-plugins check` to verify detection works

---

*This documentation should be updated whenever new agents are added or folder structures change.*
