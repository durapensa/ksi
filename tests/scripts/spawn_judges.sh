#!/bin/bash
# Spawn champion judges
echo "Spawning champion judges..."
EVAL_CHAMPION=$(echo '{"event": "agent:spawn", "data": {"profile": "evaluator_judge_detailed_rubric", "context": {"name": "evaluator_champion"}}}' | nc -U var/run/daemon.sock | jq -r '.data.agent_id')
echo "Evaluator champion: $EVAL_CHAMPION"

ANALYST_CHAMPION=$(echo '{"event": "agent:spawn", "data": {"profile": "analyst_judge_root_cause_focus", "context": {"name": "analyst_champion"}}}' | nc -U var/run/daemon.sock | jq -r '.data.agent_id')
echo "Analyst champion: $ANALYST_CHAMPION"

REWRITER_CHAMPION=$(echo '{"event": "agent:spawn", "data": {"profile": "rewriter_judge_incremental_improvement", "context": {"name": "rewriter_champion"}}}' | nc -U var/run/daemon.sock | jq -r '.data.agent_id')
echo "Rewriter champion: $REWRITER_CHAMPION"

# Spawn challenger judges
echo "Spawning challenger judges..."
EVAL_CHALLENGER=$(echo '{"event": "agent:spawn", "data": {"profile": "evaluator_judge_pattern_focused", "context": {"name": "evaluator_challenger"}}}' | nc -U var/run/daemon.sock | jq -r '.data.agent_id')
echo "Evaluator challenger: $EVAL_CHALLENGER"

ANALYST_CHALLENGER=$(echo '{"event": "agent:spawn", "data": {"profile": "analyst_judge_pattern_recognition", "context": {"name": "analyst_challenger"}}}' | nc -U var/run/daemon.sock | jq -r '.data.agent_id')
echo "Analyst challenger: $ANALYST_CHALLENGER"

REWRITER_CHALLENGER=$(echo '{"event": "agent:spawn", "data": {"profile": "rewriter_judge_comprehensive_restructure", "context": {"name": "rewriter_challenger"}}}' | nc -U var/run/daemon.sock | jq -r '.data.agent_id')
echo "Rewriter challenger: $REWRITER_CHALLENGER"

echo "All judges spawned!"
echo "Agent IDs: $EVAL_CHAMPION $ANALYST_CHAMPION $REWRITER_CHAMPION $EVAL_CHALLENGER $ANALYST_CHALLENGER $REWRITER_CHALLENGER"