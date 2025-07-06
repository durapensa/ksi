# KSI Claude Code Experiments

This directory contains experimental code and examples for working with KSI.

## Current Experiments

### practical_examples.py
Complete working examples demonstrating:
- Multi-agent research coordination
- Parallel analysis patterns  
- Observation-based task monitoring
- Dynamic agent spawning
- Conversation management

## Running Experiments

```bash
# Ensure daemon is running
./daemon_control.py start

# Run examples
python experiments/practical_examples.py
```

## Adding New Experiments

When creating new experiments:
1. Use async/await patterns consistently
2. Include error handling and timeouts
3. Document expected outcomes
4. Clean up spawned agents when done

## See Also
- `/experiments/` in project root for system-level experiments
- `docs/IMMEDIATE_EXPERIMENTS.md` for experiment ideas