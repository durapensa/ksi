/**
 * KSI System Visualizer
 * Real-time visualization of KSI agent ecosystem using Cytoscape.js
 */

// Register layout extensions if available
if (typeof cytoscapeCola !== 'undefined') {
    cytoscape.use(cytoscapeCola);
}
if (typeof cytoscapeDagre !== 'undefined') {
    cytoscape.use(cytoscapeDagre);
}

class KSIVisualizer {
    constructor() {
        this.ws = null;
        this.reconnectTimeout = null;
        this.eventLog = document.getElementById('event-log');
        this.statusElement = document.getElementById('connection-status');
        this.maxEventLogEntries = 1000;
        this.showAllEvents = true; // Show all events by default
        
        // Generate unique client ID for this browser session
        this.clientId = this.generateClientId();
        
        // Initialize Cytoscape instances
        this.initializeGraphs();
        
        // Event handlers map
        this.eventHandlers = {
            'agent:spawn': this.handleAgentSpawnRequest.bind(this),
            'agent:spawned': this.handleAgentSpawn.bind(this),
            'agent:spawn_from_component': this.handleAgentSpawnRequest.bind(this),
            'agent:list': this.handleAgentList.bind(this),
            'agent:terminate': this.handleAgentTerminate.bind(this),
            'agent:terminated': this.handleAgentTerminate.bind(this),
            'state:entity:create': this.handleEntityCreate.bind(this),
            'completion:result': this.handleCompletion.bind(this),
            'completion:async': this.handleCompletionRequest.bind(this),
            'orchestration:message': this.handleMessage.bind(this),
            'orchestration:started': this.handleOrchestrationStarted.bind(this),
            'orchestration:completed': this.handleOrchestrationCompleted.bind(this),
            'state:entity:create': this.handleEntityCreated.bind(this),
            'state:entity:created': this.handleEntityCreated.bind(this),
            'state:entity:delete': this.handleEntityDeleted.bind(this),
            'state:entity:deleted': this.handleEntityDeleted.bind(this),
            'state:entity:query': this.handleStateEntityQuery.bind(this),
            'state:relationship:create': this.handleRelationshipCreated.bind(this),
            'state:relationship:created': this.handleRelationshipCreated.bind(this),
            'transport:connected': this.handleTransportConnected.bind(this),
            'bridge:ksi_disconnected': this.handleKSIDisconnected.bind(this),
            'bridge:shutdown': this.handleBridgeShutdown.bind(this),
            'monitor:subscribe': this.handleSubscriptionResponse.bind(this)
        };
        
        // Track KSI daemon connection state
        this.ksiConnected = false;
        
        // Track agents and their relationships
        this.agents = new Map();
        this.activeCompletions = new Map();
        
        // Track recent agent spawn requests (for matching with state:entity:create)
        this.recentSpawnRequests = new Map(); // agent_id -> spawn_data
        
        // Track which entities we've already added to avoid duplicates
        this.addedStateEntities = new Set();
        
        // Track agent-state relationships  
        this.agentStateMap = new Map(); // agent_id -> Set of state_entity_ids
        this.stateAgentMap = new Map(); // state_entity_id -> agent_id (creator)
        
        // Track subscription state
        this.subscribed = false;
        
        // Connect to WebSocket
        this.connect();
        
        // Add periodic connection health check
        this.startHealthCheck();
        
        // Initialize draggable dividers
        this.initializeDividers();
    }
    
    generateClientId() {
        // Generate UUID-like client ID for this browser session
        return 'ksi-viz-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
    }
    
    sendSubscriptionRequest() {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            console.warn('❌ Cannot subscribe: WebSocket not connected');
            console.warn('WebSocket state:', this.ws ? this.ws.readyState : 'null');
            return;
        }
        
        const subscribeMsg = {
            event: "monitor:subscribe",
            data: {
                client_id: this.clientId,
                event_patterns: ["*"]  // Subscribe to all events
            }
        };
        
        console.log('📤 Sending subscription request:', subscribeMsg);
        this.ws.send(JSON.stringify(subscribeMsg));
        // Don't set subscribed=true until we get confirmation
        console.log('⏳ Waiting for subscription confirmation...');
    }
    
    requestAgentList() {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            console.warn('Cannot request agent list: WebSocket not connected');
            return;
        }
        
        const listMsg = {
            event: "agent:list",
            data: {}
        };
        
        console.log('Requesting current agent list...');
        this.ws.send(JSON.stringify(listMsg));
    }
    
    requestStateEntities() {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            console.warn('Cannot request state entities: WebSocket not connected');
            return;
        }
        
        const queryMsg = {
            event: "state:entity:query",
            data: {
                limit: 100  // Get first 100 non-agent entities
            }
        };
        
        console.log('Requesting current state entities...');
        this.ws.send(JSON.stringify(queryMsg));
    }
    
    initializeGraphs() {
        // Agent ecosystem graph
        this.agentGraph = cytoscape({
            container: document.getElementById('agent-graph'),
            style: [
                {
                    selector: 'node',
                    style: {
                        'label': 'data(label)',
                        'text-valign': 'center',
                        'text-halign': 'center',
                        'background-color': '#666',
                        'color': '#fff',
                        'text-outline-width': 2,
                        'text-outline-color': '#666',
                        'font-size': '10px',
                        'width': 80,
                        'height': 60,
                        'text-wrap': 'wrap',
                        'text-max-width': '100px',
                        'padding': 5
                    }
                },
                {
                    selector: 'node[type="agent"]',
                    style: {
                        'background-color': '#4CAF50',
                        'shape': 'ellipse'
                    }
                },
                {
                    selector: 'node[type="orchestration"]',
                    style: {
                        'background-color': '#FF9800',
                        'shape': 'round-rectangle',
                        'width': 100,
                        'height': 60
                    }
                },
                {
                    selector: 'node.completing',
                    style: {
                        'background-color': '#2196F3',
                        'border-width': 3,
                        'border-color': '#1976D2'
                    }
                },
                {
                    selector: 'edge',
                    style: {
                        'width': 3,
                        'target-arrow-shape': 'triangle',
                        'line-color': '#888',
                        'target-arrow-color': '#888',
                        'curve-style': 'bezier',
                        'arrow-scale': 1.2,
                        'opacity': 0.8
                    }
                },
                {
                    selector: 'edge[type="spawned"]',
                    style: {
                        'line-color': '#4CAF50',
                        'target-arrow-color': '#4CAF50',
                        'width': 3,
                        'target-arrow-shape': 'triangle',
                        'arrow-scale': 1.5,
                        'label': 'spawned'
                    }
                },
                {
                    selector: 'edge[type="event_route"]',
                    style: {
                        'line-color': '#2196F3',
                        'target-arrow-color': '#2196F3',
                        'line-style': 'dashed',
                        'width': 2,
                        'target-arrow-shape': 'chevron',
                        'label': 'data(subscription_level)'
                    }
                },
                {
                    selector: 'edge[type="error_route"]',
                    style: {
                        'line-color': '#F44336',
                        'target-arrow-color': '#F44336',
                        'line-style': 'dashed',
                        'width': 4,
                        'target-arrow-shape': 'triangle-tee',
                        'label': 'error'
                    }
                },
                {
                    selector: 'edge[type="message"]',
                    style: {
                        'line-color': '#FF9800',
                        'target-arrow-color': '#FF9800',
                        'line-style': 'dotted',
                        'width': 2,
                        'target-arrow-shape': 'circle',
                        'source-arrow-shape': 'circle',
                        'label': 'message'
                    }
                },
                {
                    selector: 'edge[type="orchestrator_feedback"]',
                    style: {
                        'line-color': '#9C27B0',
                        'target-arrow-color': '#9C27B0',
                        'width': 3,
                        'target-arrow-shape': 'diamond',
                        'label': 'orchestrator'
                    }
                },
                {
                    selector: 'edge.active-flow',
                    style: {
                        'line-color': '#FFD700',
                        'target-arrow-color': '#FFD700',
                        'width': 5,
                        'z-index': 999
                    }
                }
            ],
            layout: {
                name: 'grid',  // Start with simple grid layout
                animate: true
            }
        });
        
        // Add agent hover → pulsate state entities
        this.agentGraph.on('mouseover', 'node[type="agent"]', (event) => {
            const agentId = event.target.id();
            console.log(`🖱️ Agent hover: ${agentId}`);
            this.pulsateAgentStateEntities(agentId);
            this.showAgentTooltip(event.target);
        });
        
        this.agentGraph.on('mouseout', 'node[type="agent"]', (event) => {
            this.hideAgentTooltip();
        });
        
        // Add orchestration hover
        this.agentGraph.on('mouseover', 'node[type="orchestration"]', (event) => {
            this.showOrchestrationTooltip(event.target);
        });
        
        this.agentGraph.on('mouseout', 'node[type="orchestration"]', (event) => {
            this.hideAgentTooltip();
        });
        
        // State system graph
        this.stateGraph = cytoscape({
            container: document.getElementById('state-graph'),
            style: [
                {
                    selector: 'node',
                    style: {
                        'label': 'data(label)',
                        'text-valign': 'center',
                        'text-halign': 'center',
                        'background-color': '#9C27B0',
                        'color': '#fff',
                        'text-outline-width': 2,
                        'text-outline-color': '#9C27B0',
                        'font-size': '10px'
                    }
                },
                {
                    selector: 'edge',
                    style: {
                        'width': 2,
                        'target-arrow-shape': 'triangle',
                        'line-color': '#666',
                        'target-arrow-color': '#666',
                        'curve-style': 'bezier'
                    }
                }
            ],
            layout: {
                name: 'circle',  // Start with simple circle layout
                animate: true
            }
        });
    }
    
    connect() {
        this.updateStatus('connecting');
        
        try {
            this.ws = new WebSocket('ws://localhost:8765');
            
            this.ws.onopen = () => {
                this.updateStatus('connected');
                console.log('✅ Connected to KSI WebSocket bridge');
                console.log('WebSocket state:', this.ws.readyState);
                if (this.reconnectTimeout) {
                    clearTimeout(this.reconnectTimeout);
                    this.reconnectTimeout = null;
                }
            };
            
            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    // Log all incoming events for debugging
                    console.log('WS received:', data.event || data.event_name || 'unknown', data);
                    this.handleEvent(data);
                } catch (e) {
                    console.error('Failed to parse event:', e, event.data);
                }
            };
            
            this.ws.onclose = () => {
                this.updateStatus('disconnected');
                console.log('Disconnected from KSI WebSocket bridge');
                this.scheduleReconnect();
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
            
        } catch (e) {
            console.error('Failed to create WebSocket:', e);
            this.scheduleReconnect();
        }
    }
    
    scheduleReconnect() {
        if (!this.reconnectTimeout) {
            this.reconnectTimeout = setTimeout(() => {
                console.log('Attempting to reconnect...');
                this.connect();
            }, 5000);
        }
    }
    
    startHealthCheck() {
        // Check connection health every 10 seconds
        setInterval(() => {
            if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
                console.log('Health check: Connection is down, attempting reconnect...');
                this.updateStatus('disconnected');
                this.scheduleReconnect();
            }
        }, 10000);
    }
    
    updateStatus(status, message) {
        this.statusElement.className = `status-${status}`;
        this.statusElement.textContent = message || status.charAt(0).toUpperCase() + status.slice(1);
    }
    
    handleEvent(data) {
        // Handle both 'event' and 'event_name' fields for compatibility
        const eventName = data.event || data.event_name;
        
        // Update data structure to normalize
        if (!data.event && data.event_name) {
            data.event = data.event_name;
        }
        
        // Log event with enhanced metadata context
        this.logEventWithMetadata(data);
        
        // Minimal debug logging for important events only
        if (eventName && (eventName.startsWith('agent:') || eventName.startsWith('error:') || eventName === 'bridge:ksi_disconnected')) {
            console.log(`[${eventName}]`, data.data);
        }
        
        // Visual feedback for agent-originated events using daemon metadata
        const originatorId = data._agent_id;
        if (originatorId && !eventName.startsWith('observe:')) {
            this.showAgentActivity(originatorId);
        }
        
        // Animate event flow for routing
        this.animateEventRouting(data, eventName);
        
        // Update agent hierarchy from daemon metadata
        this.updateAgentHierarchy(data);
        
        // Route to specific handler
        const handler = this.eventHandlers[eventName];
        if (handler) {
            try {
                handler(data.data || {}, data); // Pass full event for metadata access
            } catch (e) {
                console.error(`Error handling ${eventName}:`, e, data);
            }
        } else if (eventName) {
            // Check for important unhandled events
            if (eventName.includes('state:entity') || eventName.includes('agent:') || eventName.includes('orchestration:')) {
                console.warn(`⚠️ No handler for important event: ${eventName}`, data);
            } else {
                console.debug(`No handler for event: ${eventName}`);
            }
        }
    }
    
    logEventWithMetadata(data) {
        // Enhanced event logging with daemon metadata awareness
        const entry = document.createElement('div');
        entry.className = 'event-entry';
        
        const eventName = data.event || data.event_name;
        
        // Convert Unix timestamp (seconds) to milliseconds for JavaScript Date
        let timestampMs = Date.now();
        if (data._event_timestamp) {
            timestampMs = data._event_timestamp * 1000;
        } else if (data.timestamp) {
            timestampMs = data.timestamp * 1000;
        }
        
        const timestamp = new Date(timestampMs).toLocaleTimeString('en-US', {
            timeZone: 'America/New_York',
            hour12: true,
            hour: 'numeric',
            minute: '2-digit',
            second: '2-digit'
        });
        
        // Extract metadata for enriched display
        const agentId = data._agent_id;
        const clientId = data._client_id;
        const orchestrationId = data.data?.orchestration_id;
        const depth = data.data?.orchestration_depth;
        
        // Create rich HTML display without emojis
        entry.innerHTML = `
            <span class="event-time">[${timestamp} EST]</span>
            <span class="event-type">${eventName}</span>
        `;
        
        // Add metadata badges
        if (agentId) {
            entry.innerHTML += ` <span class="event-badge agent-badge">agent:${agentId.substring(0, 8)}</span>`;
        }
        
        if (clientId && clientId !== this.clientId) {
            entry.innerHTML += ` <span class="event-badge client-badge">client:${clientId.substring(0, 8)}</span>`;
        }
        
        if (orchestrationId) {
            entry.innerHTML += ` <span class="event-badge orch-badge">orch:${orchestrationId.substring(0, 8)}`;
            if (depth !== undefined) {
                entry.innerHTML += `:L${depth}`;
            }
            entry.innerHTML += `</span>`;
        }
        
        // Add data preview if available
        if (data.data && Object.keys(data.data).length > 0) {
            const dataPreview = this.createDataPreview(data.data);
            if (dataPreview) {
                entry.innerHTML += ` <span class="event-data-preview">${dataPreview}</span>`;
            }
        }
        
        // Enhanced color coding based on event type
        if (eventName?.startsWith('agent:')) {
            entry.classList.add('event-agent');
        } else if (eventName?.startsWith('orchestration:')) {
            entry.classList.add('event-orchestration');
        } else if (eventName?.startsWith('completion:')) {
            entry.classList.add('event-completion');
        } else if (eventName?.startsWith('state:')) {
            entry.classList.add('event-state');
        } else if (eventName?.startsWith('monitor:')) {
            entry.classList.add('event-monitor');
        } else if (eventName?.startsWith('bridge:')) {
            entry.classList.add('event-bridge');
        } else if (agentId) {
            entry.classList.add('agent-originated');
        }
        
        // Add tooltip with full metadata
        const tooltip = this.buildMetadataTooltip(data);
        entry.title = tooltip;
        
        // Add to log
        this.eventLog.insertBefore(entry, this.eventLog.firstChild);
        
        // Limit log size
        while (this.eventLog.children.length > this.maxEventLogEntries) {
            this.eventLog.removeChild(this.eventLog.lastChild);
        }
    }
    
    buildMetadataTooltip(data) {
        // Build comprehensive metadata tooltip
        const lines = [];
        
        lines.push(`Event: ${data.event || data.event_name}`);
        
        // Daemon metadata
        if (data._agent_id) lines.push(`Agent ID: ${data._agent_id}`);
        if (data._client_id) lines.push(`Client ID: ${data._client_id}`);
        if (data._event_id) lines.push(`Event ID: ${data._event_id}`);
        if (data._correlation_id) lines.push(`Correlation: ${data._correlation_id}`);
        
        // Hierarchical metadata from data
        if (data.data) {
            if (data.data.orchestration_id) lines.push(`Orchestration: ${data.data.orchestration_id}`);
            if (data.data.orchestration_depth !== undefined) lines.push(`Depth: ${data.data.orchestration_depth}`);
            if (data.data.parent_agent_id) lines.push(`Parent: ${data.data.parent_agent_id}`);
            if (data.data.event_subscription_level) lines.push(`Sub Level: ${data.data.event_subscription_level}`);
        }
        
        return lines.join('\n');
    }
    
    createDataPreview(data) {
        // Create a concise preview of event data
        const previewParts = [];
        
        // Show key fields in a readable format
        if (data.agent_id) previewParts.push(`agent:${data.agent_id.substring(0, 8)}`);
        if (data.status) previewParts.push(`status:${data.status}`);
        if (data.message) previewParts.push(`"${data.message.substring(0, 30)}..."`);
        if (data.count !== undefined) previewParts.push(`count:${data.count}`);
        if (data.pattern) previewParts.push(`pattern:${data.pattern}`);
        if (data.component) previewParts.push(`component:${data.component.split('/').pop()}`);
        if (data.profile) previewParts.push(`profile:${data.profile}`);
        if (data.error) previewParts.push(`error:${data.error.substring(0, 30)}`);
        if (data.result) previewParts.push(`result:${JSON.stringify(data.result).substring(0, 30)}...`);
        
        // Show array lengths
        if (data.agents && Array.isArray(data.agents)) previewParts.push(`agents:[${data.agents.length}]`);
        if (data.entities && Array.isArray(data.entities)) previewParts.push(`entities:[${data.entities.length}]`);
        if (data.patterns && Array.isArray(data.patterns)) previewParts.push(`patterns:[${data.patterns.join(',')}]`);
        
        return previewParts.length > 0 ? `{${previewParts.join(', ')}}` : null;
    }
    
    updateAgentHierarchy(data) {
        // Update agent hierarchy visualization based on daemon metadata
        const agentId = data._agent_id;
        if (!agentId) return;
        
        const eventData = data.data || {};
        
        // Update agent metadata if it exists in graph
        const agentNode = this.agentGraph.getElementById(agentId);
        if (agentNode.length > 0) {
            const currentData = agentNode.data();
            
            // Enhance metadata with daemon information
            const enhancedMetadata = {
                ...currentData.metadata,
                orchestration_id: eventData.orchestration_id,
                orchestration_depth: eventData.orchestration_depth,
                parent_agent_id: eventData.parent_agent_id,
                event_subscription_level: eventData.event_subscription_level,
                error_subscription_level: eventData.error_subscription_level,
                last_activity: data._event_timestamp || Date.now()
            };
            
            agentNode.data('metadata', enhancedMetadata);
            
            // Update visual styling based on hierarchy depth
            if (eventData.orchestration_depth !== undefined) {
                agentNode.removeClass('depth-0 depth-1 depth-2 depth-3 depth-4+');
                const depthClass = eventData.orchestration_depth > 4 ? 'depth-4+' : `depth-${eventData.orchestration_depth}`;
                agentNode.addClass(depthClass);
            }
        }
        
        // Create orchestration relationships if metadata indicates hierarchy
        if (eventData.orchestration_id && eventData.parent_agent_id && eventData.parent_agent_id !== agentId) {
            this.createOrchestrationEdge(eventData.parent_agent_id, agentId, eventData.orchestration_id);
        }
    }
    
    createOrchestrationEdge(parentId, childId, orchestrationId) {
        // Create edge representing orchestration hierarchy
        const edgeId = `${parentId}-orch-${childId}`;
        
        if (!this.agentGraph.getElementById(edgeId).length) {
            this.agentGraph.add({
                data: {
                    id: edgeId,
                    source: parentId,
                    target: childId,
                    type: 'orchestration',
                    orchestration_id: orchestrationId
                }
            });
        }
    }
    
    createEventRoutingEdges(agentId, data) {
        // Create event routing edges based on subscription levels
        if (data.parent_agent_id && data.event_subscription_level !== undefined) {
            const edgeId = `${agentId}-event_route-${data.parent_agent_id}`;
            
            if (!this.agentGraph.getElementById(edgeId).length) {
                this.agentGraph.add({
                    data: {
                        id: edgeId,
                        source: agentId,
                        target: data.parent_agent_id,
                        type: 'event_route',
                        subscription_level: `L${data.event_subscription_level}`,
                        orchestration_id: data.orchestration_id
                    }
                });
            }
        }
        
        // Create error routing edge if error subscription level is different
        if (data.parent_agent_id && data.error_subscription_level !== undefined && 
            data.error_subscription_level !== data.event_subscription_level) {
            const errorEdgeId = `${agentId}-error_route-${data.parent_agent_id}`;
            
            if (!this.agentGraph.getElementById(errorEdgeId).length) {
                this.agentGraph.add({
                    data: {
                        id: errorEdgeId,
                        source: agentId,
                        target: data.parent_agent_id,
                        type: 'error_route',
                        subscription_level: `E${data.error_subscription_level}`,
                        orchestration_id: data.orchestration_id
                    }
                });
            }
        }
    }
    
    createMessageEdge(fromAgent, toAgent, messageType) {
        // Create bidirectional message edge
        const edgeId = `${fromAgent}-message-${toAgent}`;
        const reverseEdgeId = `${toAgent}-message-${fromAgent}`;
        
        // Check if edge already exists in either direction
        if (!this.agentGraph.getElementById(edgeId).length && 
            !this.agentGraph.getElementById(reverseEdgeId).length) {
            this.agentGraph.add({
                data: {
                    id: edgeId,
                    source: fromAgent,
                    target: toAgent,
                    type: 'message',
                    messageType: messageType,
                    timestamp: Date.now()
                }
            });
        }
    }
    
    createOrchestratorFeedbackEdge(agentId, orchestratorId) {
        // Create orchestrator feedback edge
        const edgeId = `${agentId}-orchestrator_feedback-${orchestratorId}`;
        
        if (!this.agentGraph.getElementById(edgeId).length) {
            this.agentGraph.add({
                data: {
                    id: edgeId,
                    source: agentId,
                    target: orchestratorId,
                    type: 'orchestrator_feedback',
                    timestamp: Date.now()
                }
            });
        }
    }
    
    animateEventFlow(fromNode, toNode, eventType) {
        // Animate event flow along edge
        const edge = this.agentGraph.edges(`[source="${fromNode}"][target="${toNode}"]`).first();
        
        if (edge) {
            // Add active flow class temporarily
            edge.addClass('active-flow');
            
            // Remove after animation
            setTimeout(() => {
                edge.removeClass('active-flow');
            }, 1000);
        }
    }
    
    animateEventRouting(data, eventName) {
        // Animate event flows based on routing metadata
        const fromAgent = data._agent_id;
        const toClient = data._client_id;
        const orchestrationId = data.data?.orchestration_id;
        const parentAgentId = data.data?.parent_agent_id;
        
        // Animate error propagation
        if (eventName && eventName.includes('error') && fromAgent && parentAgentId) {
            this.animateEventFlow(fromAgent, parentAgentId, 'error');
        }
        
        // Animate event routing to orchestrator
        if (fromAgent && toClient === 'claude-code') {
            // This event was routed to Claude Code as orchestrator
            this.animateEventFlow(fromAgent, 'claude-code', 'orchestrator_feedback');
        }
        
        // Animate orchestration events
        if (orchestrationId && fromAgent) {
            this.animateEventFlow(fromAgent, orchestrationId, 'event_route');
        }
        
        // Animate completion events
        if (eventName === 'completion:async' && fromAgent) {
            // Show completion request animation
            const node = this.agentGraph.getElementById(fromAgent);
            if (node) {
                node.addClass('completing');
                setTimeout(() => {
                    node.removeClass('completing');
                }, 1500);
            }
        }
        
        // Animate agent spawn flow
        if (eventName === 'agent:spawn' && parentAgentId && data.data?.agent_id) {
            this.animateEventFlow(parentAgentId, data.data.agent_id, 'spawned');
        }
    }

    buildAgentLabel(agentId, metadata) {
        // Build intelligent agent labels using available metadata
        const shortId = agentId.substring(0, 12);
        
        if (metadata.inferred) {
            return `${shortId}\n(inferred)`;
        }
        
        // Use component info if available
        if (metadata.component) {
            const componentName = metadata.component.split('/').pop() || 'unknown';
            return `${shortId}\n(${componentName})`;
        }
        
        // Use profile info as fallback
        if (metadata.profile) {
            return `${shortId}\n(${metadata.profile})`;
        }
        
        // Show orchestration depth if available
        if (metadata.orchestration_depth !== undefined) {
            return `${shortId}\nL${metadata.orchestration_depth}`;
        }
        
        return `${shortId}\n(agent)`;
    }
    
    logEvent(data) {
        // Legacy method - delegate to enhanced version
        this.logEventWithMetadata(data);
    }
    
    // Event Handlers
    
    handleTransportConnected(data) {
        console.log('🚀 Transport connected:', data.message);
        console.log('🆔 Client ID:', data.client_id);
        console.log('🔌 Transport type:', data.transport);
        
        this.ksiConnected = true;
        this.updateStatus('connected', 'Connected (Native WebSocket)');
        
        // Subscribe to events when transport connection is established
        console.log('📋 Step 1: Subscribing to events...');
        this.sendSubscriptionRequest();
        
        // Request current agent list to populate initial state
        console.log('📋 Step 2: Requesting agent list...');
        this.requestAgentList();
        
        // Request current state entities to populate state graph
        console.log('📋 Step 3: Requesting state entities...');
        this.requestStateEntities();
    }
    
    handleKSIDisconnected(data) {
        console.log('KSI daemon disconnected:', data.message);
        this.ksiConnected = false;
        this.updateStatus('connected', 'Connected (KSI Offline)');
        
        // Maintain all visualization state - daemon will restore on reconnect
    }
    
    handleBridgeShutdown(data) {
        console.log('Bridge shutdown notification:', data.message);
        this.updateStatus('disconnected', 'Bridge Shutting Down');
        
        // Close our WebSocket connection immediately to trigger reconnection
        if (this.ws) {
            this.ws.close();
        }
    }
    
    handleSubscriptionResponse(data) {
        console.log('Subscription response received:', data);
        
        if (data.status === 'subscribed') {
            console.log(`Successfully subscribed to patterns: ${data.patterns?.join(', ')}`);
            console.log(`Using client ID: ${data.client_id}`);
            this.subscribed = true;
        } else if (data.error) {
            console.error('Subscription failed:', data.error);
            this.subscribed = false;
        }
    }
    
    handleAgentSpawnRequest(data, eventMetadata) {
        // Track spawn requests so we can match them with state:entity:create events
        console.log('🚀 Agent spawn requested:', data, 'eventMetadata:', eventMetadata);
        
        // Generate expected agent ID pattern or use provided one
        const expectedAgentId = data.agent_id || `agent_${Math.random().toString(36).substr(2, 8)}`;
        
        // Store spawn request with timestamp for matching
        this.recentSpawnRequests.set(expectedAgentId, {
            ...data,
            _spawn_timestamp: Date.now(),
            _eventMetadata: eventMetadata
        });
        
        // Clean up old spawn requests (older than 30 seconds)
        const cutoff = Date.now() - 30000;
        for (const [agentId, spawnData] of this.recentSpawnRequests.entries()) {
            if (spawnData._spawn_timestamp < cutoff) {
                this.recentSpawnRequests.delete(agentId);
            }
        }
        
        console.log(`📝 Stored spawn request for ${expectedAgentId}. Total pending: ${this.recentSpawnRequests.size}`);
    }
    
    handleEntityCreate(data, eventMetadata) {
        // Route state:entity:create events to correct visualization
        const entityId = data.id || data.entity_id;
        const entityType = data.type;
        
        console.log('📦 Entity created:', entityId, 'type:', entityType, 'data:', data);
        
        if (entityType === 'agent') {
            // Agent entities → Agent Ecosystem
            console.log(`🤖 Routing agent ${entityId} to Agent Ecosystem`);
            this.handleAgentCreated(data, eventMetadata);
        } else if (entityType === 'orchestration') {
            // Orchestration entities → Agent Ecosystem  
            console.log(`🎭 Routing orchestration ${entityId} to Agent Ecosystem`);
            this.handleOrchestrationEntity(data, eventMetadata);
        } else {
            // Everything else → State System
            console.log(`💾 Routing state entity ${entityId} (type: ${entityType}) to State System`);
            this.handleStateEntityCreated(data, eventMetadata);
        }
    }
    
    handleAgentCreated(data, eventMetadata) {
        const agentId = data.id || data.entity_id;
        if (!agentId) {
            console.warn('Agent created event missing ID:', data);
            return;
        }
        
        console.log('🎯 Agent entity created:', agentId, 'properties:', data.properties);
        
        // Try to match with recent spawn request
        let spawnData = this.recentSpawnRequests.get(agentId);
        if (spawnData) {
            console.log(`✅ Matched agent ${agentId} with spawn request`);
            this.recentSpawnRequests.delete(agentId);
        } else {
            // Check if any spawn request matches by pattern or timing
            console.log(`⚠️ No exact match for agent ${agentId}, checking recent requests...`);
            spawnData = { profile: 'unknown', _spawn_timestamp: Date.now() };
        }
        
        // Extract agent metadata from properties + spawn data
        const properties = data.properties || {};
        const agentData = {
            agent_id: agentId,
            profile: properties.profile || spawnData.profile,
            component: properties.component || spawnData.component,
            parent_agent_id: properties.parent_agent_id || spawnData.parent_agent_id,
            orchestration_id: properties.orchestration_id,
            orchestration_depth: properties.orchestration_depth,
            event_subscription_level: properties.event_subscription_level,
            error_subscription_level: properties.error_subscription_level,
            sandbox_uuid: properties.sandbox_uuid,
            status: properties.status || 'active',
            created_at: Date.now()
        };
        
        // Add to Agent Ecosystem
        this.handleAgentSpawn(agentData, eventMetadata);
        
        console.log(`📊 Agent tracking: ${this.recentSpawnRequests.size} pending spawns, ${this.agents.size} active agents`);
    }
    
    handleAgentSpawn(data, eventMetadata) {
        const agentId = data.agent_id;
        if (!agentId) return;
        
        console.log('🚀 handleAgentSpawn - agentId:', agentId, 'data:', data, 'eventMetadata:', eventMetadata);
        
        // Enhanced metadata from daemon
        const enhancedData = {
            ...data,
            orchestration_id: data.orchestration_id,
            orchestration_depth: data.orchestration_depth,
            parent_agent_id: data.parent_agent_id,
            event_subscription_level: data.event_subscription_level,
            component: data.component,
            _event_source: eventMetadata?._agent_id, // Who triggered this spawn
        };
        
        // Track agent with enhanced metadata
        this.agents.set(agentId, enhancedData);
        
        // Add node to graph with rich metadata
        this.agentGraph.add({
            data: {
                id: agentId,
                label: this.buildAgentLabel(agentId, enhancedData),
                type: 'agent',
                metadata: enhancedData
            }
        });
        
        // Add hierarchical relationships using daemon metadata
        const parentId = data.parent_agent_id || eventMetadata?._agent_id;
        console.log(`🔍 Agent ${agentId} - parent_agent_id: ${data.parent_agent_id}, eventMetadata._agent_id: ${eventMetadata?._agent_id}`);
        
        if (parentId && parentId !== agentId) {
            // Ensure parent exists in graph
            if (!this.agentGraph.getElementById(parentId).length) {
                console.log(`➕ Creating inferred parent agent: ${parentId}`);
                this.agentGraph.add({
                    data: {
                        id: parentId,
                        label: this.buildAgentLabel(parentId, { inferred: true }),
                        type: 'agent',
                        metadata: { inferred: true }
                    }
                });
            }
            
            console.log(`🔗 Creating hierarchical edge from ${parentId} to ${agentId}`);
            
            // Create spawned edge (parent spawned child)
            const edgeId = `${parentId}-spawned-${agentId}`;
            console.log(`🔗 Creating spawned edge: ${edgeId}`);
            
            this.agentGraph.add({
                data: {
                    id: edgeId,
                    source: parentId,
                    target: agentId,
                    type: 'spawned',
                    orchestration_id: data.orchestration_id,
                    timestamp: Date.now()
                }
            });
            
            console.log(`✅ Added edge ${edgeId} to graph`);
            
            // If part of orchestration, also create event routing edges
            if (data.orchestration_id) {
                this.createEventRoutingEdges(agentId, data);
            }
        } else {
            console.log(`ℹ️ Agent ${agentId} has no parent - will appear as standalone node`);
        }
        
        // Apply hierarchical layout with improved spacing
        try {
            this.agentGraph.layout({ 
                name: 'dagre', 
                animate: true,
                padding: 20,
                spacingFactor: 1.8,
                nodeSep: 60,
                rankSep: 120,
                rankDir: 'TB' // Top to bottom for hierarchy
            }).run();
            
            console.log(`✅ Agent graph now has ${this.agentGraph.nodes().length} nodes and ${this.agentGraph.edges().length} edges`);
        } catch (error) {
            console.error('❌ Layout error:', error);
            // Fallback to simple grid layout
            this.agentGraph.layout({ name: 'grid', animate: true }).run();
        }
    }
    
    handleOrchestrationEntity(data, eventMetadata) {
        const orchestrationId = data.id || data.entity_id;
        if (!orchestrationId) {
            console.warn('Orchestration entity missing ID:', data);
            return;
        }
        
        console.log('🎭 Orchestration entity created:', orchestrationId, 'properties:', data.properties);
        
        // Add orchestration node to Agent Ecosystem
        const properties = data.properties || {};
        this.agentGraph.add({
            data: {
                id: orchestrationId,
                label: properties.pattern || orchestrationId.substring(0, 8),
                type: 'orchestration',
                metadata: {
                    ...properties,
                    created_at: Date.now(),
                    entity_type: 'orchestration'
                }
            }
        });
        
        // Run layout
        this.agentGraph.layout({ 
            name: 'dagre', 
            animate: true,
            rankDir: 'TB'
        }).run();
        
        console.log(`✅ Added orchestration ${orchestrationId} to Agent Ecosystem`);
    }
    
    handleStateEntityCreated(data, eventMetadata) {
        const entityId = data.id || data.entity_id;
        if (!entityId) {
            console.warn('State entity missing ID:', data);
            return;
        }
        
        console.log('💾 State entity created:', entityId, 'type:', data.type, 'properties:', data.properties);
        
        // Track which agent created this state entity
        const creatorAgent = eventMetadata?._agent_id;
        if (creatorAgent) {
            // Track agent→state relationship
            if (!this.agentStateMap.has(creatorAgent)) {
                this.agentStateMap.set(creatorAgent, new Set());
            }
            this.agentStateMap.get(creatorAgent).add(entityId);
            this.stateAgentMap.set(entityId, creatorAgent);
            
            console.log(`🔗 Linked state entity ${entityId} to creator agent ${creatorAgent}`);
        }
        
        // Create descriptive label
        let label = entityId.substring(0, 12);
        const properties = data.properties || {};
        
        if (properties.name) {
            label = properties.name.substring(0, 15);
        } else if (data.type && data.type !== 'entity') {
            label = `${data.type}\\n${entityId.substring(0, 10)}`;
        }
        
        // Color code by entity type
        const typeColor = this.getEntityTypeColor(data.type);
        
        // Check if entity already exists
        if (this.addedStateEntities.has(entityId)) {
            console.log(`⚠️ State entity ${entityId} already exists, skipping`);
            return;
        }
        
        // Add to State System graph
        this.stateGraph.add({
            data: {
                id: entityId,
                label: label,
                type: data.type || 'entity',
                metadata: {
                    ...data,
                    properties: properties,
                    creator_agent: creatorAgent,
                    created_at: Date.now()
                }
            }
        });
        
        // Mark as added
        this.addedStateEntities.add(entityId);
        
        // Update styling based on type
        const node = this.stateGraph.getElementById(entityId);
        if (node) {
            node.style('background-color', typeColor);
            
            // Add hover tooltip
            node.on('mouseover', (event) => {
                this.showEntityTooltip(event.target, properties);
            });
            
            node.on('mouseout', (event) => {
                this.hideEntityTooltip();
            });
        }
        
        // Run layout
        this.stateGraph.layout({ 
            name: 'circle', 
            animate: true 
        }).run();
        
        console.log(`✅ Added state entity ${entityId} (type: ${data.type}) to State System`);
    }
    
    getEntityTypeColor(entityType) {
        // Color coding for different entity types
        const colorMap = {
            'analysis': '#2196F3',      // Blue
            'dataset': '#4CAF50',       // Green
            'config': '#FF9800',        // Orange
            'result': '#9C27B0',        // Purple
            'workflow': '#F44336',      // Red
            'document': '#795548',      // Brown
            'log': '#607D8B',           // Blue Grey
            'metric': '#E91E63',        // Pink
            'session': '#3F51B5',       // Indigo
            'task': '#009688',          // Teal
            'default': '#666666'        // Grey
        };
        
        return colorMap[entityType] || colorMap['default'];
    }
    
    showEntityTooltip(node, properties) {
        // Create tooltip showing entity properties
        const tooltip = document.getElementById('entity-tooltip') || this.createTooltip();
        
        // Build property list
        const propEntries = Object.entries(properties).map(([key, value]) => {
            const displayValue = typeof value === 'string' ? value.substring(0, 50) : JSON.stringify(value).substring(0, 50);
            return `<div><strong>${key}:</strong> ${displayValue}</div>`;
        }).join('');
        
        tooltip.innerHTML = `
            <div class="tooltip-header">Entity: ${node.id()}</div>
            <div class="tooltip-type">Type: ${node.data('type')}</div>
            <div class="tooltip-properties">${propEntries}</div>
        `;
        
        // Position tooltip near cursor
        tooltip.style.display = 'block';
        tooltip.style.position = 'fixed';
        tooltip.style.zIndex = '1000';
        tooltip.style.background = '#2a2a2a';
        tooltip.style.color = '#e0e0e0';
        tooltip.style.padding = '10px';
        tooltip.style.borderRadius = '4px';
        tooltip.style.border = '1px solid #555';
        tooltip.style.maxWidth = '300px';
        tooltip.style.fontSize = '12px';
    }
    
    hideEntityTooltip() {
        const tooltip = document.getElementById('entity-tooltip');
        if (tooltip) {
            tooltip.style.display = 'none';
        }
    }
    
    createTooltip() {
        const tooltip = document.createElement('div');
        tooltip.id = 'entity-tooltip';
        tooltip.style.display = 'none';
        document.body.appendChild(tooltip);
        return tooltip;
    }
    
    showAgentTooltip(node) {
        const tooltip = document.getElementById('agent-tooltip') || this.createAgentTooltip();
        const metadata = node.data('metadata') || {};
        
        const agentId = node.id();
        const profile = metadata.profile || 'unknown';
        const status = metadata.status || 'active';
        const created = metadata.created_at ? new Date(metadata.created_at).toLocaleTimeString() : 'unknown';
        
        tooltip.innerHTML = `
            <div class="tooltip-header">Agent: ${agentId}</div>
            <div class="tooltip-type">Profile: ${profile}</div>
            <div class="tooltip-type">Status: ${status}</div>
            <div class="tooltip-type">Created: ${created}</div>
        `;
        
        tooltip.style.display = 'block';
        this.positionTooltip(tooltip);
    }
    
    showOrchestrationTooltip(node) {
        const tooltip = document.getElementById('agent-tooltip') || this.createAgentTooltip();
        const metadata = node.data('metadata') || {};
        
        const orchId = node.id();
        const pattern = metadata.pattern || 'unknown';
        const orchestratorId = metadata.orchestrator_agent_id || 'none';
        
        tooltip.innerHTML = `
            <div class="tooltip-header">Orchestration: ${orchId}</div>
            <div class="tooltip-type">Pattern: ${pattern}</div>
            <div class="tooltip-type">Orchestrator: ${orchestratorId}</div>
        `;
        
        tooltip.style.display = 'block';
        this.positionTooltip(tooltip);
    }
    
    hideAgentTooltip() {
        const tooltip = document.getElementById('agent-tooltip');
        if (tooltip) {
            tooltip.style.display = 'none';
        }
    }
    
    createAgentTooltip() {
        const tooltip = document.createElement('div');
        tooltip.id = 'agent-tooltip';
        tooltip.style.display = 'none';
        tooltip.style.position = 'fixed';
        tooltip.style.zIndex = '1000';
        tooltip.style.background = '#2a2a2a';
        tooltip.style.color = '#e0e0e0';
        tooltip.style.padding = '10px';
        tooltip.style.borderRadius = '4px';
        tooltip.style.border = '1px solid #555';
        tooltip.style.maxWidth = '250px';
        tooltip.style.fontSize = '12px';
        document.body.appendChild(tooltip);
        return tooltip;
    }
    
    positionTooltip(tooltip) {
        // Position tooltip near cursor (simplified)
        tooltip.style.left = '50px';
        tooltip.style.top = '50px';
    }
    
    pulsateAgentStateEntities(agentId) {
        // Find state entities created by this agent
        const stateEntityIds = this.agentStateMap.get(agentId);
        if (!stateEntityIds || stateEntityIds.size === 0) {
            console.log(`🔍 No state entities found for agent ${agentId}`);
            return;
        }
        
        console.log(`✨ Pulsating ${stateEntityIds.size} state entities for agent ${agentId}`);
        
        // Pulsate each related state entity
        stateEntityIds.forEach(entityId => {
            const node = this.stateGraph.getElementById(entityId);
            if (node && node.length > 0) {
                // Add pulsate animation
                node.addClass('pulsate');
                
                // Remove after animation
                setTimeout(() => {
                    node.removeClass('pulsate');
                }, 1000);
            }
        });
    }
    
    handleAgentList(data) {
        console.log('Received agent list:', data);
        
        if (!data.agents || !Array.isArray(data.agents)) {
            console.warn('Invalid agent list data:', data);
            return;
        }
        
        // Clear existing agents (in case of reconnect)
        this.agentGraph.elements().remove();
        this.agents.clear();
        
        // Add each agent to the graph
        data.agents.forEach(agent => {
            if (agent.agent_id) {
                this.agents.set(agent.agent_id, agent);
                
                this.agentGraph.add({
                    data: {
                        id: agent.agent_id,
                        label: agent.agent_id.substring(0, 12) + '\n(' + (agent.profile || 'unknown') + ')',
                        type: 'agent',
                        metadata: agent
                    }
                });
            }
        });
        
        // Run layout with better spacing for larger nodes
        this.agentGraph.layout({ 
            name: 'grid', 
            animate: true,
            padding: 10,
            avoidOverlap: true,
            avoidOverlapPadding: 10
        }).run();
        console.log(`Populated ${data.agents.length} agents in graph`);
    }
    
    handleAgentTerminate(data) {
        console.log('Handling agent termination:', data);
        
        // Handle both single agent and bulk termination
        const agentIds = [];
        
        if (data.agent_id) {
            // Single agent termination
            agentIds.push(data.agent_id);
        } else if (data.terminated && Array.isArray(data.terminated)) {
            // Bulk termination result
            agentIds.push(...data.terminated);
        } else if (data.agents && Array.isArray(data.agents)) {
            // Alternative bulk format
            agentIds.push(...data.agents);
        }
        
        if (agentIds.length === 0) {
            console.warn('Agent termination event missing agent IDs:', data);
            return;
        }
        
        // Remove each terminated agent
        agentIds.forEach(agentId => {
            console.log(`Removing agent ${agentId} from visualization`);
            
            // Remove from tracking
            this.agents.delete(agentId);
            
            // Remove node and connected edges
            const node = this.agentGraph.getElementById(agentId);
            if (node && node.length > 0) {
                this.agentGraph.remove(node);
                console.log(`Removed agent ${agentId} from graph`);
            } else {
                console.log(`Agent ${agentId} not found in graph`);
            }
        });
        
        console.log(`Processed termination for ${agentIds.length} agents`);
    }
    
    handleCompletionRequest(data) {
        if (data.agent_id) {
            this.activeCompletions.set(data.agent_id, Date.now());
            
            // Start completion animation
            const node = this.agentGraph.getElementById(data.agent_id);
            if (node) {
                node.addClass('completing');
            }
        }
    }
    
    handleCompletion(data) {
        const agentId = data.agent_id;
        if (!agentId) return;
        
        // End completion animation
        const node = this.agentGraph.getElementById(agentId);
        if (node) {
            setTimeout(() => {
                node.removeClass('completing');
            }, 500);
            
            // Update metadata
            node.data('lastCompletion', {
                timestamp: data.timestamp,
                duration: data.result?.duration_ms,
                provider: data.result?.provider
            });
        }
        
        this.activeCompletions.delete(agentId);
    }
    
    handleMessage(data) {
        const fromAgent = data.from_agent || data.from || data._agent_id;
        const toAgents = data.to_agents || (data.to ? [data.to] : []);
        const messageType = data.type || 'message';
        
        if (!fromAgent) return;
        
        // Create persistent message edges
        toAgents.forEach(toAgent => {
            this.createMessageEdge(fromAgent, toAgent, messageType);
            
            // Animate the message flow
            this.animateEventFlow(fromAgent, toAgent, 'message');
        });
        
        // If this is an orchestrator feedback message
        if (data._orchestrator_agent_id && data._agent_id) {
            this.createOrchestratorFeedbackEdge(data._agent_id, data._orchestrator_agent_id);
            this.animateEventFlow(data._agent_id, data._orchestrator_agent_id, 'orchestrator_feedback');
        }
    }
    
    handleOrchestrationStarted(data) {
        const orchId = data.orchestration_id;
        if (!orchId) return;
        
        // Add orchestration node
        this.agentGraph.add({
            data: {
                id: orchId,
                label: data.pattern || orchId.substring(0, 8),
                type: 'orchestration',
                metadata: data,
                orchestrator_agent_id: data.orchestrator_agent_id,
                event_subscription_level: data.event_subscription_level,
                error_subscription_level: data.error_subscription_level
            }
        });
        
        // If there's an orchestrator agent, create feedback edge
        if (data.orchestrator_agent_id) {
            // Ensure orchestrator agent exists in graph
            if (!this.agentGraph.getElementById(data.orchestrator_agent_id).length) {
                this.agentGraph.add({
                    data: {
                        id: data.orchestrator_agent_id,
                        label: `${data.orchestrator_agent_id}\\n(orchestrator)`,
                        type: 'agent',
                        metadata: { orchestrator: true }
                    }
                });
            }
            
            // Create orchestrator feedback edge
            this.createOrchestratorFeedbackEdge(orchId, data.orchestrator_agent_id);
        }
        
        // Run hierarchical layout
        this.agentGraph.layout({ 
            name: 'dagre', 
            animate: true,
            rankDir: 'TB'
        }).run();
    }
    
    handleOrchestrationCompleted(data) {
        const orchId = data.orchestration_id;
        if (!orchId) return;
        
        // Could update visual state or remove
        const node = this.agentGraph.getElementById(orchId);
        if (node) {
            node.data('status', 'completed');
        }
    }
    
    handleEntityCreated(data) {
        // Legacy method - redirect to new routing system
        console.log('⚠️ Legacy handleEntityCreated called, redirecting to handleEntityCreate');
        this.handleEntityCreate(data, null);
    }
    
    handleRelationshipCreated(data) {
        if (!data.from_id || !data.to_id) return;
        
        console.log('Handling relationship created:', data);
        
        // Ensure both entities exist in state graph before adding relationship
        const sourceExists = this.stateGraph.getElementById(data.from_id).length > 0;
        const targetExists = this.stateGraph.getElementById(data.to_id).length > 0;
        
        if (!sourceExists || !targetExists) {
            console.warn(`Cannot create relationship: missing entities (source: ${sourceExists}, target: ${targetExists})`);
            return;
        }
        
        const edgeId = `${data.from_id}-${data.relation_type}-${data.to_id}`;
        
        // Add edge if not already present
        if (this.stateGraph.getElementById(edgeId).length === 0) {
            this.stateGraph.add({
                data: {
                    id: edgeId,
                    source: data.from_id,
                    target: data.to_id,
                    type: data.relation_type,
                    label: data.relation_type
                }
            });
            
            console.log(`Added relationship ${data.from_id} --${data.relation_type}--> ${data.to_id}`);
            
            // Re-run layout to accommodate new edge
            this.stateGraph.layout({ 
                name: 'circle', 
                animate: true,
                padding: 10,
                avoidOverlap: true
            }).run();
        }
    }
    
    handleStateEntityQuery(data) {
        console.log('Received state entities:', data);
        
        // Check if this is a response with entities
        if (!data.entities && !data.results) {
            console.warn('State entity query - waiting for response with entities');
            return;
        }
        
        // Handle both 'entities' and 'results' field names
        const entities = data.entities || data.results;
        if (!entities || !Array.isArray(entities)) {
            console.warn('Invalid state entities data:', data);
            return;
        }
        
        // Clear existing state graph
        this.stateGraph.elements().remove();
        
        // Filter out agent entities - they're shown in Agent Ecosystem
        const nonAgentEntities = entities.filter(entity => entity.type !== 'agent');
        
        console.log(`Filtered ${data.entities.length} entities to ${nonAgentEntities.length} non-agent entities`);
        
        // Add non-agent entities to state graph
        nonAgentEntities.forEach(entity => {
            if (entity.id) {
                // Create descriptive label based on entity type and properties
                let label = entity.id.substring(0, 12);
                if (entity.type && entity.type !== 'entity') {
                    label = `${entity.type}\\n${entity.id.substring(0, 10)}`;
                }
                if (entity.properties && entity.properties.name) {
                    label = entity.properties.name.substring(0, 15);
                }
                
                this.stateGraph.add({
                    data: {
                        id: entity.id,
                        label: label,
                        type: entity.type || 'entity',
                        metadata: entity
                    }
                });
            }
        });
        
        // Run layout with better spacing for diverse entity types
        this.stateGraph.layout({ 
            name: 'circle', 
            animate: true,
            padding: 10,
            avoidOverlap: true
        }).run();
        
        console.log(`Populated ${nonAgentEntities.length} non-agent entities in state graph`);
    }
    
    handleEntityDeleted(data) {
        // Handle both entity_id (old format) and id (new format)
        const entityId = data.entity_id || data.id;
        if (!entityId) {
            console.warn('Entity deleted event missing ID:', data);
            return;
        }
        
        console.log('Handling entity deleted:', entityId, data);
        
        // Remove from state graph if present
        const node = this.stateGraph.getElementById(entityId);
        if (node && node.length > 0) {
            this.stateGraph.remove(node);
            console.log(`Removed entity ${entityId} from state graph`);
        } else {
            console.log(`Entity ${entityId} not found in state graph (may be agent)`);
        }
    }
    
    showAgentActivity(agentId) {
        // Visual feedback when agent originates an event
        const node = this.agentGraph.getElementById(agentId);
        if (!node || !node.length) return;
        
        // Add activity class with animation
        node.addClass('active');
        
        // Create a pulse effect
        node.animate({
            style: {
                'background-color': '#FFD700',
                'border-width': 5,
                'border-color': '#FFA500'
            }
        }, {
            duration: 200
        }).animate({
            style: {
                'background-color': node.data('type') === 'orchestration' ? '#FF9800' : '#4CAF50',
                'border-width': 0
            }
        }, {
            duration: 800
        });
        
        // Remove active class after animation
        setTimeout(() => {
            node.removeClass('active');
        }, 1000);
    }
    
    initializeDividers() {
        const verticalDivider = document.getElementById('vertical-divider');
        const horizontalDivider = document.getElementById('horizontal-divider');
        const agentPanel = document.getElementById('agent-panel');
        const statePanel = document.getElementById('state-panel');
        const eventPanel = document.getElementById('event-panel');
        
        let isDragging = false;
        let dragTarget = null;
        
        const startDrag = (e, divider) => {
            isDragging = true;
            dragTarget = divider;
            divider.classList.add('divider-dragging');
            e.preventDefault();
        };
        
        const doDrag = (e) => {
            if (!isDragging || !dragTarget) return;
            
            const rect = document.getElementById('main-layout').getBoundingClientRect();
            
            if (dragTarget.id === 'vertical-divider') {
                // Calculate percentage position
                const percentage = ((e.clientX - rect.left) / rect.width) * 100;
                
                // Constrain between 20% and 80%
                const constrainedPercentage = Math.max(20, Math.min(80, percentage));
                
                // Update divider position
                dragTarget.style.left = `${constrainedPercentage}%`;
                
                // Update panel widths
                agentPanel.style.width = `${constrainedPercentage}%`;
                statePanel.style.width = `${100 - constrainedPercentage}%`;
                
                // Refresh Cytoscape layouts
                this.agentGraph.resize();
                this.stateGraph.resize();
            }
            else if (dragTarget.id === 'horizontal-divider') {
                // Calculate percentage position
                const percentage = ((e.clientY - rect.top) / rect.height) * 100;
                
                // Constrain between 20% and 80%
                const constrainedPercentage = Math.max(20, Math.min(80, percentage));
                
                // Update divider position
                dragTarget.style.top = `${constrainedPercentage}%`;
                
                // Update panel heights
                agentPanel.style.height = `${constrainedPercentage}%`;
                statePanel.style.height = `${constrainedPercentage}%`;
                eventPanel.style.height = `${100 - constrainedPercentage}%`;
                verticalDivider.style.height = `${constrainedPercentage}%`;
                
                // Refresh Cytoscape layouts
                this.agentGraph.resize();
                this.stateGraph.resize();
            }
        };
        
        const endDrag = () => {
            if (dragTarget) {
                dragTarget.classList.remove('divider-dragging');
            }
            isDragging = false;
            dragTarget = null;
        };
        
        // Add event listeners
        verticalDivider.addEventListener('mousedown', (e) => startDrag(e, verticalDivider));
        horizontalDivider.addEventListener('mousedown', (e) => startDrag(e, horizontalDivider));
        
        document.addEventListener('mousemove', doDrag);
        document.addEventListener('mouseup', endDrag);
        
        // Handle window resize
        window.addEventListener('resize', () => {
            this.agentGraph.resize();
            this.stateGraph.resize();
        });
        
        // Add debug helpers
        window.debugKSI = {
            refreshAgents: () => {
                console.log('🔄 Manual agent list refresh');
                this.requestAgentList();
            },
            refreshState: () => {
                console.log('🔄 Manual state entities refresh');
                this.requestStateEntities();
            },
            graphStats: () => {
                console.log('📊 Agent Graph:', {
                    nodes: this.agentGraph.nodes().length,
                    edges: this.agentGraph.edges().length,
                    nodeIds: this.agentGraph.nodes().map(n => n.id())
                });
                console.log('📊 State Graph:', {
                    nodes: this.stateGraph.nodes().length,
                    edges: this.stateGraph.edges().length,
                    nodeIds: this.stateGraph.nodes().map(n => n.id())
                });
                console.log('🔗 Agent-State Relationships:', {
                    agentStateMap: Object.fromEntries(
                        Array.from(this.agentStateMap.entries()).map(([k, v]) => [k, Array.from(v)])
                    ),
                    stateAgentMap: Object.fromEntries(this.stateAgentMap),
                    pendingSpawns: this.recentSpawnRequests.size
                });
            },
            clearGraphs: () => {
                console.log('🧹 Clearing all graphs');
                this.agentGraph.elements().remove();
                this.stateGraph.elements().remove();
                this.addedStateEntities.clear();
                this.agentStateMap.clear();
                this.stateAgentMap.clear();
            },
            testAgent: (agentId = 'test_agent_123') => {
                console.log('🧪 Adding test agent:', agentId);
                this.agentGraph.add({
                    data: {
                        id: agentId,
                        label: `${agentId}\\n(test)`,
                        type: 'agent'
                    }
                });
                this.agentGraph.layout({ name: 'grid', animate: true }).run();
            },
            testStateEntity: (entityId = 'test_entity_123', type = 'analysis') => {
                // Clear existing entity first
                if (this.addedStateEntities.has(entityId)) {
                    console.log('🧹 Removing existing test entity:', entityId);
                    const node = this.stateGraph.getElementById(entityId);
                    if (node) {
                        this.stateGraph.remove(node);
                    }
                    this.addedStateEntities.delete(entityId);
                }
                
                console.log('🧪 Adding test state entity:', entityId);
                this.handleStateEntityCreated({
                    id: entityId,
                    type: type,
                    properties: {
                        name: 'Test Analysis',
                        status: 'completed',
                        result: 'Test result data'
                    }
                }, { _agent_id: 'test_agent_123' });
            },
            testEdges: () => {
                console.log('🧪 Testing edge creation');
                // Add test agents
                this.agentGraph.add([
                    { data: { id: 'parent_test', label: 'Parent\\n(test)', type: 'agent' } },
                    { data: { id: 'child_test', label: 'Child\\n(test)', type: 'agent' } }
                ]);
                
                // Add test edge
                this.agentGraph.add({
                    data: {
                        id: 'parent_test-spawned-child_test',
                        source: 'parent_test',
                        target: 'child_test',
                        type: 'spawned'
                    }
                });
                
                this.agentGraph.layout({ name: 'dagre', animate: true, rankDir: 'LR' }).run();
                console.log('✅ Added test parent-child relationship with edge');
            },
            testPulsate: (agentId = 'test_agent_123') => {
                console.log('🧪 Testing pulsate for agent:', agentId);
                this.pulsateAgentStateEntities(agentId);
            }
        };
        
        console.log('🔧 Debug helpers available: window.debugKSI');
    }
}

// Initialize visualizer when page loads
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 DOMContentLoaded - Initializing KSI Visualizer...');
    try {
        window.ksiVisualizer = new KSIVisualizer();
        console.log('✅ KSI Visualizer initialized successfully');
    } catch (error) {
        console.error('❌ Failed to initialize KSI Visualizer:', error);
        console.error('Stack trace:', error.stack);
    }
});