# System Engineering Workflow Patterns

## Meta-Instructions for System Engineering

**CRITICAL COMPLIANCE**: These patterns are MANDATORY when working on system-level changes, architecture, or knowledge management in the ksi system.

## Memory Management Workflow

### Knowledge Capture Protocol
**When** discovering new system quirks, patterns, or solutions:
- **Then** IMMEDIATELY update appropriate memory store without waiting for prompts
- **Then** identify correct audience (claude_code/, spawned_agents/, session_patterns/, workflow_patterns/)
- **Then** document both the pattern and the reasoning
- **Then** test that future Claude instances can discover and apply the knowledge

### Memory Discovery Pattern
**When** starting work in ksi system:
- **Then** ALWAYS read `memory/README.md` first
- **Then** identify your role (Claude Code, spawned agent, session instance, system engineer)
- **Then** read relevant memory stores before beginning work
- **Then** validate knowledge is current and correct

## System Engineering Before Experiments

### Documentation First Principle
**When** implementing new system features:
- **Then** document expected behavior in appropriate memory store
- **Then** implement validation/testing for the documented behavior
- **Then** test actual behavior against documentation
- **Then** update documentation immediately if reality differs

### Protocol Validation Approach
**When** working with daemon/socket systems:
- **Then** create validation scripts to test documented protocols
- **Then** run validation before implementing complex features
- **Then** update memory stores when discovering protocol mismatches
- **Then** maintain validation scripts as living documentation

### Error Handling Strategy
**When** encountering system errors or debugging issues:
- **Then** capture stderr and error patterns in debugging memory
- **Then** document reproduction steps and solutions
- **Then** create monitoring/detection for similar issues
- **Then** update system architecture to prevent recurrence

## Collaboration Patterns with Claude Code

### Separation of Concerns
**When** working alongside Claude Code:
- **Then** use git commits to separate your work from Claude Code's work
- **Then** document your changes in workflow_patterns/ memory
- **Then** keep Claude Code focused on its domain (interactive development)
- **Then** avoid conflicting with Claude Code's file organization

### Knowledge Handoff Protocol
**When** Claude Code makes architectural changes:
- **Then** review changes for memory system implications
- **Then** update memory stores to reflect new patterns
- **Then** validate that spawned agents still have correct instructions
- **Then** test knowledge discovery still works correctly

## Infrastructure Development Patterns

### Isolation and Containment
**When** creating systems that spawn autonomous agents:
- **Then** design isolation first (workspaces, sandboxes, constraints)
- **Then** document isolation requirements in spawned_agents/ memory
- **Then** create enforcement mechanisms and validation
- **Then** test isolation under stress (multiple concurrent agents)

### Monitoring and Observability
**When** building complex multi-agent systems:
- **Then** implement monitoring/logging from the start
- **Then** create tools for observing system state and progress
- **Then** document monitoring patterns in tools and memory
- **Then** design for debuggability and transparency

## Knowledge Evolution Patterns

### Memory System Maintenance
**When** memory stores become large or unwieldy:
- **Then** refactor into more specific, focused documents
- **Then** maintain clear navigation and discovery mechanisms
- **Then** archive obsolete patterns with deprecation notes
- **Then** test that knowledge discovery still works efficiently

### Cross-Session Learning
**When** patterns emerge across multiple sessions:
- **Then** abstract the patterns into reusable memory
- **Then** create templates and standard approaches
- **Then** document when to apply each pattern
- **Then** validate patterns work for different Claude instances

---

**REMEMBER**: These workflow patterns ensure knowledge persistence and systematic improvement of the ksi system across sessions and Claude instances.

*For system engineering and architecture work in ksi*