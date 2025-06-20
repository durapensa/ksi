# Autonomous Agent Workspaces

Each autonomous experiment gets its own isolated workspace directory to prevent contamination of the main ksi system files.

## Structure

```
workspaces/
├── entropy_analysis/          # Workspace for entropy analysis experiment
├── concept_graph_analysis/    # Workspace for concept graph experiment
├── attractor_detection/       # Workspace for attractor detection experiment
├── cost_efficiency_analysis/  # Workspace for cost efficiency experiment
├── meta_analysis/            # Workspace for meta analysis experiment
└── shared/                   # Shared utilities (read-only for agents)
```

## Agent Guidelines

### For Autonomous Agents:
1. **Work in your dedicated workspace**: `autonomous_experiments/workspaces/{experiment_name}/`
2. **Place all scripts here**: Analysis scripts, utilities, temporary files
3. **Final outputs go to parent**: `autonomous_experiments/{report_name}.md` or `.json`
4. **Don't modify ksi system files**: Stay in your workspace
5. **Use relative paths**: `../cognitive_data/` to access input data

### Workspace Contents:
- `analysis.py` - Main analysis script
- `utils.py` - Helper functions
- `temp/` - Temporary files and intermediate results
- `data/` - Processed data specific to this experiment
- `README.md` - Experiment-specific documentation

## Benefits
- **Isolation**: No contamination of main system
- **Organization**: Each experiment self-contained
- **Debugging**: Easy to find experiment-specific files
- **Cleanup**: Can delete entire workspace when done
- **Parallel**: Multiple agents can work without conflicts