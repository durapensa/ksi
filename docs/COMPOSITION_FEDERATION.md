# Composition Federation Architecture

## Vision: Distributed Composition Ecosystem

Think package manager meets git submodules for AI compositions.

### Repository Relationships

```yaml
# In repository metadata: .ksi/repo.yaml
repositories:
  upstream:
    - url: "https://github.com/ksi-core/compositions.git"
      branch: "stable"
      prefix: "core"
      
  peers:
    - url: "https://github.com/ai-research-lab/compositions.git" 
      branch: "main"
      prefix: "research"
      trust_level: "verify"  # vs "trust"
      
  forks:
    - url: "https://github.com/ourteam/ksi-compositions.git"
      branch: "experimental"
      prefix: "experimental"

composition_references:
  # Cross-repository references
  "core:base_agent": "pin:v1.2.0"      # Pin to specific version
  "research:analyst": "track:latest"    # Track latest
  "experimental:*": "local"             # All experimental compositions
```

### Cross-Repository Composition References

```yaml
# In our local composition
name: "advanced_researcher"
type: "profile" 
extends: "research:base_researcher"    # From research repo
components:
  - name: "core_skills"
    composition: "core:analyst_skills"  # From core repo
  - name: "experimental_tools"
    composition: "experimental:new_tools" # From experimental
```

### Repository Sync Strategy

```python
class RepositoryFederation:
    """Manages many-to-many repository relationships"""
    
    async def sync_federation(self):
        """Smart sync based on dependency graph"""
        # 1. Sync upstream first (dependencies)
        # 2. Sync peers in parallel (independent)  
        # 3. Sync forks last (may depend on others)
        
    async def resolve_reference(self, ref: str):
        """Resolve cross-repo references on-demand"""
        # "research:analyst" -> load from research repo
        # Handle version pinning, conflicts, etc.
```

## Agent-Driven Loading Patterns

```python
# Orchestrator agent loading strategy
class OrchestrationAgent:
    async def plan_debate(self, topic):
        # Agent decides what it needs
        debate_compositions = await self.composition_service.load_tree(
            "orchestrations:debate", 
            include_profiles=True,
            include_prompts=True
        )
        
        # Agent gets everything and makes intelligent decisions
        for pattern in debate_compositions.values():
            if self.matches_topic(pattern, topic):
                return await self.customize_pattern(pattern, topic)
```

## Benefits of No-Cache Approach

1. **Simplicity**: No cache invalidation logic
2. **Consistency**: Always fresh from source
3. **Memory efficiency**: Only agents hold what they need
4. **Agent intelligence**: Agents optimize their own loading
5. **Development speed**: No cache warming, no stale data

## Implementation Priority

1. **Phase 1**: Index-only service (no cache)
2. **Phase 2**: Bulk loading operations for agents  
3. **Phase 3**: Single-repository system (current)
4. **Phase 4**: Multi-repository federation (future)