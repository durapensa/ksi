# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
Python project managed with UV - a fast Python package installer and resolver.

## Development Setup and Commands

### UV Installation
If UV is not installed: `curl -LsSf https://astral.sh/uv/install.sh | sh`

### Common UV Commands
- **Create virtual environment**: `uv venv`
- **Activate virtual environment**: `source .venv/bin/activate`
- **Install dependencies**: `uv pip install -r requirements.txt`
- **Add new dependency**: `uv pip install <package>` then `uv pip freeze > requirements.txt`
- **Run Python scripts**: `uv run python <script.py>`
- **Install in development mode**: `uv pip install -e .`

### Project Structure
- Python source files should be organized in a package directory
- Use `requirements.txt` for dependency management
- Create `pyproject.toml` for project metadata if needed

### Testing
- Run tests: `uv run pytest`
- Run specific test: `uv run pytest path/to/test_file.py::test_function`
- Run with coverage: `uv run pytest --cov`

### Code Quality
- Format code: `uv run black .`
- Lint code: `uv run ruff check`
- Type check: `uv run mypy .`

## Development Workflow
1. Always ensure virtual environment is activated before development
2. Use UV for all package management operations
3. Keep requirements.txt updated when adding/removing dependencies
4. Run formatters and linters before committing code

## Claude Process Management Daemon

This project includes a daemon system for reliable process management and dynamic code execution:

### Architecture
- **daemon.py**: Asyncio-based daemon that listens on Unix domain socket
- **client.py**: JSONL client library for communicating with daemon
- **claude_modules/**: Directory for hot-reloadable Python modules

### Key Features
- Spawn and manage `claude -p` processes reliably
- Hot-reload Python modules without restarting daemon
- Execute functions in loaded modules dynamically
- JSONL protocol for simple, blocking communication

### Usage
1. Start daemon: `python3 daemon.py`
2. Use client: `python3 client.py <command>` or import `ClaudeClient`
3. Write modules in `claude_modules/` - daemon can reload them on command

### Common Daemon Commands
- `spawn_process`: Spawn a new managed process
- `load_module`: Load/reload a Python module from claude_modules/
- `call_function`: Execute a function in a loaded module
- `list_processes`: Show all managed processes
- `list_modules`: Show all loaded modules and their functions

### Writing Claude Modules
Place Python files in `claude_modules/`. The daemon can dynamically load and execute functions from these modules. This enables Claude to build complex systems incrementally by writing new modules that extend functionality.