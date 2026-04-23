# Profile Discovery System Design

> **Implementation Status**: See [PROFILE_DISCOVERY_IMPLEMENTATION_STATUS.md](./PROFILE_DISCOVERY_IMPLEMENTATION_STATUS.md) for current progress and known issues.

## Executive Summary

This document outlines the design and implementation plan for a new profile discovery system that leverages Git for storage, the state system for metadata indexing (using EAV pattern), and provides specialized event primitives for profile management.

## Current State Analysis

### Existing Systems
- **Git Storage**: Profiles stored in `var/lib/compositions/profiles/`
- **SQLite Index**: Redundant composition_index.py with full metadata
- **State System**: Used for runtime agent communication, not profiles
- **Profile Loading**: Direct file access without discovery

### Problems
1. **Over-specified base profiles**: Mixing persona override with domain knowledge
2. **No systematic discovery**: Agents can't find appropriate profiles
3. **Redundant storage**: SQLite duplicates Git + potential state metadata
4. **Poor composability**: Monolithic profiles instead of modular components

## Proposed Architecture

### Storage Layers

#### 1. Git Repository (Source of Truth)
```
var/lib/compositions/
├── profiles/
│   ├── provider_base/     # Minimal LLM-specific bases
│   │   ├── claude_base.yaml
│   │   ├── gpt4_base.yaml
│   │   └── gemini_base.yaml
│   ├── system/            # KSI system profiles
│   │   ├── single_agent.yaml
│   │   ├── multi_agent.yaml
│   │   └── orchestrator.yaml
│   ├── domain/            # Domain-specific profiles
│   │   ├── research/
│   │   ├── analysis/
│   │   └── synthesis/
│   └── experimental/      # Testing profiles
├── capabilities/          # Capability definitions
│   ├── base.yaml
│   ├── agent_messaging.yaml
│   └── orchestration.yaml
└── .git/                  # Version control
```

#### 2. State System (Discovery Index)

Using **EAV (Entity-Attribute-Value)** pattern for flexible querying:

```python
# Entity format: "profile:{category}/{name}"
# Example: "profile:system/orchestrator"

# Attributes stored separately:
("profile:system/orchestrator", "name", "orchestrator")
("profile:system/orchestrator", "category", "system")
("profile:system/orchestrator", "extends", "system/multi_agent")
("profile:system/orchestrator", "capability", "orchestration")
("profile:system/orchestrator", "capability", "agent_messaging")
("profile:system/orchestrator", "tag", "system")
("profile:system/orchestrator", "tag", "coordinator")
("profile:system/orchestrator", "git_ref", "v2.0.0")
("profile:system/orchestrator", "file_hash", "sha256:abc123...")
("profile:system/orchestrator", "compatible_provider", "claude-3-*")
("profile:system/orchestrator", "compatible_provider", "claude-4-*")
```

### Profile Event Primitives

#### Discovery Events

```python
# List all profiles
{
  "event": "profile:list",
  "data": {
    "category": "system",  # Optional filter
    "limit": 10
  }
}

# Discover profiles by attributes
{
  "event": "profile:discover",
  "data": {
    "where": {
      "capability": "orchestration",
      "compatible_provider": "claude-4-*"
    },
    "include_inherited": true  # Include inherited capabilities
  }
}

# Get specific profile metadata
{
  "event": "profile:get_metadata",
  "data": {
    "name": "system/orchestrator",
    "attributes": ["extends", "capabilities", "git_ref"]
  }
}

# Resolve inheritance chain
{
  "event": "profile:resolve_inheritance",
  "data": {
    "name": "domain/research/literature_analyst"
  }
}
# Returns: ["literature_analyst", "research_base", "multi_agent", "single_agent", "claude_base"]
```

#### Management Events

```python
# Register/update profile in index
{
  "event": "profile:register",
  "data": {
    "name": "system/orchestrator",
    "path": "profiles/system/orchestrator.yaml",
    "attributes": {
      "category": "system",
      "extends": "system/multi_agent",
      "capabilities": ["orchestration", "agent_messaging"],
      "tags": ["system", "coordinator"],
      "git_ref": "HEAD"
    }
  }
}

# Compose profile (with inheritance resolution)
{
  "event": "profile:compose",
  "data": {
    "name": "domain/research/literature_analyst",
    "variables": {
      "focus_area": "machine learning"
    }
  }
}

# Validate profile
{
  "event": "profile:validate",
  "data": {
    "name": "system/orchestrator"
  }
}
```

## Capability Model

### Definition
A capability represents a cohesive set of permissions and knowledge:

```yaml
# capabilities/orchestration.yaml
name: orchestration
extends: agent_messaging
description: Multi-agent orchestration capabilities

permissions:
  events:
    - agent:spawn
    - agent:terminate
    - orchestration:*
    - monitor:get_status
  claude_tools: []  # No Claude tools needed
  mcp_servers: []   # No MCP servers needed

knowledge:
  instructions: |
    ## Orchestration Patterns
    
    Spawn specialized agent:
    {"event": "agent:spawn", "data": {"profile": "domain/research", "prompt": "task"}}
    
    Monitor agent status:
    {"event": "monitor:get_status", "data": {"include_agents": true}}
    
  examples:
    - name: "Spawn research team"
      code: |
        {"event": "agent:spawn", "data": {"profile": "research_lead", "prompt": "Coordinate literature review on transformers"}}
        {"event": "agent:spawn", "data": {"profile": "research_analyst", "prompt": "Analyze recent papers"}}
```

### Capability Resolution
When a profile declares `capabilities: [orchestration]`:
1. System loads capability definition
2. Grants all permissions recursively (including inherited)
3. Injects knowledge into profile instructions
4. Validates agent has required permissions at spawn time

## Implementation Plan

### Phase 1: State System Integration (Week 1)

#### 1.1 Create Profile Entity Type
```python
# In state_service.py or new profile_state.py
PROFILE_ENTITY_TYPE = "agent_profile"

# Standard attributes for profiles
PROFILE_ATTRIBUTES = {
    "name": "string",
    "category": "string", 
    "extends": "string",
    "capability": "string[]",
    "tag": "string[]",
    "git_ref": "string",
    "file_hash": "string",
    "compatible_provider": "string[]",
    "version": "string",
    "indexed_at": "timestamp"
}
```

#### 1.2 Profile-Specific State Events
```python
@event_handler("profile:set_attribute")
async def handle_set_attribute(data):
    """Set a single attribute on a profile"""
    profile_id = f"profile:{data['name']}"
    attribute = data['attribute']
    value = data['value']
    
    # Store in EAV style
    await state_manager.set_attribute(profile_id, attribute, value)

@event_handler("profile:get_attributes") 
async def handle_get_attributes(data):
    """Get specific attributes for a profile"""
    profile_id = f"profile:{data['name']}"
    attributes = data.get('attributes', [])
    
    # Retrieve EAV style
    return await state_manager.get_attributes(profile_id, attributes)

@event_handler("profile:query_by_attribute")
async def handle_query_by_attribute(data):
    """Find profiles with specific attribute values"""
    # e.g. Find all profiles with capability="orchestration"
    attribute = data['attribute']
    value = data['value']
    
    return await state_manager.query_entities_by_attribute(
        entity_type=PROFILE_ENTITY_TYPE,
        attribute=attribute,
        value=value
    )
```

### Phase 2: Profile Service Module (Week 1-2)

Create `ksi_daemon/profile/profile_service.py`:

```python
@event_handler("profile:discover")
async def handle_discover(data):
    """Smart profile discovery with multi-attribute filtering"""
    where = data.get('where', {})
    include_inherited = data.get('include_inherited', False)
    
    # Build EAV query
    candidates = set()
    for attr, value in where.items():
        matches = await state_manager.query_by_attribute(
            PROFILE_ENTITY_TYPE, attr, value
        )
        if candidates:
            candidates &= matches
        else:
            candidates = matches
    
    # Resolve inheritance if requested
    if include_inherited:
        # Expand to include parent profiles
        pass
    
    return list(candidates)

@event_handler("profile:rebuild_index")
async def handle_rebuild_index(data):
    """Scan Git repository and update state index"""
    profiles_dir = Path(config.compositions_dir) / "profiles"
    
    for yaml_file in profiles_dir.rglob("*.yaml"):
        profile_data = load_yaml_file(yaml_file)
        
        # Extract metadata
        name = profile_data['name']
        category = str(yaml_file.parent.relative_to(profiles_dir))
        
        # Register in state system (EAV style)
        profile_id = f"profile:{category}/{name}"
        
        # Set each attribute individually
        await emit("profile:set_attribute", {
            "name": f"{category}/{name}",
            "attribute": "name", 
            "value": name
        })
        
        await emit("profile:set_attribute", {
            "name": f"{category}/{name}",
            "attribute": "category",
            "value": category  
        })
        
        # Handle multi-value attributes
        for capability in profile_data.get('capabilities', []):
            await emit("profile:set_attribute", {
                "name": f"{category}/{name}",
                "attribute": "capability",
                "value": capability
            })
```

### Phase 3: Capability System (Week 2)

#### 3.1 Capability Definition Loader
```python
class CapabilityDefinition:
    name: str
    extends: Optional[str]
    permissions: Dict[str, List[str]]
    knowledge: Dict[str, str]
    
    def resolve_permissions(self) -> Dict[str, List[str]]:
        """Recursively resolve all permissions including inherited"""
        pass

@event_handler("capability:load")
async def handle_load_capability(data):
    """Load and resolve a capability definition"""
    name = data['name']
    path = Path(config.compositions_dir) / "capabilities" / f"{name}.yaml"
    
    cap_data = load_yaml_file(path)
    capability = CapabilityDefinition(**cap_data)
    
    # Cache in memory
    _capability_cache[name] = capability
    
    return capability.to_dict()
```

#### 3.2 Profile-Capability Integration
```python
@event_handler("profile:resolve_capabilities")  
async def handle_resolve_capabilities(data):
    """Resolve all capabilities for a profile including inherited"""
    profile_name = data['name']
    
    # Get profile's declared capabilities
    capabilities = await emit("profile:get_attributes", {
        "name": profile_name,
        "attributes": ["capability"]
    })
    
    # Resolve each capability
    resolved = {}
    for cap_name in capabilities:
        cap = await emit("capability:load", {"name": cap_name})
        resolved[cap_name] = cap
    
    # Merge permissions and knowledge
    return merge_capabilities(resolved)
```

### Phase 4: Migration and Cleanup (Week 2-3)

#### 4.1 Migration Script
```python
# scripts/migrate_profiles_v2.py

async def migrate():
    """Migrate existing profiles to new structure"""
    
    # 1. Archive current state
    subprocess.run(["git", "tag", "archive/pre-profile-reorg-2025-01-16"])
    
    # 2. Reorganize directory structure
    reorganize_profiles()
    
    # 3. Split monolithic profiles
    for profile in find_monolithic_profiles():
        base, domain = split_profile(profile)
        save_profile(base, "provider_base")
        save_profile(domain, "system")
    
    # 4. Rebuild index in state system
    await emit("profile:rebuild_index")
    
    # 5. Remove SQLite database
    Path("var/lib/compositions.db").unlink(missing_ok=True)
    
    # 6. Update orchestrations to use new names
    update_orchestration_references()
```

#### 4.2 Testing Strategy
```python
# tests/test_profile_discovery.py

async def test_eav_storage():
    """Test EAV attribute storage and retrieval"""
    await emit("profile:set_attribute", {
        "name": "test/example",
        "attribute": "capability", 
        "value": "orchestration"
    })
    
    # Query by attribute
    results = await emit("profile:query_by_attribute", {
        "attribute": "capability",
        "value": "orchestration"
    })
    
    assert "profile:test/example" in results

async def test_profile_discovery():
    """Test multi-attribute discovery"""
    results = await emit("profile:discover", {
        "where": {
            "capability": "orchestration",
            "compatible_provider": "claude-4-*"
        }
    })
    
    assert len(results) > 0
    assert all("orchestration" in r['capabilities'] for r in results)
```

### Phase 5: Documentation and Orchestrator Updates (Week 3)

#### 5.1 Update Orchestrator Profiles
```yaml
# profiles/system/orchestrator.yaml
name: orchestrator
extends: multi_agent
capabilities: [orchestration]

prompt: |
  ## Profile Discovery
  
  Find profiles by capability:
  {"event": "profile:discover", "data": {"where": {"capability": "research"}}}
  
  List profiles in category:
  {"event": "profile:list", "data": {"category": "domain/research"}}
  
  Get profile details:
  {"event": "profile:get_metadata", "data": {"name": "research_analyst", "attributes": ["extends", "capabilities"]}}
```

#### 5.2 Migration Guide
- Document new profile URI scheme
- Provide examples of discovery queries
- Show capability definition examples
- Migration checklist for existing profiles

## Benefits

1. **Single Source of Truth**: Git manages all profile files
2. **Flexible Querying**: EAV pattern allows rich attribute queries
3. **Clear Abstractions**: Capabilities encapsulate permissions + knowledge
4. **Event-Driven**: Profile changes can trigger updates
5. **Future-Proof**: Easy to add new attributes without schema changes

## Timeline

- **Week 1**: State system integration, basic profile events
- **Week 2**: Profile service, capability system
- **Week 3**: Migration, testing, documentation
- **Week 4**: Buffer for issues, optimization

## Success Criteria

1. All profiles migrated to new structure
2. SQLite database removed
3. Profile discovery working via state system
4. Orchestrators can discover and spawn appropriate agents
5. No regression in existing functionality