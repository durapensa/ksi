# Conversation Event Architecture & Transformer Possibilities

## Event Interaction Pattern

The `agent:conversation_summary` implementation showcases a powerful pattern in KSI's event-driven architecture:

### 1. Two-Layer Event Architecture

```
External API Layer:
├── agent:conversation_summary (agent_service.py)
│   └── User-friendly interface
│   └── Agent-centric view
│   └── Handles agent context

Internal Service Layer:
└── completion:get_conversation_summary (completion_service.py)
    └── Direct data access
    └── Service-level functionality
    └── Reusable by any component
```

### 2. How They Interact

```python
# In agent_service.py
@event_handler("agent:conversation_summary")
async def handle_agent_conversation_summary(data, context):
    # Emits internal event
    summary_result = await agent_emit_event(
        "system",
        "completion:get_conversation_summary",  # ← Calls completion service
        {"agent_id": agent_id, "include_fields": include_fields},
        context
    )
    return event_response_builder(summary_result, context)

# In completion_service.py  
@event_handler("completion:get_conversation_summary")
async def handle_get_conversation_summary(data, context):
    # Direct access to conversation_tracker
    summary = await conversation_tracker.get_agent_conversation_summary(...)
    return event_response_builder(summary, context)
```

### 3. Why This Pattern is Powerful

#### A. **Multiple Access Points**
- External clients use `agent:conversation_summary` (higher abstraction)
- Agents can directly use `completion:get_conversation_summary` (raw access)
- Both are discoverable and documented

#### B. **Module Independence**
- No direct imports between modules
- Pure event-based communication
- Each module remains self-contained

#### C. **Flexibility for Agents**
Agents can choose their level of abstraction:
```bash
# High-level agent interface
{"event": "agent:conversation_summary", "data": {"agent_id": "self"}}

# Direct completion service access
{"event": "completion:get_conversation_summary", "data": {"agent_id": "other_agent"}}
```

## Event Transformer Possibilities

Having `completion:get_conversation_summary` as a regular event opens fascinating possibilities with KSI's event transformer system:

### 1. Conversation Monitoring Transformer

```yaml
# Transform conversation summaries into monitoring events
source: "completion:get_conversation_summary"
target: "monitor:conversation_activity"
condition: "response.context_chain_length > 10"
mapping:
  agent_id: "response.agent_id"
  conversation_length: "response.context_chain_length"
  alert: "'Long conversation detected'"
```

### 2. Cross-Agent Conversation Awareness

```yaml
# When one agent checks another's conversation
source: "completion:get_conversation_summary"
target: "agent:peer_conversation_observed"
condition: "data.agent_id != context._agent_id"
mapping:
  observer: "context._agent_id"
  observed: "data.agent_id"
  summary: "response"
```

### 3. Conversation Quality Analysis Pipeline

```yaml
# Route summaries to quality analysis
source: "completion:get_conversation_summary"
target: "analysis:evaluate_conversation"
async: true
mapping:
  conversation_data: "response"
  evaluation_criteria: ["coherence", "task_progress", "context_usage"]
response_route:
  target: "agent:quality_feedback"
  mapping:
    agent_id: "response.agent_id"
    quality_score: "response.quality_metrics"
```

### 4. Automatic Conversation Archival

```yaml
# Archive completed conversations
source: "completion:get_conversation_summary"
target: "storage:archive_conversation"
condition: "response.status == 'completed' or response.context_chain_length > 50"
mapping:
  archive_data: "response"
  archive_reason: "condition_matched"
```

### 5. Multi-Agent Coordination Triggers

```yaml
# Trigger team coordination based on conversation state
source: "completion:get_conversation_summary"
target: "orchestration:coordinate_team_response"
condition: "response.contexts[-1].context.contains('need assistance')"
mapping:
  requesting_agent: "response.agent_id"
  context: "response.contexts[-1]"
  coordination_type: "assistance_request"
```

## Advanced Patterns

### 1. Conversation State Machine
```yaml
# Transform conversation summaries into state transitions
transformers:
  - source: "completion:get_conversation_summary"
    target: "state:conversation_phase"
    mapping:
      phase: |
        CASE
          WHEN response.context_chain_length < 3 THEN 'greeting'
          WHEN response.context_chain_length < 10 THEN 'exploration'
          WHEN response.context_chain_length < 20 THEN 'deep_work'
          ELSE 'conclusion'
        END
```

### 2. Conversation Metrics Stream
```yaml
# Stream metrics for real-time dashboards
source: "completion:get_conversation_summary"
target: "metrics:conversation_update"
mapping:
  metric_type: "conversation"
  dimensions:
    agent_id: "response.agent_id"
    session_id: "response.session_id"
  values:
    length: "response.context_chain_length"
    request_count: "response.request_count"
    active: "response.status == 'active_session'"
```

### 3. Intelligent Context Routing
```yaml
# Route conversations to specialized handlers based on content
source: "completion:get_conversation_summary"
target: "router:conversation_classifier"
async: true
response_route:
  - condition: "response.classification == 'technical_support'"
    target: "agent:spawn_technical_assistant"
  - condition: "response.classification == 'creative_work'"
    target: "agent:enhance_creative_mode"
  - default:
    target: "agent:continue_standard"
```

## Implementation Example

To register a conversation monitoring transformer:

```bash
ksi send router:register_transformer --transformer '{
  "source": "completion:get_conversation_summary",
  "target": "monitor:conversation_metrics",
  "mapping": {
    "agent_id": "response.agent_id",
    "metrics": {
      "session_length": "response.context_chain_length",
      "is_active": "response.status == \"active_session\"",
      "last_activity": "response.last_activity"
    }
  }
}'
```

## Benefits of This Architecture

1. **Observability**: Any component can observe conversation states
2. **Automation**: Trigger actions based on conversation patterns
3. **Analytics**: Stream conversation data for analysis
4. **Coordination**: Enable multi-agent awareness and cooperation
5. **Quality Control**: Automatic monitoring and intervention

## Future Possibilities

### 1. Conversation Intelligence Layer
Build a meta-layer that:
- Monitors all agent conversations
- Detects patterns and anomalies
- Suggests optimizations
- Triggers interventions

### 2. Conversation Marketplace
Agents could:
- "Sell" successful conversation patterns
- "Buy" conversation strategies
- Share conversation insights
- Learn from peer interactions

### 3. Autonomous Conversation Management
Transformers could:
- Automatically fork conversations at decision points
- Create checkpoints before risky operations
- Merge insights from parallel conversation branches
- Optimize conversation flow in real-time

The combination of accessible internal events and the transformer system creates a powerful foundation for building intelligent, self-improving conversation systems.