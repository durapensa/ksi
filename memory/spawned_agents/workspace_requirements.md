# Workspace Requirements for Autonomous Agents

## CRITICAL: Workspace Isolation Required

All autonomous agents MUST work in isolated workspaces to prevent contamination of the ksi system.

## Workspace Structure

### Your Dedicated Workspace
- **Location**: `autonomous_experiments/workspaces/{experiment_name}/`
- **Scope**: ALL scripts, temporary files, and intermediate results
- **Isolation**: Never modify files outside your workspace

### Workspace Contents
```
autonomous_experiments/workspaces/{experiment_name}/
├── analysis.py          # Main analysis script
├── utils.py             # Helper functions  
├── temp/                # Temporary files
├── data/                # Processed data specific to experiment
└── README.md            # Experiment documentation
```

## Required Patterns

### Input Data Access
- **Cognitive data**: Use relative path `../../../cognitive_data/`
- **Previous results**: Use relative path `../../*.md` and `../../*.json`
- **Never copy large datasets** - always use relative references

### Output Requirements
- **Final reports**: Place in `../../{report_name}.md`
- **Final data**: Place in `../../{report_name}.json`
- **Intermediate files**: Keep in your workspace

### Script Placement
- **All analysis scripts**: Create in your workspace
- **Temporary utilities**: Create in your workspace  
- **Never place scripts**: In ksi root directory or system directories

## Standard Agent Instructions

Include these in every autonomous agent prompt:
```
WORKSPACE: autonomous_experiments/workspaces/{experiment_name}/
Create all analysis scripts in your workspace.
Use relative paths: ../../../cognitive_data/ for input data.
Final output: ../../{report_name}.md or .json
```

## Benefits of Isolation
- **No system contamination**: Agent scripts don't mix with ksi core files
- **Parallel execution**: Multiple agents can work without conflicts  
- **Easy cleanup**: Delete entire workspace when experiment complete
- **Organized debugging**: All experiment files in one location

## Enforcement
- Workspace isolation is MANDATORY, not optional
- Violating isolation contaminates the system
- Scripts outside workspaces will be moved to legacy cleanup

---
*For autonomous Claude agents spawned for independent research*