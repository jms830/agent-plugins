# Agent Plugins

Universal plugin manager for AI coding agents. Mirrors Claude Code's plugin/marketplace system and syncs across Claude, OpenCode, Codex, Gemini, Cursor, and 10+ more agents.

## Quick Start

```bash
# Install (one-time)
uv tool install agent-plugins --from git+https://github.com/jasonkneen/agent-plugins.git

# Initialize (sets up ~/.agent/ and symlinks to all detected agents)
agent-plugins init

# Add Claude's official marketplace
agent-plugins marketplace add anthropics/claude-code-plugins

# Done! Skills, agents, commands, and hooks are now synced
```

## Why?

Each AI coding agent has its own config directory:
- Claude Code: `~/.claude/`
- OpenCode: `~/.opencode/`
- Codex: `~/.codex/`
- Gemini: `~/.gemini/`
- Cursor: `~/.cursor/`
- And many more...

**The problem**: If you use multiple agents, you need to maintain skills/plugins in multiple places.

**The solution**: `agent-plugins` provides a single canonical location (`~/.agent/`) and automatically syncs to each agent via symlinks (or junction points on Windows).

## Installation

```bash
# Using uv (recommended)
uv tool install agent-plugins --from git+https://github.com/jasonkneen/agent-plugins.git

# Or if published to PyPI
uv tool install agent-plugins

# Or with pip
pip install git+https://github.com/jasonkneen/agent-plugins.git
```

## Updating

```bash
# Update everything (CLI + marketplaces + re-extract components)
agent-plugins upgrade

# Or just update the CLI
uv tool upgrade agent-plugins

# Check current version
agent-plugins version --check
```

## Commands

### Core Commands

| Command | Description |
|---------|-------------|
| `agent-plugins init` | Initialize ~/.agent/ and set up symlinks to all agents |
| `agent-plugins status` | Show current configuration and linked agents |
| `agent-plugins check` | Check which agents are installed on your system |
| `agent-plugins sync` | Re-sync symlinks to all enabled agents |
| `agent-plugins extract` | Extract skills/agents/commands/hooks from marketplaces |
| `agent-plugins list` | List all installed plugins, skills, and commands |

### Version & Update Commands

| Command | Description |
|---------|-------------|
| `agent-plugins version` | Show version info |
| `agent-plugins version --check` | Check for available updates |
| `agent-plugins upgrade` | Upgrade CLI + update marketplaces + re-extract |

### Marketplace Commands

| Command | Description |
|---------|-------------|
| `agent-plugins marketplace add <repo>` | Add marketplace from GitHub (e.g., `anthropics/skills`) |
| `agent-plugins marketplace remove <name>` | Remove a marketplace |
| `agent-plugins marketplace update` | Update all marketplaces |
| `agent-plugins marketplace list` | List installed marketplaces |

### Skill Commands

| Command | Description |
|---------|-------------|
| `agent-plugins add-skill <path>` | Add a skill from local path |
| `agent-plugins remove-skill <name>` | Remove an installed skill |

## What Gets Synced

Agent-plugins extracts and syncs all Claude marketplace components:

| Component | Description | Location |
|-----------|-------------|----------|
| **Skills** | SKILL.md files with AI instructions | `~/.agent/skills/` |
| **Agents** | Specialized agent definitions | `~/.agent/agents/` |
| **Commands** | Slash commands (like `/commit`) | `~/.agent/commands/` |
| **Hooks** | Pre/post tool execution hooks | `~/.agent/hooks/` |
| **Marketplaces** | Git repos with plugins | `~/.agent/plugins/marketplaces/` |

## Directory Structure

```
~/.agent/                           # Canonical location (source of truth)
├── config.json                     # Your configuration
├── skills/                         # All extracted skills
├── agents/                         # All extracted agents  
├── commands/                       # All extracted commands
├── hooks/                          # All extracted hooks
└── plugins/
    └── marketplaces/               # Cloned marketplace repos
        ├── claude-code-plugins/
        ├── anthropic-agent-skills/
        └── ...
```

Symlinks created:
```
~/.claude/skills    → ~/.agent/skills
~/.claude/agents    → ~/.agent/agents
~/.claude/commands  → ~/.agent/commands
~/.claude/hooks     → ~/.agent/hooks
~/.opencode/skills  → ~/.agent/skills
~/.codex/skills     → ~/.agent/skills
~/.gemini/skills    → ~/.agent/skills
~/.cursor/skills    → ~/.agent/skills
...
```

## Supported Agents

| Agent | CLI | Skills | Agents | Commands | Hooks |
|-------|-----|--------|--------|----------|-------|
| Claude Code | ✅ | ✅ | ✅ | ✅ | ✅ |
| OpenCode | ✅ | ✅ | - | ✅ | - |
| Codex | ✅ | ✅ | - | - | - |
| Gemini CLI | ✅ | ✅ | - | - | - |
| Cursor | IDE | ✅ | - | - | - |
| Windsurf | IDE | ✅ | - | - | - |
| Qwen Code | ✅ | ✅ | - | - | - |
| Amazon Q | ✅ | ✅ | - | - | - |
| Auggie | ✅ | ✅ | - | - | - |
| Amp | ✅ | ✅ | - | - | - |
| + more... | | | | | |

## Windows Support

On Windows, agent-plugins automatically uses **junction points** instead of symlinks, which:
- Work without Administrator privileges
- Are transparent to applications (Claude/Codex/Gemini work perfectly)
- Require no special setup or Developer Mode

The fallback chain is: symlink → junction point → copy

## Examples

### Add Popular Marketplaces

```bash
# Anthropic's official skills
agent-plugins marketplace add anthropics/claude-code-plugins
agent-plugins marketplace add anthropics/agent-skills

# Extract all components
agent-plugins extract
```

### Create a Personal Skill

```bash
mkdir -p ~/.agent/skills/my-helper
cat > ~/.agent/skills/my-helper/SKILL.md << 'EOF'
---
name: my-helper
description: My personal coding assistant with custom instructions
---

# My Helper

Your custom instructions here...
EOF

# Sync to all agents
agent-plugins sync
```

### Check What's Installed

```bash
# See all agents and their status
agent-plugins check

# See what's in your marketplaces
agent-plugins list

# Detailed status
agent-plugins status
```

## Configuration

Config is stored in `~/.agent/config.json`:

```json
{
  "enabled_agents": ["claude", "opencode", "codex", "gemini", "cursor"],
  "marketplaces": [],
  "sync_mode": "symlink"
}
```

## Relationship to Other Tools

| Tool | Purpose | Relationship |
|------|---------|--------------|
| [spec-kit](https://github.com/github/spec-kit) | Spec-driven development workflow | Complementary - spec-kit for workflow, agent-plugins for skills |
| Claude Code CLI | Native plugin system | agent-plugins mirrors and extends it to other agents |
| OpenCode | Open-source Claude alternative | Skills synced via symlink |

## License

MIT
