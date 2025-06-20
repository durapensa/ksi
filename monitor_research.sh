#!/bin/bash
# Autonomous Research Monitor
echo "=== Cognitive Research Status ==="
echo "Started: $(date)"
echo

if [ -f autonomous_experiments/status.json ]; then
    echo "=== Experiment Status ==="
    cat autonomous_experiments/status.json | jq -r '.status'
    echo
fi

echo "=== Latest Observations ==="
ls -la cognitive_data/*.json | tail -5
echo

echo "=== Experiment Results ==="
for file in autonomous_experiments/*.md autonomous_experiments/*.json; do
    if [ -f "$file" ]; then
        echo "✓ $(basename $file) - $(wc -l < "$file") lines"
    fi
done
echo

echo "=== Recent Experiment Activity ==="
if [ -f autonomous_experiments/experiment_log.jsonl ]; then
    tail -10 autonomous_experiments/experiment_log.jsonl | jq -r '.experiment_name + " -> " + .session_id'
fi

echo
echo "Run './monitor_research.sh' to check again"
