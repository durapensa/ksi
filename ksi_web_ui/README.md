# KSI Web UI - Real-time System Visualization

Real-time visualization of the KSI agent ecosystem using Cytoscape.js.

## Architecture

The KSI visualization system now uses native WebSocket transport:

1. **KSI Daemon** - The core system with native WebSocket transport (ws://localhost:8765)
2. **Web UI** - This visualization interface (http://localhost:8080)

## Quick Start

### 1. Start KSI daemon with WebSocket transport:
```bash
KSI_TRANSPORTS=unix,websocket ./daemon_control.py start
```

### 2. Start the Web UI:

**Using web_control.py (recommended):**
```bash
./web_control.py start
```

**Or manually with Python HTTP server:**
```bash
cd ksi_web_ui
python -m http.server 8080
```

### 3. Open visualization:
Navigate to http://localhost:8080

## Features

- **Agent Ecosystem Panel**: Shows agents, their relationships, and message flows
  - Agent nodes pulse with gold animation when they originate events
  - Parent-child relationships shown for agent spawning
  - Active completions highlighted in blue
  
- **State System Panel**: Displays graph database entities and relationships
  
- **Event Stream Panel**: Real-time log of all KSI events
  - Agent-originated events marked with 🤖 icon and gold highlighting
  - Shows originator agent ID for full traceability
  - Tooltips show full event data and agent IDs
  - Color-coded by event type (agent, completion, orchestration, state)

## Architecture

```
KSI Daemon (with native WebSocket) ←→ Browser Visualization
```

The daemon:
- Provides native WebSocket transport on port 8765
- Streams events directly to browser clients
- Handles CORS for cross-origin connections

The visualization:
- Connects directly to daemon WebSocket
- Maintains state across daemon restarts
- Shows real-time agent activity
- Uses automatic graph layouts

## Development

The system is designed for active development:
- Native WebSocket transport eliminates need for separate bridge
- Visualization preserves state (assumes checkpoint restore)
- All events are logged in the event stream panel
- New event handlers can be added incrementally

### Custom CORS Configuration

If serving the UI from a different port or domain, configure CORS in the daemon:

```bash
# Set allowed origins
export KSI_WEBSOCKET_CORS_ORIGINS="http://localhost:3001,https://myapp.com"
KSI_TRANSPORTS=unix,websocket ./daemon_control.py start
```

Default allowed origins:
- `http://localhost:8080` (default for ksi_web_ui)
- `http://localhost:3000` (common React dev server)
- `*` (if no origins specified - development only)

## Troubleshooting

### WebSocket not connecting
- Ensure daemon was started with WebSocket transport: `KSI_TRANSPORTS=unix,websocket`
- Check if port 8765 is available: `lsof -i :8765`
- Verify CORS settings if accessing from non-localhost

### No events appearing
- Check browser console for WebSocket errors
- Verify subscription was successful (look for `monitor:subscribe` response)
- Ensure daemon is running and healthy: `./daemon_control.py health`