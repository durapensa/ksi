# Claude Process Management Daemon

A lightweight, reliable daemon for managing `claude -p` processes with hot-reloadable Python modules.

## Architecture

The system consists of three main components:

1. **Daemon (`daemon.py`)**: Long-running process that manages other processes and dynamically loads Python modules
2. **Client Library (`client.py`)**: JSONL-based Unix domain socket client for communicating with the daemon
3. **Claude Modules (`claude_modules/`)**: Directory for Python modules that Claude can write and the daemon can hot-reload

## Features

- **Process Management**: Spawn and track `claude -p` processes reliably
- **Hot Module Reloading**: Write Python code that gets loaded without restarting the daemon
- **Simple JSONL Protocol**: Easy-to-implement communication format
- **Dynamic Function Calls**: Execute functions in loaded modules without modifying daemon code
- **Async Architecture**: Built on asyncio for concurrent client handling

## Quick Start

1. **Start the daemon**:
   ```bash
   python3 daemon.py
   ```

2. **Test the system**:
   ```bash
   python3 test_daemon.py
   ```

3. **Use the client CLI**:
   ```bash
   # Ping the daemon
   python3 client.py ping

   # Load a module
   python3 client.py load example

   # Call a function
   python3 client.py call example hello Claude

   # Spawn a process
   python3 client.py spawn claude -p "test command"

   # List processes
   python3 client.py list
   ```

## Protocol

The daemon uses a simple JSONL (JSON Lines) protocol over Unix domain socket:

### Request Format
```json
{"command": "command_name", "param1": "value1", "param2": "value2"}
```

### Response Format
```json
{"success": true, "result": "..."}
{"success": false, "error": "error message"}
```

### Available Commands

- `spawn_process`: Spawn a new process
  - Parameters: `cmd` (list), `process_id` (optional)
  
- `list_processes`: List all managed processes
  
- `process_info`: Get information about a specific process
  - Parameters: `process_id`
  
- `load_module`: Load or reload a Python module
  - Parameters: `module_name`
  
- `call_function`: Call a function in a loaded module
  - Parameters: `module_name`, `function_name`, `args` (optional), `kwargs` (optional)
  
- `list_modules`: List all loaded modules and their functions
  
- `ping`: Health check
  
- `shutdown`: Gracefully shut down the daemon

## Writing Claude Modules

Claude can write Python modules in the `claude_modules/` directory. These modules are hot-reloadable and can contain any Python functions. Example:

```python
# claude_modules/my_module.py
def process_data(input_data):
    """Process some data"""
    return {"processed": input_data.upper()}

def spawn_analysis():
    """Spawn another claude process for analysis"""
    from client import spawn_claude_process
    return spawn_claude_process(['claude', '-p', 'analyze'])
```

Then load and use it:
```python
client.load_module('my_module')
client.call_function('my_module', 'process_data', ['hello'])
```

## Environment Variables

- `CLAUDE_DAEMON_SOCKET`: Path to Unix domain socket (default: `/tmp/claude_daemon.sock`)

## Integration with Claude

When Claude needs to spawn another `claude -p` process or build complex systems, it can:

1. Write Python modules to `claude_modules/`
2. Load them into the daemon
3. Call functions that orchestrate complex workflows
4. Spawn and manage multiple processes reliably

This enables Claude to build sophisticated multi-process systems while keeping the core daemon simple and stable.