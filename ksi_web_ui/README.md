# KSI Web UI - Real-time System Visualization

Real-time visualization of the KSI agent ecosystem using Cytoscape.js.

## Architecture

The KSI visualization system has three independent components:

1. **KSI Daemon** - The core system (Unix socket)
2. **WebSocket Bridge** - Transport adapter (ws://localhost:8765)
3. **Web UI** - This visualization interface (http://localhost:8080)

## Quick Start

### 1. Start KSI daemon (if not already running):
```bash
./daemon_control.py start
```

### 2. Start WebSocket bridge (in separate terminal):
```bash
python websocket_bridge.py
```

Bridge options:
- `--ws-port 8765` - WebSocket port (default: 8765)
- `--ws-host localhost` - WebSocket host (default: localhost)
- `--cors-origin` - Add additional CORS origin (can use multiple times)

Note: The bridge defaults to allowing CORS from:
- `http://localhost:8080` (default for ksi_web_ui)
- `http://localhost:3000` (common React dev server)
- `file://` (direct file access)

### 3. Serve the Web UI (in separate terminal):

**Option A - Python HTTP server (recommended for development):**
```bash
cd ksi_web_ui
python -m http.server 8080
```

**Option B - Node.js http-server:**
```bash
npx http-server ksi_web_ui -p 8080
```

**Option C - Direct file access:**
```bash
open ksi_web_ui/index.html
```
Note: Some browsers restrict WebSocket connections from file:// URLs

### 4. Open visualization:
Navigate to http://localhost:8080

## Features

- **Agent Ecosystem Panel**: Shows agents, their relationships, and message flows
- **State System Panel**: Displays graph database entities and relationships  
- **Event Stream Panel**: Real-time log of all KSI events

## Architecture

```
KSI Daemon ←→ WebSocket Bridge ←→ Browser Visualization
```

The bridge:
- Connects to KSI via Unix socket
- Subscribes to all events
- Forwards events to WebSocket clients
- Automatically reconnects when daemon restarts

The visualization:
- Maintains state across daemon restarts
- Assumes checkpoint restore works
- Shows real-time agent activity
- Uses automatic graph layouts

## Development

The system is designed for active development:
- Bridge reconnects automatically when daemon restarts
- Visualization preserves state (assumes checkpoint restore)
- All events are logged in the event stream panel
- New event handlers can be added incrementally

### Custom CORS Configuration

If serving the UI from a different port or domain:

```bash
# Simple comma-separated format
export KSI_WEBSOCKET_BRIDGE_CORS_ORIGINS="http://localhost:3001,https://myapp.com"
python websocket_bridge.py

# Or use command line for one-off origins
python websocket_bridge.py --cors-origin http://localhost:3001
```