# Immediate KSI Experiments

Experiments we can run with the current system to explore its capabilities and identify enhancement opportunities.

## Experiment 1: Agent Network Dynamics

### 1.1 Spawn Tree Exploration
Test different agent spawning patterns and observe network formation.

```python
# Create an originator that spawns coordinators
originator_experiment = {
    "profile": "base_multi_agent",
    "prompt": """You are an experiment originator. Your task is to:
    1. Spawn 3 coordinator agents with different specializations
    2. Ask each coordinator to spawn 2 worker agents
    3. Create a collaboration network between them
    4. Report on the network structure
    """,
    "metadata": {
        "experiment": "spawn_tree",
        "depth_target": 3
    }
}

# Track the network formation
await ksi.spawn_agent(originator_experiment)
# Then query the graph to see the structure
```

### 1.2 Collaboration Patterns
Test inter-agent communication and task delegation.

```python
# Test pub/sub messaging between agents
collaboration_test = {
    "agents": [
        {"role": "publisher", "topics": ["tasks", "updates"]},
        {"role": "subscriber", "topics": ["tasks"]},
        {"role": "coordinator", "topics": ["tasks", "updates"]}
    ],
    "experiment": "message_patterns"
}
```

## Experiment 2: Event Pattern Mining

### 2.1 Behavioral Analysis
Mine event logs to understand agent behavior patterns.

```python
# Find common event sequences
pattern_analysis = {
    "event": "observation:analyze_patterns",
    "data": {
        "target": "originator_1",
        "analysis_type": "frequency",
        "window": "1h"
    }
}

# Look for n-grams in event sequences
sequence_mining = {
    "event": "observation:query_history",
    "data": {
        "target": "all_agents",
        "pattern": "completion:*",
        "analyze_sequences": true
    }
}
```

### 2.2 Performance Profiling
Analyze completion times and error patterns.

```python
# Track completion performance
performance_query = {
    "event": "monitor:query",
    "data": {
        "pattern": ["observe:begin", "observe:end"],
        "calculate_durations": true,
        "group_by": "originator_id"
    }
}
```

## Experiment 3: Graph Database Stress Test

### 3.1 Complex Relationship Networks
Create complex entity relationships and test traversal performance.

```python
# Create a knowledge graph
knowledge_graph = {
    "entities": [
        {"type": "concept", "id": "ai", "properties": {"name": "Artificial Intelligence"}},
        {"type": "concept", "id": "ml", "properties": {"name": "Machine Learning"}},
        {"type": "concept", "id": "dl", "properties": {"name": "Deep Learning"}},
        {"type": "paper", "id": "attention", "properties": {"title": "Attention Is All You Need"}},
        {"type": "author", "id": "vaswani", "properties": {"name": "Vaswani et al."}}
    ],
    "relationships": [
        {"from": "ml", "to": "ai", "type": "subset_of"},
        {"from": "dl", "to": "ml", "type": "subset_of"},
        {"from": "attention", "to": "dl", "type": "applies"},
        {"from": "vaswani", "to": "attention", "type": "authored"}
    ]
}

# Test graph traversal
traversal_test = {
    "event": "state:graph:traverse",
    "data": {
        "from": "ai",
        "direction": "incoming",
        "depth": 3,
        "types": ["subset_of"],
        "include_entities": true
    }
}
```

### 3.2 Scale Testing
Create thousands of entities and test query performance.

```python
# Generate a social network graph
for i in range(1000):
    await create_entity(f"user_{i}", "person", {"active": random.choice([true, false])})
    # Create random friendships
    for _ in range(random.randint(1, 10)):
        friend = f"user_{random.randint(0, 999)}"
        await create_relationship(f"user_{i}", friend, "friends_with")

# Query active users with most friends
active_influencers = {
    "event": "state:entity:query",
    "data": {
        "type": "person",
        "where": {"active": "true"},
        "include": ["relationships"],
        "order_by": "relationship_count DESC",
        "limit": 10
    }
}
```

## Experiment 4: Observation & Replay

### 4.1 Event Replay Testing
Record agent interactions and replay them.

```python
# Record a conversation
recording_session = {
    "observer": "experiment_observer",
    "target": "test_agent",
    "events": ["completion:*", "agent:*"],
    "duration": "10m"
}

# Replay with different parameters
replay_config = {
    "event": "observation:replay",
    "data": {
        "session": recording_session["id"],
        "speed": 2.0,  # 2x speed
        "target_agent": "replay_test_agent"
    }
}
```

### 4.2 Behavioral Cloning
Analyze and replicate agent behavior patterns.

```python
# Extract behavior patterns
behavior_extract = {
    "event": "observation:extract_patterns",
    "data": {
        "source_agent": "expert_agent",
        "pattern_types": ["response_style", "tool_usage", "decision_patterns"],
        "create_profile": true
    }
}
```

## Experiment 5: Time-Series Analysis

### 5.1 Event Frequency Analysis
Analyze event patterns over time.

```python
# Hourly event distribution
time_analysis = {
    "event": "event_log:query",
    "data": {
        "aggregation": "hourly",
        "metrics": ["count", "unique_originators", "error_rate"],
        "time_range": "24h"
    }
}

# Detect anomalies
anomaly_detection = {
    "event": "monitor:detect_anomalies",
    "data": {
        "baseline_period": "7d",
        "detection_window": "1h",
        "metrics": ["event_rate", "error_rate", "response_time"]
    }
}
```

### 5.2 Trend Analysis
Identify trends in system usage.

```python
# Weekly trends
trend_analysis = {
    "event": "monitor:analyze_trends",
    "data": {
        "metrics": ["agent_spawns", "completion_requests", "state_operations"],
        "period": "weekly",
        "duration": "30d"
    }
}
```

## Experiment 6: Capability Evolution Testing

### 6.1 Manual Evolution
Test changing agent capabilities at runtime.

```python
# Start with limited agent
limited_agent = {
    "profile": "base_single_agent",
    "capabilities": {
        "state_write": false,
        "spawn_agents": false
    }
}

# Monitor performance
# Then upgrade based on needs
upgrade_event = {
    "event": "agent:update_capabilities",
    "data": {
        "agent_id": limited_agent["id"],
        "add_capabilities": ["state_write"],
        "reason": "Needs to persist findings"
    }
}
```

### 6.2 Performance-Based Evolution
Track metrics and suggest capability changes.

```python
# Monitor agent performance
performance_monitor = {
    "event": "agent:analyze_performance",
    "data": {
        "agent_id": "test_agent",
        "metrics": ["task_completion_rate", "error_rate", "resource_usage"],
        "suggest_evolution": true
    }
}
```

## Experiment 7: Message Bus & Orchestration

### 7.1 Pub/Sub Patterns
Test different messaging patterns.

```python
# Fan-out pattern
fanout_test = {
    "publisher": "coordinator",
    "topic": "tasks",
    "subscribers": ["worker_1", "worker_2", "worker_3"],
    "message_pattern": "broadcast"
}

# Request-response pattern
rpc_test = {
    "client": "requester",
    "service": "calculator",
    "pattern": "request_response",
    "timeout": 5000
}
```

### 7.2 Workflow Orchestration
Test complex multi-step workflows.

```python
# Define a workflow
research_workflow = {
    "steps": [
        {"agent": "researcher", "task": "gather_sources"},
        {"agent": "analyzer", "task": "analyze_data", "depends_on": ["gather_sources"]},
        {"agent": "writer", "task": "create_report", "depends_on": ["analyze_data"]},
        {"agent": "reviewer", "task": "review_report", "depends_on": ["create_report"]}
    ],
    "error_handling": "retry_with_backoff"
}
```

## Running the Experiments

### Setup
```bash
# Start daemon with debug logging
KSI_LOG_LEVEL=DEBUG ./daemon_control.py start

# Monitor logs in separate terminal
tail -f var/logs/daemon/daemon.log

# Watch event stream
tail -f var/logs/events/$(date +%Y-%m-%d)/*.jsonl | jq .
```

### Execution Framework
```python
# experiments/run_experiments.py
import asyncio
from ksi_client import EventClient
from typing import List, Dict, Any

class ExperimentRunner:
    def __init__(self):
        self.client = EventClient()
        self.results = []
    
    async def run_experiment(self, name: str, events: List[Dict[str, Any]]):
        """Run a series of events and collect results."""
        print(f"\n=== Running Experiment: {name} ===")
        
        for event in events:
            try:
                result = await self.client.send_single(
                    event["event"], 
                    event["data"]
                )
                self.results.append({
                    "experiment": name,
                    "event": event["event"],
                    "result": result,
                    "timestamp": time.time()
                })
                print(f"✓ {event['event']}: Success")
            except Exception as e:
                print(f"✗ {event['event']}: {e}")
    
    async def analyze_results(self):
        """Analyze experiment results."""
        # Group by experiment
        # Calculate success rates
        # Identify patterns
        pass

# Run all experiments
async def main():
    runner = ExperimentRunner()
    
    # Add experiments here
    await runner.run_experiment("spawn_tree", spawn_tree_events)
    await runner.run_experiment("graph_scale", graph_scale_events)
    
    await runner.analyze_results()

if __name__ == "__main__":
    asyncio.run(main())
```

### Metrics to Track
1. **Performance**: Query times, traversal depth vs time
2. **Scale**: Number of entities/relationships vs response time  
3. **Reliability**: Error rates, retry patterns
4. **Patterns**: Common event sequences, bottlenecks
5. **Evolution**: Capability usage vs task success

### Expected Insights
- Current graph DB performance limits
- Event pattern mining opportunities
- Agent collaboration effectiveness
- System bottlenecks and optimization points
- Feature gaps that need addressing

## Next Steps

After running these experiments:
1. Analyze results to validate enhancement priorities
2. Identify quick wins we can implement immediately
3. Benchmark current performance for comparison
4. Design targeted improvements based on findings
5. Create regression tests from experiment scenarios

These experiments will give us concrete data about KSI's current capabilities and guide our enhancement strategy.