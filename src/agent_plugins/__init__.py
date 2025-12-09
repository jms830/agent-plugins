#!/usr/bin/env python3
"""
Agent Plugins - Universal plugin manager for AI coding agents.

Mirrors Claude Code's plugin/marketplace system and syncs across:
- Claude Code (~/.claude/)
- OpenCode (~/.opencode/)
- Codex (~/.codex/)
- Gemini (~/.gemini/)
- And more...

Usage:
    uv tool install agent-plugins
    agent-plugins init
    agent-plugins marketplace add anthropics/skills
    agent-plugins install pdf-processing
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, List, Any

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

# =============================================================================
# Constants & Agent Configuration
# =============================================================================

# Canonical location for agent-plugins (source of truth)
AGENT_PLUGINS_HOME = Path.home() / ".agent"

# Agent-specific configurations (mirrors spec-kit's approach)
AGENT_CONFIG = {
    "claude": {
        "name": "Claude Code",
        "home": Path.home() / ".claude",
        "skills_dir": "skills",
        "plugins_dir": "plugins/marketplaces",
        "project_dir": ".claude",
        "supports_plugins": True,
        "supports_skills": True,
        "supports_commands": True,
        "supports_agents": True,
        "supports_hooks": True,
    },
    "opencode": {
        "name": "OpenCode",
        "home": Path.home() / ".opencode",
        "skills_dir": "skills",
        "plugins_dir": None,  # No native plugin system
        "project_dir": ".opencode",
        "supports_plugins": False,
        "supports_skills": True,  # Via opencode-skills plugin
        "supports_commands": True,  # Via ~/.config/opencode/command/
        "supports_agents": False,
        "supports_hooks": False,
    },
    "codex": {
        "name": "OpenAI Codex",
        "home": Path.home() / ".codex",
        "skills_dir": "skills",
        "plugins_dir": None,
        "project_dir": ".codex",
        "supports_plugins": False,
        "supports_skills": True,
        "supports_commands": False,
        "supports_agents": False,
        "supports_hooks": False,
    },
    "gemini": {
        "name": "Gemini CLI",
        "home": Path.home() / ".gemini",
        "skills_dir": "skills",
        "plugins_dir": None,
        "project_dir": ".gemini",
        "supports_plugins": False,
        "supports_skills": True,  # Assuming similar SKILL.md support
        "supports_commands": False,
        "supports_agents": False,
        "supports_hooks": False,
    },
}

BANNER = """
 █████╗  ██████╗ ███████╗███╗   ██╗████████╗
██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝
███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   
██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   
██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   
╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   
██████╗ ██╗     ██╗   ██╗ ██████╗ ██╗███╗   ██╗███████╗
██╔══██╗██║     ██║   ██║██╔════╝ ██║████╗  ██║██╔════╝
██████╔╝██║     ██║   ██║██║  ███╗██║██╔██╗ ██║███████╗
██╔═══╝ ██║     ██║   ██║██║   ██║██║██║╚██╗██║╚════██║
██║     ███████╗╚██████╔╝╚██████╔╝██║██║ ╚████║███████║
╚═╝     ╚══════╝ ╚═════╝  ╚═════╝ ╚═╝╚═╝  ╚═══╝╚══════╝
"""

console = Console()
app = typer.Typer(
    name="agent-plugins",
    help="Universal plugin manager for AI coding agents",
    add_completion=False,
)

# Sub-app for marketplace commands
marketplace_app = typer.Typer(help="Manage plugin marketplaces")
app.add_typer(marketplace_app, name="marketplace")


# =============================================================================
# Utility Functions
# =============================================================================

def show_banner():
    """Display the ASCII art banner."""
    console.print(f"[cyan]{BANNER}[/cyan]")
    console.print("[dim]Universal plugin manager for AI coding agents[/dim]\n")


def get_config_path() -> Path:
    """Get the path to the agent-plugins config file."""
    return AGENT_PLUGINS_HOME / "config.json"


def load_config() -> Dict[str, Any]:
    """Load the agent-plugins configuration."""
    config_path = get_config_path()
    if config_path.exists():
        with open(config_path, "r") as f:
            return json.load(f)
    return {
        "enabled_agents": ["claude", "opencode", "codex", "gemini"],
        "marketplaces": [],
        "sync_mode": "symlink",  # or "copy"
    }


def save_config(config: Dict[str, Any]):
    """Save the agent-plugins configuration."""
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)


def check_agent_installed(agent_key: str) -> bool:
    """Check if an agent CLI is installed."""
    return shutil.which(agent_key) is not None


def get_installed_agents() -> List[str]:
    """Get list of installed agents."""
    installed = []
    for agent_key in AGENT_CONFIG:
        if check_agent_installed(agent_key):
            installed.append(agent_key)
        # Also check if home dir exists (for IDE-based agents)
        elif AGENT_CONFIG[agent_key]["home"].exists():
            installed.append(agent_key)
    return installed


def ensure_directory_structure():
    """Ensure the agent-plugins directory structure exists."""
    dirs = [
        AGENT_PLUGINS_HOME,
        AGENT_PLUGINS_HOME / "plugins" / "marketplaces",
        AGENT_PLUGINS_HOME / "skills",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def create_symlink(source: Path, target: Path, force: bool = False):
    """Create a symlink from target to source."""
    if target.exists() or target.is_symlink():
        if force:
            if target.is_symlink():
                target.unlink()
            elif target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        else:
            console.print(f"[yellow]Warning:[/yellow] {target} already exists, skipping")
            return False
    
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(source)
    return True


def sync_to_agent(agent_key: str, component: str = "skills"):
    """Sync skills/plugins to a specific agent's directory."""
    agent = AGENT_CONFIG.get(agent_key)
    if not agent:
        return False
    
    source = AGENT_PLUGINS_HOME / component
    if not source.exists():
        return False
    
    if component == "skills" and agent["supports_skills"]:
        target = agent["home"] / agent["skills_dir"]
        return create_symlink(source, target, force=False)
    
    return False


# =============================================================================
# CLI Commands
# =============================================================================

@app.command()
def init(
    agents: Optional[str] = typer.Option(
        None, "--agents", "-a",
        help="Comma-separated list of agents to enable (claude,opencode,codex,gemini)"
    ),
    force: bool = typer.Option(
        False, "--force", "-f",
        help="Force overwrite existing symlinks"
    ),
):
    """
    Initialize agent-plugins and set up directory structure.
    
    This creates ~/.agent/ as the canonical location and sets up
    symlinks to each agent's expected skills/plugins directory.
    """
    show_banner()
    
    console.print("[cyan]Initializing agent-plugins...[/cyan]\n")
    
    # Create directory structure
    ensure_directory_structure()
    console.print(f"[green]✓[/green] Created {AGENT_PLUGINS_HOME}")
    
    # Determine which agents to enable
    if agents:
        enabled = [a.strip() for a in agents.split(",")]
    else:
        enabled = get_installed_agents()
        if not enabled:
            enabled = ["claude", "opencode", "codex", "gemini"]
    
    # Save config
    config = load_config()
    config["enabled_agents"] = enabled
    save_config(config)
    console.print(f"[green]✓[/green] Saved configuration")
    
    # Set up symlinks for each agent
    console.print("\n[cyan]Setting up agent symlinks...[/cyan]")
    
    for agent_key in enabled:
        agent = AGENT_CONFIG.get(agent_key)
        if not agent:
            console.print(f"[yellow]⚠[/yellow] Unknown agent: {agent_key}")
            continue
        
        # Skills symlink
        if agent["supports_skills"]:
            source = AGENT_PLUGINS_HOME / "skills"
            target = agent["home"] / agent["skills_dir"]
            
            if target.is_symlink() and target.resolve() == source.resolve():
                console.print(f"[dim]  {agent['name']}: skills already linked[/dim]")
            elif create_symlink(source, target, force=force):
                console.print(f"[green]✓[/green] {agent['name']}: skills → {target}")
            else:
                console.print(f"[yellow]⚠[/yellow] {agent['name']}: skills exists (use --force)")
        
        # Plugins/marketplaces symlink (only for agents that support it)
        if agent["supports_plugins"] and agent["plugins_dir"]:
            source = AGENT_PLUGINS_HOME / "plugins" / "marketplaces"
            target = agent["home"] / agent["plugins_dir"]
            
            if target.is_symlink() and target.resolve() == source.resolve():
                console.print(f"[dim]  {agent['name']}: marketplaces already linked[/dim]")
            elif create_symlink(source, target, force=force):
                console.print(f"[green]✓[/green] {agent['name']}: marketplaces → {target}")
    
    console.print("\n[bold green]Initialization complete![/bold green]")
    console.print("\nNext steps:")
    console.print("  agent-plugins marketplace add <github-repo>")
    console.print("  agent-plugins list")


@app.command()
def status():
    """Show current agent-plugins status and configuration."""
    show_banner()
    
    config = load_config()
    
    # Status table
    table = Table(title="Agent Status")
    table.add_column("Agent", style="cyan")
    table.add_column("Installed", style="green")
    table.add_column("Skills Linked", style="yellow")
    table.add_column("Home Directory")
    
    for agent_key, agent in AGENT_CONFIG.items():
        installed = "✓" if check_agent_installed(agent_key) or agent["home"].exists() else "✗"
        
        skills_target = agent["home"] / agent["skills_dir"]
        skills_linked = "✓" if skills_target.is_symlink() else "✗"
        
        table.add_row(
            agent["name"],
            installed,
            skills_linked if agent["supports_skills"] else "N/A",
            str(agent["home"])
        )
    
    console.print(table)
    
    # Marketplaces
    marketplaces_dir = AGENT_PLUGINS_HOME / "plugins" / "marketplaces"
    if marketplaces_dir.exists():
        marketplaces = [d.name for d in marketplaces_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
        if marketplaces:
            console.print(f"\n[cyan]Installed Marketplaces:[/cyan] {', '.join(marketplaces)}")
    
    # Skills count
    skills_dir = AGENT_PLUGINS_HOME / "skills"
    if skills_dir.exists():
        skills = list(skills_dir.glob("*/SKILL.md"))
        console.print(f"[cyan]Skills:[/cyan] {len(skills)}")


@app.command(name="list")
def list_plugins():
    """List all installed plugins, skills, and commands."""
    config = load_config()
    
    marketplaces_dir = AGENT_PLUGINS_HOME / "plugins" / "marketplaces"
    
    if not marketplaces_dir.exists():
        console.print("[yellow]No marketplaces installed. Run 'agent-plugins init' first.[/yellow]")
        return
    
    tree = Tree("[bold cyan]Agent Plugins[/bold cyan]")
    
    for mp_dir in sorted(marketplaces_dir.iterdir()):
        if not mp_dir.is_dir() or mp_dir.name.startswith("."):
            continue
        
        mp_branch = tree.add(f"[cyan]{mp_dir.name}[/cyan]")
        
        # Check for marketplace.json
        mp_json = mp_dir / ".claude-plugin" / "marketplace.json"
        if mp_json.exists():
            with open(mp_json) as f:
                mp_data = json.load(f)
            
            for plugin in mp_data.get("plugins", []):
                plugin_name = plugin.get("name", "unknown")
                plugin_desc = plugin.get("description", "")[:50]
                plugin_branch = mp_branch.add(f"[green]{plugin_name}[/green] - {plugin_desc}")
                
                # Check for skills
                for skill_path in plugin.get("skills", []):
                    skill_branch = plugin_branch.add(f"[yellow]skill:[/yellow] {skill_path}")
        
        # Also check for direct commands folder
        commands_dir = mp_dir / "commands"
        if commands_dir.exists():
            for cmd_file in commands_dir.glob("*.md"):
                mp_branch.add(f"[blue]cmd:[/blue] {cmd_file.stem}")
        
        # Check for nested plugin commands
        plugins_dir = mp_dir / "plugins"
        if plugins_dir.exists():
            for plugin_dir in plugins_dir.iterdir():
                if plugin_dir.is_dir():
                    cmds_dir = plugin_dir / "commands"
                    if cmds_dir.exists():
                        for cmd_file in cmds_dir.glob("*.md"):
                            mp_branch.add(f"[blue]cmd:[/blue] {plugin_dir.name}/{cmd_file.stem}")
    
    console.print(tree)


# =============================================================================
# Marketplace Commands
# =============================================================================

@marketplace_app.command("add")
def marketplace_add(
    source: str = typer.Argument(..., help="GitHub repo (user/repo) or git URL"),
):
    """
    Add a marketplace from a GitHub repository.
    
    Examples:
        agent-plugins marketplace add anthropics/skills
        agent-plugins marketplace add https://github.com/user/my-plugins.git
    """
    marketplaces_dir = AGENT_PLUGINS_HOME / "plugins" / "marketplaces"
    marketplaces_dir.mkdir(parents=True, exist_ok=True)
    
    # Parse source
    if source.startswith("http") or source.startswith("git@"):
        git_url = source
        repo_name = source.rstrip("/").split("/")[-1].replace(".git", "")
    else:
        # Assume GitHub shorthand
        git_url = f"https://github.com/{source}.git"
        repo_name = source.split("/")[-1]
    
    target_dir = marketplaces_dir / repo_name
    
    if target_dir.exists():
        console.print(f"[yellow]Marketplace '{repo_name}' already exists. Use 'update' to refresh.[/yellow]")
        return
    
    console.print(f"[cyan]Cloning {git_url}...[/cyan]")
    
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", git_url, str(target_dir)],
            check=True,
            capture_output=True,
            text=True
        )
        console.print(f"[green]✓[/green] Added marketplace: {repo_name}")
        
        # Show what was added
        mp_json = target_dir / ".claude-plugin" / "marketplace.json"
        if mp_json.exists():
            with open(mp_json) as f:
                mp_data = json.load(f)
            plugins = mp_data.get("plugins", [])
            console.print(f"  Contains {len(plugins)} plugin(s)")
        
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error cloning repository:[/red] {e.stderr}")
        raise typer.Exit(1)


@marketplace_app.command("remove")
def marketplace_remove(
    name: str = typer.Argument(..., help="Marketplace name to remove"),
):
    """Remove an installed marketplace."""
    marketplaces_dir = AGENT_PLUGINS_HOME / "plugins" / "marketplaces"
    target_dir = marketplaces_dir / name
    
    if not target_dir.exists():
        console.print(f"[red]Marketplace '{name}' not found.[/red]")
        raise typer.Exit(1)
    
    shutil.rmtree(target_dir)
    console.print(f"[green]✓[/green] Removed marketplace: {name}")


@marketplace_app.command("update")
def marketplace_update(
    name: Optional[str] = typer.Argument(None, help="Marketplace name (or all if not specified)"),
):
    """Update marketplace(s) from their git source."""
    marketplaces_dir = AGENT_PLUGINS_HOME / "plugins" / "marketplaces"
    
    if name:
        targets = [marketplaces_dir / name]
    else:
        targets = [d for d in marketplaces_dir.iterdir() if d.is_dir() and (d / ".git").exists()]
    
    for target in targets:
        if not target.exists():
            console.print(f"[yellow]Skipping {target.name}: not found[/yellow]")
            continue
        
        console.print(f"[cyan]Updating {target.name}...[/cyan]")
        try:
            subprocess.run(
                ["git", "pull", "--ff-only"],
                cwd=target,
                check=True,
                capture_output=True,
                text=True
            )
            console.print(f"[green]✓[/green] Updated {target.name}")
        except subprocess.CalledProcessError as e:
            console.print(f"[red]Error updating {target.name}:[/red] {e.stderr}")


@marketplace_app.command(name="list")
def marketplace_list():
    """List installed marketplaces."""
    marketplaces_dir = AGENT_PLUGINS_HOME / "plugins" / "marketplaces"
    
    if not marketplaces_dir.exists():
        console.print("[yellow]No marketplaces directory. Run 'agent-plugins init' first.[/yellow]")
        return
    
    table = Table(title="Installed Marketplaces")
    table.add_column("Name", style="cyan")
    table.add_column("Plugins", style="green")
    table.add_column("Description")
    
    for mp_dir in sorted(marketplaces_dir.iterdir()):
        if not mp_dir.is_dir() or mp_dir.name.startswith("."):
            continue
        
        mp_json = mp_dir / ".claude-plugin" / "marketplace.json"
        if mp_json.exists():
            with open(mp_json) as f:
                mp_data = json.load(f)
            plugins_count = len(mp_data.get("plugins", []))
            description = mp_data.get("description", mp_data.get("metadata", {}).get("description", ""))[:40]
        else:
            plugins_count = "?"
            description = ""
        
        table.add_row(mp_dir.name, str(plugins_count), description)
    
    console.print(table)


# =============================================================================
# Skill Commands
# =============================================================================

@app.command()
def add_skill(
    path: str = typer.Argument(..., help="Path to skill directory or SKILL.md file"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Skill name (defaults to directory name)"),
):
    """Add a skill from a local path."""
    source_path = Path(path).resolve()
    
    if source_path.is_file() and source_path.name == "SKILL.md":
        source_path = source_path.parent
    
    if not (source_path / "SKILL.md").exists():
        console.print(f"[red]Error: No SKILL.md found in {source_path}[/red]")
        raise typer.Exit(1)
    
    skill_name = name or source_path.name
    target = AGENT_PLUGINS_HOME / "skills" / skill_name
    
    if target.exists():
        console.print(f"[yellow]Skill '{skill_name}' already exists.[/yellow]")
        return
    
    shutil.copytree(source_path, target)
    console.print(f"[green]✓[/green] Added skill: {skill_name}")


@app.command()
def remove_skill(
    name: str = typer.Argument(..., help="Skill name to remove"),
):
    """Remove an installed skill."""
    target = AGENT_PLUGINS_HOME / "skills" / name
    
    if not target.exists():
        console.print(f"[red]Skill '{name}' not found.[/red]")
        raise typer.Exit(1)
    
    shutil.rmtree(target)
    console.print(f"[green]✓[/green] Removed skill: {name}")


@app.command()
def sync(
    agent: Optional[str] = typer.Option(None, "--agent", "-a", help="Specific agent to sync to"),
    force: bool = typer.Option(False, "--force", "-f", help="Force overwrite existing links"),
):
    """Sync skills and plugins to all enabled agents."""
    config = load_config()
    agents_to_sync = [agent] if agent else config.get("enabled_agents", [])
    
    for agent_key in agents_to_sync:
        agent_config = AGENT_CONFIG.get(agent_key)
        if not agent_config:
            console.print(f"[yellow]Unknown agent: {agent_key}[/yellow]")
            continue
        
        console.print(f"[cyan]Syncing to {agent_config['name']}...[/cyan]")
        
        # Sync skills
        if agent_config["supports_skills"]:
            source = AGENT_PLUGINS_HOME / "skills"
            target = agent_config["home"] / agent_config["skills_dir"]
            
            if create_symlink(source, target, force=force):
                console.print(f"  [green]✓[/green] Skills linked")
            elif target.is_symlink():
                console.print(f"  [dim]Skills already linked[/dim]")
    
    console.print("[green]Sync complete![/green]")


@app.command()
def check():
    """Check which agents are installed and their status."""
    table = Table(title="Agent Detection")
    table.add_column("Agent", style="cyan")
    table.add_column("CLI Installed", style="green")
    table.add_column("Home Exists", style="yellow")
    table.add_column("Skills Support")
    table.add_column("Plugins Support")
    
    for agent_key, agent in AGENT_CONFIG.items():
        cli_installed = "✓" if check_agent_installed(agent_key) else "✗"
        home_exists = "✓" if agent["home"].exists() else "✗"
        skills = "✓" if agent["supports_skills"] else "✗"
        plugins = "✓" if agent["supports_plugins"] else "✗"
        
        table.add_row(agent["name"], cli_installed, home_exists, skills, plugins)
    
    console.print(table)


def main():
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
