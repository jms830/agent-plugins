---
description: "Manage plugins, skills, and marketplaces using agent-plugins"
---

## Context

You are helping the user manage their AI agent plugins using the `agent-plugins` CLI tool.

Agent-plugins is a universal plugin manager that syncs skills, commands, agents, and hooks across multiple AI coding agents (Claude, OpenCode, Codex, Gemini, Cursor, and more).

## Available Commands

```
agent-plugins init                    # Initialize and set up symlinks
agent-plugins status                  # Show current configuration
agent-plugins check                   # Check which agents are installed
agent-plugins sync                    # Re-sync symlinks to all agents
agent-plugins extract                 # Extract components from marketplaces
agent-plugins list                    # List installed plugins and skills
agent-plugins version --check         # Check for updates
agent-plugins upgrade                 # Upgrade CLI and refresh marketplaces

# Marketplace management
agent-plugins marketplace add <repo>  # Add from GitHub (e.g., anthropics/skills)
agent-plugins marketplace remove <n>  # Remove a marketplace
agent-plugins marketplace update      # Update all marketplaces
agent-plugins marketplace list        # List installed marketplaces

# Plugin management  
agent-plugins plugin install <name>   # Install a plugin
agent-plugins plugin uninstall <name> # Uninstall a plugin
agent-plugins plugin list             # List available plugins
agent-plugins plugin enable <name>    # Enable a plugin
agent-plugins plugin disable <name>   # Disable a plugin

# Skill management
agent-plugins add-skill <path>        # Add skill from local path
agent-plugins remove-skill <name>     # Remove an installed skill
```

## Your Task

The user wants to: $ARGUMENTS

Run the appropriate `agent-plugins` command(s) to fulfill their request. If no specific request is given, show the current status with `agent-plugins status`.

If agent-plugins is not installed, guide the user to install it:
```bash
uv tool install agent-plugins --from git+https://github.com/jms830/agent-plugins.git
```
