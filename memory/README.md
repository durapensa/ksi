# KSI Memory System

**CRITICAL**: Any Claude instance working in the ksi system should READ THIS FILE FIRST.

## Memory Architecture

This memory system separates knowledge by audience and purpose to prevent confusion and ensure discoverability.

### Directory Structure

```
memory/
├── claude_code/          # Knowledge specifically for Claude Code interactive sessions
├── spawned_agents/       # Instructions and patterns for autonomous Claude agents  
├── session_patterns/     # Patterns for daemon-spawned Claude instances
├── workflow_patterns/    # My (ksi Claude) workflow and engineering patterns
└── README.md            # This discovery file (READ FIRST)
```

### When to Use Each Memory Store

**claude_code/**: Knowledge that Claude Code needs to know
- Project structure and conventions
- Build/test commands
- Deployment procedures
- File organization rules

**spawned_agents/**: Instructions for autonomous experiments
- Workspace isolation requirements
- Analysis patterns and templates
- Output formatting guidelines
- Resource constraints

**session_patterns/**: For daemon-spawned Claude instances
- Daemon protocol knowledge
- Communication patterns
- Session management
- Tool availability

**workflow_patterns/**: My operational patterns
- System engineering principles
- Knowledge capture workflows
- Debugging approaches
- Collaboration patterns

## Memory Discovery Protocol

### For Any Claude Instance:
1. **Always read** `memory/README.md` first (this file)
2. **Check relevance** based on how you were invoked:
   - Claude Code interactive → read `claude_code/`
   - Daemon spawn → read `session_patterns/`
   - Autonomous agent → read `spawned_agents/`
   - KSI system Claude → read `workflow_patterns/`
3. **Update immediately** when discovering new patterns
4. **Cross-reference** between memory stores as needed

### Memory Update Triggers:
- Discovering new system quirks or patterns
- Solving previously unknown problems
- Creating new tools or processes
- Changing system architecture
- Finding better workflows

## Integration with KSI System

### Memory Persistence Strategy:
- **Memory files tracked in git** - survives system changes
- **Explicit discovery protocol** - no assumptions about automatic reading
- **Audience separation** - prevents confusion between Claude types
- **Update triggers documented** - ensures memory stays current

### Claude Instance Identification:
Different Claude instances have different knowledge needs:
- **Claude Code**: Interactive development environment
- **Daemon spawned**: Single-task focused instances  
- **Autonomous agents**: Self-directed research instances
- **KSI system Claude**: System engineering and orchestration

## Memory System Benefits

1. **Discoverability**: Always start with memory/README.md
2. **Separation of concerns**: No more mixed knowledge in CLAUDE.md
3. **Persistence**: Survives across sessions and system changes
4. **Scalability**: Easy to add new memory categories
5. **Maintenance**: Clear ownership and update triggers

---

**REMEMBER**: This memory system only works if Claude instances actually read it. Make this the first step in any ksi work.

*Memory system created: 2025-06-20*  
*Next evolution: Add memory validation and consistency checks*