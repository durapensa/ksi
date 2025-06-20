# Legacy Agent Scripts

These scripts were created by autonomous agents before the workspace isolation system was implemented.

**Date**: 2025-06-20  
**Reason**: Scripts were placed in root directory, contaminating ksi system files  
**Resolution**: Moved to isolated location, implemented workspace system

## Files
- `cognitive_attractor_analysis.py` - Attractor detection analysis
- `detailed_entropy_analysis.py` - Detailed entropy calculations  
- `efficiency_correlation_analysis.py` - Cost/efficiency correlations
- `simple_cognitive_analysis.py` - Simple cognitive pattern analysis

## New Pattern
All future autonomous agents will work in isolated workspaces:
- `autonomous_experiments/workspaces/{experiment_name}/`
- Scripts stay isolated from ksi system files
- Easy cleanup and organization

## Note
These legacy scripts demonstrate why workspace isolation is necessary - without it, agent scripts mix with system files and create organizational chaos.