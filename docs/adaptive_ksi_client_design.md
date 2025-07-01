# Adaptive KSI Client Design

## Overview

This document outlines the design for a new, adaptive `ksi_client` that:
1. **Self-bootstraps** - Automatically starts/restarts the daemon if needed
2. **Self-discovers** - Dynamically discovers available events and permissions
3. **Zero maintenance** - No hardcoded event lists to maintain
4. **Type-safe** - Generates type stubs from discovery
5. **Secure by default** - Permission-aware with restricted profiles for chat

## Architecture

### 1. Bootstrap Layer

The client has minimal hardcoded bootstrap functionality:

```python
# Only these are hardcoded
BOOTSTRAP_EVENTS = {
    "system:health",      # Check connection
    "system:discover",    # Discover all other events
    "system:help",        # Get detailed event help
}

BOOTSTRAP_TIMEOUT = 5.0  # seconds
```

### 2. Daemon Management

The client incorporates daemon control functionality:

```python
class DaemonManager:
    """Manages daemon lifecycle - start, stop, health checks"""
    
    def __init__(self):
        self.venv_path = Path(".venv")
        self.daemon_script = "ksi-daemon.py"
        self.pid_file = Path("var/run/ksi_daemon.pid")
        self.socket_path = Path("var/run/daemon.sock")
        
    async def ensure_daemon_running(self) -> bool:
        """Ensure daemon is running and healthy"""
        # 1. Check if PID file exists and process is running
        # 2. If not, activate venv and start daemon
        # 3. Wait for daemon to be healthy
        # 4. Return success/failure
```

### 3. Adaptive Event Client

```python
class EventClient:
    """
    Self-discovering event client with automatic daemon management.
    
    Usage:
        async with EventClient() as client:
            # Daemon automatically started if needed
            # Events automatically discovered
            
            # Use discovered events with namespace syntax
            response = await client.completion.async(
                prompt="Hello!",
                agent_config={"permission_profile": "restricted"}
            )
    """
    
    def __init__(self, 
                 auto_start_daemon: bool = True,
                 discovery_cache_ttl: int = 3600):
        self.daemon_manager = DaemonManager() if auto_start_daemon else None
        self._event_cache = {}
        self._permission_cache = {}
        self._discovered = False
        self._cache_ttl = discovery_cache_ttl
        
    async def __aenter__(self):
        # 1. Ensure daemon is running (if auto_start enabled)
        if self.daemon_manager:
            if not await self.daemon_manager.ensure_daemon_running():
                raise KSIConnectionError("Failed to start daemon")
        
        # 2. Connect to socket
        await self.connect()
        
        # 3. Discover available events
        await self.discover()
        
        return self
        
    async def __aexit__(self, *args):
        await self.disconnect()
```

### 4. Dynamic Event Discovery

```python
class EventClient:
    async def discover(self):
        """Discover all available events and permissions"""
        try:
            # Discover all events
            response = await self._send_bootstrap_event("system:discover", {})
            self._event_cache = response["events"]
            
            # Discover permission profiles
            if "permission:list_profiles" in self._flatten_events():
                response = await self.send_event("permission:list_profiles", {})
                self._permission_cache = response.get("profiles", {})
            
            self._discovered = True
            self._cache_time = time.time()
            
        except Exception as e:
            logger.warning(f"Discovery failed: {e}")
            # Client still works with bootstrap events only
```

### 5. Dynamic Attribute Access

```python
class EventNamespace:
    """Dynamic namespace for events like client.completion.async()"""
    
    def __init__(self, client: 'EventClient', namespace: str):
        self._client = client
        self._namespace = namespace
        
    def __getattr__(self, event_name: str):
        """Create event method dynamically"""
        full_event = f"{self._namespace}:{event_name}"
        
        # Check if event exists in cache
        if self._client._discovered:
            if not self._client.has_event(full_event):
                raise AttributeError(f"Unknown event: {full_event}")
        
        async def event_method(**kwargs):
            # Validate parameters if schema available
            if self._client._discovered:
                self._client._validate_params(full_event, kwargs)
            
            return await self._client.send_event(full_event, kwargs)
        
        # Add docstring from discovery
        event_method.__doc__ = self._client.get_event_doc(full_event)
        event_method.__name__ = event_name
        
        return event_method

class EventClient:
    def __getattr__(self, namespace: str):
        """Access event namespaces dynamically"""
        return EventNamespace(self, namespace)
```

### 6. Permission-Aware Helpers

```python
class EventClient:
    def get_permission_profiles(self) -> List[str]:
        """Get available permission profiles"""
        return list(self._permission_cache.keys())
    
    def get_profile_tools(self, profile: str) -> Dict[str, List[str]]:
        """Get tools allowed/disallowed for a profile"""
        if profile not in self._permission_cache:
            raise ValueError(f"Unknown profile: {profile}")
        return self._permission_cache[profile]["tools"]
    
    async def create_chat_completion(self, 
                                   prompt: str,
                                   permission_profile: str = "restricted",
                                   session_id: Optional[str] = None):
        """High-level helper for secure chat completions"""
        # Validate permission profile
        if self._discovered and profile not in self._permission_cache:
            raise ValueError(f"Unknown permission profile: {profile}")
        
        return await self.completion.async(
            prompt=prompt,
            session_id=session_id,
            agent_config={
                "permission_profile": permission_profile,
                "profile": "conversationalist"
            }
        )
```

### 7. Type Stub Generation

```python
class EventClient:
    def generate_type_stubs(self, output_path: Path = None):
        """Generate .pyi files from discovered events"""
        if not self._discovered:
            raise RuntimeError("No discovery data available")
        
        output_path = output_path or Path("ksi_client/types/discovered.pyi")
        
        stub = """# Auto-generated type stubs from KSI daemon discovery
from typing import Dict, Any, Optional, List

"""
        
        # Generate namespace classes
        for namespace, events in self._event_cache.items():
            class_name = f"{namespace.title().replace(':', '')}Namespace"
            stub += f"class {class_name}:\n"
            
            for event in events:
                method_name = event["event"].split(":")[-1]
                params = self._format_stub_params(event.get("parameters", {}))
                
                stub += f'    async def {method_name}(self, {params}) -> Dict[str, Any]:\n'
                stub += f'        """{event.get("summary", "")}"""\n'
                stub += '        ...\n\n'
            
            stub += "\n"
        
        # Generate main client class
        stub += "class EventClient:\n"
        for namespace in self._event_cache:
            attr_name = namespace.replace(":", "_")
            class_name = f"{namespace.title().replace(':', '')}Namespace"
            stub += f"    {attr_name}: {class_name}\n"
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(stub)
```

### 8. Client-Side Validation

```python
class EventClient:
    def _validate_params(self, event_name: str, params: Dict[str, Any]):
        """Validate parameters against discovered schema"""
        event_info = self.get_event_info(event_name)
        if not event_info:
            return  # No schema to validate against
        
        schema = event_info.get("parameters", {})
        
        # Check required parameters
        for param_name, param_info in schema.items():
            if param_info.get("required") and param_name not in params:
                raise ValueError(f"Missing required parameter: {param_name}")
            
            # Validate types if specified
            if param_name in params and "type" in param_info:
                expected_type = param_info["type"]
                value = params[param_name]
                
                if not self._check_type(value, expected_type):
                    raise TypeError(
                        f"Parameter {param_name} expected {expected_type}, "
                        f"got {type(value).__name__}"
                    )
```

## Usage Examples

### Basic Usage with Auto-Discovery

```python
import asyncio
from ksi_client import EventClient

async def main():
    # Client automatically:
    # 1. Starts daemon if needed
    # 2. Discovers all events
    # 3. Sets up dynamic attributes
    
    async with EventClient() as client:
        # Health check (bootstrap event)
        health = await client.system.health()
        print(f"Daemon status: {health['status']}")
        
        # Completion with restricted permissions (discovered)
        response = await client.completion.async(
            prompt="Explain KSI architecture",
            agent_config={"permission_profile": "restricted"}
        )
        
        # List available permission profiles
        profiles = client.get_permission_profiles()
        print(f"Available profiles: {profiles}")
        # Output: ["restricted", "standard", "trusted", "researcher"]
        
        # Show tools for a profile
        tools = client.get_profile_tools("restricted")
        print(f"Restricted profile allows: {tools['allowed']}")
        # Output: ["Read", "Grep", "Glob", "LS"]

asyncio.run(main())
```

### Manual Daemon Control

```python
# Disable auto-start for manual control
async with EventClient(auto_start_daemon=False) as client:
    try:
        await client.connect()
    except KSIConnectionError:
        print("Please start daemon manually")
```

### Type-Safe Development

```python
# Generate type stubs after discovery
async with EventClient() as client:
    client.generate_type_stubs()
    
# Now IDEs can provide autocomplete for:
# client.completion.async(...)
# client.conversation.list(...)
# client.agent.spawn(...)
```

### Integration with ksi-chat

```python
class ChatApp:
    async def setup(self):
        # Client handles all daemon management
        self.client = EventClient()
        await self.client.__aenter__()
        
        # Display available tools in UI
        profile = "restricted"
        tools = self.client.get_profile_tools(profile)
        self.display_status(f"AI Tools: {', '.join(tools['allowed'])}")
    
    async def send_message(self, content: str):
        # Use high-level helper with secure defaults
        response = await self.client.create_chat_completion(
            prompt=content,
            permission_profile="restricted",  # No Bash access
            session_id=self.current_session_id
        )
```

## Implementation Plan

### Phase 1: Core Bootstrap (Week 1)
- [ ] Create minimal EventClient with bootstrap events only
- [ ] Implement basic socket communication
- [ ] Add DaemonManager with start/stop/health functionality
- [ ] Test auto-start behavior

### Phase 2: Discovery System (Week 2)
- [ ] Implement discovery() method
- [ ] Add event and permission caching
- [ ] Create EventNamespace for dynamic access
- [ ] Test with real daemon events

### Phase 3: Type Safety (Week 3)
- [ ] Add parameter validation
- [ ] Implement type stub generation
- [ ] Create high-level helpers (create_chat_completion)
- [ ] Generate comprehensive type stubs

### Phase 4: Integration (Week 4)
- [ ] Update ksi-chat to use new client
- [ ] Remove old service layers
- [ ] Add permission display to UI
- [ ] Implement session switching with discovered events

## Benefits

1. **Zero Configuration** - Users just import and use, daemon starts automatically
2. **Future Proof** - New daemon events automatically available
3. **Type Safe** - IDE autocomplete from discovered events
4. **Secure by Default** - Permission profiles prevent dangerous operations
5. **Maintainable** - No duplicate event definitions between client and daemon
6. **Self-Documenting** - Event descriptions become docstrings and type hints

## Migration Strategy

### From Old Client
```python
# Old way (manual everything)
client = EventChatClient()
await client.connect()
response = await client.send_prompt(...)

# New way (automatic everything) 
async with EventClient() as client:
    response = await client.create_chat_completion(...)
```

### From Service Layers
```python
# Old way (service wrappers)
chat_service = ChatService()
sessions = await chat_service.list_sessions()

# New way (direct events)
async with EventClient() as client:
    sessions = await client.conversation.list()
```

## Security Considerations

1. **Default Restrictions** - Chat completions default to "restricted" profile
2. **Permission Validation** - Client validates permission profiles exist
3. **Tool Visibility** - UI shows what tools the AI can access
4. **No Bash by Default** - Restricted profile has no Bash access
5. **Daemon Isolation** - Each client connection is isolated

## Conclusion

This adaptive client design eliminates maintenance burden while providing a superior developer experience. By combining daemon management, event discovery, and type generation, we create a client that "just works" while remaining secure and type-safe.