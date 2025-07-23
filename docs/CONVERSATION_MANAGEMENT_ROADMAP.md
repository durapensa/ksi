# Conversation Management Roadmap

## Overview

This document outlines the future enhancements for KSI's conversation management system, focusing on agent conversation continuity, forking, and advanced management capabilities.

## Current Implementation

### ✅ Completed (2025-07-23)
- **`agent:conversation_summary`** - Get agent conversation with resolved contexts
  - Implemented using internal events to avoid cross-module imports
  - Returns last N contexts with full resolution
  - Supports field filtering for efficiency
  
- **`agent:conversation_reset`** - Reset agent conversation history
  - Clears agent's session mapping to start fresh
  - Uses internal event `completion:reset_conversation`
  - Returns confirmation with `had_active_session` flag
  - Usage:
    ```bash
    # Reset an agent's conversation
    ksi send agent:conversation_reset --agent-id agent_123
    
    # Response:
    {
      "agent_id": "agent_123",
      "reset": true,
      "had_active_session": true
    }
    ```
  
#### Implementation Details
- **Module Independence**: Uses `completion:get_conversation_summary` internal event instead of direct imports
- **Architecture**: 
  - `agent_service.py` → (event) → `completion_service.py` → `conversation_tracker.py`
  - No cross-module dependencies, pure event-based communication
- **Usage**:
  ```bash
  # Basic usage
  ksi send agent:conversation_summary --agent-id agent_123
  
  # With field filtering
  ksi send agent:conversation_summary --agent-id agent_123 --include-fields '["_event_id", "_session_id"]'
  ```

## Future Enhancements

### 1. Conversation Forking & Branching

#### Concept
Like git branches for conversations - allow agents to explore different conversation paths from a checkpoint.

```bash
# Create a conversation checkpoint
ksi send agent:conversation_checkpoint --agent-id agent_123 --checkpoint-name "before_analysis"

# Fork from checkpoint
ksi send agent:conversation_fork --agent-id agent_123 --from-checkpoint "before_analysis" --branch-name "alternative_approach"

# Switch between branches
ksi send agent:conversation_switch --agent-id agent_123 --branch "main"
```

#### Implementation Considerations
- Store conversation trees in state system
- Track parent-child relationships between conversation branches
- Support for merging insights from different branches

### 2. Advanced Conversation Metrics

#### Real-time Metrics
```json
{
  "conversation_metrics": {
    "duration_seconds": 3600,
    "total_tokens": {
      "input": 15000,
      "output": 20000
    },
    "average_response_time": 2.5,
    "context_depth": 15,
    "topic_shifts": 3,
    "quality_indicators": {
      "coherence_score": 0.92,
      "task_completion_rate": 0.85
    }
  }
}
```

#### Analytics Events
- `agent:conversation_analytics` - Deep conversation analysis
- `agent:conversation_quality` - Quality metrics and suggestions
- `agent:conversation_topics` - Topic extraction and flow analysis

### 3. Context Window Management

#### Smart Context Pruning
For long conversations exceeding context limits:
- Automatic summarization of older contexts
- Importance-based context retention
- Semantic clustering of related contexts

```bash
# Manual context management
ksi send agent:prune_context --agent-id agent_123 --strategy "importance" --retain-last 10

# Auto-management settings
ksi send agent:set_context_policy --agent-id agent_123 --max-contexts 50 --pruning-strategy "semantic"
```

### 4. Cross-Agent Conversation Sync

#### Shared Context Pools
Allow multiple agents to share conversation context:
```bash
# Create shared context pool
ksi send conversation:create_pool --pool-id "research_team" --agents ["agent_1", "agent_2", "agent_3"]

# Agents can read from shared pool
ksi send agent:join_context_pool --agent-id agent_4 --pool-id "research_team"
```

### 5. Conversation Persistence & Export

#### Advanced Export Formats
- **Claude-compatible**: Export in format ready for `claude --resume`
- **OpenAI-compatible**: Thread format for OpenAI Assistants API
- **Research format**: Structured data for analysis
- **Training format**: Prepared for fine-tuning

```bash
# Export for different platforms
ksi send conversation:export --agent-id agent_123 --format "claude-resume" --output conversation.json
ksi send conversation:export --agent-id agent_123 --format "openai-thread" --output thread.json
```

### 6. Conversation Templates & Replay

#### Template System
Save successful conversation patterns as reusable templates:
```bash
# Save conversation as template
ksi send conversation:save_template --agent-id agent_123 --template-name "research_interview" --checkpoint "after_methodology"

# Start new conversation from template
ksi send agent:spawn --profile researcher --conversation-template "research_interview"
```

#### Replay Capabilities
- Replay conversations with different models
- A/B test conversation strategies
- Automated conversation testing

### 7. Real-time Conversation Monitoring

#### Live Dashboard Events
```bash
# Subscribe to conversation events
ksi send conversation:subscribe --agent-id agent_123 --events ["message", "context_change", "topic_shift"]

# Real-time quality monitoring
ksi send conversation:monitor_quality --agent-id agent_123 --alert-on ["coherence < 0.7", "loop_detected"]
```

### 8. Conversation Recovery & Resilience

#### Automatic Recovery
- Checkpoint conversations at key moments
- Restore from system crashes
- Handle network interruptions gracefully

```bash
# Manual recovery
ksi send agent:recover_conversation --agent-id agent_123 --from-checkpoint "auto_save_123"

# Set auto-recovery policy
ksi send agent:set_recovery_policy --agent-id agent_123 --checkpoint-interval 300 --recovery-strategy "last_stable"
```

## Implementation Priority

### Phase 1 (Next Sprint)
1. ✅ Basic conversation summary (DONE)
2. ✅ Conversation reset/clear functionality (DONE)
3. Basic metrics (token count, duration)

### Phase 2 (Following Sprint)
1. Conversation checkpointing
2. Basic forking (single branch)
3. Context export formats

### Phase 3 (Future)
1. Full branching system
2. Shared context pools
3. Advanced analytics
4. Template system

## Technical Considerations

### Storage Requirements
- Conversation checkpoints: ~10KB per checkpoint
- Metrics data: ~1KB per conversation per hour
- Templates: ~5-50KB depending on length

### Performance Impact
- Summary generation: <100ms for typical conversation
- Checkpoint creation: <200ms
- Fork operation: <500ms

### Integration Points
- State system for persistence
- Context manager for reference resolution
- Event system for cross-module communication
- Monitoring system for analytics

## Related Work
- Context Reference Architecture: Provides efficient storage
- Agent Service: Hosts conversation management endpoints
- Completion Service: Manages underlying conversation tracking

---

This roadmap will evolve as we learn more about conversation patterns and agent collaboration needs.