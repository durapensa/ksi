#!/bin/bash
# Migration script for daemon.log -> daemon.log.jsonl

echo "KSI Daemon Log Migration Script"
echo "==============================="
echo ""

LOG_DIR="var/logs/daemon"

# Check if log directory exists
if [ ! -d "$LOG_DIR" ]; then
    echo "Log directory $LOG_DIR does not exist"
    exit 1
fi

# Count existing daemon.log files
OLD_LOGS=$(find "$LOG_DIR" -name "daemon*.log" -not -name "*.jsonl" 2>/dev/null | wc -l | tr -d ' ')

if [ "$OLD_LOGS" -eq "0" ]; then
    echo "No daemon.log files found to migrate"
    exit 0
fi

echo "Found $OLD_LOGS daemon log file(s) to migrate"
echo ""

# Migrate current daemon.log
if [ -f "$LOG_DIR/daemon.log" ]; then
    echo "Migrating: daemon.log -> daemon.log.jsonl"
    mv "$LOG_DIR/daemon.log" "$LOG_DIR/daemon.log.jsonl"
fi

# Migrate rotated logs
for log in "$LOG_DIR"/daemon_*.log; do
    if [ -f "$log" ] && [[ ! "$log" =~ \.jsonl$ ]]; then
        newname="${log%.log}.log.jsonl"
        echo "Migrating: $(basename "$log") -> $(basename "$newname")"
        mv "$log" "$newname"
    fi
done

echo ""
echo "Migration complete!"
echo ""
echo "Updated log files:"
ls -la "$LOG_DIR"/daemon*.jsonl | tail -10

echo ""
echo "Note: The daemon will now log to daemon.log.jsonl"