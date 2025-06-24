#!/bin/bash
#
# KSI Daemon Control Script
# Usage: ./daemon_control.sh {start|stop|restart|status|health|logs}
#

set -e

# Configuration - can be overridden with KSI_* environment variables
DAEMON_SCRIPT="ksi-daemon.py"
PID_FILE="${KSI_PID_FILE:-var/run/ksi_daemon.pid}"

# Socket configuration - single socket for event-based architecture
SOCKET_DIR="${KSI_SOCKET_DIR:-/tmp/ksi}"
SOCKET_FILE="$SOCKET_DIR/daemon.sock"

# Logging configuration
LOG_DIR="${KSI_LOG_DIR:-var/logs/daemon}"
LOG_FILE="$LOG_DIR/daemon.log"
LOG_LEVEL="${KSI_LOG_LEVEL:-INFO}"
LOG_FORMAT="${KSI_LOG_FORMAT:-console}"  # console or json
LOG_STRUCTURED="${KSI_LOG_STRUCTURED:-true}"

VENV_DIR=".venv"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Change to script directory
cd "$(dirname "$0")"

# Helper function to send JSON events
send_json_event() {
    local event="$1"
    local data="${2:-{}}"
    
    # Build JSON event
    local json_event='{"event": "'"$event"'", "data": '"$data"'}'
    
    # Send event and get response
    echo "$json_event" | nc -U "$SOCKET_FILE" 2>/dev/null
}

# Check virtual environment
check_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        echo -e "${RED}Error: Virtual environment not found ($VENV_DIR)${NC}"
        echo "Run: python3 -m venv $VENV_DIR && source $VENV_DIR/bin/activate && pip install -r requirements.txt"
        exit 1
    fi
}

# Get daemon PID if running
get_daemon_pid() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE" 2>/dev/null)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            echo "$pid"
            return 0
        fi
    fi
    return 1
}

# Check daemon status
daemon_status() {
    if pid=$(get_daemon_pid); then
        echo -e "${GREEN}✓ Daemon is running${NC} (PID: $pid)"
        return 0
    else
        echo -e "${RED}✗ Daemon is not running${NC}"
        return 1
    fi
}

# Check daemon health via socket
daemon_health() {
    if ! daemon_status >/dev/null 2>&1; then
        echo -e "${RED}✗ Daemon is not running${NC}"
        return 1
    fi
    
    if [ ! -S "$SOCKET_FILE" ]; then
        echo -e "${YELLOW}⚠ Daemon is running but socket not found${NC}"
        return 1
    fi
    
    # Send health check event
    response=$(send_json_event "system:health" || echo '{"error":{"code":"CONNECTION_FAILED"}}')
    
    # Parse JSON response
    health_status=$(echo "$response" | python3 -c "import json,sys; d=json.load(sys.stdin); print('healthy' if not d.get('error') and d.get('status')=='healthy' else 'unhealthy')" 2>/dev/null || echo "error")
    
    if [ "$health_status" = "healthy" ]; then
        echo -e "${GREEN}✓ Daemon is healthy${NC}"
        
        # Get additional stats
        echo ""
        echo "Additional Information:"
        
        # Get agent count
        agents=$(send_json_event "agent:list" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    if not data.get('error'):
        agents = data.get('agents', [])
        print('  Active agents: ' + str(len(agents)))
    else:
        print('  Active agents: 0')
except:
    print('  Active agents: Unable to retrieve')
" 2>/dev/null || echo "  Active agents: Unable to retrieve")
        
        # Get process count
        processes=$(send_json_event "state:get" '{"namespace": "processes", "key": "active"}' | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    if not data.get('error') and data.get('value'):
        procs = data.get('value', {})
        print('  Running processes: ' + str(len(procs)))
    else:
        print('  Running processes: 0')
except:
    print('  Running processes: Unable to retrieve')
" 2>/dev/null || echo "  Running processes: Unable to retrieve")
        
        echo "$agents"
        echo "$processes"
        echo ""
        echo "Socket Configuration:"
        echo "  Socket: $SOCKET_FILE"
        echo ""
        echo "Logging Configuration:"
        echo "  Log File: $LOG_FILE"
        echo "  Log Level: $LOG_LEVEL"
        echo "  Log Format: $LOG_FORMAT"
        
        return 0
    else
        echo -e "${RED}✗ Daemon health check failed${NC}"
        echo "Response: $response"
        return 1
    fi
}

# Start daemon
start_daemon() {
    echo "Starting KSI daemon..."
    
    if daemon_status >/dev/null 2>&1; then
        echo -e "${YELLOW}Daemon is already running${NC}"
        return 1
    fi
    
    check_venv
    
    # Ensure directories exist
    mkdir -p var/run var/logs/daemon var/logs/sessions var/db var/tmp "$SOCKET_DIR" logs
    
    # Export logging environment variables
    export KSI_LOG_LEVEL="$LOG_LEVEL"
    export KSI_LOG_FORMAT="$LOG_FORMAT"
    export KSI_LOG_STRUCTURED="$LOG_STRUCTURED"
    
    # Display configuration
    echo "Configuration:"
    echo "  Log Level: $LOG_LEVEL"
    echo "  Log Format: $LOG_FORMAT"
    echo "  Socket: $SOCKET_FILE"
    
    # Use venv python directly (nohup doesn't inherit venv activation properly)
    VENV_PYTHON="$VENV_DIR/bin/python3"
    if [ ! -x "$VENV_PYTHON" ]; then
        echo -e "${RED}Error: Virtual environment python not found: $VENV_PYTHON${NC}"
        exit 1
    fi
    
    # Let daemon handle its own logging via config system
    nohup "$VENV_PYTHON" "$DAEMON_SCRIPT" >/dev/null 2>&1 &
    
    # Wait for daemon to start
    echo -n "Waiting for daemon to start"
    for i in {1..10}; do
        sleep 1
        echo -n "."
        if daemon_status >/dev/null 2>&1; then
            echo ""
            echo -e "${GREEN}✓ Daemon started successfully${NC}"
            daemon_health
            return 0
        fi
    done
    
    echo ""
    echo -e "${RED}✗ Failed to start daemon${NC}"
    echo "Check logs: tail -f $LOG_FILE"
    return 1
}

# Stop daemon
stop_daemon() {
    echo "Stopping KSI daemon..."
    
    if ! pid=$(get_daemon_pid); then
        echo -e "${YELLOW}Daemon is not running${NC}"
        return 0
    fi
    
    # Try graceful shutdown via socket first
    if [ -S "$SOCKET_FILE" ]; then
        echo "Sending SHUTDOWN command..."
        send_json_event "system:shutdown" >/dev/null 2>&1 || true
        
        # Wait for graceful shutdown
        echo -n "Waiting for graceful shutdown"
        for i in {1..5}; do
            sleep 1
            echo -n "."
            if ! kill -0 "$pid" 2>/dev/null; then
                echo ""
                echo -e "${GREEN}✓ Daemon stopped gracefully${NC}"
                rm -f "$PID_FILE"
                return 0
            fi
        done
        echo ""
    fi
    
    # Force kill if still running
    echo "Forcing daemon shutdown..."
    kill -TERM "$pid" 2>/dev/null || true
    
    # Wait for termination
    for i in {1..5}; do
        if ! kill -0 "$pid" 2>/dev/null; then
            echo -e "${GREEN}✓ Daemon stopped${NC}"
            rm -f "$PID_FILE"
            return 0
        fi
        sleep 1
    done
    
    # Force kill -9 as last resort
    echo "Force killing daemon..."
    kill -9 "$pid" 2>/dev/null || true
    rm -f "$PID_FILE"
    echo -e "${GREEN}✓ Daemon killed${NC}"
    return 0
}

# Restart daemon
restart_daemon() {
    echo "Restarting KSI daemon..."
    stop_daemon
    sleep 2
    start_daemon
}

# Show recent logs
show_logs() {
    if [ ! -f "$LOG_FILE" ]; then
        echo -e "${RED}Log file not found: $LOG_FILE${NC}"
        return 1
    fi
    
    echo "Recent daemon logs (last 50 lines):"
    echo "=================================="
    tail -50 "$LOG_FILE"
    echo ""
    echo "To follow logs: tail -f $LOG_FILE"
}

# Main command handling
case "$1" in
    start)
        start_daemon
        ;;
    stop)
        stop_daemon
        ;;
    restart)
        restart_daemon
        ;;
    status)
        daemon_status
        ;;
    health)
        daemon_health
        ;;
    logs)
        show_logs
        ;;
    *)
        echo "KSI Daemon Control Script"
        echo "Usage: $0 {start|stop|restart|status|health|logs}"
        echo ""
        echo "Commands:"
        echo "  start    - Start the daemon"
        echo "  stop     - Stop the daemon (graceful shutdown)"
        echo "  restart  - Restart the daemon"
        echo "  status   - Check if daemon is running"
        echo "  health   - Check daemon health and show statistics"
        echo "  logs     - Show recent daemon logs"
        echo ""
        echo "Environment Variables:"
        echo "  KSI_LOG_LEVEL         - Logging level (default: INFO)"
        echo "  KSI_LOG_FORMAT        - Log format: console or json (default: console)"
        echo "  KSI_ADMIN_SOCKET      - Admin socket (default: sockets/admin.sock)"
        echo "  KSI_AGENTS_SOCKET     - Agents socket (default: sockets/agents.sock)"
        echo "  KSI_MESSAGING_SOCKET  - Messaging socket (default: sockets/messaging.sock)"
        echo "  KSI_STATE_SOCKET      - State socket (default: sockets/state.sock)"
        echo "  KSI_COMPLETION_SOCKET - Completion socket (default: sockets/completion.sock)"
        exit 1
        ;;
esac