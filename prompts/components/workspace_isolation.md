# Workspace Isolation Requirements

## CRITICAL: Use Your Designated Workspace

**Your workspace**: `{{workspace_path}}`

### Mandatory Isolation Rules
1. **All scripts and code**: Create ONLY in your workspace directory
2. **Temporary files**: Store ONLY in your workspace
3. **Intermediate results**: Keep ONLY in your workspace  
4. **Never contaminate**: Do not create files in the ksi root directory or system directories

### Workspace Structure
```
{{workspace_path}}/
├── analysis.py          # Your main analysis script
├── utils.py             # Helper functions
├── temp/                # Temporary files
├── data/                # Processed data
└── README.md            # Document your work
```

### Access Patterns
- **Input data**: Use relative path `{{input_data_path}}` 
- **Previous results**: Use relative path `{{previous_results_path}}`
- **Final output**: Place in `{{final_output_path}}`

### Why Isolation Matters
- Prevents contamination of the ksi system
- Enables parallel agent execution
- Makes cleanup and debugging easier
- Maintains system organization

**VIOLATION OF ISOLATION RULES WILL RESULT IN SYSTEM CONTAMINATION**