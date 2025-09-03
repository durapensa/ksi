#!/bin/bash
# Launch Native KSI Melting Pot Experiment
# =========================================
# This demonstrates true agent-directed experimentation
# where the experiment itself is orchestrated by agents,
# not external scripts.

echo "
================================================================================
NATIVE KSI MELTING POT EXPERIMENT
================================================================================
This launches a truly unbiased experiment orchestrated entirely by KSI agents.
No external scripts control the experiment - agents manage everything.
================================================================================
"

# First, ensure components are indexed
echo "📚 Rebuilding component index..."
ksi send composition:rebuild_index

# Create the experiment operator agent
echo "
🧪 Spawning Experiment Operator Agent...
"

ksi send agent:spawn \
  --component "experiments/melting_pot_operator" \
  --prompt "You are the lead scientist for an unbiased Melting Pot experiment. 

Your mission:
1. Run 5 trials of prisoner's dilemma with COMPLETELY NEUTRAL participants
2. Collect data through KSI events only  
3. Use blind evaluation for analysis
4. Report emergent behaviors (not programmed outcomes)

CRITICAL: Participants must receive ONLY game mechanics:
- Choice A or B (not cooperate/defect)
- Payoff matrix only
- No hints about strategy
- No suggestions about outcomes

Begin by initializing the experiment and spawning your first trial participants."

echo "
================================================================================
The experiment is now running autonomously within KSI.
The operator agent will:
- Spawn neutral participants for each trial
- Collect decisions through events
- Coordinate blind evaluation
- Report unbiased results

Monitor progress with:
  ksi send monitor:get_events --event_patterns 'experiment:*'
  
Check results in state:
  ksi send state:entity:query --type experiment_results
================================================================================
"