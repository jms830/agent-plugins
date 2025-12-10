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
import httpx
import readchar
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich.live import Live


# =============================================================================
# GitHub API Helpers
# =============================================================================

def get_github_token(cli_token: Optional[str] = None) -> Optional[str]:
    """Return GitHub token from CLI arg, GH_TOKEN, or GITHUB_TOKEN env var."""
    token = (cli_token or os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN") or "").strip()
    return token if token else None


def get_github_auth_headers(cli_token: Optional[str] = None) -> Dict[str, str]:
    """Return Authorization header dict if token exists."""
    token = get_github_token(cli_token)
    return {"Authorization": f"Bearer {token}"} if token else {}


def get_authenticated_git_url(url: str, token: Optional[str] = None) -> str:
    """Convert GitHub URL to authenticated URL if token available.
    
    This embeds the token in the URL for git clone operations,
    which helps with rate limits and private repos.
    """
    token = get_github_token(token)
    if not token:
        return url
    
    # Convert https://github.com/user/repo.git to https://TOKEN@github.com/user/repo.git
    if url.startswith("https://github.com/"):
        return url.replace("https://github.com/", f"https://{token}@github.com/")
    return url


# =============================================================================
# Interactive Selection Helpers
# =============================================================================

def get_key() -> str:
    """Get a single keypress in a cross-platform way using readchar."""
    try:
        key = readchar.readkey()
        
        if key == readchar.key.UP or key == readchar.key.CTRL_P:
            return 'up'
        if key == readchar.key.DOWN or key == readchar.key.CTRL_N:
            return 'down'
        if key == readchar.key.ENTER:
            return 'enter'
        if key == readchar.key.ESC:
            return 'esc'
        if key == readchar.key.CTRL_C:
            raise KeyboardInterrupt
        if key == ' ':
            return 'space'
        if key.lower() == 'a':
            return 'a'
        return key
    except Exception:
        return 'esc'


def select_agents_interactive(
    agents: Dict[str, Dict],
    prompt_text: str = "Select agents to sync",
    preselected: List[str] = None
) -> List[str]:
    """
    Interactive multi-select for agents using arrow keys and space.
    
    Controls:
    - ↑/↓: Navigate
    - Space: Toggle selection
    - A: Select/deselect all
    - Enter: Confirm
    - Esc: Cancel
    
    Returns list of selected agent keys.
    """
    console = Console()
    option_keys = list(agents.keys())
    selected = set(preselected or [])
    cursor_index = 0
    
    def create_selection_panel():
        """Create the selection panel with current selections."""
        lines = []
        for i, key in enumerate(option_keys):
            agent = agents[key]
            cursor = "→" if i == cursor_index else " "
            check = "✓" if key in selected else " "
            installed = "✓" if check_agent_installed(key) or agent["home"].exists() else " "
            
            if i == cursor_index:
                line = f"[bold cyan]{cursor} [{check}] {agent['name']}[/bold cyan] [dim](installed: {installed})[/dim]"
            else:
                line = f"[white]{cursor} [{check}] {agent['name']}[/white] [dim](installed: {installed})[/dim]"
            lines.append(line)
        
        lines.append("")
        lines.append("[dim]↑/↓: navigate  Space: toggle  A: all  Enter: confirm  Esc: cancel[/dim]")
        
        return Panel(
            "\n".join(lines),
            title=f"[bold cyan]{prompt_text}[/bold cyan]",
            border_style="cyan"
        )
    
    # Check if we're in an interactive terminal
    if not sys.stdin.isatty():
        # Non-interactive: return preselected or installed agents
        return list(selected) if selected else [k for k in option_keys if check_agent_installed(k) or agents[k]["home"].exists()]
    
    try:
        with Live(create_selection_panel(), console=console, transient=True, refresh_per_second=10) as live:
            while True:
                try:
                    key = get_key()
                    
                    if key == 'up':
                        cursor_index = (cursor_index - 1) % len(option_keys)
                    elif key == 'down':
                        cursor_index = (cursor_index + 1) % len(option_keys)
                    elif key == 'space':
                        current_key = option_keys[cursor_index]
                        if current_key in selected:
                            selected.remove(current_key)
                        else:
                            selected.add(current_key)
                    elif key == 'a':
                        # Toggle all
                        if len(selected) == len(option_keys):
                            selected.clear()
                        else:
                            selected = set(option_keys)
                    elif key == 'enter':
                        break
                    elif key == 'esc':
                        console.print("\n[yellow]Selection cancelled[/yellow]")
                        raise typer.Exit(1)
                    
                    live.update(create_selection_panel())
                    
                except KeyboardInterrupt:
                    console.print("\n[yellow]Selection cancelled[/yellow]")
                    raise typer.Exit(1)
    except Exception as e:
        # Fallback for non-TTY environments
        console.print(f"[yellow]Interactive mode unavailable, using defaults[/yellow]")
        return list(selected) if selected else [k for k in option_keys if check_agent_installed(k) or agents[k]["home"].exists()]
    
    return list(selected)


# =============================================================================
# Constants & Agent Configuration
# =============================================================================

# Canonical location for agent-plugins (source of truth)
AGENT_PLUGINS_HOME = Path.home() / ".agent"

# Claude local path after `claude migrate-installer` (removes from PATH, creates alias here)
CLAUDE_LOCAL_PATH = Path.home() / ".claude" / "local" / "claude"

# Agent-specific configurations
# Folder structures sourced from: https://github.com/github/spec-kit/blob/main/AGENTS.md
# Keep in sync with Speckit for compatibility
AGENT_CONFIG = {
    "claude": {
        "name": "Claude Code",
        "home": Path.home() / ".claude",
        "project_dir": ".claude",
        "skills_dir": "skills",
        "commands_dir": "commands",          # .claude/commands/
        "agents_dir": "agents",
        "hooks_dir": "hooks",
        "plugins_dir": "plugins/marketplaces",
        "command_format": "markdown",
        "install_url": "https://docs.anthropic.com/en/docs/claude-code/setup",
        "requires_cli": True,
        "supports_plugins": True,
        "supports_skills": True,
        "supports_commands": True,
        "supports_agents": True,
        "supports_hooks": True,
    },
    "opencode": {
        "name": "OpenCode",
        "home": Path.home() / ".opencode",
        "project_dir": ".opencode",
        "skills_dir": "skills",
        "commands_dir": "command",           # .opencode/command/ (singular!)
        "commands_alt_dir": Path.home() / ".config" / "opencode" / "command",
        "agents_dir": None,
        "hooks_dir": None,
        "plugins_dir": None,
        "command_format": "markdown",
        "install_url": "https://opencode.ai",
        "requires_cli": True,
        "supports_plugins": False,
        "supports_skills": True,
        "supports_commands": True,
        "supports_agents": False,
        "supports_hooks": False,
    },
    "codex": {
        "name": "Codex CLI",
        "home": Path.home() / ".codex",
        "project_dir": ".codex",
        "skills_dir": "skills",
        "commands_dir": "commands",          # .codex/commands/
        "agents_dir": None,
        "hooks_dir": None,
        "plugins_dir": None,
        "command_format": "markdown",
        "install_url": "https://github.com/openai/codex",
        "requires_cli": True,
        "supports_plugins": False,
        "supports_skills": True,
        "supports_commands": True,
        "supports_agents": False,
        "supports_hooks": False,
    },
    "gemini": {
        "name": "Gemini CLI",
        "home": Path.home() / ".gemini",
        "project_dir": ".gemini",
        "skills_dir": "skills",
        "commands_dir": "commands",          # .gemini/commands/
        "agents_dir": None,
        "hooks_dir": None,
        "plugins_dir": None,
        "command_format": "toml",            # Gemini uses TOML!
        "install_url": "https://github.com/google-gemini/gemini-cli",
        "requires_cli": True,
        "supports_plugins": False,
        "supports_skills": True,
        "supports_commands": True,
        "supports_agents": False,
        "supports_hooks": False,
    },
    "cursor-agent": {
        "name": "Cursor",
        "home": Path.home() / ".cursor",
        "project_dir": ".cursor",
        "skills_dir": "skills",
        "commands_dir": "commands",          # .cursor/commands/
        "agents_dir": None,
        "hooks_dir": None,
        "plugins_dir": None,
        "command_format": "markdown",
        "install_url": None,
        "requires_cli": False,
        "supports_plugins": False,
        "supports_skills": True,
        "supports_commands": True,
        "supports_agents": False,
        "supports_hooks": False,
    },
    "windsurf": {
        "name": "Windsurf",
        "home": Path.home() / ".windsurf",
        "project_dir": ".windsurf",
        "skills_dir": "skills",
        "commands_dir": "workflows",         # .windsurf/workflows/
        "agents_dir": None,
        "hooks_dir": None,
        "plugins_dir": None,
        "command_format": "markdown",
        "install_url": None,
        "requires_cli": False,
        "supports_plugins": False,
        "supports_skills": True,
        "supports_commands": True,
        "supports_agents": False,
        "supports_hooks": False,
    },
    "copilot": {
        "name": "GitHub Copilot",
        "home": Path.home() / ".github",
        "project_dir": ".github",
        "skills_dir": None,
        "commands_dir": "agents",            # .github/agents/
        "agents_dir": "agents",
        "hooks_dir": None,
        "plugins_dir": None,
        "command_format": "markdown",
        "install_url": None,
        "requires_cli": False,
        "supports_plugins": False,
        "supports_skills": False,
        "supports_commands": True,
        "supports_agents": True,
        "supports_hooks": False,
    },
    "qwen": {
        "name": "Qwen Code",
        "home": Path.home() / ".qwen",
        "project_dir": ".qwen",
        "skills_dir": "skills",
        "commands_dir": "commands",          # .qwen/commands/
        "agents_dir": None,
        "hooks_dir": None,
        "plugins_dir": None,
        "command_format": "toml",            # Qwen uses TOML!
        "install_url": "https://github.com/QwenLM/qwen-code",
        "requires_cli": True,
        "supports_plugins": False,
        "supports_skills": True,
        "supports_commands": True,
        "supports_agents": False,
        "supports_hooks": False,
    },
    "kilocode": {
        "name": "Kilo Code",
        "home": Path.home() / ".kilocode",
        "project_dir": ".kilocode",
        "skills_dir": "skills",
        "commands_dir": "rules",             # .kilocode/rules/
        "agents_dir": None,
        "hooks_dir": None,
        "plugins_dir": None,
        "command_format": "markdown",
        "install_url": None,
        "requires_cli": False,
        "supports_plugins": False,
        "supports_skills": True,
        "supports_commands": True,
        "supports_agents": False,
        "supports_hooks": False,
    },
    "auggie": {
        "name": "Auggie CLI",
        "home": Path.home() / ".augment",
        "project_dir": ".augment",
        "skills_dir": "skills",
        "commands_dir": "rules",             # .augment/rules/
        "agents_dir": None,
        "hooks_dir": None,
        "plugins_dir": None,
        "command_format": "markdown",
        "install_url": "https://docs.augmentcode.com/cli/setup-auggie/install-auggie-cli",
        "requires_cli": True,
        "supports_plugins": False,
        "supports_skills": True,
        "supports_commands": True,
        "supports_agents": False,
        "supports_hooks": False,
    },
    "codebuddy": {
        "name": "CodeBuddy",
        "home": Path.home() / ".codebuddy",
        "project_dir": ".codebuddy",
        "skills_dir": "skills",
        "commands_dir": "commands",          # .codebuddy/commands/
        "agents_dir": None,
        "hooks_dir": None,
        "plugins_dir": None,
        "command_format": "markdown",
        "install_url": "https://www.codebuddy.ai/cli",
        "requires_cli": True,
        "supports_plugins": False,
        "supports_skills": True,
        "supports_commands": True,
        "supports_agents": False,
        "supports_hooks": False,
    },
    "roo": {
        "name": "Roo Code",
        "home": Path.home() / ".roo",
        "project_dir": ".roo",
        "skills_dir": "skills",
        "commands_dir": "rules",             # .roo/rules/
        "agents_dir": None,
        "hooks_dir": None,
        "plugins_dir": None,
        "command_format": "markdown",
        "install_url": None,
        "requires_cli": False,
        "supports_plugins": False,
        "supports_skills": True,
        "supports_commands": True,
        "supports_agents": False,
        "supports_hooks": False,
    },
    "q": {
        "name": "Amazon Q Developer CLI",
        "home": Path.home() / ".amazonq",
        "project_dir": ".amazonq",
        "skills_dir": "skills",
        "commands_dir": "prompts",           # .amazonq/prompts/
        "agents_dir": None,
        "hooks_dir": None,
        "plugins_dir": None,
        "command_format": "markdown",
        "install_url": "https://aws.amazon.com/developer/learning/q-developer-cli/",
        "requires_cli": True,
        "supports_plugins": False,
        "supports_skills": True,
        "supports_commands": True,
        "supports_agents": False,
        "supports_hooks": False,
    },
    "amp": {
        "name": "Amp",
        "home": Path.home() / ".agents",
        "project_dir": ".agents",
        "skills_dir": "skills",
        "commands_dir": "commands",          # .agents/commands/
        "agents_dir": None,
        "hooks_dir": None,
        "plugins_dir": None,
        "command_format": "markdown",
        "install_url": "https://ampcode.com/manual#install",
        "requires_cli": True,
        "supports_plugins": False,
        "supports_skills": True,
        "supports_commands": True,
        "supports_agents": False,
        "supports_hooks": False,
    },
    "shai": {
        "name": "SHAI",
        "home": Path.home() / ".shai",
        "project_dir": ".shai",
        "skills_dir": "skills",
        "commands_dir": "commands",          # .shai/commands/
        "agents_dir": None,
        "hooks_dir": None,
        "plugins_dir": None,
        "command_format": "markdown",
        "install_url": "https://github.com/ovh/shai",
        "requires_cli": True,
        "supports_plugins": False,
        "supports_skills": True,
        "supports_commands": True,
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

@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context):
    """
    Universal plugin manager for AI coding agents.
    """
    if ctx.invoked_subcommand is None:
        show_banner()
        console.print(ctx.get_help())

# Sub-app for plugin commands (mirrors 'claude plugin')
plugin_app = typer.Typer(
    help="Manage plugins and marketplaces",
    no_args_is_help=True,
)
app.add_typer(plugin_app, name="plugin")

# Sub-app for marketplace commands (under plugin)
marketplace_app = typer.Typer(
    help="Manage plugin marketplaces",
    no_args_is_help=True,
)
plugin_app.add_typer(marketplace_app, name="marketplace")

# Keep backwards-compatible top-level marketplace command
app.add_typer(marketplace_app, name="marketplace", hidden=True)


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
    """Check if an agent CLI is installed.
    
    Special handling for Claude after `claude migrate-installer` which
    removes the original executable from PATH and creates an alias at
    ~/.claude/local/claude instead.
    """
    # Special case: Claude migrated installer
    if agent_key == "claude":
        if CLAUDE_LOCAL_PATH.exists() and CLAUDE_LOCAL_PATH.is_file():
            return True
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
    """Ensure the agent-plugins directory structure exists.
    
    Creates the full Claude-compatible directory structure:
    ~/.agent/
    ├── plugins/
    │   └── marketplaces/     # Git repos with marketplace.json
    ├── skills/               # SKILL.md files
    ├── agents/               # Agent definitions
    ├── commands/             # Slash commands
    └── hooks/                # Hook scripts
    """
    dirs = [
        AGENT_PLUGINS_HOME,
        AGENT_PLUGINS_HOME / "plugins" / "marketplaces",
        AGENT_PLUGINS_HOME / "skills",
        AGENT_PLUGINS_HOME / "agents",
        AGENT_PLUGINS_HOME / "commands",
        AGENT_PLUGINS_HOME / "hooks",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def install_builtin_commands():
    """Install built-in commands from the package to ~/.agent/commands/.
    
    This copies commands bundled with agent-plugins (like /plugin-manager)
    to the canonical commands directory so they're available to all agents.
    
    Returns count of commands installed.
    """
    import importlib.resources
    
    commands_dir = AGENT_PLUGINS_HOME / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)
    
    count = 0
    
    # Try to find bundled commands in the package
    try:
        # Python 3.9+ approach
        if hasattr(importlib.resources, 'files'):
            package_commands = importlib.resources.files('agent_plugins').joinpath('commands')
            if package_commands.is_dir():
                for item in package_commands.iterdir():
                    if item.name.endswith('.md'):
                        dest = commands_dir / item.name
                        # Always overwrite built-in commands to ensure latest version
                        dest.write_text(item.read_text())
                        count += 1
        else:
            # Fallback for older Python
            import pkg_resources
            package_dir = Path(pkg_resources.resource_filename('agent_plugins', 'commands'))
            if package_dir.exists():
                for cmd_file in package_dir.glob('*.md'):
                    dest = commands_dir / cmd_file.name
                    shutil.copy2(cmd_file, dest)
                    count += 1
    except Exception:
        # If package resources fail, try relative path (development mode)
        dev_commands = Path(__file__).parent / "commands"
        if dev_commands.exists():
            for cmd_file in dev_commands.glob('*.md'):
                dest = commands_dir / cmd_file.name
                shutil.copy2(cmd_file, dest)
                count += 1
    
    return count


def is_junction(path: Path) -> bool:
    """Check if a path is a Windows junction point."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        FILE_ATTRIBUTE_REPARSE_POINT = 0x400
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
        return attrs != -1 and (attrs & FILE_ATTRIBUTE_REPARSE_POINT)
    except Exception:
        return False


def create_junction(source: Path, target: Path) -> bool:
    """Create a Windows junction point (directory symlink that doesn't need admin).
    
    Junction points work without elevation and are transparent to applications.
    They only work for directories on the same volume.
    """
    if sys.platform != "win32":
        return False
    
    try:
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(target), str(source)],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def create_link(source: Path, target: Path, force: bool = False) -> bool:
    """Create a directory link from target to source.
    
    Link creation strategy (in order):
    1. Try native symlink (works on Unix, Windows with Developer Mode)
    2. On Windows: Try junction point (no elevation needed, transparent to apps)
    3. Fallback: Copy files (last resort)
    
    Args:
        source: The source path (what we're linking TO) - must be a directory
        target: The target path (where the link will be created)
        force: Whether to overwrite existing files/links
        
    Returns:
        True if link/copy was created, False if skipped
    """
    # Handle existing target
    if target.exists() or target.is_symlink() or is_junction(target):
        if force:
            if target.is_symlink():
                target.unlink()
            elif is_junction(target):
                # Junctions are removed like directories on Windows
                target.rmdir()
            elif target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        else:
            console.print(f"[yellow]Warning:[/yellow] {target} already exists, skipping")
            return False
    
    target.parent.mkdir(parents=True, exist_ok=True)
    
    # Strategy 1: Try native symlink first
    # Works on: Linux, macOS, Windows with Developer Mode enabled
    try:
        target.symlink_to(source)
        return True
    except OSError:
        pass
    
    # Strategy 2: On Windows, try junction point (no admin needed)
    # Junctions are transparent to applications - Claude/Codex/Gemini work perfectly
    if sys.platform == "win32" and source.is_dir():
        if create_junction(source, target):
            console.print(f"[dim]  (using junction point)[/dim]")
            return True
    
    # Strategy 3: Last resort - copy files
    # This ensures it always works, even in edge cases
    if source.is_dir():
        shutil.copytree(source, target)
    else:
        shutil.copy2(source, target)
    console.print(f"[dim]  (copied - symlink/junction unavailable)[/dim]")
    return True


# Alias for backwards compatibility
def create_symlink(source: Path, target: Path, force: bool = False) -> bool:
    """Deprecated: Use create_link instead."""
    return create_link(source, target, force)


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
        help="Comma-separated list of agents (e.g., claude,opencode,codex). If not specified, shows interactive selector."
    ),
    all_agents: bool = typer.Option(
        False, "--all",
        help="Enable all supported agents without prompting"
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
    
    Examples:
        agent-plugins init                    # Interactive agent selection
        agent-plugins init --all              # Enable all agents
        agent-plugins init -a claude,opencode # Enable specific agents
    """
    show_banner()
    
    console.print("[cyan]Initializing agent-plugins...[/cyan]\n")
    
    # Create directory structure
    ensure_directory_structure()
    console.print(f"[green]✓[/green] Created {AGENT_PLUGINS_HOME}")
    
    # Install built-in commands (like /plugin-manager)
    builtin_count = install_builtin_commands()
    if builtin_count > 0:
        console.print(f"[green]✓[/green] Installed {builtin_count} built-in command(s)")
    
    # Determine which agents to enable
    if agents:
        # Explicit list provided
        enabled = [a.strip() for a in agents.split(",")]
    elif all_agents:
        # All agents
        enabled = list(AGENT_CONFIG.keys())
    else:
        # Interactive selection
        # Pre-select installed agents
        installed = get_installed_agents()
        if not installed:
            installed = ["claude", "opencode", "codex", "gemini"]
        
        console.print("")  # Add spacing before interactive selector
        enabled = select_agents_interactive(
            AGENT_CONFIG,
            prompt_text="Select agents to sync (installed agents pre-selected)",
            preselected=installed
        )
        console.print("")  # Add spacing after selection
    
    if not enabled:
        console.print("[yellow]No agents selected. Exiting.[/yellow]")
        raise typer.Exit(1)
    
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
        
        # Sync plugins (if supported)
        if agent["supports_plugins"] and agent["plugins_dir"]:
            source = AGENT_PLUGINS_HOME / "plugins" / "marketplaces"
            target = agent["home"] / agent["plugins_dir"]
            
            if target.is_symlink() and target.resolve() == source.resolve():
                console.print(f"  [dim]Marketplaces already linked[/dim]")
            elif create_symlink(source, target, force=force):
                console.print(f"  [green]✓[/green] Marketplaces linked")

        # Sync agents (if supported)
        if agent.get("supports_agents") and agent.get("agents_dir"):
            source = AGENT_PLUGINS_HOME / "agents"
            target = agent["home"] / agent["agents_dir"]
            
            if target.is_symlink() and target.resolve() == source.resolve():
                console.print(f"  [dim]Agents already linked[/dim]")
            elif create_link(source, target, force=force):
                console.print(f"  [green]✓[/green] Agents linked")

        # Sync commands (if supported)
        if agent.get("supports_commands"):
            source = AGENT_PLUGINS_HOME / "commands"
            
            # Determine target - some agents use alt location (e.g., OpenCode)
            if agent.get("commands_alt_dir"):
                target = agent["commands_alt_dir"]
            elif agent.get("commands_dir"):
                target = agent["home"] / agent["commands_dir"]
            else:
                target = None
            
            if target:
                if target.is_symlink() and target.resolve() == source.resolve():
                    console.print(f"  [dim]Commands already linked[/dim]")
                elif create_link(source, target, force=force):
                    console.print(f"  [green]✓[/green] Commands linked → {target}")

        # Sync hooks (if supported)
        if agent.get("supports_hooks") and agent.get("hooks_dir"):
            source = AGENT_PLUGINS_HOME / "hooks"
            target = agent["home"] / agent["hooks_dir"]
            
            if target.is_symlink() and target.resolve() == source.resolve():
                console.print(f"  [dim]Hooks already linked[/dim]")
            elif create_link(source, target, force=force):
                console.print(f"  [green]✓[/green] Hooks linked")

    console.print("\n[green]✓ Initialization complete![/green]")


def sync_agent_commands(agent_key: str, force: bool = False) -> bool:
    """Sync commands to an agent's command directory via symlink.
    
    For agents with a standard commands_dir, creates a symlink from
    agent_home/commands_dir → ~/.agent/commands/
    
    For agents with commands_alt_dir (like OpenCode), creates a symlink
    to the alternate location.
    
    Returns True if synced, False if skipped.
    """
    agent = AGENT_CONFIG.get(agent_key)
    if not agent or not agent.get("supports_commands"):
        return False
    
    source = AGENT_PLUGINS_HOME / "commands"
    if not source.exists():
        source.mkdir(parents=True, exist_ok=True)
    
    # Determine target directory
    if agent.get("commands_dir"):
        target = agent["home"] / agent["commands_dir"]
    elif agent.get("commands_alt_dir"):
        target = agent["commands_alt_dir"]
    else:
        return False
    
    # Create symlink
    return create_link(source, target, force=force)


def get_all_marketplace_dirs() -> List[Path]:
    """Get all marketplace directories from all known locations.
    
    Checks:
    - ~/.agent/plugins/marketplaces/
    - ~/.claude/plugins/marketplaces/
    - Other agent home dirs with marketplaces
    """
    marketplace_dirs = []
    
    # Check our canonical location
    agent_mp = AGENT_PLUGINS_HOME / "plugins" / "marketplaces"
    if agent_mp.exists():
        for mp_dir in agent_mp.iterdir():
            if mp_dir.is_dir() and not mp_dir.name.startswith("."):
                marketplace_dirs.append(mp_dir)
    
    # Check Claude's location (often the primary source)
    claude_mp = Path.home() / ".claude" / "plugins" / "marketplaces"
    if claude_mp.exists():
        for mp_dir in claude_mp.iterdir():
            if mp_dir.is_dir() and not mp_dir.name.startswith("."):
                # Avoid duplicates by name
                if not any(existing.name == mp_dir.name for existing in marketplace_dirs):
                    marketplace_dirs.append(mp_dir)
    
    return marketplace_dirs


def extract_agents_from_marketplaces() -> int:
    """Extract agent definitions from marketplaces to ~/.agent/agents/.
    
    Agents are defined as .md files in:
    - marketplaces/*/agents/*.md
    - marketplaces/*/plugins/*/agents/*.md
    
    Returns count of agents extracted.
    """
    agents_dir = AGENT_PLUGINS_HOME / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    
    for mp_dir in get_all_marketplace_dirs():
        if not mp_dir.is_dir() or mp_dir.name.startswith("."):
            continue
        
        # 1. Direct agents folder
        mp_agents = mp_dir / "agents"
        if mp_agents.exists():
            for agent_file in mp_agents.glob("*.md"):
                dest_name = f"{mp_dir.name}-{agent_file.name}"
                dest_path = agents_dir / dest_name
                shutil.copy2(agent_file, dest_path)
                count += 1
        
        # 2. Nested plugin agents
        plugins_dir = mp_dir / "plugins"
        if plugins_dir.exists():
            for plugin_dir in plugins_dir.iterdir():
                if plugin_dir.is_dir():
                    plugin_agents = plugin_dir / "agents"
                    if plugin_agents.exists():
                        for agent_file in plugin_agents.glob("*.md"):
                            dest_name = f"{mp_dir.name}-{plugin_dir.name}-{agent_file.name}"
                            dest_path = agents_dir / dest_name
                            shutil.copy2(agent_file, dest_path)
                            count += 1
    
    return count


def extract_commands_from_marketplaces() -> int:
    """Extract command definitions from marketplaces to ~/.agent/commands/.
    
    Commands are defined as .md files in:
    - marketplaces/*/commands/*.md
    - marketplaces/*/.claude/commands/*.md
    - marketplaces/*/plugins/*/commands/*.md
    
    Returns count of commands extracted.
    """
    commands_dir = AGENT_PLUGINS_HOME / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    
    for mp_dir in get_all_marketplace_dirs():
        
        # 1. Direct commands folder
        for cmd_source in [mp_dir / "commands", mp_dir / ".claude" / "commands"]:
            if cmd_source.exists():
                for cmd_file in cmd_source.glob("*.md"):
                    dest_name = f"{mp_dir.name}-{cmd_file.name}"
                    dest_path = commands_dir / dest_name
                    shutil.copy2(cmd_file, dest_path)
                    count += 1
        
        # 2. Nested plugin commands
        plugins_dir = mp_dir / "plugins"
        if plugins_dir.exists():
            for plugin_dir in plugins_dir.iterdir():
                if plugin_dir.is_dir():
                    cmds_dir = plugin_dir / "commands"
                    if cmds_dir.exists():
                        for cmd_file in cmds_dir.glob("*.md"):
                            dest_name = f"{mp_dir.name}-{plugin_dir.name}-{cmd_file.name}"
                            dest_path = commands_dir / dest_name
                            shutil.copy2(cmd_file, dest_path)
                            count += 1
    
    return count


def extract_hooks_from_marketplaces() -> int:
    """Extract hook definitions from marketplaces to ~/.agent/hooks/.
    
    Hooks are defined as hooks.json + scripts in:
    - marketplaces/*/hooks/
    - marketplaces/*/plugins/*/hooks/
    
    Returns count of hook sets extracted.
    """
    hooks_dir = AGENT_PLUGINS_HOME / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    
    for mp_dir in get_all_marketplace_dirs():
        
        # 1. Direct hooks folder
        mp_hooks = mp_dir / "hooks"
        if mp_hooks.exists() and (mp_hooks / "hooks.json").exists():
            dest_dir = hooks_dir / mp_dir.name
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            shutil.copytree(mp_hooks, dest_dir)
            count += 1
        
        # 2. Nested plugin hooks
        plugins_dir = mp_dir / "plugins"
        if plugins_dir.exists():
            for plugin_dir in plugins_dir.iterdir():
                if plugin_dir.is_dir():
                    plugin_hooks = plugin_dir / "hooks"
                    if plugin_hooks.exists() and (plugin_hooks / "hooks.json").exists():
                        dest_dir = hooks_dir / f"{mp_dir.name}-{plugin_dir.name}"
                        if dest_dir.exists():
                            shutil.rmtree(dest_dir)
                        shutil.copytree(plugin_hooks, dest_dir)
                        count += 1
    
    return count


def extract_skills_from_marketplaces() -> int:
    """Extract skill definitions from marketplaces to ~/.agent/skills/.
    
    Skills are defined as directories containing SKILL.md in:
    - marketplaces/*/skills/*/
    - marketplaces/*/plugins/*/skills/*/
    - Also referenced in marketplace.json plugins[].skills
    
    Returns count of skills extracted.
    """
    skills_dir = AGENT_PLUGINS_HOME / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    
    for mp_dir in get_all_marketplace_dirs():
        
        # Check marketplace.json for skill references
        mp_json_paths = [
            mp_dir / ".claude-plugin" / "marketplace.json",
            mp_dir / "marketplace.json",
        ]
        
        skill_paths = []
        for mp_json_path in mp_json_paths:
            if mp_json_path.exists():
                with open(mp_json_path) as f:
                    mp_data = json.load(f)
                for plugin in mp_data.get("plugins", []):
                    for skill_ref in plugin.get("skills", []):
                        # skill_ref is like "./document-skills/xlsx"
                        skill_path = mp_dir / skill_ref.lstrip("./")
                        if skill_path.exists() and (skill_path / "SKILL.md").exists():
                            skill_paths.append(skill_path)
        
        # Also look for any SKILL.md files directly
        for skill_md in mp_dir.rglob("SKILL.md"):
            skill_path = skill_md.parent
            if skill_path not in skill_paths:
                skill_paths.append(skill_path)
        
        # Copy each skill
        for skill_path in skill_paths:
            skill_name = f"{mp_dir.name}-{skill_path.name}"
            dest_dir = skills_dir / skill_name
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            shutil.copytree(skill_path, dest_dir)
            count += 1
    
    return count



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
        
        # Check skills link status (handle agents without skills_dir)
        skills_linked = "N/A"
        if agent.get("supports_skills") and agent.get("skills_dir"):
            skills_target = agent["home"] / agent["skills_dir"]
            skills_linked = "✓" if skills_target.is_symlink() else "✗"
        
        table.add_row(
            agent["name"],
            installed,
            skills_linked,
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


@app.command()
def extract(
    component: Optional[str] = typer.Argument(
        None,
        help="Component to extract: skills, agents, commands, hooks (or all if not specified)"
    ),
):
    """
    Extract components from marketplaces to ~/.agent/.
    
    This copies skills, agents, commands, and hooks from installed
    marketplaces into the canonical ~/.agent/ directories.
    
    Examples:
        agent-plugins extract           # Extract all components
        agent-plugins extract skills    # Extract only skills
        agent-plugins extract agents    # Extract only agents
    """
    components = ["skills", "agents", "commands", "hooks"]
    
    if component:
        if component not in components:
            console.print(f"[red]Unknown component: {component}[/red]")
            console.print(f"Valid components: {', '.join(components)}")
            raise typer.Exit(1)
        components = [component]
    
    console.print("[cyan]Extracting components from marketplaces...[/cyan]\n")
    
    results = {}
    
    if "skills" in components:
        count = extract_skills_from_marketplaces()
        results["skills"] = count
        console.print(f"[green]✓[/green] Extracted {count} skills")
    
    if "agents" in components:
        count = extract_agents_from_marketplaces()
        results["agents"] = count
        console.print(f"[green]✓[/green] Extracted {count} agents")
    
    if "commands" in components:
        count = extract_commands_from_marketplaces()
        results["commands"] = count
        console.print(f"[green]✓[/green] Extracted {count} commands")
    
    if "hooks" in components:
        count = extract_hooks_from_marketplaces()
        results["hooks"] = count
        console.print(f"[green]✓[/green] Extracted {count} hook sets")
    
    total = sum(results.values())
    console.print(f"\n[green]✓ Extracted {total} total components to {AGENT_PLUGINS_HOME}[/green]")


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
# Plugin Commands (mirrors 'claude plugin')
# =============================================================================

def get_available_plugins() -> List[Dict[str, Any]]:
    """Get all available plugins from all marketplaces."""
    plugins = []
    
    # Check both agent-plugins and Claude directories
    mp_dirs = [
        AGENT_PLUGINS_HOME / "plugins" / "marketplaces",
        Path.home() / ".claude" / "plugins" / "marketplaces",
    ]
    
    seen = set()
    for mp_base in mp_dirs:
        if not mp_base.exists():
            continue
        for mp_dir in mp_base.iterdir():
            if not mp_dir.is_dir() or mp_dir.name.startswith("."):
                continue
            
            mp_json = mp_dir / ".claude-plugin" / "marketplace.json"
            if mp_json.exists():
                try:
                    with open(mp_json) as f:
                        mp_data = json.load(f)
                    for plugin in mp_data.get("plugins", []):
                        plugin_key = f"{plugin.get('name')}@{mp_dir.name}"
                        if plugin_key not in seen:
                            seen.add(plugin_key)
                            plugins.append({
                                **plugin,
                                "marketplace": mp_dir.name,
                                "marketplace_path": mp_dir,
                            })
                except Exception:
                    pass
    
    return plugins


def get_installed_plugins() -> Dict[str, Any]:
    """Get installed plugins from config."""
    config = load_config()
    return config.get("installed_plugins", {})


def save_installed_plugins(plugins: Dict[str, Any]):
    """Save installed plugins to config."""
    config = load_config()
    config["installed_plugins"] = plugins
    save_config(config)


@plugin_app.command("install")
def plugin_install(
    plugin: str = typer.Argument(..., help="Plugin name (use plugin@marketplace for specific marketplace)"),
    scope: str = typer.Option("user", "--scope", "-s", help="Installation scope: user, project, or local"),
):
    """
    Install a plugin from available marketplaces.
    
    Examples:
        agent-plugins plugin install pdf-processing
        agent-plugins plugin install pdf-processing@anthropic-skills
    """
    # Parse plugin@marketplace syntax
    if "@" in plugin:
        plugin_name, marketplace_name = plugin.rsplit("@", 1)
    else:
        plugin_name = plugin
        marketplace_name = None
    
    available = get_available_plugins()
    
    # Find matching plugins
    matches = []
    for p in available:
        if p.get("name") == plugin_name:
            if marketplace_name is None or p.get("marketplace") == marketplace_name:
                matches.append(p)
    
    if not matches:
        console.print(f"[red]Error:[/red] Plugin '{plugin_name}' not found in any marketplace")
        if marketplace_name:
            console.print(f"[dim]Searched in marketplace: {marketplace_name}[/dim]")
        console.print("\n[dim]Use 'agent-plugins plugin marketplace list' to see available marketplaces[/dim]")
        raise typer.Exit(1)
    
    if len(matches) > 1 and marketplace_name is None:
        console.print(f"[yellow]Plugin '{plugin_name}' found in multiple marketplaces:[/yellow]")
        for m in matches:
            console.print(f"  - {m.get('name')}@{m.get('marketplace')}")
        console.print("\n[dim]Use plugin@marketplace syntax to specify which one[/dim]")
        raise typer.Exit(1)
    
    plugin_info = matches[0]
    mp_name = plugin_info.get("marketplace")
    mp_path = plugin_info.get("marketplace_path")
    
    console.print(f"[cyan]Installing {plugin_name} from {mp_name}...[/cyan]")
    
    # Determine plugin source path
    source = plugin_info.get("source", f"./{plugin_name}")
    if isinstance(source, str) and source.startswith("./"):
        plugin_path = mp_path / source.lstrip("./")
    else:
        plugin_path = mp_path / "plugins" / plugin_name
    
    if not plugin_path.exists():
        # Try alternate locations
        for alt in [mp_path / plugin_name, mp_path / "skills" / plugin_name]:
            if alt.exists():
                plugin_path = alt
                break
    
    if not plugin_path.exists():
        console.print(f"[red]Error:[/red] Plugin source not found at {plugin_path}")
        raise typer.Exit(1)
    
    # Track installation
    installed = get_installed_plugins()
    installed[plugin_name] = {
        "marketplace": mp_name,
        "source": str(plugin_path),
        "version": plugin_info.get("version", "unknown"),
        "scope": scope,
    }
    save_installed_plugins(installed)
    
    console.print(f"[green]✓[/green] Installed {plugin_name}@{mp_name}")
    
    # Show plugin details
    if plugin_info.get("description"):
        console.print(f"[dim]  {plugin_info.get('description')}[/dim]")


@plugin_app.command("uninstall")
def plugin_uninstall(
    plugin: str = typer.Argument(..., help="Plugin name to uninstall"),
):
    """Uninstall an installed plugin."""
    installed = get_installed_plugins()
    
    if plugin not in installed:
        console.print(f"[red]Error:[/red] Plugin '{plugin}' is not installed")
        raise typer.Exit(1)
    
    del installed[plugin]
    save_installed_plugins(installed)
    
    console.print(f"[green]✓[/green] Uninstalled {plugin}")


# Alias for uninstall
@plugin_app.command("remove", hidden=True)
def plugin_remove(plugin: str = typer.Argument(...)):
    """Remove an installed plugin (alias for uninstall)."""
    plugin_uninstall(plugin)


@plugin_app.command("list")
def plugin_list():
    """List installed and available plugins."""
    installed = get_installed_plugins()
    available = get_available_plugins()
    
    if installed:
        console.print("\n[bold]Installed plugins:[/bold]\n")
        for name, info in installed.items():
            console.print(f"  [green]✓[/green] [bold]{name}[/bold]@{info.get('marketplace', 'unknown')}")
            if info.get("version"):
                console.print(f"    [dim]Version: {info.get('version')}[/dim]")
    
    console.print("\n[bold]Available plugins:[/bold]\n")
    
    # Group by marketplace
    by_marketplace: Dict[str, List] = {}
    for p in available:
        mp = p.get("marketplace", "unknown")
        if mp not in by_marketplace:
            by_marketplace[mp] = []
        by_marketplace[mp].append(p)
    
    for mp, plugins in sorted(by_marketplace.items()):
        console.print(f"  [cyan]{mp}[/cyan]")
        for p in plugins[:5]:  # Show first 5
            name = p.get("name", "unknown")
            desc = p.get("description", "")[:50]
            installed_marker = "[green]✓[/green] " if name in installed else "  "
            console.print(f"    {installed_marker}{name}")
            if desc:
                console.print(f"      [dim]{desc}[/dim]")
        if len(plugins) > 5:
            console.print(f"    [dim]... and {len(plugins) - 5} more[/dim]")
        console.print()


@plugin_app.command("enable")
def plugin_enable(plugin: str = typer.Argument(..., help="Plugin name to enable")):
    """Enable a disabled plugin."""
    installed = get_installed_plugins()
    
    if plugin not in installed:
        console.print(f"[red]Error:[/red] Plugin '{plugin}' is not installed")
        raise typer.Exit(1)
    
    installed[plugin]["enabled"] = True
    save_installed_plugins(installed)
    console.print(f"[green]✓[/green] Enabled {plugin}")


@plugin_app.command("disable")
def plugin_disable(plugin: str = typer.Argument(..., help="Plugin name to disable")):
    """Disable an enabled plugin."""
    installed = get_installed_plugins()
    
    if plugin not in installed:
        console.print(f"[red]Error:[/red] Plugin '{plugin}' is not installed")
        raise typer.Exit(1)
    
    installed[plugin]["enabled"] = False
    save_installed_plugins(installed)
    console.print(f"[green]✓[/green] Disabled {plugin}")


# =============================================================================
# Marketplace Commands
# =============================================================================

@marketplace_app.command("add")
def marketplace_add(
    source: str = typer.Argument(..., help="GitHub repo (user/repo) or git URL"),
    github_token: Optional[str] = typer.Option(
        None, "--github-token", "-t",
        help="GitHub token for private repos (or set GH_TOKEN/GITHUB_TOKEN env)"
    ),
):
    """
    Add a marketplace from a GitHub repository.
    
    Examples:
        agent-plugins marketplace add anthropics/skills
        agent-plugins marketplace add https://github.com/user/my-plugins.git
        agent-plugins marketplace add user/private-repo --github-token ghp_xxx
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
    
    # Use authenticated URL if token available
    clone_url = get_authenticated_git_url(git_url, github_token)
    
    # Show public URL (don't leak token)
    console.print(f"[cyan]Cloning {git_url}...[/cyan]")
    if get_github_token(github_token):
        console.print("[dim]  (using authenticated request)[/dim]")
    
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", clone_url, str(target_dir)],
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
    """List all configured marketplaces."""
    marketplaces_dir = AGENT_PLUGINS_HOME / "plugins" / "marketplaces"
    
    # Also check Claude's marketplace directory
    claude_mp_dir = Path.home() / ".claude" / "plugins" / "marketplaces"
    
    if not marketplaces_dir.exists() and not claude_mp_dir.exists():
        console.print("[yellow]No marketplaces directory. Run 'agent-plugins init' first.[/yellow]")
        return
    
    console.print("\n[bold]Configured marketplaces:[/bold]\n")
    
    seen = set()
    
    def print_marketplace(mp_dir: Path):
        if mp_dir.name in seen or mp_dir.name.startswith("."):
            return
        seen.add(mp_dir.name)
        
        # Determine source type
        git_config = mp_dir / ".git" / "config"
        source_info = "Local"
        
        if git_config.exists():
            try:
                with open(git_config) as f:
                    content = f.read()
                    if "url = " in content:
                        for line in content.split("\n"):
                            if "url = " in line:
                                url = line.split("url = ")[1].strip()
                                if "github.com" in url:
                                    # Extract owner/repo from GitHub URL
                                    parts = url.replace(".git", "").split("github.com")[-1].strip("/:")
                                    source_info = f"GitHub ({parts})"
                                else:
                                    source_info = f"Git ({url})"
                                break
            except Exception:
                pass
        
        console.print(f"  [cyan]❯[/cyan] [bold]{mp_dir.name}[/bold]")
        console.print(f"    [dim]Source: {source_info}[/dim]")
        console.print()
    
    # List from agent-plugins directory
    if marketplaces_dir.exists():
        for mp_dir in sorted(marketplaces_dir.iterdir()):
            if mp_dir.is_dir():
                print_marketplace(mp_dir)
    
    # List from Claude's directory (if different)
    if claude_mp_dir.exists() and claude_mp_dir != marketplaces_dir:
        for mp_dir in sorted(claude_mp_dir.iterdir()):
            if mp_dir.is_dir():
                print_marketplace(mp_dir)


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
        if agent_config.get("supports_skills"):
            source = AGENT_PLUGINS_HOME / "skills"
            target = agent_config["home"] / agent_config["skills_dir"]
            
            if create_symlink(source, target, force=force):
                console.print(f"  [green]✓[/green] Skills linked")
            elif target.is_symlink():
                console.print(f"  [dim]Skills already linked[/dim]")
        
        # Sync plugins (if supported)
        if agent_config.get("supports_plugins") and agent_config.get("plugins_dir"):
            source = AGENT_PLUGINS_HOME / "plugins" / "marketplaces"
            target = agent_config["home"] / agent_config["plugins_dir"]
            
            if target.is_symlink() and target.resolve() == source.resolve():
                console.print(f"  [dim]Marketplaces already linked[/dim]")
            elif create_symlink(source, target, force=force):
                console.print(f"  [green]✓[/green] Marketplaces linked")

        # Sync commands (if supported)
        if agent_config.get("supports_commands"):
            source = AGENT_PLUGINS_HOME / "commands"
            
            # Determine target - some agents use alt location (e.g., OpenCode)
            if agent_config.get("commands_alt_dir"):
                target = agent_config["commands_alt_dir"]
            elif agent_config.get("commands_dir"):
                target = agent_config["home"] / agent_config["commands_dir"]
            else:
                target = None
            
            if target:
                if create_link(source, target, force=force):
                    console.print(f"  [green]✓[/green] Commands linked")
                elif target.is_symlink():
                    console.print(f"  [dim]Commands already linked[/dim]")

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


# =============================================================================
# Version & Update Commands
# =============================================================================

# Package version - keep in sync with pyproject.toml
__version__ = "0.1.0"


def get_installed_version() -> str:
    """Get the currently installed version."""
    try:
        import importlib.metadata
        return importlib.metadata.version("agent-plugins")
    except Exception:
        return __version__


def get_latest_version() -> Optional[str]:
    """Fetch the latest version from PyPI or GitHub."""
    # Try PyPI first
    try:
        response = httpx.get(
            "https://pypi.org/pypi/agent-plugins/json",
            timeout=5,
            follow_redirects=True
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("info", {}).get("version")
    except Exception:
        pass
    
    # Fallback: Try GitHub releases API
    try:
        response = httpx.get(
            "https://api.github.com/repos/jms830/agent-plugins/releases/latest",
            timeout=5,
            follow_redirects=True,
            headers=get_github_auth_headers()
        )
        if response.status_code == 200:
            data = response.json()
            tag = data.get("tag_name", "")
            # Remove 'v' prefix if present
            return tag.lstrip("v") if tag else None
    except Exception:
        pass
    
    return None


@app.command()
def version(
    check_update: bool = typer.Option(
        False, "--check", "-c",
        help="Check for available updates"
    ),
):
    """Display version and check for updates."""
    import platform
    
    show_banner()
    
    installed = get_installed_version()
    
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="cyan", justify="right")
    table.add_column("Value", style="white")
    
    table.add_row("Version", installed)
    table.add_row("Python", platform.python_version())
    table.add_row("Platform", platform.system())
    table.add_row("Config", str(AGENT_PLUGINS_HOME / "config.json"))
    
    if check_update:
        console.print("[dim]Checking for updates...[/dim]")
        latest = get_latest_version()
        if latest:
            table.add_row("Latest", latest)
            if latest != installed:
                table.add_row("", "[yellow]Update available![/yellow]")
        else:
            table.add_row("Latest", "[dim]Unable to check[/dim]")
    
    panel = Panel(
        table,
        title="[bold cyan]Agent Plugins[/bold cyan]",
        border_style="cyan",
        padding=(1, 2)
    )
    console.print(panel)
    
    if check_update:
        console.print("\n[dim]To update, run:[/dim]")
        console.print("  [cyan]uv tool upgrade agent-plugins[/cyan]")
        console.print("  [dim]or[/dim]")
        console.print("  [cyan]pip install --upgrade agent-plugins[/cyan]")


@app.command()
def upgrade(
    force: bool = typer.Option(
        False, "--force", "-f",
        help="Force upgrade even if already on latest"
    ),
):
    """Upgrade agent-plugins to the latest version.
    
    This command updates both the CLI tool and refreshes all
    installed marketplaces.
    """
    show_banner()
    
    console.print("[cyan]Checking for updates...[/cyan]\n")
    
    installed = get_installed_version()
    latest = get_latest_version()
    
    console.print(f"Installed: [cyan]{installed}[/cyan]")
    if latest:
        console.print(f"Latest:    [cyan]{latest}[/cyan]")
    else:
        console.print("Latest:    [dim]Unable to determine[/dim]")
    
    # Check if update is needed
    needs_update = force or (latest and latest != installed) or (latest is None)
    
    if not needs_update:
        console.print("\n[green]✓ Already on the latest version![/green]")
    else:
        if latest is None:
            console.print("\n[yellow]Unable to determine latest version. Attempting upgrade...[/yellow]")
        else:
            console.print("\n[cyan]Upgrading agent-plugins...[/cyan]")
        
        # Try uv first, then pip
        upgrade_cmd = None
        git_source = "git+https://github.com/jms830/agent-plugins.git"
        use_git_reinstall = latest is None
        
        if shutil.which("uv"):
            if use_git_reinstall:
                upgrade_cmd = ["uv", "tool", "install", "agent-plugins", "--force", "--from", git_source]
            else:
                upgrade_cmd = ["uv", "tool", "upgrade", "agent-plugins"]
        elif shutil.which("pip"):
            if use_git_reinstall:
                upgrade_cmd = [sys.executable, "-m", "pip", "install", "--force-reinstall", git_source]
            else:
                upgrade_cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "agent-plugins"]
        
        if upgrade_cmd:
            try:
                result = subprocess.run(
                    upgrade_cmd,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    console.print("[green]✓ CLI upgraded successfully![/green]")
                else:
                    console.print(f"[yellow]Warning: Upgrade may have failed[/yellow]")
                    if result.stderr:
                        console.print(f"[dim]{result.stderr[:200]}[/dim]")
            except Exception as e:
                console.print(f"[red]Error upgrading:[/red] {e}")
        else:
            console.print("[yellow]No package manager found (uv or pip)[/yellow]")
            console.print("Please run manually:")
            if use_git_reinstall:
                console.print("  [cyan]uv tool install agent-plugins --force --from git+https://github.com/jms830/agent-plugins.git[/cyan]")
                console.print("  [dim]or[/dim]")
                console.print("  [cyan]pip install --force-reinstall git+https://github.com/jms830/agent-plugins.git[/cyan]")
            else:
                console.print("  [cyan]uv tool upgrade agent-plugins[/cyan]")
                console.print("  [dim]or[/dim]")
                console.print("  [cyan]pip install --upgrade agent-plugins[/cyan]")
        
        if latest is None:
            console.print("\n[dim]Tip: If you installed from git, you can force reinstall with[/dim]")
            console.print("  [cyan]uv tool install agent-plugins --force --from git+https://github.com/jms830/agent-plugins.git[/cyan]")
            console.print("  [dim]or[/dim]")
            console.print("  [cyan]pip install --force-reinstall git+https://github.com/jms830/agent-plugins.git[/cyan]")
    
    # Also update marketplaces
    console.print("\n[cyan]Updating marketplaces...[/cyan]")
    marketplace_update(name=None)
    
    # Re-extract components
    console.print("\n[cyan]Re-extracting components...[/cyan]")
    
    skills_count = extract_skills_from_marketplaces()
    agents_count = extract_agents_from_marketplaces()
    commands_count = extract_commands_from_marketplaces()
    hooks_count = extract_hooks_from_marketplaces()
    
    console.print(f"[green]✓[/green] Extracted {skills_count} skills, {agents_count} agents, {commands_count} commands, {hooks_count} hooks")
    
    console.print("\n[green]✓ Upgrade complete![/green]")


def main():
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
