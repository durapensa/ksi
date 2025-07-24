# KSI Component Library DSPy Optimization Plan

## Optimization Priorities (Based on Assessment)

### Tier 1: Immediate Optimization (Ready Now)
1. **`personas/analysts/ksi_aware_analyst.md`** - Perfect structure, proven patterns
2. **`behaviors/communication/imperative_style.md`** - Critical JSON emission behavior  
3. **`personas/developers/optimization_engineer.md`** - Self-optimizing optimization expert

### Tier 2: High Impact After Minor Fixes
4. **`core/base_agent.md`** - Foundation affects all agents
5. **`personas/judges/game_theory_pairwise_judge.md`** - Evaluation system core
6. **`personas/coordinators/research_coordinator.md`** - Multi-agent coordination

### Tier 3: High Potential, Needs Restructure
7. **`personas/analysts/data_analyst.md`** - High usage, needs KSI integration
8. **`personas/systematic_thinker.md`** - General reasoning, broad applicability
9. **`behaviors/orchestration/claude_code_override.md`** - Claude Code integration
10. **`personas/creative_thinker.md`** - Innovation and variation generation

## Current Library Statistics
- **Total Components**: 76 active (excluding archived)
- **Proper Modern Metadata**: 22 components (29%)
- **Legacy Metadata**: 44 components (58%)
- **Missing Metadata**: 10 components (13%)

## Optimization Strategy

### Bootstrap vs Production Pattern
- **Bootstrap Phase**: `optimize_*.py` scripts for discovery (✅ Current: `optimize_ksi_analyst.py`)
- **Integration Phase**: Use `ksi send optimization:*` events with proven techniques
- **Production Phase**: KSI orchestrations for systematic, observable optimization

### Optimization Techniques by Component Type
1. **LLM-as-Judge** for personas (pairwise comparisons)
2. **KSI system feedback** for behaviors (JSON emission success)
3. **Multi-task evaluation** for core components
4. **Hybrid optimization** combining DSPy + Judge approaches

### KSI-Native Implementation
```bash
# Use existing optimization service instead of standalone scripts
ksi send optimization:optimize --component "personas/analysts/ksi_aware_analyst" --technique MIPRO
ksi send optimization:evaluate --metric persona_quality_judge
ksi send optimization:status --opt-id xyz123
```

## Quality Issues to Address
- Inconsistent metadata standards (`type:` vs `component_type:`)
- Missing dependency declarations
- Invalid event names in JSON patterns
- Pure personas lacking KSI system awareness

## Success Metrics
- Component effectiveness scores (baseline vs optimized)
- JSON emission success rates
- Agent spawning and task completion metrics
- LLM-as-Judge pairwise win rates

## Production Orchestration Pattern

### Component Optimization Orchestration
```yaml
orchestrations/component_optimization.yaml:
  orchestrator_agent_id: "claude-code"
  steps:
    1. optimization:optimize (component, technique, metrics)
    2. optimization:status (monitor progress)
    3. optimization:evaluate (quality assessment)
    4. composition:update_component (if successful)
    5. git:commit (version optimized component)
  observability: Full introspection support
```

### Anti-Pattern Recognition
- ❌ **Standalone Scripts**: Bypass event-driven architecture
- ❌ **Manual Execution**: Not observable or reproducible
- ❌ **Direct Imports**: Skip optimization service infrastructure
- ✅ **Bootstrap Usage**: Discovery and pattern development only

**Current Status**: Bootstrap phase complete (`optimize_ksi_analyst.py`), ready for KSI-native integration