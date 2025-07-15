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
        
        // Generate unique client ID for this browser session
        this.clientId = this.generateClientId();
        
        // Initialize Cytoscape instances
        this.initializeGraphs();
        
        // Event handlers map
        this.eventHandlers = {
            'agent:spawn': this.handleAgentSpawn.bind(this),
            'agent:spawned': this.handleAgentSpawn.bind(this), 
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
            'bridge:connected': this.handleBridgeConnected.bind(this),
            'bridge:ksi_connected': this.handleKSIConnected.bind(this),
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
            console.warn('Cannot subscribe: WebSocket not connected');
            return;
        }
        
        const subscribeMsg = {
            event: "monitor:subscribe",
            data: {
                client_id: this.clientId,
                event_patterns: ["*"]  // Subscribe to all events
            }
        };
        
        console.log('Sending subscription request:', subscribeMsg);
        this.ws.send(JSON.stringify(subscribeMsg));
        this.subscribed = true;
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
                console.log('Connected to KSI WebSocket bridge');
                if (this.reconnectTimeout) {
                    clearTimeout(this.reconnectTimeout);
                    this.reconnectTimeout = null;
                }
            };
            
            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
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
        
        // Log event
        this.logEvent(data);
        
        // Debug logging
        if (eventName && eventName.startsWith('agent:')) {
            console.log('Agent event received:', eventName, data);
        }
        
        // Visual feedback for agent-originated events
        const originatorId = data._originator_agent_id || data._agent_id;
        if (originatorId && !eventName.startsWith('observe:')) {
            this.showAgentActivity(originatorId);
        }
        
        // Route to specific handler
        const handler = this.eventHandlers[eventName];
        if (handler) {
            try {
                handler(data.data || {});
            } catch (e) {
                console.error(`Error handling ${eventName}:`, e, data);
            }
        } else if (eventName) {
            console.debug(`No handler for event: ${eventName}`);
        }
    }
    
    logEvent(data) {
        const entry = document.createElement('div');
        entry.className = 'event-entry';
        
        // Determine event category for styling
        const eventName = data.event || data.event_name || '';
        if (eventName.startsWith('agent:')) {
            entry.classList.add('event-agent');
        } else if (eventName.startsWith('completion:')) {
            entry.classList.add('event-completion');
        } else if (eventName.startsWith('orchestration:')) {
            entry.classList.add('event-orchestration');
        } else if (eventName.startsWith('state:')) {
            entry.classList.add('event-state');
        }
        
        // Mark agent-originated events - check both top level and inside data
        if (data._originated_by_agent || data._agent_id || 
            (data.data && (data.data._originated_by_agent || data.data._agent_id))) {
            entry.classList.add('agent-originated');
        } else if (data._client_id || (data.data && data.data._client_id)) {
            entry.classList.add('client-originated');
        }
        
        // Format timestamp - KSI uses Unix epoch seconds
        let time = 'No timestamp';
        if (data.timestamp) {
            // Convert seconds to milliseconds and format with full precision
            const date = new Date(data.timestamp * 1000);
            time = date.toLocaleTimeString('en-US', { 
                hour12: false, 
                hour: '2-digit', 
                minute: '2-digit', 
                second: '2-digit',
                fractionalSecondDigits: 3 
            });
        }
        
        // Build entry content with enhanced tooltips
        const eventDataStr = JSON.stringify(data.data || {});
        const truncatedData = eventDataStr.length > 100 ? 
            eventDataStr.substring(0, 100) + '...' : eventDataStr;
        
        entry.innerHTML = `
            <span class="event-time">${time}</span>
            <span class="event-type">${eventName}</span>
            <span class="event-data" title="${eventDataStr.replace(/"/g, '&quot;')}">${truncatedData}</span>
        `;
        
        // Add to log (prepend for newest first)
        this.eventLog.insertBefore(entry, this.eventLog.firstChild);
        
        // Limit log size
        while (this.eventLog.children.length > this.maxEventLogEntries) {
            this.eventLog.removeChild(this.eventLog.lastChild);
        }
    }
    
    // Event Handlers
    
    handleBridgeConnected(data) {
        console.log('Bridge confirmed connection:', data.message);
        console.log('Using client ID:', this.clientId);
        
        // Subscribe to events when bridge connection is established
        this.sendSubscriptionRequest();
        
        // Request current agent list to populate initial state
        this.requestAgentList();
        
        // Request current state entities to populate state graph
        this.requestStateEntities();
    }
    
    handleKSIConnected(data) {
        console.log('KSI daemon connected:', data.message);
        this.ksiConnected = true;
        this.updateStatus('connected', 'Connected (KSI Active)');
        
        // Re-subscribe when KSI daemon reconnects (handles daemon restarts)
        console.log('Re-subscribing after KSI daemon reconnection');
        this.sendSubscriptionRequest();
        
        // Don't clear state - daemon checkpoint restore should handle consistency
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
    
    handleAgentSpawn(data) {
        const agentId = data.agent_id;
        if (!agentId) return;
        
        console.log('handleAgentSpawn - data:', data);
        
        // Track agent
        this.agents.set(agentId, data);
        
        // Add node to graph
        this.agentGraph.add({
            data: {
                id: agentId,
                label: agentId.substring(0, 12) + '\n(' + (data.profile || 'unknown') + ')',
                type: 'agent',
                metadata: data
            }
        });
        
        // Add relationship if spawned by another agent
        // Check both _originator_agent_id (from enhanced websocket) and _agent_id (direct from KSI)
        const originatorId = data._originator_agent_id || data._agent_id || data.parent_agent_id;
        if (originatorId && originatorId !== agentId) {
            // Ensure originator exists in graph
            if (!this.agentGraph.getElementById(originatorId).length) {
                this.agentGraph.add({
                    data: {
                        id: originatorId,
                        label: originatorId.substring(0, 12) + '\n(inferred)',
                        type: 'agent',
                        metadata: { inferred: true }
                    }
                });
            }
            
            console.log(`Creating spawn edge from ${originatorId} to ${agentId}`);
            this.agentGraph.add({
                data: {
                    id: `${originatorId}-spawns-${agentId}`,
                    source: originatorId,
                    target: agentId,
                    type: 'spawned'
                }
            });
        } else {
            console.log(`No originator found for ${agentId} - originatorId: ${originatorId}`);
        }
        
        // Run layout with dagre for hierarchical display
        this.agentGraph.layout({ 
            name: 'dagre', 
            animate: true,
            padding: 10,
            spacingFactor: 1.5,
            nodeSep: 50,
            rankSep: 100
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
        
        if (!data.entities || !Array.isArray(data.entities)) {
            console.warn('Invalid state entities data:', data);
            return;
        }
        
        // Clear existing state graph
        this.stateGraph.elements().remove();
        
        // Filter out agent entities - they're shown in Agent Ecosystem
        const nonAgentEntities = data.entities.filter(entity => entity.type !== 'agent');
        
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
    window.ksiVisualizer = new KSIVisualizer();
});