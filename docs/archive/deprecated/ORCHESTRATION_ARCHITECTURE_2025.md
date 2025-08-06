# Orchestration Architecture 2025

## Core Philosophy

The orchestration system is an **enabler**, not a controller. It provides infrastructure for autonomous agents to coordinate naturally through communication.

## Design Principles

1. **Agent Autonomy**: Agents are self-directed entities with full context
2. **Simple Initialization**: Spawn agents with compositions and optional prompts
3. **Emergent Coordination**: Patterns emerge from agent behavior, not system control
4. **Direct Communication**: Agents coordinate through messages (currently completion:async, future: pub/sub)

## Agent Initialization

### Simple and Direct

```yaml
agents:
  analyst:
    component: "components/personas/data_analyst"
    prompt: "Analyze this dataset: {{data}}"  # Optional kickoff message
    
  coordinator:
    component: "components/behaviors/coordinator"
    # No prompt - agent starts based on its composition
```

### What Happens

1. Agent receives its full composition (identity, capabilities, behavioral patterns)
2. Agent receives optional prompt to begin work
3. System gets out of the way

### No "Strategies" or "Phases"

The system does NOT:
- Control message routing between agents
- Enforce turn-taking or phases
- Define roles or coordination patterns
- Manage "initialization strategies"

These emerge from agent compositions and behaviors.

## InitializationRouter Evolution (2025)

### The Cleanup
- **Before**: 478 lines with 7 hard-coded "strategies" (legacy, role_based, peer_to_peer, distributed, hierarchical, state_machine, dynamic)
- **After**: 123 lines of simple prompt extraction and delivery
- **Removed**: All coordination control logic - agents handle this themselves
- **Preserved**: DSL patterns for agent interpretation (not system execution)

### Key Change
```python
# OLD: System tried to control coordination
if strategy == "role_based":
    self._apply_role_based_routing(messages, roles)
elif strategy == "peer_to_peer":
    self._setup_peer_connections(agents)
# ... etc

# NEW: System just delivers prompts
def route_messages(self, orchestration_config, agent_list):
    """Extract and prepare initial prompts for agents."""
    # Only extracts prompts from agent definitions
    # No coordination control
```

## Future: Proper Messaging

Current: Agents use `completion:async` for communication (expedient but limited)

Future: Event-based messaging system with:
- **Subscribe**: Agents subscribe to specific message types/sources
- **Publish**: Agents publish messages to topics
- **Unicast**: Direct agent-to-agent messages
- **Multicast**: Messages to agent groups
- **Broadcast**: System-wide announcements

## Graph-Based Architecture

- Agents and orchestrations are nodes in a directed graph
- Event routing follows edges (parent-child relationships)
- Subscription levels control propagation depth
- Natural hierarchies emerge from spawning patterns

## Examples

### Simple Tournament
```yaml
name: simple_tournament
agents:
  judge:
    component: "components/evaluators/tournament_judge"
    prompt: "Evaluate solutions from three analysts"
    
  analyst_1:
    component: "components/personas/basic_analyst"
    prompt: "Analyze: {{problem}}"
    
  analyst_2:
    component: "components/personas/detailed_analyst"  
    prompt: "Analyze: {{problem}}"
    
  analyst_3:
    component: "components/personas/creative_analyst"
    prompt: "Analyze: {{problem}}"
```

Coordination emerges from agent behaviors, not system control.