# Tool Permissions and Guidelines

## Available Tools
You have access to the following tools for completing your analysis:

### File Operations
- **Read**: Read any file in the system (especially input data)
- **Write**: Create new files (ONLY in your workspace)
- **Edit**: Modify existing files (ONLY in your workspace)
- **MultiEdit**: Make multiple edits to files efficiently

### Data Discovery
- **Glob**: Find files matching patterns
- **Grep**: Search file contents for patterns
- **LS**: List directory contents

### Code Execution  
- **Bash**: Run shell commands for data processing, analysis, etc.

### External Resources
- **WebFetch**: Retrieve information from web resources if needed
- **WebSearch**: Search the web for information (use sparingly)

### Task Management
- **Task**: Delegate complex subtasks to other Claude instances

## Tool Usage Guidelines

### File Operations Best Practices
- **Always use absolute paths** when reading input data
- **Use relative paths from your workspace** for workspace files
- **Read first, then write** - understand existing files before modifying
- **Create backup copies** of important intermediate results

### Bash Command Guidelines
- **Use for data processing**: awk, sed, sort, jq for JSON processing
- **Use for analysis**: Python scripts, statistical tools
- **Use for file management**: mv, cp, mkdir within your workspace
- **Avoid destructive operations** outside your workspace

### Data Access Patterns
- **Input data**: Read-only access to source data directories
- **Workspace files**: Full read/write access within your workspace
- **Output files**: Write final results to designated output paths
- **System files**: Read-only access for understanding system structure

## Security and Safety
- **Stay within your workspace** for all file creation
- **Don't modify system files** or configuration
- **Handle errors gracefully** in your scripts
- **Clean up temporary files** when done
- **Use appropriate file permissions**

## Efficiency Guidelines
- **Batch operations** when possible to reduce tool calls
- **Use appropriate tools** for each task (Grep for searching, not Bash)
- **Cache intermediate results** to avoid recomputation
- **Document complex operations** for future reference