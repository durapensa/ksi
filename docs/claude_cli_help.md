Usage: claude [options] [command] [prompt]

Claude Code - starts an interactive session by default, use -p/--print for
non-interactive output

Arguments:
  prompt                          Your prompt

Options:
  -d, --debug                     Enable debug mode
  --verbose                       Override verbose mode setting from config
  -p, --print                     Print response and exit (useful for pipes)
  --output-format <format>        Output format (only works with --print):
                                  "text" (default), "json" (single result), or
                                  "stream-json" (realtime streaming) (choices:
                                  "text", "json", "stream-json")
  --input-format <format>         Input format (only works with --print):
                                  "text" (default), or "stream-json" (realtime
                                  streaming input) (choices: "text",
                                  "stream-json")
  --mcp-debug                     [DEPRECATED. Use --debug instead] Enable MCP
                                  debug mode (shows MCP server errors)
  --dangerously-skip-permissions  Bypass all permission checks. Recommended
                                  only for sandboxes with no internet access.
  --allowedTools <tools...>       Comma or space-separated list of tool names
                                  to allow (e.g. "Bash(git:*) Edit")
  --disallowedTools <tools...>    Comma or space-separated list of tool names
                                  to deny (e.g. "Bash(git:*) Edit")
  --mcp-config <file or string>   Load MCP servers from a JSON file or string
  -c, --continue                  Continue the most recent conversation
  -r, --resume [sessionId]        Resume a conversation - provide a session ID
                                  or interactively select a conversation to
                                  resume
  --model <model>                 Model for the current session. Provide an
                                  alias for the latest model (e.g. 'sonnet' or
                                  'opus') or a model's full name (e.g.
                                  'claude-sonnet-4-20250514').
  --fallback-model <model>        Enable automatic fallback to specified model
                                  when default model is overloaded (only works
                                  with --print)
  --add-dir <directories...>      Additional directories to allow tool access
                                  to
  -v, --version                   Output the version number
  -h, --help                      Display help for command

Commands:
  config                          Manage configuration (eg. claude config set
                                  -g theme dark)
  mcp                             Configure and manage MCP servers
  migrate-installer               Migrate from global npm installation to local
                                  installation
  doctor                          Check the health of your Claude Code
                                  auto-updater
  update                          Check for updates and install if available
