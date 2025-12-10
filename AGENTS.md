# AGENTS.md

## Build & Run
- **Install:** `uv tool install -e .` or `pip install -e .`
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

## Project Structure
- All code lives in `src/agent_plugins/__init__.py` (single-file module)
- Entry point: `main()` function
- Sub-commands via `app.add_typer()` pattern
- Agent configs mirror [spec-kit](https://github.com/github/spec-kit) methodology
