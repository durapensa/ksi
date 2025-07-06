#!/usr/bin/env python3
"""
KSI Prompt Generator for Claude Agents

Transforms KSI discovery information into Claude-friendly prompts that maximize
Claude's ability to understand and use the system effectively.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import json
from pathlib import Path
import textwrap


class KSIPromptGenerator:
    """Generates Claude-optimized prompts from KSI discovery data."""
    
    # Additional context not available in discovery
    CONTEXT_KNOWLEDGE = {
        "models": {
            "claude-cli": ["sonnet", "opus", "haiku"],
            "litellm": ["gpt-4", "gpt-3.5-turbo", "claude-3-sonnet-20240229"]
        },
        "session_behavior": {
            "new_session": "Omit session_id to start a new conversation",
            "continue_session": "Include session_id from previous response to continue",
            "session_id_updates": "Claude CLI returns NEW session_id with each response"
        },
        "async_patterns": {
            "completion:async": "Returns immediately with request_id, result comes via completion:result event",
            "agent:spawn": "Creates background agent, returns agent_id for tracking"
        },
        "best_practices": [
            "Always check system:health before starting operations",
            "Use conversation:active to find recent sessions",
            "Monitor completion:status for long-running requests",
            "Clean up with agent:cleanup when done with multi-agent work"
        ]
    }
    
    def __init__(self, discovery_data: Dict[str, Any]):
        """Initialize with discovery data from system:discover."""
        self.discovery_data = discovery_data
        self.namespaces = discovery_data.get("namespaces", [])
        self.events = discovery_data.get("events", {})
        self.total_events = discovery_data.get("total_events", 0)
    
    def generate_prompt(self, 
                       include_examples: bool = True,
                       include_workflows: bool = True,
                       focus_namespaces: Optional[List[str]] = None) -> str:
        """
        Generate Claude-friendly prompt from discovery data.
        
        Args:
            include_examples: Include usage examples
            include_workflows: Include multi-step workflow examples
            focus_namespaces: Limit to specific namespaces (None for all)
            
        Returns:
            Generated prompt text
        """
        sections = []
        
        # Header
        sections.append(self._generate_header())
        
        # Quick start
        sections.append(self._generate_quickstart())
        
        # Capabilities by use case
        sections.append(self._generate_capabilities(focus_namespaces))
        
        # Examples
        if include_examples:
            sections.append(self._generate_examples())
        
        # Workflows
        if include_workflows:
            sections.append(self._generate_workflows())
        
        # Best practices
        sections.append(self._generate_best_practices())
        
        # Discovery section
        sections.append(self._generate_discovery_section())
        
        return "\n\n".join(sections)
    
    def _generate_header(self) -> str:
        """Generate prompt header."""
        return f"""# KSI System Interface

You have access to the KSI (Knowledge Systems Interface) daemon with {self.total_events} available events across {len(self.namespaces)} namespaces. KSI uses an event-driven architecture where all operations are performed by sending JSON events.

## Event Format
All commands use this JSON format:
```json
{{
  "event": "namespace:action",
  "data": {{
    "parameter": "value"
  }}
}}
```"""
    
    def _generate_quickstart(self) -> str:
        """Generate quick start section."""
        return """## Quick Start

1. **Check system health**: `{"event": "system:health", "data": {}}`
2. **Send a message**: `{"event": "completion:async", "data": {"prompt": "Hello", "model": "claude-cli/sonnet"}}`
3. **List conversations**: `{"event": "conversation:list", "data": {"limit": 10}}`
4. **Get help on any event**: `{"event": "system:help", "data": {"event": "event:name"}}`"""
    
    def _generate_capabilities(self, focus_namespaces: Optional[List[str]] = None) -> str:
        """Generate capabilities section grouped by use case."""
        sections = []
        sections.append("## Available Capabilities\n")
        
        # Group namespaces by use case
        use_cases = {
            "Core Operations": ["system", "completion", "conversation"],
            "State Management": ["state", "async_state"],
            "Multi-Agent": ["agent", "message"],
            "Advanced": ["injection", "orchestration", "composition"],
            "Monitoring": ["monitor", "module", "permission"]
        }
        
        for use_case, namespace_list in use_cases.items():
            case_events = []
            
            for namespace in namespace_list:
                if focus_namespaces and namespace not in focus_namespaces:
                    continue
                    
                if namespace in self.events:
                    case_events.extend([
                        (namespace, event) 
                        for event in self.events[namespace]
                    ])
            
            if case_events:
                sections.append(f"### {use_case}")
                sections.append(self._format_namespace_events(case_events))
        
        return "\n\n".join(sections)
    
    def _format_namespace_events(self, events: List[tuple]) -> str:
        """Format events for a use case."""
        lines = []
        
        for namespace, event_info in events:
            event_name = event_info.get("event", "")
            summary = event_info.get("summary", "No description")
            params = event_info.get("parameters", {})
            
            # Format event with inline parameter info
            param_list = []
            for param_name, param_info in params.items():
                required = "required" if param_info.get("required") else "optional"
                param_type = param_info.get("type", "any")
                param_list.append(f"{param_name} ({param_type}, {required})")
            
            param_str = ", ".join(param_list) if param_list else "no parameters"
            
            lines.append(f"- **{event_name}**: {summary}")
            lines.append(f"  Parameters: {param_str}")
            
            # Add example if available
            examples = event_info.get("examples", [])
            if examples and len(examples) > 0:
                example = examples[0]
                example_json = json.dumps({
                    "event": event_name,
                    "data": example.get("data", {})
                }, indent=2)
                lines.append(f"  Example: `{example_json}`")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def _generate_examples(self) -> str:
        """Generate examples section."""
        return """## Examples

### Send a message and get response
```json
{
  "event": "completion:async",
  "data": {
    "prompt": "Explain quantum computing",
    "model": "claude-cli/sonnet",
    "request_id": "req_123"
  }
}
```

### Continue a conversation
```json
{
  "event": "completion:async",
  "data": {
    "prompt": "Can you elaborate on superposition?",
    "model": "claude-cli/sonnet",
    "session_id": "session_abc123",
    "request_id": "req_124"
  }
}
```

### Store persistent state
```json
{
  "event": "state:set",
  "data": {
    "key": "project_config",
    "value": {"theme": "dark", "language": "python"},
    "namespace": "user_preferences"
  }
}
```"""
    
    def _generate_workflows(self) -> str:
        """Generate workflow examples."""
        return """## Common Workflows

### Multi-turn Conversation
1. Start conversation: `{"event": "completion:async", "data": {"prompt": "Hello", "model": "claude-cli/sonnet"}}`
2. Get session_id from response
3. Continue: `{"event": "completion:async", "data": {"prompt": "Tell me more", "session_id": "sid_123", "model": "claude-cli/sonnet"}}`

### Multi-Agent Coordination
1. Spawn researcher: `{"event": "agent:spawn", "data": {"profile": "researcher", "config": {"focus": "ml_papers"}}}`
2. Spawn analyzer: `{"event": "agent:spawn", "data": {"profile": "analyzer", "config": {"source_agent": "agent_123"}}}`
3. Coordinate: `{"event": "message:publish", "data": {"event_type": "TASK_ASSIGNED", "data": {"task": "analyze_paper", "paper_id": "abc"}}}`
4. Cleanup: `{"event": "agent:cleanup", "data": {}}`"""
    
    def _generate_best_practices(self) -> str:
        """Generate best practices section."""
        practices = "\n".join([f"- {practice}" for practice in self.CONTEXT_KNOWLEDGE["best_practices"]])
        
        return f"""## Best Practices

{practices}

### Session Management
- {self.CONTEXT_KNOWLEDGE["session_behavior"]["new_session"]}
- {self.CONTEXT_KNOWLEDGE["session_behavior"]["continue_session"]}
- {self.CONTEXT_KNOWLEDGE["session_behavior"]["session_id_updates"]}

### Model Selection
- Claude CLI models: {", ".join(self.CONTEXT_KNOWLEDGE["models"]["claude-cli"])}
- LiteLLM models: {", ".join(self.CONTEXT_KNOWLEDGE["models"]["litellm"][:3])} (and more)"""
    
    def _generate_discovery_section(self) -> str:
        """Generate discovery section."""
        return """## Discovering More

- **List all events**: `{"event": "system:discover", "data": {}}`
- **Filter by namespace**: `{"event": "system:discover", "data": {"namespace": "agent"}}`
- **Get detailed help**: `{"event": "system:help", "data": {"event": "completion:async"}}`
- **Check capabilities**: `{"event": "system:capabilities", "data": {}}`

Remember: KSI is event-driven and asynchronous. Most operations return immediately with an ID, and results come through separate events."""

    def save_to_file(self, filepath: Path, **kwargs):
        """Save generated prompt to file."""
        prompt = self.generate_prompt(**kwargs)
        filepath.write_text(prompt)
        
    @classmethod
    def from_client(cls, client: 'EventClient') -> 'KSIPromptGenerator':
        """Create generator from connected EventClient."""
        if not client._discovered:
            raise ValueError("Client must complete discovery first")
            
        # Reconstruct discovery format from client's cache
        discovery_data = {
            "namespaces": list(client._event_cache.keys()),
            "events": client._event_cache,
            "total_events": sum(len(events) for events in client._event_cache.values())
        }
        
        return cls(discovery_data)


def generate_ksi_prompt(output_path: Optional[Path] = None) -> str:
    """
    Generate KSI prompt for Claude by connecting to daemon and discovering events.
    
    Args:
        output_path: Optional path to save prompt file
        
    Returns:
        Generated prompt text
    """
    import asyncio
    from ksi_client import EventClient
    
    async def _generate():
        async with EventClient() as client:
            # Ensure discovery is complete
            if not client._discovered:
                await client.discover()
            
            # Create generator
            generator = KSIPromptGenerator.from_client(client)
            
            # Generate prompt
            prompt = generator.generate_prompt()
            
            # Save if path provided
            if output_path:
                output_path.write_text(prompt)
                print(f"Saved KSI prompt to: {output_path}")
            
            return prompt
    
    return asyncio.run(_generate())


if __name__ == "__main__":
    # Generate prompt when run directly
    import sys
    
    output_file = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("ksi_prompt.txt")
    prompt = generate_ksi_prompt(output_file)
    print(f"Generated {len(prompt)} characters of Claude-friendly KSI documentation")