#!/bin/bash
# Monitor KSI pattern evolution in real-time

echo "🔍 Evolution Monitor - Watching for pattern evolution activity"
echo "=================================================="
echo "Press Ctrl+C to stop monitoring"
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Monitor decision files
monitor_decisions() {
    echo -e "${BLUE}[$(date +%H:%M:%S)] Checking decision tracking files...${NC}"
    
    # Find recent decision files
    find var/lib/compositions/orchestrations -name "*_decisions.yaml" -mmin -5 2>/dev/null | while read file; do
        echo -e "${GREEN}📊 Recent decisions in: $(basename $file)${NC}"
        tail -20 "$file" | grep -E "(decision:|confidence:|outcome:)" | tail -5
    done
}

# Monitor daemon logs for evolution events
monitor_logs() {
    echo -e "${BLUE}[$(date +%H:%M:%S)] Checking evolution events...${NC}"
    
    tail -100 var/logs/daemon/daemon.log.jsonl 2>/dev/null | grep -E "(track_decision|improvement_discovered|composition:fork|evolution)" | tail -10 | while read line; do
        if [[ $line == *"track_decision"* ]]; then
            echo -e "${YELLOW}🎯 Decision tracked${NC}"
        elif [[ $line == *"improvement_discovered"* ]]; then
            echo -e "${GREEN}✨ Improvement discovered!${NC}"
        elif [[ $line == *"composition:fork"* ]]; then
            echo -e "${GREEN}🔀 Pattern forked!${NC}"
        fi
    done
}

# Monitor orchestration status
monitor_orchestrations() {
    echo -e "${BLUE}[$(date +%H:%M:%S)] Active orchestrations...${NC}"
    
    # This would need the orchestration ID - for now just check if daemon is active
    if pgrep -f "ksi_daemon" > /dev/null; then
        echo -e "${GREEN}✓ KSI daemon is running${NC}"
    else
        echo -e "${YELLOW}⚠ KSI daemon not detected${NC}"
    fi
}

# Main monitoring loop
while true; do
    clear
    echo "🔍 Evolution Monitor - $(date)"
    echo "=================================================="
    
    monitor_decisions
    echo ""
    monitor_logs
    echo ""
    monitor_orchestrations
    
    echo ""
    echo "Refreshing in 5 seconds..."
    sleep 5
done