# KSI Unified Platform Architecture Plan

**Date**: 2025-01-23  
**Author**: Claude (Opus 4)  
**Purpose**: Comprehensive plan to evolve KSI into a general-purpose AI application platform built on SQLite reference architecture

## Executive Summary

This plan unifies two complementary visions for KSI's future:
1. **SQLite Reference Architecture**: A lightweight, operationally simple foundation using SQLite for metadata and events
2. **Application Platform Vision**: A declarative platform for building AI-native applications

The unified architecture creates "Kubernetes for AI agents" - a platform where developers define applications declaratively while KSI handles the complexity of multi-agent orchestration, state management, and distributed coordination.

## Table of Contents

1. [Vision and Strategic Goals](#vision-and-strategic-goals)
2. [Current State Analysis](#current-state-analysis)
3. [Unified Architecture Design](#unified-architecture-design)
4. [Technical Architecture](#technical-architecture)
5. [Application Model](#application-model)
6. [Platform Services](#platform-services)
7. [Implementation Roadmap](#implementation-roadmap)
8. [Migration Strategy](#migration-strategy)
9. [Operational Excellence](#operational-excellence)
10. [Risk Analysis and Mitigation](#risk-analysis-and-mitigation)
11. [Success Metrics](#success-metrics)
12. [Future Directions](#future-directions)

## Vision and Strategic Goals

### Vision Statement
Transform KSI into a general-purpose platform for building, deploying, and managing AI-native applications through declarative manifests, with SQLite providing a rock-solid, operationally simple foundation.

### Strategic Goals

1. **Simplicity**: One SQLite file + file system = entire platform state
2. **Declarative**: Applications defined in YAML, not code
3. **AI-Native**: Claude agents as first-class application components
4. **Scalable**: From single-agent tools to complex multi-agent systems
5. **Extensible**: Plugin architecture for custom capabilities
6. **Observable**: Built-in monitoring, tracing, and debugging
7. **Reliable**: Crash-resilient with automatic recovery

### Target Outcomes

- **For Developers**: Build AI applications in hours, not months
- **For Operators**: Deploy and manage with minimal complexity
- **For Organizations**: Standardized platform for AI initiatives
- **For Community**: Ecosystem of reusable components and applications

## Current State Analysis

### KSI Today

**Strengths to Preserve:**
- ✅ Modular daemon architecture with clean separation of concerns
- ✅ Working multi-agent coordination and message bus
- ✅ Composition system for behavior definition
- ✅ Session persistence and conversation continuity
- ✅ Hot-reload capability for development
- ✅ Event-driven design (no polling)
- ✅ File-based storage for large data

**Limitations to Address:**
- ❌ No application isolation or multi-tenancy
- ❌ Limited service discovery capabilities
- ❌ No resource management or quotas
- ❌ Lacks declarative application deployment
- ❌ No built-in monitoring or observability
- ❌ Complex manual setup for multi-agent scenarios
- ❌ No standardized application packaging

### Architecture Evolution Path

```
Current KSI          →  SQLite Foundation  →  Application Platform
(Multi-agent daemon)    (Reference arch)      (Full platform)
     Stage 0                Stage 1               Stage 2
```

## Unified Architecture Design

### Conceptual Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   App: CRM   │  │ App: Analytics│ │ App: Support│  ...   │
│  │ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌─────────┐ │         │
│  │ │ Agents  │ │  │ │ Agents  │ │  │ │ Agents  │ │         │
│  │ ├─────────┤ │  │ ├─────────┤ │  │ ├─────────┤ │         │
│  │ │Workflows│ │  │ │Workflows│ │  │ │Workflows│ │         │
│  │ ├─────────┤ │  │ ├─────────┤ │  │ ├─────────┤ │         │
│  │ │  State  │ │  │ │  State  │ │  │ │  State  │ │         │
│  │ └─────────┘ │  │ └─────────┘ │  │ └─────────┘ │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    Platform Services                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Lifecycle   │  │   Service    │  │   Resource   │      │
│  │  Manager     │  │  Discovery   │  │   Manager    │      │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤      │
│  │  Security    │  │  Monitoring  │  │   Template   │      │
│  │  Manager     │  │   Service    │  │   Engine     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                 Core Infrastructure                           │
│  ┌─────────────────────────────────────────────────────┐    │
│  │            FastAPI + FastStream                      │    │
│  │  ┌────────┐  ┌────────┐  ┌───────────────────────┐ │    │
│  │  │  HTTP  │  │   WS   │  │  Message Handlers     │ │    │
│  │  └────────┘  └────────┘  └───────────────────────┘ │    │
│  └─────────────────────────┬───────────────────────────┘    │
│                            │                                  │
│  ┌─────────────────────────▼───────────────────────────┐    │
│  │              SQLite (WAL mode)                      │    │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │    │
│  │  │Messages │ │ Agents  │ │  Apps   │ │Services │  │    │
│  │  ├─────────┤ ├─────────┤ ├─────────┤ ├─────────┤  │    │
│  │  │Workflows│ │ State   │ │Resources│ │ Config  │  │    │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              File System Storage                     │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │    │
│  │  │  Claude  │  │   App    │  │    Platform      │  │    │
│  │  │   Logs   │  │  State   │  │    Artifacts     │  │    │
│  │  └──────────┘  └──────────┘  └──────────────────┘  │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Reference-Based Storage**
   - SQLite: Metadata, routing, small state (<10KB)
   - Files: Claude responses, large state, artifacts
   - Benefits: Fast queries + efficient storage

2. **Application Isolation**
   - Namespace separation in database
   - Directory isolation in file system
   - Event routing boundaries
   - Resource quotas per app

3. **Declarative Configuration**
   - YAML manifests define entire applications
   - No imperative setup required
   - Version-controlled application definitions

4. **Event-Driven Core**
   - All communication via event bus
   - No polling or busy-waiting
   - Async message handlers

## Technical Architecture

### Enhanced Database Schema

```sql
-- Core platform tables
CREATE TABLE applications (
    id TEXT PRIMARY KEY,                    -- app_123abc
    name TEXT NOT NULL UNIQUE,              -- "customer_support"
    version TEXT NOT NULL,                  -- "1.2.0"
    manifest JSON NOT NULL,                 -- Full application manifest
    status TEXT DEFAULT 'deployed',         -- deployed/stopped/failed
    deployed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON                           -- {author, description, license}
);

CREATE TABLE services (
    id TEXT PRIMARY KEY,                    -- svc_456def
    app_id TEXT NOT NULL,
    service_name TEXT NOT NULL,
    service_type TEXT NOT NULL,             -- agent/workflow/api
    capabilities JSON,                      -- ["nlp", "code_analysis"]
    endpoint TEXT,                          -- Internal service endpoint
    health_status TEXT DEFAULT 'unknown',   -- healthy/unhealthy/unknown
    health_check_interval INTEGER DEFAULT 30,
    last_health_check TIMESTAMP,
    metadata JSON,
    FOREIGN KEY (app_id) REFERENCES applications(id) ON DELETE CASCADE,
    UNIQUE(app_id, service_name)
);

CREATE TABLE resources (
    id TEXT PRIMARY KEY,
    app_id TEXT NOT NULL,
    resource_type TEXT NOT NULL,            -- memory/compute/storage
    allocated_amount INTEGER NOT NULL,
    used_amount INTEGER DEFAULT 0,
    limit_amount INTEGER,
    unit TEXT NOT NULL,                     -- MB/cores/GB
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (app_id) REFERENCES applications(id) ON DELETE CASCADE
);

CREATE TABLE permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id TEXT NOT NULL,
    permission_type TEXT NOT NULL,          -- read/write/execute
    resource_type TEXT NOT NULL,            -- file/api/service
    resource_pattern TEXT NOT NULL,         -- glob pattern or regex
    granted BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (app_id) REFERENCES applications(id) ON DELETE CASCADE,
    UNIQUE(app_id, permission_type, resource_type, resource_pattern)
);

-- Extended existing tables
ALTER TABLE messages ADD COLUMN app_id TEXT;
ALTER TABLE messages ADD COLUMN correlation_id TEXT;
ALTER TABLE messages ADD COLUMN ttl INTEGER;  -- Time to live in seconds

ALTER TABLE agents ADD COLUMN app_id TEXT;
ALTER TABLE agents ADD COLUMN service_id TEXT;
ALTER TABLE agents ADD FOREIGN KEY (app_id) REFERENCES applications(id);
ALTER TABLE agents ADD FOREIGN KEY (service_id) REFERENCES services(id);

ALTER TABLE workflows ADD COLUMN app_id TEXT;
ALTER TABLE workflows ADD FOREIGN KEY (app_id) REFERENCES applications(id);

-- Performance and monitoring tables
CREATE TABLE app_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    metric_type TEXT NOT NULL,              -- counter/gauge/histogram
    tags JSON,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (app_id) REFERENCES applications(id) ON DELETE CASCADE
);

CREATE TABLE app_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id TEXT NOT NULL,
    service_id TEXT,
    log_level TEXT NOT NULL,                -- debug/info/warn/error
    message TEXT NOT NULL,
    context JSON,                           -- Structured log data
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (app_id) REFERENCES applications(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX idx_messages_app_topic ON messages(app_id, topic);
CREATE INDEX idx_services_app_status ON services(app_id, health_status);
CREATE INDEX idx_app_metrics_time ON app_metrics(app_id, metric_name, timestamp);
CREATE INDEX idx_app_logs_time ON app_logs(app_id, timestamp);
```

### Application Isolation Model

```python
class ApplicationContext:
    """Isolation context for an application"""
    
    def __init__(self, app_id: str, manifest: dict):
        self.app_id = app_id
        self.manifest = manifest
        self.namespace = f"app.{app_id}"
        self.root_dir = Path(f"applications/{app_id}")
        self.resource_limits = self._parse_resource_limits(manifest)
        
    def get_event_topic(self, topic: str) -> str:
        """Namespace event topics for isolation"""
        return f"{self.namespace}.{topic}"
        
    def get_file_path(self, relative_path: str) -> Path:
        """Ensure file access within app directory"""
        path = self.root_dir / relative_path
        if not path.resolve().is_relative_to(self.root_dir):
            raise SecurityError("Path traversal detected")
        return path
        
    def check_resource_usage(self, resource_type: str, amount: int) -> bool:
        """Verify resource usage within limits"""
        current = self.get_current_usage(resource_type)
        limit = self.resource_limits.get(resource_type, float('inf'))
        return (current + amount) <= limit
```

### Message Bus Extensions

```python
class ApplicationAwareMessageBus:
    """Extended message bus with application isolation"""
    
    async def publish(self, topic: str, data: dict, 
                     app_context: ApplicationContext = None):
        """Publish message with application context"""
        
        # Add application context to message
        message = {
            "id": generate_id(),
            "topic": topic,
            "app_id": app_context.app_id if app_context else "system",
            "data": data,
            "timestamp": datetime.utcnow(),
            "correlation_id": data.get("correlation_id", generate_id())
        }
        
        # Validate permissions
        if app_context:
            if not await self.check_publish_permission(app_context, topic):
                raise PermissionError(f"App {app_context.app_id} cannot publish to {topic}")
                
        # Store in SQLite
        await self.db.execute("""
            INSERT INTO messages (topic, event_type, data, app_id, correlation_id)
            VALUES (?, ?, ?, ?, ?)
        """, topic, data.get("type", "UNKNOWN"), 
             json.dumps(data), message["app_id"], message["correlation_id"])
        
    async def subscribe(self, pattern: str, handler: Callable,
                       app_context: ApplicationContext = None):
        """Subscribe to messages with application filtering"""
        
        # Namespace the subscription pattern
        if app_context:
            pattern = f"{app_context.namespace}.{pattern}"
            
        # Register subscription
        await self.db.execute("""
            INSERT INTO subscriptions (agent_id, topic_pattern, app_id)
            VALUES (?, ?, ?)
        """, handler.__name__, pattern, 
             app_context.app_id if app_context else None)
```

### State Management Abstraction

```python
class StateStore:
    """Unified state storage with backend abstraction"""
    
    def __init__(self, app_context: ApplicationContext):
        self.app_context = app_context
        self.backends = {
            "memory": InMemoryBackend(),
            "sqlite": SQLiteBackend(db_path="ksi.db"),
            "file": FileBackend(base_path=app_context.root_dir / "state")
        }
        
    async def get(self, key: str, backend: str = "sqlite") -> Any:
        """Get value with automatic backend selection"""
        namespaced_key = f"{self.app_context.app_id}:{key}"
        return await self.backends[backend].get(namespaced_key)
        
    async def set(self, key: str, value: Any, backend: str = None):
        """Set value with automatic backend selection"""
        # Auto-select backend based on size
        if backend is None:
            size = len(json.dumps(value))
            backend = "file" if size > 10240 else "sqlite"  # 10KB threshold
            
        namespaced_key = f"{self.app_context.app_id}:{key}"
        await self.backends[backend].set(namespaced_key, value)
        
        # Store reference in SQLite if using file backend
        if backend == "file":
            await self.backends["sqlite"].set(
                f"{namespaced_key}:ref",
                {"backend": "file", "path": f"state/{key}.json"}
            )
```

## Application Model

### Application Manifest Schema

```yaml
# Complete application manifest structure
apiVersion: ksi/v1
kind: Application
metadata:
  name: intelligent-customer-support
  version: 1.0.0
  description: AI-powered customer support system
  author: ACME Corp
  license: MIT

spec:
  # Agent definitions
  agents:
    - name: ticket-classifier
      composition: components/classifier.yaml
      instances: 2
      capabilities:
        - text-analysis
        - classification
      resources:
        memory: 512MB
        
    - name: solution-finder
      composition: components/knowledge-searcher.yaml
      instances: 1
      model: opus  # Override composition default
      
  # Workflow definitions
  workflows:
    - name: ticket-processing
      trigger:
        event: NEW_TICKET
      steps:
        - name: classify
          agent: ticket-classifier
          input: "{{ event.data.ticket }}"
          output: classification
          
        - name: search-knowledge
          agent: solution-finder
          input: "{{ steps.classify.output }}"
          output: solutions
          
        - name: generate-response
          agent: response-writer
          input:
            ticket: "{{ event.data.ticket }}"
            classification: "{{ steps.classify.output }}"
            solutions: "{{ steps.search-knowledge.output }}"
            
  # State management
  state:
    stores:
      - name: ticket-history
        type: document
        backend: file
        retention: 30d
        
      - name: customer-profiles
        type: key-value
        backend: sqlite
        
  # Event definitions
  events:
    - name: NEW_TICKET
      schema:
        type: object
        required: [ticket_id, content, customer_id]
        
    - name: TICKET_RESOLVED
      schema:
        type: object
        required: [ticket_id, resolution]
        
  # External integrations
  integrations:
    - name: zendesk
      type: webhook
      config:
        url: "${ZENDESK_WEBHOOK_URL}"
        auth: bearer
        
  # Resource limits
  resources:
    memory: 4GB
    storage: 10GB
    agents: 10
    
  # Security policies
  security:
    isolation: strict
    permissions:
      - type: read
        resource: "files://knowledge-base/**"
      - type: write  
        resource: "files://tickets/**"
```

### Composition System Extensions

```yaml
# Enhanced composition with platform features
name: knowledge-searcher
version: 1.0.0

# Base configuration
model: sonnet
temperature: 0.3

# Platform-specific features
capabilities:
  - semantic-search
  - knowledge-retrieval
  
resources:
  memory: 256MB
  
components:
  - name: system-identity
    source: platform://components/system-identity
    vars:
      role: knowledge base expert
      
  - name: search-tools
    source: platform://components/search-toolkit
    config:
      backends:
        - elasticsearch
        - vector-db
        
# Lifecycle hooks
lifecycle:
  preStart:
    - action: load-knowledge-base
      params:
        source: "{{ app.config.knowledge_base_path }}"
        
  postStop:
    - action: save-search-cache
```

## Platform Services

### Application Lifecycle Manager

```python
class ApplicationLifecycleManager:
    """Manages application deployment and lifecycle"""
    
    def __init__(self, platform_context: PlatformContext):
        self.platform = platform_context
        self.db = platform_context.db
        self.message_bus = platform_context.message_bus
        
    async def deploy_application(self, manifest_path: str) -> str:
        """Deploy application from manifest"""
        
        # Parse and validate manifest
        manifest = await self.load_manifest(manifest_path)
        validation_errors = await self.validate_manifest(manifest)
        if validation_errors:
            raise ValidationError(f"Invalid manifest: {validation_errors}")
            
        # Create application record
        app_id = generate_app_id()
        app_context = ApplicationContext(app_id, manifest)
        
        # Create application infrastructure
        await self.create_app_infrastructure(app_context)
        
        # Deploy agents
        for agent_spec in manifest.spec.agents:
            await self.deploy_agent_instances(app_context, agent_spec)
            
        # Setup workflows
        for workflow_spec in manifest.spec.workflows:
            await self.setup_workflow(app_context, workflow_spec)
            
        # Configure integrations
        for integration_spec in manifest.spec.integrations:
            await self.setup_integration(app_context, integration_spec)
            
        # Start monitoring
        await self.start_monitoring(app_context)
        
        # Update application status
        await self.update_app_status(app_id, "deployed")
        
        return app_id
        
    async def create_app_infrastructure(self, app_context: ApplicationContext):
        """Create necessary infrastructure for application"""
        
        # Create directories
        app_dirs = [
            app_context.root_dir,
            app_context.root_dir / "logs",
            app_context.root_dir / "state",
            app_context.root_dir / "claude_logs"
        ]
        for dir_path in app_dirs:
            dir_path.mkdir(parents=True, exist_ok=True)
            
        # Initialize database records
        await self.db.execute("""
            INSERT INTO applications (id, name, version, manifest, status)
            VALUES (?, ?, ?, ?, ?)
        """, app_context.app_id, app_context.manifest.metadata.name,
             app_context.manifest.metadata.version,
             json.dumps(app_context.manifest.dict()), "deploying")
             
        # Setup resource quotas
        for resource_type, limit in app_context.resource_limits.items():
            await self.db.execute("""
                INSERT INTO resources (id, app_id, resource_type, 
                                     allocated_amount, limit_amount, unit)
                VALUES (?, ?, ?, ?, ?, ?)
            """, generate_id(), app_context.app_id, resource_type,
                 0, limit["amount"], limit["unit"])
```

### Service Discovery and Registry

```python
class ServiceRegistry:
    """Service discovery for platform applications"""
    
    async def register_service(self, app_id: str, service: ServiceSpec) -> str:
        """Register a service"""
        service_id = generate_id()
        
        await self.db.execute("""
            INSERT INTO services (id, app_id, service_name, service_type,
                                capabilities, endpoint, health_status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, service_id, app_id, service.name, service.type,
             json.dumps(service.capabilities), service.endpoint, "unknown")
             
        # Start health checking
        asyncio.create_task(self.monitor_service_health(service_id))
        
        return service_id
        
    async def discover_services(self, capability: str = None, 
                               app_id: str = None) -> List[Service]:
        """Discover services by capability or app"""
        
        query = """
            SELECT * FROM services 
            WHERE health_status = 'healthy'
        """
        params = []
        
        if capability:
            query += " AND capabilities LIKE ?"
            params.append(f'%"{capability}"%')
            
        if app_id:
            query += " AND app_id = ?"
            params.append(app_id)
            
        results = await self.db.fetch(query, *params)
        return [Service.from_db_row(row) for row in results]
        
    async def get_service_endpoint(self, app_id: str, 
                                  service_name: str) -> str:
        """Get endpoint for a specific service"""
        
        result = await self.db.fetchone("""
            SELECT endpoint FROM services
            WHERE app_id = ? AND service_name = ? 
            AND health_status = 'healthy'
        """, app_id, service_name)
        
        if not result:
            raise ServiceNotFoundError(f"Service {service_name} not found")
            
        return result["endpoint"]
```

### Resource Manager

```python
class ResourceManager:
    """Manage and enforce resource limits"""
    
    async def allocate_resources(self, app_id: str, 
                                resource_type: str, amount: int) -> bool:
        """Allocate resources if available"""
        
        # Check current usage and limits
        resource = await self.db.fetchone("""
            SELECT allocated_amount, limit_amount 
            FROM resources
            WHERE app_id = ? AND resource_type = ?
        """, app_id, resource_type)
        
        if not resource:
            return False
            
        new_amount = resource["allocated_amount"] + amount
        if new_amount > resource["limit_amount"]:
            raise ResourceExhaustedError(
                f"Resource limit exceeded for {resource_type}"
            )
            
        # Update allocation
        await self.db.execute("""
            UPDATE resources 
            SET allocated_amount = ?, updated_at = CURRENT_TIMESTAMP
            WHERE app_id = ? AND resource_type = ?
        """, new_amount, app_id, resource_type)
        
        return True
        
    async def get_resource_usage(self, app_id: str) -> Dict[str, ResourceUsage]:
        """Get current resource usage for an app"""
        
        resources = await self.db.fetch("""
            SELECT resource_type, allocated_amount, used_amount, 
                   limit_amount, unit
            FROM resources
            WHERE app_id = ?
        """, app_id)
        
        return {
            row["resource_type"]: ResourceUsage(
                allocated=row["allocated_amount"],
                used=row["used_amount"],
                limit=row["limit_amount"],
                unit=row["unit"],
                percentage=(row["used_amount"] / row["limit_amount"]) * 100
            )
            for row in resources
        }
```

### Monitoring Service

```python
class MonitoringService:
    """Platform-wide monitoring and observability"""
    
    async def collect_metrics(self):
        """Collect metrics from all applications"""
        
        # Application-level metrics
        app_metrics = await self.db.fetch("""
            SELECT 
                a.id as app_id,
                COUNT(DISTINCT ag.id) as agent_count,
                COUNT(DISTINCT w.id) as workflow_count,
                SUM(r.used_amount) as total_memory_mb
            FROM applications a
            LEFT JOIN agents ag ON a.id = ag.app_id
            LEFT JOIN workflows w ON a.id = w.app_id
            LEFT JOIN resources r ON a.id = r.app_id 
                AND r.resource_type = 'memory'
            WHERE a.status = 'deployed'
            GROUP BY a.id
        """)
        
        for metric in app_metrics:
            await self.record_metric(
                app_id=metric["app_id"],
                metric_name="app.agents.count",
                value=metric["agent_count"],
                metric_type="gauge"
            )
            
    async def get_app_dashboard_data(self, app_id: str) -> Dict:
        """Get dashboard data for an application"""
        
        # Recent logs
        logs = await self.db.fetch("""
            SELECT * FROM app_logs
            WHERE app_id = ? 
            ORDER BY timestamp DESC
            LIMIT 100
        """, app_id)
        
        # Recent metrics
        metrics = await self.db.fetch("""
            SELECT metric_name, metric_value, timestamp
            FROM app_metrics
            WHERE app_id = ? 
            AND timestamp > datetime('now', '-1 hour')
            ORDER BY timestamp DESC
        """, app_id)
        
        # Active agents
        agents = await self.db.fetch("""
            SELECT * FROM agents
            WHERE app_id = ? AND status = 'active'
        """, app_id)
        
        # Running workflows
        workflows = await self.db.fetch("""
            SELECT * FROM workflows
            WHERE app_id = ? AND status = 'running'
        """, app_id)
        
        return {
            "logs": logs,
            "metrics": metrics,
            "agents": agents,
            "workflows": workflows,
            "health": await self.calculate_app_health(app_id)
        }
```

## Implementation Roadmap

### Phase 1: Foundation (Weeks 1-3)

#### Week 1: Core Infrastructure
- **Day 1-2**: Project setup and dependencies
  - Initialize new project structure
  - Install FastAPI, FastStream, SQLite, aiofiles, etc.
  - Setup development environment
  
- **Day 3-4**: SQLite foundation
  - Implement enhanced schema with migrations
  - Create database abstraction layer
  - Build connection pooling
  
- **Day 5-7**: Message bus implementation
  - SQLite-backed message storage
  - Event publishing and subscription
  - Application-aware routing

#### Week 2: File Storage and References
- **Day 1-3**: Reference system
  - File storage utilities
  - Reference resolution
  - Large data handling
  
- **Day 4-5**: Integration layer
  - FastAPI endpoints
  - WebSocket support
  - Basic authentication
  
- **Day 6-7**: Testing framework
  - Unit test infrastructure
  - Integration test helpers
  - In-memory SQLite for tests

#### Week 3: Process Management
- **Day 1-3**: Process lifecycle
  - State machine implementation
  - Retry logic with Tenacity
  - Process monitoring
  
- **Day 4-5**: Agent management
  - Agent registry
  - Capability tracking
  - Session management
  
- **Day 6-7**: System integration
  - End-to-end spawn flow
  - Error handling
  - Recovery mechanisms

### Phase 2: Platform Services (Weeks 4-5)

#### Week 4: Application Foundation
- **Day 1-3**: Application model
  - Manifest parser
  - Application context
  - Isolation boundaries
  
- **Day 4-5**: Lifecycle manager
  - Deploy/undeploy logic
  - State management
  - Resource allocation
  
- **Day 6-7**: Service registry
  - Service discovery
  - Health checking
  - Dynamic routing

#### Week 5: Core Platform Features
- **Day 1-2**: Resource management
  - Quota enforcement
  - Usage tracking
  - Limit policies
  
- **Day 3-4**: Security layer
  - Permission system
  - Isolation enforcement
  - Audit logging
  
- **Day 5-7**: Monitoring foundation
  - Metrics collection
  - Log aggregation
  - Basic dashboards

### Phase 3: Workflow Engine (Week 6)

- **Day 1-3**: Workflow engine core
  - Step executor
  - State persistence
  - Checkpoint system
  
- **Day 4-5**: Workflow patterns
  - Sequential execution
  - Parallel execution
  - Conditional branching
  
- **Day 6-7**: Application workflows
  - Workflow templates
  - Error handling
  - Retry policies

### Phase 4: Developer Experience (Week 7)

- **Day 1-3**: CLI tools
  - `ksi deploy app.yaml`
  - `ksi list apps`
  - `ksi logs <app-id>`
  - `ksi exec <app-id> <command>`
  
- **Day 2-4**: Application templates
  - Starter templates
  - Template generator
  - Documentation
  
- **Day 5-7**: Development tools
  - Local development mode
  - Hot reload support
  - Debugging utilities

### Phase 5: Production Features (Week 8)

- **Day 1-2**: Operational tools
  - Backup/restore
  - Migration utilities
  - Health endpoints
  
- **Day 3-4**: Performance optimization
  - Query optimization
  - Caching layer
  - Connection pooling
  
- **Day 5-7**: Final integration
  - End-to-end testing
  - Performance testing
  - Documentation completion

## Migration Strategy

### Zero-Downtime Migration Path

#### Stage 1: Parallel Deployment
```python
# Run new platform alongside existing daemon
class DualModeCoordinator:
    def __init__(self):
        self.legacy_daemon = LegacyDaemon()
        self.platform = KSIPlatform()
        
    async def handle_request(self, request):
        # Route to appropriate system
        if request.is_platform_app():
            return await self.platform.handle(request)
        else:
            return await self.legacy_daemon.handle(request)
```

#### Stage 2: Legacy Wrapper
```yaml
# Wrap existing functionality as platform app
apiVersion: ksi/v1
kind: Application
metadata:
  name: legacy-ksi-daemon
  version: legacy
  
spec:
  agents:
    - name: legacy-daemon
      type: external
      endpoint: "unix:///tmp/ksi.sock"
      
  compatibility:
    mode: legacy
    preserve_paths: true
```

#### Stage 3: Gradual Migration
1. Deploy new applications on platform
2. Migrate existing agents one by one
3. Convert workflows to platform model
4. Retire legacy daemon

#### Stage 4: Data Migration
```python
async def migrate_legacy_data():
    """Migrate existing data to platform model"""
    
    # Create default application for legacy data
    app_id = await create_application({
        "name": "legacy-migrated",
        "version": "1.0.0"
    })
    
    # Migrate claude logs
    for log_file in Path("claude_logs").glob("*.jsonl"):
        new_path = f"applications/{app_id}/claude_logs/{log_file.name}"
        shutil.move(log_file, new_path)
        
    # Update database references
    await db.execute("""
        UPDATE messages SET app_id = ? WHERE app_id IS NULL
    """, app_id)
```

## Operational Excellence

### Deployment Architecture

```yaml
# Production deployment with systemd
[Unit]
Description=KSI Platform
After=network.target

[Service]
Type=notify
User=ksi
Group=ksi
WorkingDirectory=/opt/ksi
Environment="KSI_ENV=production"
Environment="DATABASE_URL=sqlite:///var/lib/ksi/ksi.db"
ExecStart=/opt/ksi/venv/bin/uvicorn ksi.platform:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/ksi

[Install]
WantedBy=multi-user.target
```

### Backup and Recovery

```python
class BackupManager:
    """Automated backup and recovery"""
    
    async def create_backup(self) -> str:
        """Create platform backup"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = Path(f"backups/{timestamp}")
        backup_dir.mkdir(parents=True)
        
        # Backup SQLite database
        async with aiosqlite.connect("ksi.db") as source:
            async with aiosqlite.connect(backup_dir / "ksi.db") as backup:
                await source.backup(backup)
                
        # Backup application files
        for app_dir in Path("applications").iterdir():
            if app_dir.is_dir():
                shutil.copytree(
                    app_dir, 
                    backup_dir / "applications" / app_dir.name
                )
                
        # Create backup manifest
        manifest = {
            "timestamp": timestamp,
            "version": get_platform_version(),
            "applications": await self.get_application_list(),
            "size": get_directory_size(backup_dir)
        }
        
        with open(backup_dir / "manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)
            
        return str(backup_dir)
```

### Performance Optimization

```sql
-- SQLite optimizations for platform workload
PRAGMA journal_mode = WAL;           -- Write-ahead logging
PRAGMA synchronous = NORMAL;         -- Balance safety/speed
PRAGMA cache_size = -64000;         -- 64MB cache
PRAGMA temp_store = MEMORY;         -- Memory for temp tables
PRAGMA mmap_size = 268435456;      -- 256MB memory-mapped I/O
PRAGMA wal_autocheckpoint = 1000;  -- Checkpoint every 1000 pages

-- Analyze tables periodically
ANALYZE;

-- Vacuum monthly
VACUUM;
```

### Monitoring and Alerting

```python
class PlatformMonitor:
    """Platform health monitoring"""
    
    async def health_check(self) -> HealthStatus:
        """Comprehensive health check"""
        
        checks = {
            "database": await self.check_database(),
            "disk_space": await self.check_disk_space(),
            "message_queue": await self.check_message_queue(),
            "applications": await self.check_applications(),
            "services": await self.check_services()
        }
        
        overall_status = "healthy" if all(checks.values()) else "unhealthy"
        
        return HealthStatus(
            status=overall_status,
            checks=checks,
            timestamp=datetime.utcnow()
        )
        
    async def check_applications(self) -> bool:
        """Check application health"""
        
        unhealthy_apps = await self.db.fetch("""
            SELECT COUNT(*) as count
            FROM applications
            WHERE status = 'failed'
        """)
        
        return unhealthy_apps[0]["count"] == 0
```

## Risk Analysis and Mitigation

### Technical Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| SQLite scaling limits | High | Medium | Sharding strategy, read replicas |
| Application isolation breach | High | Low | Strict validation, sandboxing |
| Resource exhaustion | Medium | Medium | Quotas, monitoring, alerts |
| Platform complexity | Medium | High | Excellent docs, templates |

### Architectural Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Over-abstraction | Medium | Medium | Start simple, iterate |
| Performance overhead | Medium | Low | Profiling, optimization |
| Feature creep | High | High | Strict roadmap adherence |
| Migration failures | High | Low | Rollback strategy, testing |

### Mitigation Strategies

1. **Incremental Development**
   - Build in small, tested increments
   - Get feedback early and often
   - Maintain backwards compatibility

2. **Comprehensive Testing**
   - Unit tests for all components
   - Integration tests for workflows
   - Chaos testing for resilience
   - Performance benchmarks

3. **Operational Excellence**
   - Monitoring from day one
   - Clear runbooks
   - Automated recovery
   - Regular disaster recovery drills

## Success Metrics

### Platform Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Code complexity | 18,500 LOC | 12,000 LOC | cloc + platform |
| Test coverage | Unknown | >85% | pytest-cov |
| Deploy time | Hours | <5 minutes | Time to deploy app |
| MTTR | Hours | <30 minutes | Incident resolution |

### Application Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Apps deployed | >10 in first month | Platform metrics |
| Developer satisfaction | >4/5 | Survey |
| Time to first app | <1 hour | User studies |
| Platform stability | 99.9% uptime | Monitoring |

### Business Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Adoption rate | 5 teams in 3 months | Usage data |
| Development velocity | 2x improvement | Sprint metrics |
| Operational cost | 50% reduction | Time tracking |
| Innovation rate | 1 new app/week | App registry |

## Future Directions

### Near-term (3-6 months)
1. **Distributed Deployment**
   - Multi-node support
   - SQLite replication
   - Geographic distribution

2. **Advanced Workflows**
   - Visual workflow designer
   - Complex DAG support
   - Human-in-the-loop

3. **Marketplace**
   - Public app registry
   - One-click deployment
   - Revenue sharing

### Medium-term (6-12 months)
1. **Cloud Native**
   - Kubernetes operator
   - Cloud provider integrations
   - Managed service offering

2. **Enterprise Features**
   - SAML/OIDC support
   - Audit compliance
   - Data residency

3. **AI Advancements**
   - Multi-model support
   - Custom model integration
   - Training integration

### Long-term (12+ months)
1. **Ecosystem Growth**
   - Developer certification
   - Partner program
   - Industry solutions

2. **Platform Evolution**
   - GraphQL API
   - Real-time collaboration
   - No-code builders

## Conclusion

This unified architecture plan transforms KSI from a capable multi-agent system into a comprehensive platform for building AI-native applications. By combining the operational simplicity of SQLite with a declarative application model, we create a system that is both powerful and approachable.

The key insights:
1. **SQLite + files** provides the perfect foundation for a platform
2. **Declarative manifests** make AI applications accessible to all developers
3. **Platform services** handle the complexity, letting developers focus on value
4. **Incremental migration** ensures smooth transition from current system

The result will be a platform that democratizes AI application development while maintaining the operational simplicity that makes KSI special. This positions KSI as the foundational platform for the AI-agent era, much like Kubernetes became for containers.

Total implementation time: 8 weeks  
Expected outcome: 10x easier AI application development  
Risk level: Moderate, with clear mitigation strategies

The future of AI applications is declarative, and KSI will lead the way.