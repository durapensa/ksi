# Dynamic Routing Architecture for KSI

## Executive Summary

This document proposes a fundamental architectural shift in KSI: replacing the static orchestration layer with a dynamic routing system where agents can modify routing rules at runtime. This would transform KSI from a system with predetermined coordination patterns into a truly adaptive, emergent multi-agent system.

## Current State Analysis

### Three-Layer Architecture
```
Orchestrations (Static YAML) → Defines routing at deployment
         ↓
Agents (LLM Intelligence) → Execute tasks but can't modify routing
         ↓  
Infrastructure (Transformers) → Execute routing rules deterministically
```

### Limitations of Current Design

1. **Static Coordination**: Routing patterns fixed at orchestration start
2. **Limited Adaptability**: Agents can't respond to changing needs
3. **Rigid Hierarchies**: Parent-child relationships predetermined
4. **No Emergent Behavior**: System can't evolve new coordination patterns
5. **Orchestration Overhead**: Extra abstraction layer for coordination

## Vision: Dynamic Routing Architecture

### Two-Layer Architecture with Dynamic Control
```
Agents (Intelligence + Routing Control) → Can modify infrastructure rules
         ↓ ↑
Infrastructure (Smart Transformers) → Execute and report on routing
```

### Core Capabilities

1. **Runtime Route Modification**
   ```python
   # Agent can add new routing rules dynamically
   {"event": "routing:add_rule", "data": {
       "rule_id": "analyzer_to_reviewer_v2",
       "source_pattern": "analysis:complete",
       "source_agent": "analyzer_{{task_id}}",
       "target_agent": "reviewer_{{task_id}}",
       "mapping": {"priority": "high"}
   }}
   ```

2. **Dynamic Agent Relationships**
   ```python
   # Agent can spawn and connect new agents
   {"event": "agent:spawn_with_routing", "data": {
       "agent_id": "specialist_analyzer",
       "component": "components/personas/domain_expert",
       "routing": {
           "parent": "self",
           "subscription_level": 1,
           "capabilities": ["analysis", "routing"]
       }
   }}
   ```

3. **Adaptive Subscription Levels**
   ```python
   # Agent can change how deeply it monitors events
   {"event": "routing:update_subscription", "data": {
       "agent_id": "coordinator",
       "subscription_level": -1,  # Now monitoring all descendants
       "reason": "Critical phase requires full visibility"
   }}
   ```

## Implementation Design

### Phase 1: Infrastructure Extensions

#### New Transformer Functions
```python
# Dynamic routing context functions
def add_routing_rule(rule_id: str, config: Dict) -> bool
def remove_routing_rule(rule_id: str) -> bool
def update_routing_rule(rule_id: str, updates: Dict) -> bool
def get_active_routes(agent_id: str) -> List[RouteConfig]
def validate_routing_permission(agent_id: str, operation: str) -> bool
```

#### New Events for Routing Control
```yaml
routing:add_rule:
  description: "Add new routing rule to transformer system"
  parameters:
    rule_id: "Unique identifier for rule"
    source_pattern: "Event pattern to match"
    condition: "Optional condition expression"
    target: "Target event or agent"
    mapping: "Data transformation"
    priority: "Rule priority (higher wins)"
    ttl: "Optional time-to-live in seconds"

routing:modify_rule:
  description: "Modify existing routing rule"
  parameters:
    rule_id: "Rule to modify"
    updates: "Fields to update"

routing:delete_rule:
  description: "Remove routing rule"
  parameters:
    rule_id: "Rule to remove"
    
routing:query_routes:
  description: "Query active routing rules"
  parameters:
    filter: "Optional filter criteria"
    agent_scope: "Limit to specific agent's rules"
```

### Phase 2: Agent Capabilities

#### New Capability: `routing_control`
Agents with this capability can:
- Add/modify/delete routing rules
- Change subscription levels
- Create agent relationships
- Query routing state

#### Enhanced Agent Spawn
```python
# Agents can spawn with initial routing AND modify it later
spawn_result = {
    "agent_id": "coordinator_123",
    "routing_context": {
        "rules": [...],  # Initial rules
        "modifiable": true,  # Agent can change rules
        "scope": "orchestration"  # Rules apply to whole orchestration
    }
}
```

### Phase 3: Safety and Governance

#### Permission Model
```python
class RoutingPermission:
    NONE = 0  # No routing control
    SELF = 1  # Can modify own routes only
    CHILDREN = 2  # Can modify children's routes
    ORCHESTRATION = 3  # Can modify orchestration routes
    GLOBAL = 4  # Can modify any routes (admin)
```

#### Validation Rules
1. Agents can only modify routes they have permission for
2. Circular routing detected and prevented
3. Route conflicts resolved by priority
4. Audit trail for all routing changes

## Use Cases and Examples

### 1. Self-Organizing Analysis Team
```python
# Coordinator dynamically builds analysis team
coordinator: "I need specialist analyzers for this complex dataset"

# Spawns analysts with routing
→ spawn(financial_analyst) with route(reports → self)
→ spawn(risk_analyst) with route(alerts → self, reports → financial_analyst)
→ spawn(summarizer) with route(* → self from [financial_analyst, risk_analyst])

# Later, based on findings
coordinator: "Need deeper investigation"
→ spawn(forensic_analyst) with route(findings → risk_analyst)
→ update_route(risk_analyst → forensic_analyst, bidirectional=true)
```

### 2. Adaptive Load Balancing
```python
# Monitor agent watches system load
monitor: "Worker_1 is overloaded"

# Dynamically redistributes routing
→ spawn(worker_3)
→ add_rule(pattern="task:*", condition="load_balanced()", 
          targets=[worker_1, worker_2, worker_3])
→ delete_rule(old_direct_routing)
```

### 3. Emergent Hierarchy Formation
```python
# Agents negotiate and form hierarchies
agent_a: "I'll coordinate data collection"
agent_b: "I'll handle analysis" 
agent_c: "I'll do visualization"

# They establish routing relationships
→ agent_a.add_route(data:raw → agent_b)
→ agent_b.add_route(data:processed → agent_c)
→ agent_c.add_route(viz:complete → agent_a)

# Later, they adapt
agent_b: "Too much data, need help"
→ spawn(agent_b_helper)
→ add_route(data:subset → agent_b_helper)
→ update_route(agent_b_helper → self, merge_results)
```

### 4. Learning and Pattern Evolution
```python
# Optimization agent observes patterns
optimizer: "This routing pattern (A→B→C) is inefficient"

# Creates improved routing
→ add_rule(A → [B,C], parallel=true)  # B and C in parallel
→ add_rule([B,C] → D, when="both_complete")  # New aggregator
→ measure_improvement()
→ if better: delete_old_rules()
```

## Benefits of Dynamic Routing

### 1. **Emergent Coordination**
- Agents discover optimal patterns through experimentation
- System evolves better coordination over time
- No need to predefine all patterns

### 2. **Adaptive Resilience**
- Failed agents trigger rerouting
- Overloaded agents can redistribute work
- System self-heals through routing changes

### 3. **Contextual Optimization**
- Different routing for different problem types
- Agents learn which patterns work when
- Context-specific coordination emerges

### 4. **Simplified Architecture**
- No orchestration layer needed
- Agents + Infrastructure only
- Cleaner conceptual model

### 5. **Innovation Enablement**
- Agents can invent new coordination patterns
- System becomes a laboratory for emergence
- Meta-learning about coordination

## Challenges and Mitigations

### 1. **Routing Conflicts**
- **Challenge**: Multiple agents modifying same routes
- **Mitigation**: Priority system, conflict detection, atomic operations

### 2. **Performance**
- **Challenge**: Dynamic rules slower than static
- **Mitigation**: Rule compilation, caching, hot path optimization

### 3. **Debugging**
- **Challenge**: Hard to understand dynamic system
- **Mitigation**: Routing visualization, event replay, audit trails

### 4. **Security**
- **Challenge**: Malicious routing modifications
- **Mitigation**: Capability-based permissions, validation, sandboxing

### 5. **Stability**
- **Challenge**: System might oscillate or diverge
- **Mitigation**: Damping mechanisms, stability monitors, rollback

## Migration Path

### Stage 1: Parallel Systems (Months 1-2)
- Keep orchestrations working as-is
- Add dynamic routing as experimental feature
- Test with simple use cases

### Stage 2: Hybrid Mode (Months 3-4)
- New developments use dynamic routing
- Orchestrations can opt-in to dynamic features
- Build confidence and patterns

### Stage 3: Full Migration (Months 5-6)
- Convert orchestrations to dynamic routing
- Deprecate orchestration system
- Full dynamic routing by default

## Example: Migrating Analysis Orchestration

### Current (Static Orchestration)
```yaml
name: analysis_workflow
agents:
  coordinator:
    component: coordinator
  analyzer:
    component: analyzer
  reviewer:
    component: reviewer
routing:
  - from: coordinator
    to: analyzer
    pattern: "task:assign"
  - from: analyzer
    to: reviewer
    pattern: "analysis:complete"
```

### Future (Dynamic Routing)
```python
# Coordinator component includes routing logic
class CoordinatorComponent:
    def on_init(self):
        # Spawn team with initial routing
        self.spawn_with_routing("analyzer", 
            route_to_self="status:*",
            route_from_self="task:*")
        
    def on_analysis_needed(self, complexity):
        if complexity > 0.8:
            # Dynamically add specialist
            specialist = self.spawn("specialist_analyzer")
            self.add_route(from=specialist, to="analyzer", 
                          pattern="insight:*")
            self.update_route(to=specialist, 
                            pattern="complex_tasks:*")
```

## Philosophical Implications

### From Orchestration to Emergence
- **Old**: Human designs coordination patterns
- **New**: Agents discover coordination patterns
- **Result**: System that improves itself

### From Static to Adaptive
- **Old**: Fixed patterns that might be suboptimal
- **New**: Dynamic patterns that adapt to context
- **Result**: Optimal coordination for each situation

### From Control to Collaboration
- **Old**: Orchestrator controls agents
- **New**: Agents negotiate relationships
- **Result**: True multi-agent collaboration

## Next Steps

1. **Prototype** key transformer functions
2. **Design** routing event schemas
3. **Implement** basic dynamic routing
4. **Test** with simple scenarios
5. **Iterate** based on learnings

## Conclusion

Dynamic routing represents a fundamental shift in how we think about multi-agent coordination. Instead of prescribing patterns, we give agents the tools to create their own. This transforms KSI from a system that executes predetermined patterns into one that discovers and evolves new forms of coordination.

The infrastructure (transformers) provides the mechanism, the agents provide the intelligence, and emergence provides the innovation. This is the path to truly adaptive, self-improving multi-agent systems.

---

*"The best architectures are not designed, they are discovered through the interactions of intelligent agents."*