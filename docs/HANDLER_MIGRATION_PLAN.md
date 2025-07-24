# KSI Event Handler to Transformer Migration Plan

## Executive Summary

**Objective**: Systematically migrate 302 event handlers across 43 files to declarative YAML transformers, achieving 50-70% code reduction while improving maintainability and performance.

**Approach**: 4-phase progressive migration strategy targeting simple forwarders first, then advancing to complex routing patterns.

**Timeline**: 8 weeks (2 weeks per phase)

**Expected Impact**: 
- Reduce handler code from 302 handlers to ~150-200 (retaining complex business logic)
- Enable hot-reloadable event configuration
- Improve event routing performance by 10-20%
- Provide visual documentation of event flows

## Current State Analysis

### Handler Distribution
- **Total**: 302 @event_handler decorators across 43 files
- **Simple Forwarders**: 30-40% - Pure routing with minimal transformation
- **Field Mappers**: 20-25% - Data restructuring and field mapping
- **Conditional Routers**: 15-20% - If/else logic for target selection
- **Multi-Target Distributors**: 10-15% - Emit to multiple targets simultaneously
- **Complex Business Logic**: 15-20% - Should NOT be migrated (DB, LLM, file I/O)

### High-Impact Migration Targets

#### Universal Patterns (Phase 1)
- **Universal broadcast handler** (`monitor.py:910-940`) - `@event_handler("*")`
- **System lifecycle propagation** - startup/shutdown notifications
- **Status propagation chains** - agent:status → monitoring systems

#### Service-Specific Patterns (Phase 2)
- **Agent service** (`agent_service.py`) - 22 event handlers
- **State management** (`state.py`) - 12 state management events
- **Configuration service** (`config_service.py`) - Config change propagation
- **Observation modules** (`observation/`) - Event replay and subscription management

#### Advanced Patterns (Phases 3-4)
- **Completion routing** (`completion_service.py`) - 12 completion events
- **Orchestration patterns** (`orchestration_service.py`) - 9 orchestration events
- **Permission routing** (`permission_service.py`) - 6 permission events
- **Evaluation chains** (`evaluation/`) - Tournament and optimization routing

## Migration Strategy

### Phase 1: Foundation & Easy Wins (Week 1-2)
**Objective**: Establish migration infrastructure and achieve immediate wins

#### Phase 1A: Infrastructure Setup (Days 1-2)
Create migration framework and tooling:

```
var/lib/compositions/transformers/migration/
├── templates/
│   ├── simple_forwarder.yaml      # Basic event forwarding
│   ├── field_mapper.yaml          # Data restructuring patterns
│   ├── conditional_router.yaml    # If/else routing patterns
│   └── multi_target.yaml          # Multiple destination patterns
├── validation/
│   └── transformer_schemas.yaml   # Validation schemas
└── migration_tools/
    └── handler_analyzer.py        # Analysis and migration utilities
```

**Migration Conventions**:
- Naming: `{service}_{pattern}_{version}.yaml`
- Documentation: Each transformer documents replaced handler
- Testing: Automated validation against original handler behavior

#### Phase 1B: Universal Broadcast Migration (Days 3-4)
**Target**: `monitor.py` universal handler - highest traffic impact

**Handler to DELETE** (monitor.py:910-940):
```python
# REMOVE COMPLETELY - NO BACKWARD COMPATIBILITY
@event_handler("*")
async def handle_universal_broadcast(data, context):
    # ~30 lines of broadcasting logic - DELETE ENTIRELY
    # Captures ALL events system-wide
```

**Replacement Transformer**:
```yaml
# transformers/system/universal_broadcast.yaml
name: universal_event_broadcast
description: Replace universal broadcast handler with declarative routing
metadata:
  replaces: monitor.py:handle_universal_broadcast
  
transformers:
  - source: "*"  # Match all events
    targets:
      - event: "monitor:event_captured"
        mapping: "{{$}}"  # Pass everything through
      - event: "audit:log"
        mapping:
          event_name: "{{event}}"
          data: "{{$}}"
          timestamp: "{{timestamp_utc()}}"
          agent_id: "{{_ksi_context._agent_id|system}}"
```

#### Phase 1C: System Lifecycle Migration (Days 5-7)
**Targets**: system:startup, system:shutdown handlers across multiple files

**Agent Startup Notifications**:
```yaml
transformers:
  - source: "system:startup"
    targets:
      - event: "agent:system_ready"
        mapping: "{{$}}"
      - event: "monitor:system_startup"
        mapping:
          timestamp: "{{timestamp_utc()}}"
          services: "{{services}}"
          startup_duration: "{{startup_time_ms}}"
```

**Service Shutdown Cascades**:
```yaml
transformers:
  - source: "system:shutdown"
    targets:
      - event: "agent:prepare_shutdown"
        mapping: "{{$}}"
      - event: "state:flush_pending"
        mapping: "{{$}}"
      - event: "monitor:system_shutdown"
        mapping:
          shutdown_reason: "{{reason|clean_shutdown}}"
          timestamp: "{{timestamp_utc()}}"
```

**Expected Outcome**: 15-20 simple forwarder handlers DELETED COMPLETELY, ~200-300 lines of code REMOVED PERMANENTLY

### Phase 2: Service-Specific Patterns (Week 3-4)
**Objective**: Migrate service-specific routing and field mapping handlers

#### Phase 2A: Agent Event Routing (Days 8-10)
**Target**: `agent_service.py` - 22 event handlers for agent lifecycle

**Agent Spawning Handler to DELETE**:
```python
# DELETE COMPLETELY - BREAKING CHANGE
@event_handler("agent:spawned")
async def handle_agent_spawned(data, context):
    # REMOVE ENTIRELY - 15+ lines of Python code
    # No backward compatibility needed
    await emit_event("monitor:agent_created", {
        "agent_id": data["agent_id"], 
        "profile": data.get("profile"),
        "timestamp": timestamp_utc()
    })
    await emit_event("state:entity:create", {
        "type": "agent",
        "id": data["agent_id"],
        "properties": data
    })
```

**New Multi-Target Transformer**:
```yaml
transformers:
  - source: "agent:spawned"
    targets:
      - event: "monitor:agent_created"
        mapping:
          agent_id: "{{agent_id}}"
          profile: "{{profile}}"
          timestamp: "{{timestamp_utc()}}"
      - event: "state:entity:create"
        mapping:
          type: "agent"
          id: "{{agent_id}}"
          properties: "{{$}}"
```

**Agent Termination Cleanup**:
```yaml
transformers:
  - source: "agent:terminated"
    targets:
      - event: "state:entity:delete"
        mapping:
          type: "agent"
          id: "{{agent_id}}"
      - event: "monitor:agent_terminated"
        mapping:
          agent_id: "{{agent_id}}"
          reason: "{{termination_reason|normal}}"
          final_state: "{{$}}"
      - event: "cleanup:agent_resources"
        mapping:
          agent_id: "{{agent_id}}"
          cleanup_sandbox: true
```

#### Phase 2B: State & Configuration Propagation (Days 11-12)
**Targets**: `state.py`, `config_service.py` notification handlers

**State Change Notifications**:
```yaml
transformers:
  - source: "state:entity:updated"
    target: "monitor:state_change"
    mapping:
      entity_type: "{{type}}"
      entity_id: "{{id}}"
      changes: "{{properties}}"
      updated_by: "{{_ksi_context._agent_id|system}}"
      timestamp: "{{timestamp_utc()}}"
```

**Configuration Propagation**:
```yaml
transformers:
  - source: "config:updated"
    targets:
      - event: "monitor:config_change"
        mapping: "{{$}}"
      - event: "services:reload_config"
        condition: "requires_reload == true"
        mapping:
          service: "{{affected_service}}"
          config_section: "{{section}}"
```

#### Phase 2C: Observation & Monitoring (Days 13-14)
**Targets**: `observation/` modules - subscription and replay handlers

**Subscription Management**:
```yaml
transformers:
  - source: "observation:subscribe"
    targets:
      - event: "monitor:subscription_created"
        mapping:
          observer_id: "{{observer_id}}"
          event_pattern: "{{pattern}}"
          subscribed_at: "{{timestamp_utc()}}"
      - event: "state:entity:create"
        mapping:
          type: "subscription"
          id: "{{subscription_id}}"
          properties: "{{$}}"
```

**Expected Outcome**: 40-50 handlers DELETED COMPLETELY, cleaner service architecture

### Phase 3: Conditional & Complex Routing (Week 5-6)
**Objective**: Migrate handlers with conditional logic and complex routing

#### Phase 3A: Error & Completion Routing (Days 15-17)
**Targets**: `completion_service.py`, `permission_service.py` conditional handlers

**Completion Handler to DELETE COMPLETELY**:
```python
# DELETE ENTIRE HANDLER - BREAKING CHANGE, NO FALLBACKS
@event_handler("completion:result")
async def handle_completion_result(data, context):
    # REMOVE ALL CONDITIONAL LOGIC - 20+ lines
    # Replace with declarative transformers below
    if data.get("status") == "error":
        await emit_event("alert:completion_error", data)
    elif data.get("tokens", {}).get("total", 0) > 10000:
        await emit_event("alert:high_token_usage", data)
    else:
        await emit_event("monitor:completion_success", data)
```

**New Conditional Transformers (BREAKING CHANGE)**:
```yaml
transformers:
  - source: "completion:result"
    condition: "status == 'error'"
    target: "alert:completion_error"
    mapping: "{{$}}"
    
  - source: "completion:result"
    condition: "tokens.total > 10000"
    target: "alert:high_token_usage"
    mapping:
      agent_id: "{{agent_id}}"
      tokens_used: "{{tokens.total}}"
      cost_estimate: "{{tokens.total * 0.00002}}"
      alert_summary: "High usage: {{tokens.total}} tokens"
      
  - source: "completion:result"
    condition: "status == 'success' && tokens.total <= 10000"
    target: "monitor:completion_success"
    mapping: "{{$}}"
```

**Permission-Based Routing**:
```yaml
transformers:
  - source: "permission:check_result"
    condition: "granted == true"
    target: "agent:permission_granted"
    mapping:
      agent_id: "{{agent_id}}"
      permission: "{{permission}}"
      granted_by: "{{_ksi_context._agent_id}}"
      
  - source: "permission:check_result"
    condition: "granted == false"
    target: "security:permission_denied"
    mapping:
      agent_id: "{{agent_id}}"
      permission: "{{permission}}"
      reason: "{{denial_reason}}"
      security_event: true
```

#### Phase 3B: Orchestration Event Routing (Days 18-19)
**Targets**: `orchestration_service.py` - complex pattern-based routing

**Pattern-Based Agent Routing**:
```yaml
transformers:
  - source: "orchestration:agent_event"
    condition: "event_type == 'status_update'"
    target: "orchestration:status_aggregation"
    mapping:
      orchestration_id: "{{orchestration_id}}"
      agent_updates: "{{agent_statuses}}"
      summary: "{{len(agents)}} agents, {{active_count}} active"
      
  - source: "orchestration:agent_event"
    condition: "event_type == 'completion'"
    targets:
      - event: "orchestration:task_completed"
        mapping:
          orchestration_id: "{{orchestration_id}}"
          completed_by: "{{agent_id}}"
          result: "{{result}}"
      - event: "monitor:orchestration_progress"
        mapping:
          progress: "{{completed_tasks / total_tasks * 100}}"
          orchestration_id: "{{orchestration_id}}"
```

**Expected Outcome**: 30-40 complex routing handlers DELETED COMPLETELY, declarative conditional logic

### Phase 4: Advanced Patterns & Optimization (Week 7-8)
**Objective**: Migrate remaining suitable handlers and optimize transformer performance

#### Phase 4A: Evaluation & Metrics Chains (Days 20-22)
**Targets**: `evaluation/` modules - tournament and optimization handlers

**Tournament Evaluation Routing**:
```yaml
transformers:
  - source: "tournament:round_complete"
    targets:
      - event: "evaluation:calculate_scores"
        mapping:
          tournament_id: "{{tournament_id}}"
          round_results: "{{results}}"
          participants: "{{participants}}"
      - event: "monitor:tournament_progress"
        mapping:
          tournament_id: "{{tournament_id}}"
          rounds_complete: "{{completed_rounds}}"
          total_rounds: "{{total_rounds}}"
          progress_pct: "{{completed_rounds / total_rounds * 100}}"
```

**Metrics Aggregation**:
```yaml
transformers:
  - source: "metrics:raw_data"
    target: "metrics:aggregated"
    mapping:
      agent_id: "{{agent_id}}"
      time_window: "{{window}}"
      metrics:
        total_tokens: "{{sum(token_counts)}}"
        avg_response_time: "{{avg(response_times)}}"
        error_rate: "{{errors / total_requests * 100}}"
      summary: "Agent {{agent_id}}: {{sum(token_counts)}} tokens, {{errors}} errors"
```

#### Phase 4B: Performance Optimization (Days 23-24)
**Template Compilation Caching**:
- Pre-compile frequently used transformer templates
- Cache template variable extraction results
- Optimize regex patterns for template matching

**Transformer Loading Optimization**:
- Lazy load transformer patterns
- Index transformers by source event patterns
- Background refresh for hot-reloadable updates

#### Phase 4C: Advanced Features Implementation (Days 25-28)
**Expression Evaluation Enhancement**:
```yaml
# Enable complex conditions:
condition: "tokens.total > threshold && user.tier == 'premium'"
condition: "len(errors) > 0 && severity in ['critical', 'high']"
```

**Multi-Target Transformer Support**:
```yaml
# Native multi-target syntax:
transformers:
  - source: "orchestration:completed"
    targets:
      - event: "monitor:orchestration_done"
        mapping: "{{$}}"
      - event: "cleanup:orchestration"
        mapping:
          id: "{{orchestration_id}}"
      - event: "metrics:orchestration_metrics"
        mapping:
          duration: "{{end_time - start_time}}"
          success: "{{status == 'completed'}}"
```

**Expected Outcome**: All suitable handlers DELETED COMPLETELY, 50-70% reduction in handler code

## Success Metrics

### Quantitative Goals
- **Code Reduction**: 50-70% fewer lines in event handler files
- **Handler Count**: From 302 handlers to ~150-200 (complex logic remains)
- **Performance**: 10-20% improvement in event routing latency
- **Files Affected**: ~20-25 service files with significantly fewer handlers

### Qualitative Improvements
- **Maintainability**: Event flow visible in YAML configuration
- **Hot-reload**: Route changes without daemon restart
- **Testing**: Transformer behavior testable in isolation
- **Documentation**: Self-documenting event flows through declarative patterns

### Migration Approach: Breaking Changes with Complete Legacy Removal
**BREAKING CHANGE POLICY**: No backward compatibility, no fallbacks, complete legacy removal

1. **Complete Handler Removal**: Delete Python handlers entirely - no commenting out
2. **Breaking Change Documentation**: Document all removed handlers and replacement transformers
3. **Comprehensive Testing**: Existing integration tests validate new transformer behavior
4. **Clean Migrations**: Each phase removes legacy code completely

## Implementation Guidelines

### Handler Classification Criteria
**Suitable for Migration**:
- Pure event forwarding with field mapping
- Conditional routing based on data values
- Multi-target event distribution
- Status and state change propagation
- Simple data transformation and enrichment

**Should Remain in Python**:
- Complex business logic and calculations
- Database operations and transactions
- External API calls and file I/O
- Error handling with recovery logic
- Stateful processing requiring memory

### Transformer Design Principles
1. **Declarative First**: Express intent, not implementation
2. **Hot-Reloadable**: Changes apply without daemon restart
3. **Self-Documenting**: YAML serves as event flow documentation
4. **Test-Friendly**: Transformers testable in isolation
5. **Performance-Oriented**: Optimize for router-level processing

### Migration Validation Process (Breaking Change Approach)
1. **Functional Equivalence**: Transformer provides same functionality as deleted handler
2. **Performance Testing**: Event processing performance maintained or improved
3. **Integration Testing**: All dependent systems work with new transformer behavior
4. **Error Handling**: Edge cases handled in transformer or deliberately removed
5. **Breaking Change Documentation**: All removed handlers and behavior changes documented
6. **No Rollback Planning**: Complete removal, move forward only

## Related Documents
- [Event Transformer Vision](EVENT_TRANSFORMER_VISION.md) - Overall transformer architecture
- [Transformer Migration Guide](TRANSFORMER_MIGRATION_GUIDE.md) - Implementation details
- [Unified Template Utility](UNIFIED_TEMPLATE_UTILITY_PROPOSAL.md) - Template processing system

---

**Status**: Ready for implementation  
**Next Step**: Begin Phase 1A - Infrastructure Setup  
**Timeline**: 8 weeks for complete migration  
**Expected Completion**: 50-70% handler code reduction achieved