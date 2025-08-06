# KSI Web UI _ksi_context Refactoring Plan

## Overview

This document outlines the systematic refactoring of `ksi_web_ui` to migrate from the old flat metadata pattern to the new `_ksi_context` structure introduced in the Event Context Simplification (BREAKING CHANGE).

**Status**: Planning Phase  
**Target**: ksi_web_ui/ksi-visualizer.js  
**Impact**: Visual display of event metadata, agent relationships, and event routing

## Background

The KSI system has migrated to a new event metadata structure where all system metadata fields are packaged within a single `_ksi_context` object instead of being spread as flat fields. The web UI currently expects the old pattern and needs to be updated.

### Old Pattern (Flat Fields)
```javascript
{
  event_name: "agent:spawn",
  _event_id: "evt_123",
  _correlation_id: "corr_456", 
  _agent_id: "agent_789",
  _client_id: "ksi-cli",
  data: { ... }
}
```

### New Pattern (_ksi_context)
```javascript
{
  timestamp: 1753156038.988,
  event_name: "agent:spawn",
  data: {
    // Business data
    ...,
    _ksi_context: {
      _event_id: "evt_123",
      _event_timestamp: 1753156038.988,
      _correlation_id: "corr_456",
      _parent_event_id: "evt_parent",
      _root_event_id: "evt_root",
      _event_depth: 1,
      _agent_id: "agent_789",
      _client_id: "ksi-cli"
    }
  }
}
```

## Current Usage Analysis

The web UI currently accesses metadata fields in these locations:

### 1. Event Processing & Display
- **File**: `ksi-visualizer.js`
- **Lines**: 416, 469-470, 542-545, 583
- **Usage**: Direct access to `data._agent_id`, `data._client_id`, `data._event_id`, `data._correlation_id`

### 2. Agent Hierarchy Tracking
- **Lines**: 598-599, 615-617, 639-640, 657-660
- **Usage**: Accessing `parent_agent_id` for building agent relationships

### 3. Event Routing Animation
- **Lines**: 731-734
- **Usage**: Using `_agent_id` and `_client_id` for routing visualization

### 4. Orchestration Management
- **Lines**: 976-977, 1084-1085, 1246, 1444-1446, 1461-1462, 1468-1482
- **Usage**: Tracking `orchestrator_agent_id` and agent relationships

## Refactoring Approach

### Phase 1: Create Metadata Accessor Function

Create a utility function to handle both old and new patterns during transition:

```javascript
/**
 * Extract metadata from event data, supporting both old flat pattern and new _ksi_context
 * @param {Object} data - Event data
 * @returns {Object} Normalized metadata object
 */
function extractMetadata(data) {
    // Check if new pattern (_ksi_context in data.data)
    if (data.data && data.data._ksi_context) {
        return {
            event_id: data.data._ksi_context._event_id,
            correlation_id: data.data._ksi_context._correlation_id,
            agent_id: data.data._ksi_context._agent_id,
            client_id: data.data._ksi_context._client_id,
            parent_event_id: data.data._ksi_context._parent_event_id,
            root_event_id: data.data._ksi_context._root_event_id,
            event_depth: data.data._ksi_context._event_depth,
            timestamp: data.timestamp || data.data._ksi_context._event_timestamp
        };
    }
    
    // Old pattern - flat fields
    return {
        event_id: data._event_id || data.event_id,
        correlation_id: data._correlation_id || data.correlation_id,
        agent_id: data._agent_id,
        client_id: data._client_id,
        parent_event_id: data._parent_event_id || data.parent_event_id,
        root_event_id: data._root_event_id || data.root_event_id,
        event_depth: data._event_depth || data.event_depth,
        timestamp: data.timestamp || data._event_timestamp
    };
}
```

### Phase 2: Update Event Handlers

Update all event processing locations to use the accessor function:

#### 2.1 Update processEvent() method
```javascript
// OLD
const originatorId = data._agent_id;

// NEW  
const metadata = extractMetadata(data);
const originatorId = metadata.agent_id;
```

#### 2.2 Update addEventToLog() method
```javascript
// OLD
const agentId = data._agent_id;
const clientId = data._client_id;

// NEW
const metadata = extractMetadata(data);
const agentId = metadata.agent_id;
const clientId = metadata.client_id;
```

#### 2.3 Update formatEventDetails() method
```javascript
// OLD
if (data._agent_id) lines.push(`Agent ID: ${data._agent_id}`);
if (data._client_id) lines.push(`Client ID: ${data._client_id}`);
if (data._event_id) lines.push(`Event ID: ${data._event_id}`);
if (data._correlation_id) lines.push(`Correlation: ${data._correlation_id}`);

// NEW
const metadata = extractMetadata(data);
if (metadata.agent_id) lines.push(`Agent ID: ${metadata.agent_id}`);
if (metadata.client_id) lines.push(`Client ID: ${metadata.client_id}`);
if (metadata.event_id) lines.push(`Event ID: ${metadata.event_id}`);
if (metadata.correlation_id) lines.push(`Correlation: ${metadata.correlation_id}`);
```

### Phase 3: Update Relationship Tracking

For agent relationships and orchestration tracking, we need to handle both metadata sources:

```javascript
// Extract business data separately from metadata
function extractBusinessData(data) {
    return data.data || data;
}

// Update agent hierarchy tracking
updateAgentHierarchy(data) {
    const metadata = extractMetadata(data);
    const businessData = extractBusinessData(data);
    
    const agentId = metadata.agent_id;
    if (!agentId) return;
    
    // Look for parent relationships in both places
    const parentAgentId = businessData.parent_agent_id || 
                         businessData.orchestrator_agent_id ||
                         metadata.parent_event_id;
    
    if (parentAgentId && parentAgentId !== agentId) {
        this.createHierarchicalEdge(parentAgentId, agentId);
    }
}
```

### Phase 4: Update Event Routing

Update event routing animation to use new metadata:

```javascript
animateEventRouting(data, eventName) {
    const metadata = extractMetadata(data);
    const businessData = extractBusinessData(data);
    
    const fromAgent = metadata.agent_id;
    const toClient = metadata.client_id;
    const orchestrationId = businessData.orchestration_id;
    const parentAgentId = businessData.parent_agent_id;
    
    // Continue with animation logic...
}
```

### Phase 5: Testing Strategy

1. **Dual Pattern Support Testing**
   - Test with old events (flat metadata)
   - Test with new events (_ksi_context)
   - Verify both display correctly

2. **Event Flow Testing**
   - Agent spawn visualization
   - Parent-child relationships
   - Orchestration feedback loops
   - Event routing animations

3. **Migration Testing**
   - Connect to daemon with BREAKING CHANGE
   - Verify all visualizations work
   - Check event log displays metadata correctly

## Implementation Steps

1. **Week 1: Preparation**
   - [ ] Add extractMetadata() utility function
   - [ ] Add extractBusinessData() utility function
   - [ ] Create test harness with sample events (both patterns)

2. **Week 2: Core Updates**
   - [ ] Update processEvent() method
   - [ ] Update addEventToLog() method
   - [ ] Update formatEventDetails() method
   - [ ] Update all direct metadata access points

3. **Week 3: Relationship Updates**
   - [ ] Update agent hierarchy tracking
   - [ ] Update orchestration management
   - [ ] Update event routing logic
   - [ ] Update graph edge creation

4. **Week 4: Testing & Cleanup**
   - [ ] Test with live KSI daemon
   - [ ] Verify all visualizations
   - [ ] Remove dual-pattern support (make it BREAKING)
   - [ ] Update documentation

## Risks & Mitigations

### Risk 1: Mixed Event Patterns
**Issue**: During transition, the system may receive both old and new event patterns.  
**Mitigation**: The extractMetadata() function handles both patterns transparently.

### Risk 2: Missing Metadata
**Issue**: Some metadata fields may not be present in all events.  
**Mitigation**: Use defensive programming with null checks and default values.

### Risk 3: Performance Impact
**Issue**: Additional object traversal for metadata extraction.  
**Mitigation**: Minimal impact as it's just property access. Can optimize if needed.

## Success Criteria

- [ ] Web UI correctly displays all event metadata
- [ ] Agent relationships visualized correctly
- [ ] Event routing animations work properly
- [ ] No console errors when processing events
- [ ] Works with both WebSocket and monitor events
- [ ] Event log shows all metadata fields

## Future Considerations

Once the migration is complete and stable:

1. **Remove Dual Pattern Support**: After all systems migrate, remove support for old pattern
2. **Optimize Metadata Access**: Consider caching extracted metadata per event
3. **Enhanced Visualizations**: Use new metadata fields like _event_depth for better hierarchy display
4. **Event Genealogy**: Visualize full event chains using _parent_event_id and _root_event_id

## Notes

- The refactoring maintains backward compatibility initially
- Final phase removes old pattern support (BREAKING CHANGE)
- All changes are in ksi-visualizer.js, no backend changes needed
- HTML and CSS remain unchanged