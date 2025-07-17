# Progressive Component System

A Docker-inspired approach to component composition in KSI, enabling simple markdown files to progressively enhance into complex compositional structures.

## Overview

The Progressive Component System allows components to remain simple markdown files by default while supporting optional frontmatter for advanced composition features. This creates a natural progression from simple content to complex hierarchical compositions.

## Design Principles

1. **Progressive Enhancement**: Start simple, add complexity only when needed
2. **Backward Compatibility**: Existing markdown components work unchanged
3. **Auto-Detection**: System automatically detects component type
4. **Recursive Composition**: Components can compose other components
5. **Unified Model**: Same composition rules apply at all levels

## Component Types

### 1. Simple Markdown (Default)
Pure content files with no composition features:
```markdown
# My Component

This is just content. No variables, no mixins, no complexity.
```

### 2. Enhanced Markdown (With Frontmatter)
Markdown files with YAML frontmatter for composition:
```markdown
---
extends: components/base_instruction.md
mixins:
  - components/{{style}}_personality.md
  - components/common/error_handling.md
variables:
  style:
    type: string
    default: professional
    allowed_values: [professional, casual, technical]
  error_mode:
    type: string
    default: verbose
---
# {{title|Default Title}}

Enhanced content that can use variables and mix in other components.

{{base_content}}
```

### 3. Full YAML Components (Maximum Power)
Complete composition definitions (future enhancement):
```yaml
name: complex_orchestrator_instruction
type: component
version: 1.0.0
extends: components/orchestration_base
mixins:
  - components/error_handling/{{error_mode}}.md
  - components/capabilities/{{capability_level}}.yaml
variables:
  error_mode:
    type: string
    default: standard
  capability_level:
    type: string
    default: advanced
conditions:
  - condition: "capability_level == 'basic'"
    mixins:
      - components/basic_limits.md
content: |
  # Advanced Orchestrator Instructions
  
  {{base_content}}
  
  ## Your specific capabilities:
  {{capability_instructions}}
```

## Implementation Phases

### Phase 1: Auto-Detection (Current)
- Modify `composition:get_component` to detect and parse frontmatter
- Return structured data including metadata and content
- Maintain backward compatibility with simple markdown

### Phase 2: Enhanced Creation
- Update `composition:create_component` to validate frontmatter
- Check that referenced mixins exist
- Validate variable definitions
- Store metadata appropriately

### Phase 3: Rendering Support ✅ COMPLETED
- Implement recursive mixin resolution
- Apply variable substitution at render time
- Handle circular dependency detection
- Support conditional mixins
- Performance testing with deep inheritance (up to 10 levels)

### Phase 4: KSI System Integration
- Event-driven component updates and notifications
- Orchestration pattern generation from component hierarchies
- Component-based agent spawning and profile management
- Integration with existing KSI monitoring and state systems
- Component versioning and lifecycle management

### Phase 5: SQLite-Backed Composition Index

#### Overview
Fix and enhance the existing SQLite composition index to actually serve as the source of truth for queries, aligning with KSI's architecture pattern where databases handle discovery and files store content.

#### Core Principle
**The database should be the source of truth for queries**, not the filesystem. Files are only accessed for:
- Initial indexing
- Content retrieval when specifically requested
- Change detection

#### Implementation Approach

##### 1. Fix Existing SQLite Index
The database schema exists in `composition_index.py` but is underutilized:
- Currently: Only stores basic metadata, queries still load files
- Fix: Store complete metadata in database, query from SQL only

##### 2. Enhanced Index Schema
```sql
-- Enhance composition_index table
ALTER TABLE composition_index ADD COLUMN full_metadata JSON;
ALTER TABLE composition_index ADD COLUMN parsed_content TEXT;
ALTER TABLE composition_index ADD COLUMN dependencies JSON;
ALTER TABLE composition_index ADD COLUMN search_text TEXT;
ALTER TABLE composition_index ADD COLUMN last_modified TEXT;
ALTER TABLE composition_index ADD COLUMN file_size INTEGER;

-- Add indexes for efficient querying
CREATE INDEX idx_comp_name ON composition_index(name);
CREATE INDEX idx_comp_author ON composition_index(author);
CREATE INDEX idx_comp_modified ON composition_index(last_modified);
CREATE VIRTUAL TABLE composition_fts USING fts5(
    full_name, name, description, search_text, content='composition_index'
);
```

##### 3. Proper Discovery System Separation
Clarify the role of discovery at different layers:

**System Layer** (What can I do?):
```python
# system:discover returns:
{
    "composition": {
        "description": "Composition management system",
        "discovery_events": [
            "composition:discover - Find compositions by criteria",
            "composition:list - List compositions with filters", 
            "composition:search - Full-text search compositions"
        ]
    }
}
```

**Domain Layer** (What's in this domain?):
- `composition:discover` → Query compositions from SQLite index
- `composition:list` → List with pagination from database
- `composition:search` → Full-text search using FTS5

##### 4. Implementation Steps

1. **Enhance index_file()**: Store complete metadata in SQLite
   ```python
   # Store full frontmatter, content hash, file stats
   full_metadata = json.dumps(comp_data)
   content_hash = hashlib.sha256(content.encode()).hexdigest()
   file_size = file_path.stat().st_size
   ```

2. **Rewrite discover()**: Use SQL queries exclusively
   ```python
   # No file loading during discovery
   SELECT * FROM composition_index WHERE type = ? AND ...
   ```

3. **Add composition:search**: FTS5 full-text search
   ```sql
   SELECT * FROM composition_fts WHERE composition_fts MATCH ?
   ```

**PERFORMANCE TESTING CHECKPOINT**
- Test with current ~250 compositions
- Verify no file I/O during discovery/list operations
- Measure query response times < 100ms
- Test full-text search functionality

#### Benefits
1. **Immediate**: Fix timeouts by eliminating file I/O during queries
2. **Correctness**: Align with KSI's established patterns
3. **Performance**: Database queries are orders of magnitude faster
4. **Features**: Enable proper search and complex filtering

### Phase 6: Full YAML Components (Future)
- Allow `.yaml` component files
- Support all composition features
- Enhanced component discovery and validation
- Component marketplace and sharing

## Usage Examples

### Creating Components

**Simple Component**:
```bash
ksi send composition:create_component \
  --name "tips/quick_tip" \
  --content "# Quick Tip\n\nAlways verify before proceeding"
```

**Enhanced Component**:
```bash
ksi send composition:create_component \
  --name "instructions/adaptive" \
  --content "---
mixins:
  - components/base.md
variables:
  mode: casual
---
# Adaptive Instructions

Content for {{mode}} mode."
```

### Using Components in Profiles

```yaml
# Profile using progressive components
name: smart_agent
type: profile
mixins:
  # Simple markdown component
  - fragments/components/basic_instruction.md
  # Enhanced component with variables
  - fragments/components/adaptive_instruction.md
variables:
  mode: technical
  style: professional
```

### Component Inheritance Chains

```
base_instruction.md (simple)
    ↓
error_handling.md (enhanced, adds mixins)
    ↓
orchestrator_instruction.md (enhanced, adds more variables)
    ↓
specialized_orchestrator.yaml (full composition)
```

## Benefits

1. **Simplicity**: Most components remain simple markdown files
2. **Power**: Complex scenarios supported without forcing complexity
3. **Discoverability**: Frontmatter makes component capabilities explicit
4. **Reusability**: Components can be mixed and matched at any level
5. **Evolution**: Natural progression from simple to complex
6. **Maintainability**: Changes to base components propagate automatically

## Testing Strategy

### Phase 1 Tests
1. Create simple markdown component, verify unchanged behavior
2. Create enhanced markdown with frontmatter, verify parsing
3. Test retrieval of both types, verify correct structure returned
4. Test malformed frontmatter handling

### Phase 2 Tests
1. Create component with invalid mixins, verify error
2. Create component with circular dependencies, verify detection
3. Test variable validation

### Phase 3 Tests ✅ COMPLETED
1. Test recursive mixin resolution
2. Test variable substitution in mixed components
3. Test conditional mixin application
4. Performance test deep inheritance chains

### Phase 4 Tests
1. Test event-driven component updates
2. Test orchestration pattern generation
3. Test component-based agent spawning
4. Test monitoring integration
5. Test component lifecycle management

### Phase 5 Tests
1. Test pagination with large component sets
2. Verify all metadata stored in database
3. Test SQL-based filtering performance
4. Test full-text search functionality
5. Benchmark query performance vs file-based approach
6. Test incremental indexing on file changes

## Migration Path

1. Existing markdown components continue working unchanged
2. Components can be progressively enhanced by adding frontmatter
3. No breaking changes to existing composition system
4. Optional migration tool to analyze and suggest enhancements

## Future Considerations

### Component Marketplace
- Share components across KSI instances
- Version management for components
- Dependency resolution

### Visual Component Editor
- GUI for composing components
- Drag-and-drop mixin management
- Real-time preview with variable substitution

### Component Analytics
- Track which components are used most
- Identify common patterns for extraction
- Suggest refactoring opportunities

## Phase 4: KSI System Integration

### Streaming Event Architecture

Components and agents now support continuous event streaming back to their originators:

#### Core Concept
Every event emitted by an agent flows back to its originator in real-time:
- No "final result" - all results are intermediate results in a continuous stream
- Errors propagate the same as success events
- Enables true orchestration with progressive feedback

#### Implementation Pattern
```python
# Originator context propagates through event chain
context = {
    "_originator": {
        "type": "agent|external|system",
        "id": "originator_id",
        "return_path": "completion:async",  # For agents
        "chain_id": "unique_chain_id"
    }
}

# Every event result flows back
Originator → Spawns Agent
          ← Initial completion flows back
          ← Event A result flows back
          ← Event B result flows back
          ← Error event flows back
          ← Event C result flows back
          ... continuous stream ...
```

#### Example Flow
```bash
# External orchestrator spawns agent
ksi send agent:spawn_from_component \
  --component data_analyzer \
  --prompt "Analyze dataset.csv" \
  --originator '{"type": "external", "id": "claude-code-123"}'

# All these events flow back to originator:
→ completion:result (initial response)
→ file:read (reading dataset.csv)  
→ state:update (found 1000 rows)
→ data:analysis_progress (25% complete)
→ error:occurred (malformed row 567)
→ data:analysis_complete (results)
```

### Event-Driven Component Updates
Components can respond to KSI events and trigger updates:

```yaml
# components/adaptive_agent_profile.md
---
extends: base_agent_profile
event_subscriptions:
  - pattern: "agent:context_update"
    variable_mappings:
      context: "{{event.data.context}}"
      capabilities: "{{event.data.capabilities}}"
  - pattern: "orchestration:vars_changed"
    variable_mappings:
      environment: "{{event.data.environment}}"
variables:
  context: "default"
  capabilities: "[]"
  environment: "development"
---
# Dynamic Agent Profile

Your context: {{context}}
Your capabilities: {{capabilities}}
Environment: {{environment}}
```

### Orchestration Pattern Generation
Generate orchestration patterns from component hierarchies:

```bash
# Generate orchestration from component
ksi send composition:generate_orchestration \
  --component "components/complex_workflow" \
  --pattern_name "workflow_orchestration"

# Use component as orchestration template
ksi send orchestration:start \
  --component "components/multi_step_process" \
  --vars '{"priority": "high", "deadline": "2024-12-31"}'
```

### Component-Based Agent Spawning
Spawn agents directly from components:

```bash
# Spawn agent using component as profile
ksi send agent:spawn_from_component \
  --component "components/specialized_analyst" \
  --vars '{"domain": "financial", "depth": "detailed"}'

# Create temporary profile from component
ksi send composition:component_to_profile \
  --component "components/task_executor" \
  --profile_name "temp_executor_profile"
```

### Integration Points

1. **Composition Service Extension**
   - Add `composition:render_component` event handler
   - Implement `composition:component_to_profile` for agent spawning
   - Add `composition:generate_orchestration` for pattern creation

2. **Agent Service Integration**
   - Add `agent:spawn_from_component` event handler
   - Support component-based profile resolution
   - Dynamic profile updates from component changes

3. **Orchestration Service Integration**
   - Pattern generation from component hierarchies
   - Component-based orchestration templates
   - Dynamic orchestration variable injection

4. **Monitoring Integration**
   - Component usage tracking
   - Performance metrics for component rendering
   - Component dependency analysis
   - Event chain result streaming for external originators
   - Complete event flow observability

### Component Lifecycle Management
Track component versions and usage:

```bash
# Version components
ksi send composition:version_component \
  --component "components/critical_instruction" \
  --version "1.2.0" \
  --changelog "Added error handling"

# Track component usage
ksi send composition:track_usage \
  --component "components/base_agent" \
  --usage_context "agent_spawn" \
  --metadata '{"agent_id": "agent_123"}'

# Component dependency analysis
ksi send composition:analyze_dependencies \
  --component "components/complex_workflow"
```

## Implementation Notes

### Frontmatter Parsing
Use existing YAML parsing with clear separation:
```python
if content.startswith('---\n'):
    # Find closing ---
    end = content.find('\n---\n', 4)
    if end > 0:
        frontmatter = yaml.safe_load(content[4:end])
        body = content[end+5:]  # Skip closing --- and newline
        return {
            "type": "enhanced",
            "metadata": frontmatter,
            "content": body
        }
```

### Metadata Storage
- Option 1: Store in content file (current approach)
- Option 2: Separate `.meta.yaml` files
- Option 3: Database metadata with file content
- Decision: Option 1 for simplicity and portability

### Variable Substitution
- Use existing template system from composition engine
- Support default values: `{{var|default}}`
- Support nested variables: `{{user.name}}`
- Support conditional sections (future)

## Success Criteria

1. Zero breaking changes to existing components
2. Intuitive progression from simple to complex
3. Clear error messages for invalid compositions
4. Performance maintains with deep hierarchies
5. Documentation examples cover common patterns

---

*This system embodies KSI's philosophy: start simple, enhance progressively, maintain clarity.*