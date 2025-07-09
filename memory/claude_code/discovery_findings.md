# KSI Discovery System Findings Log

This log tracks issues, insights, and improvements for the KSI discovery system.

## 2025-07-08: Initial Discovery System Analysis

### Finding 1: Discovery System Underutilization
**Issue**: Failed to use discovery system for finding `evaluation:prompt` parameters
**Root Cause**: 
- Default `system:discover` output with `detail=True` is overwhelming (~3000+ lines)
- Abandoned discovery in favor of grepping source code
- This defeats the entire purpose of the discovery system

**Solution Path**:
1. Change default to `detail=False` for more manageable output
2. Use namespace filtering as primary discovery pattern
3. Add progressive discovery workflow to documentation

**Action Items**:
- [ ] Update discovery.py to default `detail=False`
- [ ] Add discovery helpers for common patterns
- [ ] Document discovery-first workflow in CLAUDE.md

### Finding 2: Missing Discovery Workflow Documentation
**Issue**: CLAUDE.md lacks discovery usage examples
**Impact**: Developers bypass discovery and grep source directly

**Solution Path**:
1. Add "Discovery-First Development" section to CLAUDE.md
2. Include common discovery patterns and examples
3. Create discovery cheat sheet

### Finding 3: Parameter Discovery Inefficiency
**Issue**: No direct way to get just parameter names/types for an event
**Current Workaround**: Use `system:help` but it's still verbose

**Solution Path**:
1. Add `discover:parameters` event for focused parameter discovery
2. Add `discover:examples` for usage patterns
3. Consider format_style options for different use cases

### Finding 4: Discovery Output Format
**Issue**: Current formats (verbose, compact, ultra_compact, mcp) don't address common needs
**Missing Formats**:
- Parameter-only view
- Example-focused view
- Quick reference view

## Proposed Discovery Helpers

### 1. `discover:parameters`
```json
{
  "event": "discover:parameters",
  "data": {
    "event": "evaluation:prompt",
    "format": "table"  // or "json", "yaml"
  }
}
```
Returns just parameter names, types, and required status.

### 2. `discover:examples`
```json
{
  "event": "discover:examples", 
  "data": {
    "event": "evaluation:prompt"
  }
}
```
Returns working examples of event usage.

### 3. `discover:namespace`
```json
{
  "event": "discover:namespace",
  "data": {
    "namespace": "evaluation",
    "depth": "summary"  // or "full", "names_only"
  }
}
```
Focused namespace discovery with depth control.

## Implementation Priority

1. **Immediate**: Change `detail=False` default in discovery.py
2. **Next**: Add discovery helpers (parameters, examples, namespace)
3. **Future**: Create comprehensive discovery guide
4. **Ongoing**: Capture discovery patterns as they emerge

## Completed Improvements (2025-07-08)

### 1. Documentation Updates
- **Added Discovery-First Development section to CLAUDE.md**
  - Basic discovery workflow with examples
  - Common discovery patterns
  - Best practices for using discovery before reading source
  - When discovery fails guidelines

### 2. Evaluation:Compare Format Options
- **Implemented format parameter**: summary (default), rankings, detailed
- **Summary format**: Concise overview with top 5 rankings, key insights, best overall
- **Rankings format**: Detailed rankings by success rate, speed, and safety
- **Inline documentation**: Added descriptive comment for format parameter

### 3. KSI Hook Monitor Enhancements
- **Command-based verbosity control**:
  - `echo ksi_verbose` - Show all events with details
  - `echo ksi_summary` - Default concise mode
  - `echo ksi_errors` - Only show errors
  - `echo ksi_silent` - Temporarily disable
  - `echo ksi_status` - Check current mode
- **Status indicators**: ✓ for success, ✗ for failures/errors
- **Smart filtering**: Started implementation (needs refinement)

### 4. Key Learnings
- Discovery system works well when used properly
- Default verbosity is still a major barrier to adoption
- Format options significantly improve usability
- Command-based control better than env vars (no restart required)

### Finding 5: Discovery Success Story
**Context**: After documenting discovery-first workflow, successfully used it
**Command**: `echo '{"event": "system:help", "data": {"event": "evaluation:prompt"}}' | nc -U var/run/daemon.sock | jq '.data.parameters'`
**Result**: Found correct parameter name `composition_name` in seconds vs. minutes of grepping

**Key Insight**: When documented and used properly, discovery system works excellently

### Finding 6: Output Verbosity Issues Continue
**Issue**: `evaluation:compare` output is extremely verbose (1500+ lines)
**Impact**: 
- Difficult to find the actual comparison insights
- No clear summary section in output
- Performance implications of large JSON responses

**Solution Path**:
1. Add summary-first output structure
2. Consider paginated or progressive disclosure patterns
3. Add format options like "summary_only", "full_details"

### Finding 7: Evaluation System Observations
**Success**: Multi-composition comparison works correctly
**Issue**: Results not being persisted to disk by default
**Observation**: `evaluation:prompt` has `update_metadata` param but unclear saving behavior

**Action Items**:
- [ ] Clarify when evaluations are saved vs. in-memory only
- [ ] Add explicit save options to evaluation events
- [ ] Document evaluation persistence patterns

## Notes for Future Discovery Guide

- Include visual diagrams of discovery flow
- Add troubleshooting section for common discovery failures
- Create quick reference card for discovery commands
- Document discovery performance implications
- Add discovery best practices from real usage

---
*Last updated: 2025-07-08*