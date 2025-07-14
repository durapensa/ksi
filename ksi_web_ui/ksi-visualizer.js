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
            'agent:terminate': this.handleAgentTerminate.bind(this),
            'agent:terminated': this.handleAgentTerminate.bind(this),
            'completion:result': this.handleCompletion.bind(this),
            'completion:async': this.handleCompletionRequest.bind(this),
            'orchestration:message': this.handleMessage.bind(this),
            'orchestration:started': this.handleOrchestrationStarted.bind(this),
            'orchestration:completed': this.handleOrchestrationCompleted.bind(this),
            'state:entity:created': this.handleEntityCreated.bind(this),
            'state:relationship:created': this.handleRelationshipCreated.bind(this),
            'bridge:connected': this.handleBridgeConnected.bind(this),
            'bridge:ksi_connected': this.handleKSIConnected.bind(this),
            'bridge:ksi_disconnected': this.handleKSIDisconnected.bind(this),
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
                        'width': 40,
                        'height': 40
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
                        'width': 80,
                        'height': 40
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
                        'target-arrow-color': '#4CAF50'
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
        
        // Extract originator info if available
        let originatorStr = '';
        if (data.originator) {
            // From broadcast format
            const orig = data.originator;
            if (orig._agent_id) {
                originatorStr = `[${orig._agent_id}]`;
            }
        } else if (data._agent_id) {
            // Direct system metadata field
            originatorStr = `[${data._agent_id}]`;
        }
        
        // Build entry content
        entry.innerHTML = `
            <span class="event-time">${time}</span>
            <span class="event-originator">${originatorStr}</span>
            <span class="event-type">${eventName}</span>
            <span class="event-data">${JSON.stringify(data.data || {})}</span>
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
        
        // Track agent
        this.agents.set(agentId, data);
        
        // Add node to graph
        this.agentGraph.add({
            data: {
                id: agentId,
                label: data.profile || agentId.substring(0, 8),
                type: 'agent',
                metadata: data
            }
        });
        
        // Add relationship if spawned by another agent
        if (data.parent_agent_id) {
            this.agentGraph.add({
                data: {
                    id: `${data.parent_agent_id}-spawns-${agentId}`,
                    source: data.parent_agent_id,
                    target: agentId,
                    type: 'spawned'
                }
            });
        }
        
        // Run layout
        this.agentGraph.layout({ name: 'grid', animate: true }).run();
    }
    
    handleAgentTerminate(data) {
        const agentId = data.agent_id;
        if (!agentId) return;
        
        // Remove from tracking
        this.agents.delete(agentId);
        
        // Remove node and connected edges
        const node = this.agentGraph.getElementById(agentId);
        if (node) {
            this.agentGraph.remove(node);
        }
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
        const entityId = data.entity_id;
        if (!entityId) return;
        
        // Add to state graph
        this.stateGraph.add({
            data: {
                id: entityId,
                label: data.type || entityId.substring(0, 8),
                type: 'entity',
                properties: data.properties
            }
        });
        
        // Run layout
        this.stateGraph.layout({ name: 'circle', animate: true }).run();
    }
    
    handleRelationshipCreated(data) {
        if (!data.from_id || !data.to_id) return;
        
        // Add to state graph
        this.stateGraph.add({
            data: {
                id: `${data.from_id}-${data.relation_type}-${data.to_id}`,
                source: data.from_id,
                target: data.to_id,
                type: data.relation_type
            }
        });
    }
}

// Initialize visualizer when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.ksiVisualizer = new KSIVisualizer();
});