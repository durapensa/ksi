#!/bin/bash
#
# KSI Daemon Control Script
# Usage: ./daemon_control.sh {start|stop|restart|status|health|logs}
#

set -e

# Configuration
DAEMON_SCRIPT="daemon.py"
PID_FILE="sockets/claude_daemon.pid"
SOCKET_FILE="sockets/claude_daemon.sock"
LOG_FILE="logs/daemon.log"
VENV_DIR=".venv"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Change to script directory
cd "$(dirname "$0")"

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
    
    # Send HEALTH_CHECK command
    response=$(echo "HEALTH_CHECK" | nc -U "$SOCKET_FILE" 2>/dev/null || echo "FAILED")
    
    if [ "$response" = "HEALTHY" ]; then
        echo -e "${GREEN}✓ Daemon is healthy${NC}"
        
        # Get additional stats
        echo ""
        echo "Additional Information:"
        
        # Get agent count
        agents=$(echo "GET_AGENTS" | nc -U "$SOCKET_FILE" 2>/dev/null | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(f'  Active agents: {len(data.get(\"agents\", {}))}')
except:
    pass
" 2>/dev/null || echo "  Active agents: Unable to retrieve")
        
        # Get process count
        processes=$(echo "GET_PROCESSES" | nc -U "$SOCKET_FILE" 2>/dev/null | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(f'  Running processes: {len(data.get(\"processes\", {}))}')
except:
    pass
" 2>/dev/null || echo "  Running processes: Unable to retrieve")
        
        echo "$agents"
        echo "$processes"
        echo "  Socket: $SOCKET_FILE"
        echo "  Log: $LOG_FILE"
        
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
    mkdir -p sockets logs
    
    # Activate venv and start daemon
    source "$VENV_DIR/bin/activate"
    nohup python3 "$DAEMON_SCRIPT" > /dev/null 2>&1 &
    
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
        echo "SHUTDOWN" | nc -U "$SOCKET_FILE" 2>/dev/null || true
        
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
        exit 1
        ;;
esac