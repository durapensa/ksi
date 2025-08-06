# KSI Hook Monitor Enhancement Plan for Self-Improvement Visibility

**Purpose:** Enhance ksi_hook_monitor.py to provide better visibility into autonomous self-improvement workflows  
**Current Status:** Analysis complete, implementation pending  
**Priority:** High - critical for monitoring self-improvement progress  

## Current State Analysis

### What's Working Well

The ksi_hook_monitor.py currently provides valuable feedback:

1. **Compact Status Updates**
   - Format: `System message: KSI: EVENTS:40 AGENTS:2`
   - Provides quick event count and agent awareness
   - Non-intrusive, appears after tool use

2. **Event Tracking**
   - Shows only NEW events since last check
   - Prevents duplicate information
   - Maintains timestamp state between invocations

3. **Multiple Verbosity Modes**
   - `summary` - Ultra-concise (default)
   - `verbose` - More detail with agent capabilities
   - `orchestration` - Full debugging information
   - `errors` - Only show errors
   - `silent` - No output

4. **Optimization Awareness**
   - Detects running optimizations
   - Shows "Optimizing component" status
   - Tracks optimization:progress events

5. **Smart Filtering**
   - Only monitors KSI-related commands
   - Avoids recursion and noise
   - Groups repetitive events

### Current Limitations for Self-Improvement Monitoring

#### 1. No Workflow Awareness
**Problem:** Can't recognize improvement workflow patterns
- Doesn't detect evaluation → optimization → validation chains
- No understanding of workflow phases
- Can't track workflow_id through event sequences

**Impact:** Cannot tell where we are in an improvement cycle

#### 2. Limited Agent Context
**Problem:** Shows agent count but not relationships or roles
- No parent-child agent relationships
- Doesn't identify agent types (orchestrator, judge, optimizer)
- No visibility into agent coordination

**Impact:** Can't see how agents are working together

#### 3. No Routing Visibility
**Problem:** Misses critical routing rule creation
- Doesn't show when agents create routing rules
- Can't see event chains being established
- No visibility into transformer execution

**Impact:** Event flow orchestration is invisible

#### 4. Missing Comparative Context
**Problem:** No awareness of comparative analysis
- Doesn't highlight comparative judgments
- No indication of improvement decisions (deploy/reject/iterate)
- Can't show baseline vs optimized scores

**Impact:** Can't track improvement progress

#### 5. Event Chain Blindness
**Problem:** Treats events as isolated rather than connected
- No correlation of events by workflow_id
- Can't show cause-effect relationships
- Misses the bigger picture of orchestrated workflows

**Impact:** Complex workflows appear as noise

## Discovered KSI Introspection Capabilities (2025-08-06)

### Critical Discovery: introspection:event_tree Works! ✅

Investigation revealed powerful introspection events that can dramatically enhance the hook monitor:

#### Available Events for Hook Enhancement

1. **Introspection Events** (Most Valuable)
   - `introspection:event_tree` - Hierarchical event visualization ✅ TESTED
   - `introspection:event_chain` - Query event sequences by correlation
   - `introspection:routing_decisions` - See how events are routed
   - `introspection:routing_path` - Trace specific event paths
   - `introspection:impact_analysis` - Understand cascading effects

2. **State Graph Events**
   - `state:graph:traverse` - Map agent relationships and hierarchies

3. **Monitor Events (Enhanced)**
   - `monitor:get_correlation_chain` - Follow complete workflows
   - `monitor:get_events` - Now supports correlation context

4. **Routing Audit Events**
   - `routing:get_audit_log` - Debug routing decisions
   - `routing:query_audit_log` - Query specific routing patterns

### Example introspection:event_tree Output

```
└─ agent:spawn (evt_a123)
     Correlation: corr_workflow_001
   ├─ agent:spawned (evt_b456)
   │    Depth: 1
   │  ├─ routing:add_rule (evt_c789)
   │  │    Depth: 2
   │  └─ completion:async (evt_d012)
   │       Depth: 2
   │     └─ evaluation:run (evt_e345)
   │          Depth: 3
```

## Proposed Enhancements (Updated with Concrete Capabilities)

### 1. Event Tree Integration (NEW - High Priority)

Use introspection:event_tree for hierarchical workflow visualization:

```python
def _get_event_tree(self, correlation_id: str = None) -> Optional[Dict]:
    """Get hierarchical event tree using introspection"""
    try:
        # Use KSI's introspection:event_tree
        response = self._send_ksi_event("introspection:event_tree", {
            "correlation_id": correlation_id,
            "max_depth": 5,
            "include_data": False  # Keep it compact
        })
        return response.get("tree")
    except Exception:
        return None

def _format_workflow_tree(self, tree: Dict) -> str:
    """Format event tree for compact display"""
    # Extract key workflow phases from tree
    phases = []
    
    def traverse(node, depth=0):
        event_name = node.get("event_name", "")
        if "evaluation" in event_name:
            phases.append("📊Eval")
        elif "optimization" in event_name:
            phases.append("⚙️Opt")
        elif "agent:spawn" in event_name:
            phases.append("🤖Spawn")
        elif "routing:add" in event_name:
            phases.append("🛣️Route")
            
        for child in node.get("children", []):
            traverse(child, depth + 1)
    
    traverse(tree)
    return "→".join(phases[:5])  # First 5 phases
```

### 2. Correlation-Based Workflow Detection (ENHANCED)

Leverage correlation IDs to track complete workflows:

```python
def _is_improvement_workflow(self, events: List[Dict]) -> Tuple[bool, str]:
    """Detect if events represent an improvement workflow with correlation"""
    # Group events by correlation_id
    correlations = {}
    for event in events:
        corr_id = event.get("correlation_id")
        if corr_id:
            if corr_id not in correlations:
                correlations[corr_id] = []
            correlations[corr_id].append(event.get("event_name", ""))
    
    # Check each correlation for improvement patterns
    improvement_indicators = [
        "evaluation:run",
        "optimization:async",
        "agent:spawn",
        "routing:add_rule"
    ]
    
    for corr_id, event_names in correlations.items():
        matches = sum(1 for indicator in improvement_indicators 
                     if any(indicator in name for name in event_names))
        
        if matches >= 2:
            return True, corr_id
    
    return False, None
```

### 2. Workflow Phase Tracking

Track which phase of improvement we're in:

```python
def _detect_improvement_phase(self, events: List[Dict]) -> str:
    """Determine current phase of improvement workflow"""
    
    # Check most recent relevant events
    for event in reversed(events):
        event_name = event.get("event_name", "")
        data = event.get("data", {})
        
        if "evaluation:" in event_name:
            phase = data.get("phase", "")
            if phase == "baseline":
                return "📊 Baseline"
            elif phase == "validation":
                return "✓ Validation"
            else:
                return "📋 Evaluation"
                
        elif "optimization:" in event_name:
            if "result" in event_name:
                return "🔧 Optimized"
            elif "async" in event_name:
                return "⚙️ Optimizing"
                
        elif "judge" in event_name:
            return "⚖️ Judging"
            
        elif "composition:update" in event_name:
            return "🚀 Deploying"
    
    return "🔄 Processing"
```

### 3. Event Chain Visualization

Show connected events as chains:

```python
def _format_event_chain(self, events: List[Dict]) -> str:
    """Format related events as a chain"""
    
    # Group by workflow_id if present
    workflows = {}
    for event in events:
        workflow_id = event.get("data", {}).get("workflow_id")
        if workflow_id:
            if workflow_id not in workflows:
                workflows[workflow_id] = []
            workflows[workflow_id].append(event)
    
    # Format each workflow
    chains = []
    for workflow_id, workflow_events in workflows.items():
        # Build chain representation
        chain_parts = []
        for event in workflow_events:
            name = event.get("event_name", "").split(":")[-1]
            chain_parts.append(name[:4])  # First 4 chars
        
        chain = "→".join(chain_parts)
        chains.append(f"{workflow_id[:8]}: {chain}")
    
    return " | ".join(chains[:2])  # Show first 2 chains
```

### 4. Enhanced Agent Display (Using state:graph:traverse)

Leverage KSI's graph traversal for accurate agent relationships:

```python
def _get_agent_hierarchy(self, agent_id: str = None) -> Dict:
    """Get agent hierarchy using state graph traversal"""
    try:
        # Use state:graph:traverse to get agent relationships
        response = self._send_ksi_event("state:graph:traverse", {
            "entity_type": "agent",
            "entity_id": agent_id,
            "traverse_depth": 3,
            "include_relationships": ["spawned_by", "spawned"]
        })
        return response.get("graph", {})
    except Exception:
        return {}

def _format_agent_hierarchy(self, events: List[Dict]) -> str:
    """Format agents showing relationships using graph data"""
    
    # Get recent agent IDs from events
    agent_ids = set()
    for event in events:
        if "agent" in event.get("event_name", ""):
            data = event.get("data", {})
            if agent_id := data.get("agent_id"):
                agent_ids.add(agent_id)
    
    if not agent_ids:
        return ""
    
    # Get hierarchy for most recent agent
    hierarchy = self._get_agent_hierarchy(list(agent_ids)[0])
    
    if not hierarchy:
        # Fallback to event-based detection
        return self._format_agent_hierarchy_from_events(events)
    
    # Format hierarchy from graph
    output = []
    
    def format_node(node, depth=0):
        component = node.get("properties", {}).get("component", "")
        role = self._identify_agent_role(component)
        children = node.get("children", [])
        
        if children and depth == 0:
            child_roles = [self._identify_agent_role(
                c.get("properties", {}).get("component", "")
            ) for c in children[:3]]
            return f"{role}→[{','.join(child_roles)}]"
        return role
    
    # Format top-level agents
    if "nodes" in hierarchy:
        for node in hierarchy["nodes"][:2]:  # First 2 agents
            output.append(format_node(node))
    
    return " ".join(output)

def _identify_agent_role(self, component_path: str) -> str:
    """Identify agent role from component path"""
    
    if "orchestrator" in component_path:
        return "🎭Orch"
    elif "judge" in component_path:
        return "⚖️Judge"
    elif "optimizer" in component_path:
        return "🔧Opt"
    elif "comparator" in component_path:
        return "📊Comp"
    elif "analyzer" in component_path:
        return "🔍Anal"
    else:
        # Extract last part of path
        parts = component_path.split("/")
        name = parts[-1].replace(".md", "")[:8]
        return f"🤖{name}"
```

### 5. Routing Rule Awareness (Using introspection:routing_decisions)

Use KSI's routing introspection for deep visibility:

```python
def _get_routing_decisions(self, limit: int = 10) -> List[Dict]:
    """Get recent routing decisions using introspection"""
    try:
        response = self._send_ksi_event("introspection:routing_decisions", {
            "limit": limit,
            "include_transformations": True
        })
        return response.get("decisions", [])
    except Exception:
        return []

def _format_routing_rules(self, events: List[Dict]) -> str:
    """Format routing rules and decisions"""
    
    # Get recent routing decisions
    decisions = self._get_routing_decisions(5)
    
    if decisions:
        # Format routing decisions from introspection
        routes = []
        for decision in decisions[:3]:
            source = decision.get("source_event", "?").split(":")[-1][:4]
            targets = decision.get("targets", [])
            if targets:
                target = targets[0].split(":")[-1][:4]
                transformer = decision.get("transformer", "").split("_")[0][:4]
                routes.append(f"{source}→{target}({transformer})")
        
        if routes:
            return f"📋Routes:[{','.join(routes)}]"
    
    # Fallback to event-based detection
    routing_events = [e for e in events 
                     if e.get("event_name") == "routing:add_rule"]
    
    if not routing_events:
        return ""
    
    rules = []
    for event in routing_events[:3]:  # First 3 rules
        data = event.get("data", {})
        source = data.get("source_pattern", "?")
        target = data.get("target", "?")
        
        # Shorten patterns
        source_short = source.split(":")[-1][:4] if ":" in source else source[:4]
        target_short = target.split(":")[-1][:4] if ":" in target else target[:4]
        
        rules.append(f"{source_short}→{target_short}")
    
    return f"📋Routes:[{','.join(rules)}]"
```

### 6. Comparative Score Tracking

Show improvement scores:

```python
def _extract_improvement_scores(self, events: List[Dict]) -> str:
    """Extract and format improvement scores"""
    
    baseline_score = None
    optimized_score = None
    
    for event in events:
        event_name = event.get("event_name", "")
        data = event.get("data", {})
        
        if "evaluation:" in event_name:
            phase = data.get("phase", "")
            scores = data.get("scores", {})
            
            if phase == "baseline" and scores:
                # Get overall score or first dimension
                baseline_score = scores.get("overall", 
                                          next(iter(scores.values()), None))
            
            elif phase == "validation" and scores:
                optimized_score = scores.get("overall",
                                           next(iter(scores.values()), None))
        
        elif "judge" in event_name and "comparative" in event_name:
            # Look for comparative results
            comparison = data.get("comparison", {})
            if comparison:
                baseline_score = comparison.get("baseline", baseline_score)
                optimized_score = comparison.get("optimized", optimized_score)
    
    if baseline_score and optimized_score:
        # Calculate improvement
        if isinstance(baseline_score, (int, float)) and isinstance(optimized_score, (int, float)):
            improvement = ((optimized_score - baseline_score) / baseline_score) * 100
            if improvement > 0:
                return f"📈{baseline_score:.2f}→{optimized_score:.2f}(+{improvement:.0f}%)"
            else:
                return f"📉{baseline_score:.2f}→{optimized_score:.2f}({improvement:.0f}%)"
    
    elif baseline_score:
        return f"📊Baseline:{baseline_score:.2f}"
    
    return ""
```

### 7. New Improvement Mode (Enhanced with Introspection)

Add dedicated modes leveraging introspection capabilities:

```python
# In handle_mode_command method
mode_commands = {
    "echo ksi_verbose": "verbose",
    "echo ksi_summary": "summary",
    "echo ksi_errors": "errors",
    "echo ksi_silent": "silent",
    "echo ksi_orchestration": "orchestration",
    "echo ksi_improvement": "improvement",  # Self-improvement tracking
    "echo ksi_tree": "tree",  # Event tree visualization
    "echo ksi_routing": "routing",  # Routing decision tracking
    "echo ksi_status": None
}

# In format_output method
elif mode == "improvement":
    # Specialized improvement monitoring with introspection
    is_improvement, corr_id = self._is_improvement_workflow(events)
    
    if is_improvement:
        # Get event tree for this workflow
        tree = None
        if corr_id:
            tree = self._get_event_tree(corr_id)
        
        # Build comprehensive view
        parts = []
        
        # Add workflow tree visualization
        if tree:
            tree_format = self._format_workflow_tree(tree)
            parts.append(f"Flow:{tree_format}")
        else:
            phase = self._detect_improvement_phase(events)
            if phase:
                parts.append(phase)
        
        # Add agent hierarchy
        agents = self._format_agent_hierarchy(events)
        if agents:
            parts.append(f"Agents:{agents}")
        
        # Add improvement scores
        scores = self._extract_improvement_scores(events)
        if scores:
            parts.append(scores)
        
        # Add routing rules
        routes = self._format_routing_rules(events)
        if routes:
            parts.append(routes)
        
        if parts:
            return f"KSI 🔄 Self-Improvement: {' '.join(parts)}"
    
    # Fallback to summary if no improvement detected
    return self.format_output(events, agent_status, optimization_status)

elif mode == "tree":
    # Event tree visualization mode
    # Find most recent correlation
    corr_id = None
    for event in reversed(events):
        if corr_id := event.get("correlation_id"):
            break
    
    if corr_id:
        tree = self._get_event_tree(corr_id)
        if tree:
            tree_str = self._format_workflow_tree(tree)
            return f"KSI 🌳 Event Tree: {tree_str}"
    
    return f"KSI: EVENTS:{len(events)}"

elif mode == "routing":
    # Routing decision tracking mode
    decisions = self._get_routing_decisions(10)
    if decisions:
        # Show routing flow
        flows = []
        for d in decisions[:5]:
            source = d.get("source_event", "").split(":")[-1][:6]
            for target in d.get("targets", [])[:1]:
                target_short = target.split(":")[-1][:6]
                flows.append(f"{source}→{target_short}")
        
        if flows:
            return f"KSI 🛣️ Routing: {' '.join(flows)}"
    
    return f"KSI: EVENTS:{len(events)}"
```

## Implementation Priority (Updated with Introspection)

### Phase 1: Introspection Integration (Immediate) ✅ READY
1. Add `introspection:event_tree` support
2. Implement correlation-based workflow detection
3. Add tree visualization mode (`echo ksi_tree`)
4. Test with actual self-improvement workflows

### Phase 2: Enhanced Display (Today)
1. Integrate `state:graph:traverse` for agent hierarchies
2. Add `introspection:routing_decisions` for routing visibility
3. Implement improvement mode with full introspection
4. Add routing mode (`echo ksi_routing`)

### Phase 3: Advanced Features (This Week)
1. Use `introspection:event_chain` for sequence tracking
2. Add `introspection:impact_analysis` for effect prediction
3. Implement performance analysis with timing data
4. Create comprehensive improvement dashboard

## Expected Output Examples

### Current Output
```
System message: KSI: EVENTS:40 AGENTS:3
```

### Enhanced Output (Summary Mode)
```
System message: KSI: EVENTS:40 AGENTS:3 IMPROVING:hello_agent
```

### Enhanced Output (Improvement Mode)
```
System message: KSI 🔄 Self-Improvement: ✓ Validation Agents:🎭Orch→[⚖️Judge,🔧Opt] 📈0.75→0.82(+9%) 📋Routes:[eval→opt]
```

### Enhanced Output (Verbose Improvement)
```
System message: KSI 🔄 Improving hello_agent
Phase: Validation (workflow_test_001)
Agents: orchestrator_001 → [judge_comparative_001, optimizer_001]
Baseline: quality=0.75, tokens=100
Optimized: quality=0.82, tokens=115
Decision: Pending judge evaluation
Routes: evaluation:result→optimization:async, optimization:result→evaluation:validation
```

## Benefits for Self-Improvement Monitoring

1. **Clear Workflow Progress**: Immediately see which phase of improvement we're in
2. **Agent Coordination Visibility**: Understand how agents are working together
3. **Event Chain Understanding**: See how events flow through the system
4. **Decision Tracking**: Know when deployment decisions are made
5. **Improvement Metrics**: Track actual improvement percentages
6. **Routing Awareness**: See the event orchestration being set up
7. **Reduced Cognitive Load**: Relevant information highlighted, noise suppressed

## Success Criteria

The enhanced hook monitor will be successful when:
- ✅ Can identify improvement workflows automatically
- ✅ Shows current phase clearly
- ✅ Displays agent relationships
- ✅ Tracks improvement scores
- ✅ Shows routing rules being created
- ✅ Provides actionable information without overwhelming detail
- ✅ Helps debug bottom-up validation faster

## Conclusion

The discovery of KSI's introspection capabilities fundamentally changes what's possible with the hook monitor. Instead of inferring relationships from raw events, we can now directly query:

- **Hierarchical event trees** via `introspection:event_tree` ✅
- **Agent relationships** via `state:graph:traverse`
- **Routing decisions** via `introspection:routing_decisions`
- **Event sequences** via `introspection:event_chain`
- **Impact analysis** via `introspection:impact_analysis`

These introspection events transform the hook monitor from a simple event counter into a powerful **self-improvement observatory** that provides deep visibility into:

1. **Workflow Structure**: See the complete hierarchical flow of events
2. **Agent Coordination**: Understand parent-child relationships and collaboration
3. **Routing Intelligence**: Track how events flow through transformers
4. **Causal Chains**: Follow cause-and-effect relationships
5. **Performance Metrics**: Monitor efficiency and optimization progress

The key insight: **KSI already has powerful introspection built in - we just need to leverage it!**

### Immediate Next Steps

1. **Implement Phase 1** with `introspection:event_tree` (ready now)
2. **Test with actual workflows** to validate the visualization
3. **Deploy enhanced modes** (`ksi_tree`, `ksi_routing`, `ksi_improvement`)
4. **Iterate based on usage** to refine the display format

With these introspection capabilities, the enhanced hook monitor will provide exactly the visibility needed to monitor, debug, and optimize our autonomous self-improvement system as we build it methodically from the bottom up.