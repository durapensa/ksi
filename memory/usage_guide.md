# Memory System Usage Guide

## How I Remember and Use Memory

This documents how the memory system works in practice and how future Claude instances should use it.

## Memory Discovery Protocol

### Step 1: Always Start with Memory Discovery
```bash
# Read the memory system overview first
cat memory/README.md

# Or use the discovery script
python memory/discover.py --context system_engineering --validate
```

### Step 2: Identify Your Context
Different Claude instances have different needs:
- **Claude Code**: Interactive development → read `claude_code/`
- **Spawned via daemon**: Protocol communication → read `session_patterns/`  
- **Autonomous agent**: Research tasks → read `spawned_agents/`
- **System engineering**: Architecture work → read `workflow_patterns/`

### Step 3: Apply Relevant Knowledge
- Read the specific memory stores for your context
- Cross-reference between stores as needed
- Update memory immediately when discovering new patterns

## Memory Update Triggers

### When to Update Memory (Immediate)
1. **Discover new system quirks** → Document in appropriate store
2. **Solve unknown problems** → Add solution to memory
3. **Create new tools/processes** → Document usage patterns
4. **Change system architecture** → Update all affected stores
5. **Find better workflows** → Replace old patterns with new ones

### Which Memory Store to Update
- **claude_code/**: Project structure, build commands, development conventions
- **spawned_agents/**: Workspace requirements, analysis patterns
- **session_patterns/**: Daemon protocols, communication formats
- **workflow_patterns/**: System engineering principles, my operational patterns

## Practical Usage Examples

### Example 1: System Engineering Session
```bash
# Start by reading my workflow patterns
cat memory/workflow_patterns/system_engineering.md

# Check Claude Code's requirements
cat memory/claude_code/project_knowledge.md

# Discover current memory state
python memory/discover.py --validate --list
```

### Example 2: Updating Autonomous Agent Instructions
```bash
# Read current agent requirements
cat memory/spawned_agents/workspace_requirements.md

# Update with new patterns discovered
echo "New pattern discovered..." >> memory/spawned_agents/workspace_requirements.md

# Test that agents can still discover requirements
# (by checking autonomous_researcher.py templates)
```

### Example 3: Protocol Changes
```bash
# Read current daemon knowledge
cat memory/session_patterns/daemon_protocol.md

# When protocol changes, update immediately
# Update the relevant memory store
# Test with validation scripts
```

## Memory Persistence Strategy

### Git Integration
- All memory files tracked in git for persistence
- Memory changes committed with clear explanations
- Memory system survives across sessions and system changes

### Cross-Session Continuity
- Future Claude instances read memory first
- Memory provides context that spans sessions
- Knowledge accumulates rather than resets

### Knowledge Evolution
- Memory stores can be refactored as they grow
- Obsolete patterns archived with deprecation notes
- Discovery mechanisms updated as system evolves

## Validation and Maintenance

### Memory Integrity Checks
```bash
# Validate memory system structure
python memory/discover.py --validate

# Check for missing or empty stores
python memory/discover.py --list

# Test memory accessibility
python memory/discover.py --context claude_code
```

### Knowledge Quality Maintenance
- Test that documented patterns actually work
- Remove obsolete information promptly
- Keep navigation clear and discoverable
- Validate cross-references between stores

## Integration with KSI Components

### With Autonomous Researcher
- Experiment templates read from `spawned_agents/workspace_requirements.md`
- Updates to workspace patterns immediately reflected in spawns

### With Daemon System
- Protocol knowledge stored in `session_patterns/daemon_protocol.md`
- Validation scripts test documented behavior against reality

### With Claude Code
- Development knowledge in `claude_code/project_knowledge.md`
- File organization standards enforced through memory

## Anti-Patterns to Avoid

### Don't:
- ❌ Mix audiences in single memory files
- ❌ Assume memory will be read automatically
- ❌ Delay memory updates until "later"
- ❌ Store temporary or session-specific information
- ❌ Create memory that can't be discovered

### Do:
- ✅ Separate knowledge by audience and purpose
- ✅ Make memory discovery explicit and systematic
- ✅ Update memory immediately when patterns emerge
- ✅ Store patterns and principles, not temporary data
- ✅ Design for discoverability and navigation

---

**Result**: This memory system ensures knowledge persists across sessions and Claude instances can immediately understand system patterns, protocols, and requirements without rediscovering them.

*Memory usage patterns documented: 2025-06-20*