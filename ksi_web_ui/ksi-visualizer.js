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
            'agent:spawn': this.handleAgentSpawn.bind(this),
            'agent:spawned': this.handleAgentSpawn.bind(this),
            'agent:spawn_from_component': this.handleAgentSpawn.bind(this), // Add handler for component spawning
            'agent:list': this.handleAgentList.bind(this),
            'agent:terminate': this.handleAgentTerminate.bind(this),
            'agent:terminated': this.handleAgentTerminate.bind(this),
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
        
        // Track subscription state
        this.subscribed = false;
        
        // Connect to WebSocket
        this.connect();
        
        // Add periodic connection health check
        this.startHealthCheck();
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
                        'width': 2,
                        'target-arrow-shape': 'triangle',
                        'line-color': '#666',
                        'target-arrow-color': '#666',
                        'curve-style': 'bezier'
                    }
                },
                {
                    selector: 'edge[type="spawned"]',
                    style: {
                        'line-color': '#4CAF50',
                        'target-arrow-color': '#4CAF50',
                        'width': 3,
                        'target-arrow-shape': 'triangle',
                        'arrow-scale': 1.5
                    }
                },
                {
                    selector: 'edge.message-flow',
                    style: {
                        'line-color': '#2196F3',
                        'target-arrow-color': '#2196F3',
                        'line-style': 'dashed',
                        'width': 3
                    }
                }
            ],
            layout: {
                name: 'grid',  // Start with simple grid layout
                animate: true
            }
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
            console.debug(`No handler for event: ${eventName}`);
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
    
    handleAgentSpawn(data, eventMetadata) {
        const agentId = data.agent_id;
        if (!agentId) return;
        
        console.log('handleAgentSpawn - data:', data, 'eventMetadata:', eventMetadata);
        
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
        if (parentId && parentId !== agentId) {
            // Ensure parent exists in graph
            if (!this.agentGraph.getElementById(parentId).length) {
                this.agentGraph.add({
                    data: {
                        id: parentId,
                        label: this.buildAgentLabel(parentId, { inferred: true }),
                        type: 'agent',
                        metadata: { inferred: true }
                    }
                });
            }
            
            console.log(`Creating hierarchical edge from ${parentId} to ${agentId}`);
            
            // Determine edge type based on metadata
            const edgeType = data.orchestration_id ? 'orchestration' : 'spawn';
            
            this.agentGraph.add({
                data: {
                    id: `${parentId}-${edgeType}-${agentId}`,
                    source: parentId,
                    target: agentId,
                    type: edgeType,
                    orchestration_id: data.orchestration_id
                }
            });
        }
        
        // Apply hierarchical layout with improved spacing
        this.agentGraph.layout({ 
            name: 'dagre', 
            animate: true,
            padding: 20,
            spacingFactor: 1.8,
            nodeSep: 60,
            rankSep: 120,
            rankDir: 'TB' // Top to bottom for hierarchy
        }).run();
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
        const fromAgent = data.from_agent || data.from;
        const toAgents = data.to_agents || (data.to ? [data.to] : []);
        
        if (!fromAgent) return;
        
        // Create message flow edges
        toAgents.forEach(toAgent => {
            const edgeId = `msg-${Date.now()}-${Math.random()}`;
            
            this.agentGraph.add({
                data: {
                    id: edgeId,
                    source: fromAgent,
                    target: toAgent,
                    type: 'message'
                },
                classes: 'message-flow'
            });
            
            // Remove after animation
            setTimeout(() => {
                const edge = this.agentGraph.getElementById(edgeId);
                if (edge) {
                    this.agentGraph.remove(edge);
                }
            }, 2000);
        });
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
                metadata: data
            }
        });
        
        // Run layout
        this.agentGraph.layout({ name: 'grid', animate: true }).run();
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
        // Handle both entity_id (old format) and id (new format)
        const entityId = data.entity_id || data.id;
        if (!entityId) {
            console.warn('Entity created event missing ID:', data);
            return;
        }
        
        console.log('Handling entity created:', entityId, data);
        
        // Filter out agent entities - they're shown in Agent Ecosystem
        if (data.type === 'agent') {
            console.log(`Skipping agent entity ${entityId} - shown in Agent Ecosystem`);
            return;
        }
        
        // Create descriptive label based on entity type and properties
        let label = entityId.substring(0, 12);
        if (data.type && data.type !== 'entity') {
            label = `${data.type}\\n${entityId.substring(0, 10)}`;
        }
        if (data.properties && data.properties.name) {
            label = data.properties.name.substring(0, 15);
        }
        
        // Add to state graph if not already present
        if (this.stateGraph.getElementById(entityId).length === 0) {
            this.stateGraph.add({
                data: {
                    id: entityId,
                    label: label,
                    type: data.type || 'entity',
                    metadata: data
                }
            });
            
            // Run layout
            this.stateGraph.layout({ name: 'circle', animate: true }).run();
            console.log(`Added entity ${entityId} to state graph`);
        }
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