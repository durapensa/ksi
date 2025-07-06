# KSI-Claude Code Integration Design

## Overview

This document outlines the optimal integration between Claude Code and the KSI (Knowledge System Infrastructure) daemon. The design focuses on creating a seamless interface that allows Claude Code to orchestrate complex multi-agent workflows while maintaining clean abstractions and preserving context across sessions.

## Architecture

### Core Principles

1. **Tool-Based Abstraction**: Claude Code tools wrap KSI socket protocol complexity
2. **Async-First Design**: All operations are non-blocking to support parallel execution
3. **Context Preservation**: Session state maintained across tool invocations
4. **Error Resilience**: Graceful handling of daemon restarts and network failures
5. **Type Safety**: Strong typing for all tool parameters and responses

### Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Claude Code                          │
│  ┌─────────────────────────────────────────────────────┐  │
│  │                   Custom KSI Tools                   │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │  │
│  │  │  Agent  │ │  State  │ │ Message │ │ Monitor │  │  │
│  │  │  Spawn  │ │  Query  │ │  Send   │ │  Events │  │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘  │  │
│  └───────────────────────────┬─────────────────────────┘  │
│                              │                             │
│  ┌───────────────────────────┴─────────────────────────┐  │
│  │              KSI Client Library                     │  │
│  │  - Socket communication                             │  │
│  │  - JSON protocol handling                           │  │
│  │  - Request/response correlation                     │  │
│  └───────────────────────────┬─────────────────────────┘  │
└──────────────────────────────┼─────────────────────────────┘
                               │ Unix Socket
┌──────────────────────────────┴─────────────────────────────┐
│                         KSI Daemon                          │
│  - Agent management                                         │
│  - Event routing                                            │
│  - State persistence                                        │
└─────────────────────────────────────────────────────────────┘
```

## Tool Design Patterns

### Base Tool Class

All KSI tools inherit from a base class that handles common functionality:

```python
from typing import Dict, Any, Optional, TypedDict
import asyncio
import json
from pathlib import Path

class KSIResponse(TypedDict):
    success: bool
    data: Optional[Dict[str, Any]]
    error: Optional[str]
    request_id: Optional[str]

class KSIBaseTool:
    """Base class for all KSI-related Claude Code tools"""
    
    def __init__(self):
        self.socket_path = Path("/Users/dp/projects/ksi/var/run/daemon.sock")
        self._timeout = 30.0  # Default timeout for operations
    
    async def _send_event(self, event: str, data: Dict[str, Any]) -> KSIResponse:
        """Send event to KSI daemon and await response"""
        try:
            reader, writer = await asyncio.open_unix_connection(str(self.socket_path))
            
            # Send request
            request = json.dumps({"event": event, "data": data})
            writer.write(request.encode() + b'\n')
            await writer.drain()
            
            # Read response
            response_data = await asyncio.wait_for(
                reader.readline(), 
                timeout=self._timeout
            )
            
            writer.close()
            await writer.wait_closed()
            
            return json.loads(response_data.decode())
            
        except asyncio.TimeoutError:
            return {
                "success": False,
                "data": None,
                "error": f"Operation timed out after {self._timeout}s",
                "request_id": None
            }
        except Exception as e:
            return {
                "success": False,
                "data": None,
                "error": str(e),
                "request_id": None
            }
    
    def _validate_daemon_running(self) -> bool:
        """Check if KSI daemon is running"""
        return self.socket_path.exists()
```

### Core Tools Implementation

#### 1. Agent Spawn Tool

```python
class AgentSpawnTool(KSIBaseTool):
    """Spawn and manage KSI agents"""
    
    name = "ksi_agent_spawn"
    description = "Spawn a new KSI agent with specified profile and parameters"
    
    async def run(
        self,
        profile: str,
        prompt: str,
        model: Optional[str] = None,
        parent_request_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Spawn a new agent instance
        
        Args:
            profile: Agent profile name (e.g., 'orchestrator', 'research_lead')
            prompt: Initial prompt for the agent
            model: Optional model override (defaults to profile setting)
            parent_request_id: Parent agent's request ID for hierarchy
            session_id: Session ID for context continuation
            metadata: Additional metadata for the agent
            
        Returns:
            Dictionary containing agent_id, request_id, and spawn details
        """
        if not self._validate_daemon_running():
            raise RuntimeError("KSI daemon is not running")
        
        # Build spawn data
        spawn_data = {
            "profile": profile,
            "prompt": prompt
        }
        
        if model:
            spawn_data["model"] = model
        if parent_request_id:
            spawn_data["parent_request_id"] = parent_request_id
        if session_id:
            spawn_data["session_id"] = session_id
        if metadata:
            spawn_data["metadata"] = metadata
        
        # Send spawn event
        response = await self._send_event("agent:spawn", spawn_data)
        
        if not response["success"]:
            raise RuntimeError(f"Failed to spawn agent: {response.get('error', 'Unknown error')}")
        
        return response["data"]

# Example usage in Claude Code:
async def spawn_research_team():
    """Spawn a research team for investigating a topic"""
    tool = AgentSpawnTool()
    
    # Spawn orchestrator
    orchestrator = await tool.run(
        profile="orchestrator",
        prompt="Research the history of functional programming",
        metadata={"team": "research", "topic": "fp_history"}
    )
    
    # Spawn researchers under orchestrator
    researchers = []
    for i, focus in enumerate(["lambda_calculus", "lisp_history", "modern_fp"]):
        researcher = await tool.run(
            profile="researcher",
            prompt=f"Focus on {focus.replace('_', ' ')}",
            parent_request_id=orchestrator["request_id"],
            metadata={"focus": focus, "index": i}
        )
        researchers.append(researcher)
    
    return {
        "orchestrator": orchestrator,
        "researchers": researchers
    }
```

#### 2. State Management Tool

```python
class StateQueryTool(KSIBaseTool):
    """Query and manage shared state across agents"""
    
    name = "ksi_state_query"
    description = "Query shared state using SQL-like syntax"
    
    async def run(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a state query
        
        Args:
            query: SQL-like query string
            params: Query parameters for prepared statements
            agent_id: Optional agent ID for scoped queries
            
        Returns:
            Query results with rows and metadata
        """
        query_data = {
            "query": query,
            "params": params or {}
        }
        
        if agent_id:
            query_data["agent_id"] = agent_id
        
        response = await self._send_event("state:query", query_data)
        
        if not response["success"]:
            raise RuntimeError(f"State query failed: {response.get('error')}")
        
        return response["data"]

class StateWriteTool(KSIBaseTool):
    """Write to shared state"""
    
    name = "ksi_state_write"
    description = "Write data to shared state storage"
    
    async def run(
        self,
        table: str,
        data: Dict[str, Any],
        agent_id: Optional[str] = None,
        operation: str = "insert"
    ) -> Dict[str, Any]:
        """
        Write data to state
        
        Args:
            table: Target table name
            data: Data to write
            agent_id: Optional agent ID for attribution
            operation: Operation type (insert, update, upsert)
            
        Returns:
            Write confirmation with affected rows
        """
        write_data = {
            "table": table,
            "data": data,
            "operation": operation
        }
        
        if agent_id:
            write_data["agent_id"] = agent_id
        
        response = await self._send_event("state:write", write_data)
        
        if not response["success"]:
            raise RuntimeError(f"State write failed: {response.get('error')}")
        
        return response["data"]
```

#### 3. Agent Communication Tool

```python
class AgentMessageTool(KSIBaseTool):
    """Send messages between agents"""
    
    name = "ksi_agent_message"
    description = "Send messages to other agents in the system"
    
    async def run(
        self,
        to_agent_id: str,
        message: str,
        from_agent_id: Optional[str] = None,
        message_type: str = "text",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send a message to another agent
        
        Args:
            to_agent_id: Target agent ID
            message: Message content
            from_agent_id: Sender agent ID (if not Claude Code)
            message_type: Type of message (text, command, data)
            metadata: Additional message metadata
            
        Returns:
            Message delivery confirmation
        """
        message_data = {
            "to": to_agent_id,
            "message": message,
            "type": message_type
        }
        
        if from_agent_id:
            message_data["from"] = from_agent_id
        else:
            message_data["from"] = "claude_code"
            
        if metadata:
            message_data["metadata"] = metadata
        
        response = await self._send_event("agent:message", message_data)
        
        if not response["success"]:
            raise RuntimeError(f"Message send failed: {response.get('error')}")
        
        return response["data"]
```

#### 4. Event Monitoring Tool

```python
class EventMonitorTool(KSIBaseTool):
    """Monitor system events in real-time"""
    
    name = "ksi_event_monitor"
    description = "Monitor KSI system events with filtering"
    
    async def run(
        self,
        event_filter: Optional[str] = None,
        duration: float = 10.0,
        callback: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """
        Monitor events for a specified duration
        
        Args:
            event_filter: Regex pattern to filter events
            duration: How long to monitor (seconds)
            callback: Optional callback for real-time processing
            
        Returns:
            List of captured events
        """
        events = []
        
        try:
            reader, writer = await asyncio.open_unix_connection(str(self.socket_path))
            
            # Subscribe to events
            subscribe_request = json.dumps({
                "event": "monitor:subscribe",
                "data": {"filter": event_filter or ".*"}
            })
            writer.write(subscribe_request.encode() + b'\n')
            await writer.drain()
            
            # Monitor for duration
            end_time = asyncio.get_event_loop().time() + duration
            
            while asyncio.get_event_loop().time() < end_time:
                try:
                    # Read event with timeout
                    remaining = end_time - asyncio.get_event_loop().time()
                    if remaining <= 0:
                        break
                        
                    event_data = await asyncio.wait_for(
                        reader.readline(),
                        timeout=min(remaining, 1.0)
                    )
                    
                    if event_data:
                        event = json.loads(event_data.decode())
                        events.append(event)
                        
                        if callback:
                            await callback(event)
                            
                except asyncio.TimeoutError:
                    continue
            
            # Unsubscribe
            unsubscribe_request = json.dumps({
                "event": "monitor:unsubscribe",
                "data": {}
            })
            writer.write(unsubscribe_request.encode() + b'\n')
            await writer.drain()
            
            writer.close()
            await writer.wait_closed()
            
        except Exception as e:
            raise RuntimeError(f"Event monitoring failed: {e}")
        
        return events
```

## Agent Orchestration Strategies

### 1. Hierarchical Orchestration

```python
async def hierarchical_research(topic: str):
    """
    Orchestrate a hierarchical research team
    
    Structure:
    - Research Director
      - Literature Review Team Lead
        - Historical Researcher
        - Contemporary Researcher
      - Analysis Team Lead
        - Data Analyst
        - Theorist
    """
    spawn = AgentSpawnTool()
    state = StateWriteTool()
    
    # Create research project in state
    project_id = f"research_{topic.replace(' ', '_')}"
    await state.run(
        table="projects",
        data={
            "id": project_id,
            "topic": topic,
            "status": "active",
            "created_by": "claude_code"
        }
    )
    
    # Spawn director
    director = await spawn.run(
        profile="research_director",
        prompt=f"Lead comprehensive research on: {topic}",
        metadata={"project_id": project_id}
    )
    
    # Spawn team leads under director
    lit_lead = await spawn.run(
        profile="team_lead",
        prompt="Coordinate literature review and source gathering",
        parent_request_id=director["request_id"],
        metadata={"team": "literature", "project_id": project_id}
    )
    
    analysis_lead = await spawn.run(
        profile="team_lead",
        prompt="Coordinate data analysis and theory development",
        parent_request_id=director["request_id"],
        metadata={"team": "analysis", "project_id": project_id}
    )
    
    # Spawn researchers under team leads
    researchers = []
    
    # Literature team
    for role, prompt in [
        ("historian", "Research historical context and development"),
        ("contemporary", "Analyze current state and recent developments")
    ]:
        researcher = await spawn.run(
            profile="researcher",
            prompt=prompt,
            parent_request_id=lit_lead["request_id"],
            metadata={"role": role, "project_id": project_id}
        )
        researchers.append(researcher)
    
    # Analysis team
    for role, prompt in [
        ("data_analyst", "Analyze quantitative data and trends"),
        ("theorist", "Develop theoretical frameworks and insights")
    ]:
        researcher = await spawn.run(
            profile="researcher",
            prompt=prompt,
            parent_request_id=analysis_lead["request_id"],
            metadata={"role": role, "project_id": project_id}
        )
        researchers.append(researcher)
    
    return {
        "project_id": project_id,
        "director": director,
        "team_leads": [lit_lead, analysis_lead],
        "researchers": researchers
    }
```

### 2. Peer-to-Peer Collaboration

```python
async def peer_collaboration(problem: str, num_experts: int = 3):
    """
    Create a peer network of experts who collaborate on equal footing
    """
    spawn = AgentSpawnTool()
    message = AgentMessageTool()
    
    # Spawn expert peers
    experts = []
    for i in range(num_experts):
        expert = await spawn.run(
            profile="expert_peer",
            prompt=f"Collaborate on solving: {problem}",
            metadata={
                "peer_index": i,
                "problem": problem,
                "collaboration_mode": "peer"
            }
        )
        experts.append(expert)
    
    # Create introduction messages between all peers
    for i, expert1 in enumerate(experts):
        for j, expert2 in enumerate(experts):
            if i != j:
                await message.run(
                    to_agent_id=expert2["agent_id"],
                    from_agent_id=expert1["agent_id"],
                    message=f"Hello, I'm Expert {i}. Ready to collaborate.",
                    message_type="introduction",
                    metadata={"peer_intro": True}
                )
    
    # Send problem statement to all experts
    for expert in experts:
        await message.run(
            to_agent_id=expert["agent_id"],
            message=f"Let's solve: {problem}",
            message_type="task",
            metadata={"task_type": "collaborative_problem_solving"}
        )
    
    return {
        "problem": problem,
        "experts": experts,
        "collaboration_type": "peer_to_peer"
    }
```

### 3. Pipeline Processing

```python
async def pipeline_processing(data_source: str, stages: List[str]):
    """
    Create a processing pipeline where each agent transforms data for the next
    """
    spawn = AgentSpawnTool()
    state_write = StateWriteTool()
    state_query = StateQueryTool()
    
    # Create pipeline record
    pipeline_id = f"pipeline_{int(time.time())}"
    await state_write.run(
        table="pipelines",
        data={
            "id": pipeline_id,
            "source": data_source,
            "stages": json.dumps(stages),
            "status": "running"
        }
    )
    
    # Spawn pipeline stages
    pipeline_agents = []
    previous_agent = None
    
    for i, stage in enumerate(stages):
        agent = await spawn.run(
            profile="pipeline_processor",
            prompt=f"Process stage: {stage}",
            metadata={
                "pipeline_id": pipeline_id,
                "stage_index": i,
                "stage_name": stage,
                "previous_stage": stages[i-1] if i > 0 else "input"
            }
        )
        
        # Link to previous stage
        if previous_agent:
            await state_write.run(
                table="pipeline_links",
                data={
                    "pipeline_id": pipeline_id,
                    "from_agent": previous_agent["agent_id"],
                    "to_agent": agent["agent_id"],
                    "stage_from": i-1,
                    "stage_to": i
                }
            )
        
        pipeline_agents.append(agent)
        previous_agent = agent
    
    # Start pipeline by sending data to first agent
    if pipeline_agents:
        message = AgentMessageTool()
        await message.run(
            to_agent_id=pipeline_agents[0]["agent_id"],
            message=f"Process data from: {data_source}",
            message_type="pipeline_start",
            metadata={
                "pipeline_id": pipeline_id,
                "data_source": data_source
            }
        )
    
    return {
        "pipeline_id": pipeline_id,
        "stages": stages,
        "agents": pipeline_agents
    }
```

## State Management Approach

### Context Preservation

```python
class KSIContextManager:
    """Manages context across Claude Code sessions"""
    
    def __init__(self):
        self.state_query = StateQueryTool()
        self.state_write = StateWriteTool()
    
    async def save_session_context(
        self,
        session_id: str,
        context: Dict[str, Any]
    ) -> None:
        """Save session context for later retrieval"""
        await self.state_write.run(
            table="claude_code_sessions",
            data={
                "session_id": session_id,
                "context": json.dumps(context),
                "timestamp": datetime.utcnow().isoformat(),
                "status": "active"
            },
            operation="upsert"
        )
    
    async def load_session_context(
        self,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Load previously saved session context"""
        result = await self.state_query.run(
            query="SELECT context FROM claude_code_sessions WHERE session_id = :session_id",
            params={"session_id": session_id}
        )
        
        if result["rows"]:
            return json.loads(result["rows"][0]["context"])
        return None
    
    async def get_agent_lineage(
        self,
        agent_id: str
    ) -> List[Dict[str, Any]]:
        """Get the full lineage of an agent (parents and children)"""
        # Get parents
        parents = await self.state_query.run(
            query="""
                WITH RECURSIVE lineage AS (
                    SELECT * FROM agents WHERE agent_id = :agent_id
                    UNION ALL
                    SELECT a.* FROM agents a
                    JOIN lineage l ON a.agent_id = l.parent_agent_id
                )
                SELECT * FROM lineage
            """,
            params={"agent_id": agent_id}
        )
        
        # Get children
        children = await self.state_query.run(
            query="""
                WITH RECURSIVE descendants AS (
                    SELECT * FROM agents WHERE agent_id = :agent_id
                    UNION ALL
                    SELECT a.* FROM agents a
                    JOIN descendants d ON a.parent_agent_id = d.agent_id
                )
                SELECT * FROM descendants WHERE agent_id != :agent_id
            """,
            params={"agent_id": agent_id}
        )
        
        return {
            "lineage": parents["rows"],
            "descendants": children["rows"]
        }
```

### State Synchronization

```python
class StateSync:
    """Synchronize state across multiple agents"""
    
    def __init__(self):
        self.monitor = EventMonitorTool()
        self.state_write = StateWriteTool()
    
    async def create_shared_workspace(
        self,
        workspace_id: str,
        agents: List[str]
    ) -> None:
        """Create a shared workspace for agent collaboration"""
        # Create workspace
        await self.state_write.run(
            table="workspaces",
            data={
                "id": workspace_id,
                "agents": json.dumps(agents),
                "created_at": datetime.utcnow().isoformat(),
                "status": "active"
            }
        )
        
        # Register agents to workspace
        for agent_id in agents:
            await self.state_write.run(
                table="workspace_members",
                data={
                    "workspace_id": workspace_id,
                    "agent_id": agent_id,
                    "joined_at": datetime.utcnow().isoformat()
                }
            )
    
    async def broadcast_to_workspace(
        self,
        workspace_id: str,
        message: str,
        exclude_agent: Optional[str] = None
    ) -> None:
        """Broadcast a message to all agents in a workspace"""
        query = StateQueryTool()
        msg_tool = AgentMessageTool()
        
        # Get workspace members
        members = await query.run(
            query="""
                SELECT agent_id FROM workspace_members 
                WHERE workspace_id = :workspace_id
                AND agent_id != :exclude
            """,
            params={
                "workspace_id": workspace_id,
                "exclude": exclude_agent or ""
            }
        )
        
        # Send to each member
        for member in members["rows"]:
            await msg_tool.run(
                to_agent_id=member["agent_id"],
                message=message,
                message_type="workspace_broadcast",
                metadata={"workspace_id": workspace_id}
            )
```

## Example Complex Orchestration

### Multi-Phase Research Project

```python
async def execute_research_project(topic: str, phases: List[str]):
    """
    Execute a multi-phase research project with different agent configurations per phase
    """
    context = KSIContextManager()
    spawn = AgentSpawnTool()
    monitor = EventMonitorTool()
    
    project_id = f"project_{uuid.uuid4().hex[:8]}"
    project_context = {
        "id": project_id,
        "topic": topic,
        "phases": phases,
        "current_phase": 0,
        "results": {}
    }
    
    # Save initial context
    await context.save_session_context(project_id, project_context)
    
    for phase_idx, phase in enumerate(phases):
        print(f"Starting Phase {phase_idx + 1}: {phase}")
        
        # Update context
        project_context["current_phase"] = phase_idx
        await context.save_session_context(project_id, project_context)
        
        # Phase-specific agent configuration
        if phase == "exploration":
            # Spawn multiple independent researchers
            agents = []
            for i in range(3):
                agent = await spawn.run(
                    profile="explorer",
                    prompt=f"Explore aspect {i+1} of {topic}",
                    metadata={
                        "project_id": project_id,
                        "phase": phase,
                        "role": f"explorer_{i}"
                    }
                )
                agents.append(agent)
            
            # Monitor for completion
            completion_events = []
            async def completion_handler(event):
                if event.get("type") == "agent:completed":
                    completion_events.append(event)
            
            # Wait for all explorers to complete
            await monitor.run(
                event_filter="agent:completed",
                duration=60.0,
                callback=completion_handler
            )
            
        elif phase == "synthesis":
            # Spawn synthesizer with access to exploration results
            synthesizer = await spawn.run(
                profile="synthesizer",
                prompt=f"Synthesize findings on {topic}",
                metadata={
                    "project_id": project_id,
                    "phase": phase,
                    "previous_phase": "exploration"
                }
            )
            
            # Wait for synthesis
            await asyncio.sleep(30)
            
        elif phase == "critique":
            # Spawn multiple critics
            critics = []
            for perspective in ["methodological", "theoretical", "practical"]:
                critic = await spawn.run(
                    profile="critic",
                    prompt=f"Provide {perspective} critique",
                    metadata={
                        "project_id": project_id,
                        "phase": phase,
                        "perspective": perspective
                    }
                )
                critics.append(critic)
            
            # Let critics work
            await asyncio.sleep(45)
            
        elif phase == "revision":
            # Spawn revisor to incorporate critiques
            revisor = await spawn.run(
                profile="revisor",
                prompt="Revise findings based on critiques",
                metadata={
                    "project_id": project_id,
                    "phase": phase,
                    "final": True
                }
            )
            
            # Wait for final revision
            await asyncio.sleep(30)
        
        # Collect phase results
        state_query = StateQueryTool()
        phase_results = await state_query.run(
            query="""
                SELECT * FROM agent_outputs 
                WHERE metadata->>'project_id' = :project_id
                AND metadata->>'phase' = :phase
            """,
            params={
                "project_id": project_id,
                "phase": phase
            }
        )
        
        project_context["results"][phase] = phase_results["rows"]
    
    # Save final context
    project_context["status"] = "completed"
    await context.save_session_context(project_id, project_context)
    
    return project_context
```

## Tool Registration

```python
# In Claude Code's tool registry
def register_ksi_tools():
    """Register all KSI tools with Claude Code"""
    tools = [
        AgentSpawnTool,
        StateQueryTool,
        StateWriteTool,
        AgentMessageTool,
        EventMonitorTool
    ]
    
    for tool_class in tools:
        tool = tool_class()
        register_tool(
            name=tool.name,
            description=tool.description,
            handler=tool.run,
            schema=tool.get_schema()  # Auto-generated from type hints
        )

# Tool schema generation
def get_tool_schema(tool_class):
    """Generate OpenAI-compatible tool schema from tool class"""
    import inspect
    
    sig = inspect.signature(tool_class.run)
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }
    
    for name, param in sig.parameters.items():
        if name in ['self', 'args', 'kwargs']:
            continue
            
        param_schema = {
            "type": get_json_type(param.annotation),
            "description": get_param_description(tool_class.run, name)
        }
        
        if param.default == inspect.Parameter.empty:
            parameters["required"].append(name)
        else:
            param_schema["default"] = param.default
            
        parameters["properties"][name] = param_schema
    
    return {
        "name": tool_class.name,
        "description": tool_class.description,
        "parameters": parameters
    }
```

## Best Practices

### 1. Error Handling

```python
async def robust_agent_operation(operation_func, max_retries=3):
    """Wrapper for robust agent operations with retry logic"""
    for attempt in range(max_retries):
        try:
            return await operation_func()
        except RuntimeError as e:
            if "daemon is not running" in str(e):
                # Try to start daemon
                subprocess.run(["./daemon_control.py", "start"], check=True)
                await asyncio.sleep(2)
            elif attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            else:
                raise
```

### 2. Batch Operations

```python
async def batch_spawn_agents(profiles_and_prompts: List[Tuple[str, str]]):
    """Efficiently spawn multiple agents in parallel"""
    spawn = AgentSpawnTool()
    
    tasks = [
        spawn.run(profile=profile, prompt=prompt)
        for profile, prompt in profiles_and_prompts
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    successful = []
    failed = []
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            failed.append((profiles_and_prompts[i], result))
        else:
            successful.append(result)
    
    return {
        "successful": successful,
        "failed": failed
    }
```

### 3. Context Preservation

```python
class ClaudeCodeKSISession:
    """Manages a complete Claude Code + KSI session"""
    
    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or f"cc_ksi_{uuid.uuid4().hex[:8]}"
        self.context_manager = KSIContextManager()
        self.active_agents = []
        self.workspace_id = None
    
    async def __aenter__(self):
        # Load or create session context
        context = await self.context_manager.load_session_context(self.session_id)
        if context:
            self.active_agents = context.get("active_agents", [])
            self.workspace_id = context.get("workspace_id")
        else:
            # Create new workspace
            self.workspace_id = f"workspace_{self.session_id}"
            sync = StateSync()
            await sync.create_shared_workspace(self.workspace_id, [])
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Save session state
        await self.context_manager.save_session_context(
            self.session_id,
            {
                "active_agents": self.active_agents,
                "workspace_id": self.workspace_id,
                "last_active": datetime.utcnow().isoformat()
            }
        )
    
    async def spawn_agent(self, profile: str, prompt: str, **kwargs) -> Dict[str, Any]:
        """Spawn an agent within this session context"""
        spawn = AgentSpawnTool()
        
        # Add session metadata
        metadata = kwargs.get("metadata", {})
        metadata.update({
            "session_id": self.session_id,
            "workspace_id": self.workspace_id
        })
        kwargs["metadata"] = metadata
        
        # Spawn agent
        agent = await spawn.run(profile=profile, prompt=prompt, **kwargs)
        
        # Track in session
        self.active_agents.append(agent["agent_id"])
        
        # Add to workspace
        sync = StateSync()
        await sync.state_write.run(
            table="workspace_members",
            data={
                "workspace_id": self.workspace_id,
                "agent_id": agent["agent_id"],
                "joined_at": datetime.utcnow().isoformat()
            }
        )
        
        return agent
```

## Future Enhancements

### 1. Streaming Responses
- Implement streaming for long-running agent operations
- Real-time progress updates for complex orchestrations

### 2. Advanced Monitoring
- Visual agent hierarchy display
- Real-time collaboration visualization
- Performance metrics and bottleneck detection

### 3. Template Library
- Pre-built orchestration templates
- Reusable agent team configurations
- Domain-specific agent profiles

### 4. Integration Points
- Direct file system access for agents
- External API integration tools
- Database connection pooling

## Conclusion

This integration design provides Claude Code with powerful capabilities to orchestrate complex multi-agent workflows through KSI. The tool-based abstraction maintains clean separation of concerns while providing full access to KSI's capabilities. The patterns shown here enable everything from simple agent spawning to complex multi-phase research projects with sophisticated state management and context preservation.

The key to successful integration is maintaining the event-driven architecture while providing synchronous-feeling tools that Claude Code can use naturally. This design achieves that balance while remaining extensible for future enhancements.