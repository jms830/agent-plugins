# Agent Plugins

Universal plugin manager for AI coding agents. Mirrors Claude Code's plugin/marketplace system and syncs across Claude, OpenCode, Codex, Gemini, and more.

## Why?

Each AI coding agent has its own skills/plugins directory:
- Claude Code: `~/.claude/skills/`, `~/.claude/plugins/marketplaces/`
- OpenCode: `~/.opencode/skills/`
- Codex: `~/.codex/skills/`
- Gemini: `~/.gemini/skills/`

**The problem**: If you switch between agents, you need to maintain skills in multiple places.

**The solution**: `agent-plugins` provides a single canonical location (`~/.agent/`) and automatically syncs to each agent's expected directory via symlinks.

## Installation

```bash
# Using uv (recommended)
uv tool install agent-plugins --from git+https://github.com/jms830/agent-plugins.git

# Or with pip
pip install agent-plugins
```

## Quick Start

```bash
# Initialize and set up symlinks for all detected agents
agent-plugins init

# Add a marketplace from GitHub
agent-plugins marketplace add anthropics/skills

# List everything
agent-plugins list

# Check status
agent-plugins status
```

## Commands

### Core Commands

| Command | Description |
|---------|-------------|
| `agent-plugins init` | Initialize ~/.agent/ and set up symlinks |
| `agent-plugins status` | Show current configuration and status |
| `agent-plugins list` | List all installed plugins, skills, commands |
| `agent-plugins sync` | Re-sync to all agents |
| `agent-plugins check` | Check which agents are installed |

### Marketplace Commands

| Command | Description |
|---------|-------------|
| `agent-plugins marketplace add <repo>` | Add marketplace from GitHub |
| `agent-plugins marketplace remove <name>` | Remove a marketplace |
| `agent-plugins marketplace update [name]` | Update marketplace(s) |
| `agent-plugins marketplace list` | List installed marketplaces |

### Skill Commands

| Command | Description |
|---------|-------------|
| `agent-plugins add-skill <path>` | Add a skill from local path |
| `agent-plugins remove-skill <name>` | Remove an installed skill |

## Directory Structure

After initialization, `agent-plugins` creates:

```
~/.agent/                           # Canonical location (source of truth)
├── config.json                     # Configuration
├── plugins/
│   └── marketplaces/               # Cloned marketplace repos
│       ├── anthropic-agent-skills/
│       ├── claude-code-plugins/
│       └── my-custom-marketplace/
└── skills/                         # Direct skills
    ├── my-skill/
    │   └── SKILL.md
    └── another-skill/
        └── SKILL.md
```

And creates symlinks:
```
~/.claude/skills       → ~/.agent/skills
~/.opencode/skills     → ~/.agent/skills
~/.codex/skills        → ~/.agent/skills
~/.gemini/skills       → ~/.agent/skills
```

## Supported Agents

| Agent | Skills | Plugins | Commands | Status |
|-------|--------|---------|----------|--------|
| Claude Code | ✅ | ✅ | ✅ | Full support |
| OpenCode | ✅ | ❌ | ✅ | Skills via symlink |
| Codex | ✅ | ❌ | ❌ | Skills via symlink |
| Gemini | ✅ | ❌ | ❌ | Skills via symlink |

## How It Works

1. **Canonical Location**: All skills and marketplaces live in `~/.agent/`
2. **Symlinks**: Each agent's expected directory symlinks to `~/.agent/`
3. **Same Format**: All agents use Anthropic's SKILL.md format
4. **Claude Compatibility**: Marketplace structure mirrors Claude Code exactly

### Skills (Cross-Agent)

Skills use Anthropic's SKILL.md format, which all major agents support:

```markdown
---
name: my-skill
description: What this skill does (min 20 chars)
---

# My Skill

Instructions for the AI agent...
```

### Marketplaces (Claude-Style)

Marketplaces follow Claude Code's structure:

```
my-marketplace/
├── .claude-plugin/
│   └── marketplace.json
├── skills/
│   └── my-skill/
│       └── SKILL.md
├── commands/
│   └── my-command.md
└── plugins/
    └── my-plugin/
        ├── commands/
        ├── skills/
        └── agents/
```

## Examples

### Add Anthropic's Official Skills

```bash
agent-plugins marketplace add anthropics/skills
```

### Create a Personal Skill

```bash
mkdir -p ~/.agent/skills/git-helper
cat > ~/.agent/skills/git-helper/SKILL.md << 'EOF'
---
name: git-helper
description: Helps with git operations, commit messages, and branch management
---

# Git Helper

## Instructions
1. When asked about git, provide clear explanations
2. Generate conventional commit messages
3. Suggest branch naming conventions
EOF
```

### Sync After Manual Changes

```bash
agent-plugins sync --force
```

## Configuration

Config is stored in `~/.agent/config.json`:

```json
{
  "enabled_agents": ["claude", "opencode", "codex", "gemini"],
  "marketplaces": [],
  "sync_mode": "symlink"
}
```

## Relationship to Other Tools

- **[spec-kit](https://github.com/github/spec-kit)**: Handles spec-driven development workflow. Agent-plugins handles skills/plugins. They're complementary.
- **[opencode-skills](https://github.com/malhashemi/opencode-skills)**: OpenCode-specific skills plugin. Agent-plugins provides the skills via symlink.
- **Claude Code CLI**: Native plugin system. Agent-plugins mirrors and extends it to other agents.

## License

MIT
