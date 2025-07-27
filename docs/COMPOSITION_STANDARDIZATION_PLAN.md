# KSI Composition System Standardization Plan

This document outlines the breaking changes to standardize and clean up the KSI composition system.

## Overview

We are implementing a comprehensive standardization of the composition system to:
1. Use `component_type` exclusively for all components
2. Remove all backward compatibility code
3. Reorganize directory structure for consistency
4. Eliminate temporary profile files
5. Modernize or remove legacy systems

## Breaking Changes Summary

- **REMOVED**: Support for `type` field in components (use `component_type`)
- **REMOVED**: Temporary profile file generation
- **MOVED**: `/orchestrations/` → `/components/orchestrations/`
- **REMOVED**: Legacy prompt system in `/prompts/`
- **CLEANED**: Nested directories and duplicates

## Phase 1: Directory Reorganization

### Current Structure Issues
```
var/lib/compositions/
├── components/
├── orchestrations/        # Should be under components/
├── prompts/              # Legacy system
├── profiles/             # Contains temp_profile_* clutter
├── var/lib/evaluations/  # Wrong path - code using relative paths instead of config
└── capabilities/         # Check if this belongs here
```

**Root Cause**: Code using hardcoded paths like `Path("var/lib/evaluations")` instead of `config.evaluations_dir`

### Target Structure
```
var/lib/compositions/
├── components/
│   ├── agents/
│   ├── behaviors/
│   ├── core/
│   ├── evaluations/
│   ├── orchestrations/   # Moved from root
│   ├── personas/
│   └── tools/
├── profiles/             # Only intentional profiles
└── schemas/              # If needed
```

### Migration Steps
1. Move all `/orchestrations/*.yaml` → `/components/orchestrations/`
2. Delete `/var/lib/evaluations/` (bizarre nested duplicate)
3. Delete all `temp_profile_*` files
4. Remove `/prompts/` directory after converting any valuable content

## Phase 2: Field Standardization

### Convert type → component_type
All components must use `component_type` field exclusively.

**Affected files**: ~189 files using `type` field

**Script**:
```bash
# Update all component files
find components/ -name "*.md" -o -name "*.yaml" | 
  xargs sed -i 's/^type: /component_type: /'

# Update orchestrations during move
find orchestrations/ -name "*.yaml" |
  xargs sed -i 's/^type: orchestration/component_type: orchestration/'
```

## Phase 3: Code Updates

### 1. Remove Backward Compatibility

**composition_index.py**:
```python
# OLD (remove this)
comp_type = comp_data.get('type') or comp_data.get('component_type')

# NEW
comp_type = comp_data.get('component_type')
if not comp_type:
    logger.warning(f"Missing component_type in {file_path}")
    return None
```

**composition_service.py**:
- Remove normalization code (lines 680-682)
- Update validation to require `component_type` only
- Remove `type` from all TypedDict definitions

### 2. Implement In-Memory Agent Manifests

**Terminology Change**: "Profile" → "Agent Manifest" (clearer, avoids confusion)

**New approach**:
```python
async def spawn_agent_from_component(component_name: str, 
                                   variables: dict,
                                   config: dict) -> dict:
    """Spawn agent directly from component without temp files."""
    # Render component to agent manifest in memory
    agent_manifest = await render_component_to_manifest(
        component_name, variables
    )
    
    # Store manifest in state system with virtual ID
    manifest_id = f"virtual://{component_name}/{hash(variables)}"
    await store_virtual_manifest(manifest_id, agent_manifest)
    
    # Spawn with virtual manifest
    return await spawn_agent(manifest_id=manifest_id, config=config)
```

**Benefits**:
- No filesystem clutter
- Clear terminology: "manifest" = rendered agent specification
- Virtual URIs for in-memory references

### 3. Update Handlers

**component_to_manifest handler** (rename from component_to_profile):
- Return agent manifest data instead of writing files
- Store in state/cache if persistence needed
- Use virtual:// URI scheme for references
- Event: `composition:component_to_manifest`

## Phase 4: Prompt System Reorganization

The prompt system needs reorganization, not complete elimination.

### Current State
- **Judge prompts** (`prompts/specialized/evaluation/judges/`) are actively used by `judge_bootstrap_v2.py`
- **Test prompts** (`prompts/test_*.yaml`) are orphaned and unused

### Migration Plan
1. Move judge prompts to `components/evaluations/judge_prompts/`
2. Update `judge_bootstrap_v2.py` to use new location
3. Delete unused test prompts
4. Remove the `/prompts/` directory after migration
5. Consider converting judge prompts to components in future

## Phase 5: Database Schema Updates

1. Rename `type` column to `component_type` in composition_index
2. Update all SQL queries
3. Rebuild index after migrations

## Phase 6: Additional Technical Debt

### Hardcoded Dates in Certificate Paths
**Issue**: Code like `certificates/2025-07-26/` hardcodes dates
**Solution**: Certificates should be discovered by ID, not assumed paths

### ksi_evaluation Module Integration
**Note**: The `ksi_evaluation/` module will be integrated into `ksi_daemon/`
- Move evaluation logic into daemon services
- Remove standalone evaluation scripts
- Unify with daemon's event-driven architecture

### Judge System Migration (Incomplete)
**Current State**: Judge prompts moved to `components/evaluations/judge_prompts/`
**Issue**: Still using prompt-based approach via `judge_bootstrap_v2.py`
**Solution**: 
- Convert judge prompts to full judge components
- Each judge should be a proper persona/agent component
- Update bootstrap system to use component-based judges
- Remove dependency on prompt files entirely

## Cleanup Checklist

- [x] Move orchestrations/ → components/orchestrations/
- [x] Delete var/lib/compositions/var/lib/evaluations/
- [x] Delete all temp_profile_* files
- [x] Convert type → component_type in all files
- [x] Remove backward compatibility code
- [x] Implement in-memory agent manifests
- [x] Remove/convert prompts directory
- [x] Update all SQL queries and schemas
- [ ] Update documentation
- [x] Rebuild all indexes
- [x] Fix agent lazy loading from state system
- [x] Restore automatic JSON parameter parsing
- [x] Remove business logic from transport layer
- [x] Convert judge prompts to components
- [x] Eliminate legacy prompt system

## Testing Strategy

Since this is a breaking change:
1. No backward compatibility tests needed
2. Test each component type can be loaded
3. Test agent spawning with new in-memory profiles
4. Test composition:discover returns all components
5. Test orchestrations work from new location

## Rollback Plan

This is a breaking change with no rollback. Ensure all systems are ready before deployment.

## Phase 7: Evaluation System Paradigm Shift

### New Understanding: Evaluation as Certification Wrapper

Through investigation, we discovered that KSI already has comprehensive evaluation capabilities through its orchestration system. Evaluation events serve as certification wrappers over component testing.

**Key Insights**:
1. **`evaluation:run` is a certification wrapper** - It evaluates any component type and produces certificates as evidence
2. **Orchestration agents use evaluation for certification** - Agents can experiment/test/refine components, then emit `evaluation:run` to acquire certification
3. **Works for any component type** - Personas, behaviors, orchestrations, tools, etc. can all be evaluated and certified
4. **Certificates are evidence of evaluation** - YAML certificates in `var/lib/evaluations/certificates/` serve as immutable evidence
5. **Index enables discovery** - Certificate index allows composition system to discover tested components

### Evaluation as Certification Pattern

**`evaluation:run` Pattern**:
```python
# Orchestration agent experiments with component
agent_result = test_component_variations()

# When satisfied, acquire certification
await emit_event("evaluation:run", {
    "component_path": "personas/data_analyst",
    "test_suite": "reasoning_tasks", 
    "model": "claude-sonnet-4",
    "orchestration_pattern": "evaluations/component_testing"  # Optional
})
# → Generates certificate in var/lib/evaluations/certificates/
```

### What We're Removing

**Superseded Bootstrap Files** (Replaced by Advanced Orchestrations):
- `judge_tournament.py` (639 lines) → **Replaced by**: `component_tournament_evaluation.yaml`, `adaptive_tournament_v3.yaml`
- `autonomous_improvement.py` (470 lines) → **Replaced by**: `self_improving_system.yaml`, `continuous_optimization_pipeline.yaml`  
- `prompt_iteration.py` (406 lines) → **Replaced by**: DSL test patterns, `optimization_quality_review.yaml`
- `tournament_bootstrap_integration.py` → **Replaced by**: `multi_agent_optimization_tournament.yaml`
- `completion_utils.py` → Anti-pattern bypassing agent system (no replacement needed)

**Key Discovery**: The Python files were **bootstrap implementations** to prove concepts. The orchestrations represent **production-ready, agent-driven evolution** of those concepts with native event integration, self-improving capabilities, and sophisticated coordination.

### What We're Keeping

**Thin Certification Infrastructure**:
- `evaluation_events.py` → Event handlers for certification workflow
- `certificate_index.py` → SQLite index for certificate discovery
- Certificate file system → Evidence storage in `var/lib/evaluations/`

### Architectural Clarity

**Before**: Mixed evaluation system with hardcoded orchestration logic (9 files, 3000+ lines)
**After**: Pure certification wrapper over component evaluation + orchestration patterns (3 files, 500 lines)

**Dramatic Reduction**: 83% code reduction while gaining MORE sophisticated capabilities through orchestrations.

This maintains the file system (`registry.yaml`, `certificates/`) while ensuring all evaluation logic uses normal KSI operations (agents, orchestrations, components) rather than special Python coordination code.

**Key Achievement**: Evaluation system now properly implements **"evaluation uses normal KSI operations"** with advanced orchestration patterns replacing bootstrap Python implementations.

## Timeline

- Phase 1-2: Directory and field migration (automated) ✓
- Phase 3: Code updates (manual, careful) ✓
- Phase 4-5: System modernization ✓
- Phase 6: Technical debt cleanup ✓
- Phase 7: Evaluation system paradigm shift (in progress)
- Testing: Comprehensive validation
- Total actual time: ~4 hours of systematic work