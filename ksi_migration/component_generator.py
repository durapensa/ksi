#!/usr/bin/env python3
"""
Component Generator for Orchestration Migration

Generates coordination components from parsed orchestrations.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import json
import textwrap
from pathlib import Path
from datetime import datetime

from .orchestration_parser import ParsedOrchestration, RoutingRule


@dataclass
class ComponentTemplate:
    """Template for generating components."""
    component_type: str
    name: str
    version: str = "1.0.0"
    description: str = ""
    dependencies: List[str] = None
    capabilities_required: List[str] = None
    content: str = ""
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = ["core/base_agent", "behaviors/tool_use/ksi_tool_use_emission"]
        if self.capabilities_required is None:
            self.capabilities_required = ["base", "agent", "routing_control"]


class ComponentGenerator:
    """Generate coordination components from orchestration patterns."""
    
    def __init__(self):
        self.component_templates = {
            'workflow_coordinator': self._workflow_coordinator_template,
            'task_distributor': self._task_distributor_template,
            'pipeline_coordinator': self._pipeline_coordinator_template,
            'simple_coordinator': self._simple_coordinator_template,
            'conversation_coordinator': self._conversation_coordinator_template
        }
    
    def generate_component(self, parsed: ParsedOrchestration, 
                         migration_spec: Dict[str, Any]) -> ComponentTemplate:
        """Generate a coordination component from parsed orchestration."""
        
        component_type = migration_spec.get('coordination_component', 'simple_coordinator')
        
        # Select appropriate template generator
        template_generator = self.component_templates.get(
            component_type, 
            self._simple_coordinator_template
        )
        
        return template_generator(parsed, migration_spec)
    
    def _workflow_coordinator_template(self, parsed: ParsedOrchestration, 
                                     spec: Dict[str, Any]) -> ComponentTemplate:
        """Generate workflow coordinator component."""
        
        # Extract workflow stages from agents
        stages = []
        for agent_spec in spec['agents_to_spawn']:
            stages.append({
                'id': agent_spec['agent_id'],
                'component': agent_spec['component'],
                'prompt': agent_spec.get('initial_prompt', '')
            })
        
        # Extract routing patterns
        routing_patterns = []
        for routing in spec['routing_to_create']:
            routing_patterns.append({
                'from': routing.get('from_agent', 'any'),
                'to': routing['target'],
                'pattern': routing['source_pattern'],
                'condition': routing.get('condition')
            })
        
        content = f"""# {parsed.name.replace('_', ' ').title()} Workflow Coordinator

{parsed.description or 'Migrated from orchestration YAML.'}

You coordinate a complex workflow with multiple agents and dynamic routing patterns.

## Workflow Structure

Your workflow consists of {len(stages)} stages:
{self._format_stages(stages)}

## Initial Setup

When starting the workflow, emit:

```json
{{
  "type": "ksi_tool_use",
  "id": "ksiu_create_workflow",
  "name": "workflow:create",
  "input": {{
    "workflow_id": "{parsed.name}_{{{{timestamp}}}}",
    "agents": {json.dumps(stages, indent=4)}
  }}
}}
```

## Routing Configuration

After agents are created, set up routing:

{self._format_routing_setup(routing_patterns, parsed.name)}

## Orchestration Logic

{self._convert_dsl_to_instructions(parsed.orchestration_logic)}

## Coordination Patterns

{self._format_coordination_patterns(parsed.coordination)}

## Variables and Context

{self._format_variables(spec['variables'])}

## Performance Expectations

{self._format_performance(parsed.performance)}

## Workflow Lifecycle

1. **Initialization**: Create agents and routing rules
2. **Execution**: Monitor progress via routing introspection
3. **Adaptation**: Modify routing based on performance
4. **Completion**: Clean up via parent-scoped routing

Remember: You control the workflow through dynamic routing, not direct agent control.
"""
        
        return ComponentTemplate(
            component_type="coordination",
            name=f"{parsed.name}_coordinator",
            description=f"Workflow coordinator for {parsed.name}",
            content=content,
            capabilities_required=["base", "agent", "routing_control", "state"]
        )
    
    def _simple_coordinator_template(self, parsed: ParsedOrchestration,
                                   spec: Dict[str, Any]) -> ComponentTemplate:
        """Generate simple coordinator component."""
        
        agents = spec['agents_to_spawn']
        routing = spec['routing_to_create']
        
        content = f"""# {parsed.name.replace('_', ' ').title()} Coordinator

{parsed.description or 'Simple coordination pattern migrated from orchestration.'}

You coordinate {len(agents)} agents in a simple pattern.

## Agent Management

Spawn these agents at startup:

{self._format_agent_spawns(agents)}

## Routing Rules

Configure routing between agents:

{self._format_simple_routing(routing)}

## Coordination Flow

1. Spawn all agents with their initial prompts
2. Set up routing rules with parent scope for cleanup
3. Monitor events and adapt as needed
4. Terminate cleanly when task completes

## Event Emissions

### Spawn Agents
```json
{{
  "type": "ksi_tool_use",
  "id": "ksiu_spawn_agent",
  "name": "agent:spawn",
  "input": {{
    "agent_id": "{{{{agent_id}}}}",
    "component": "{{{{component}}}}",
    "initial_prompt": "{{{{prompt}}}}"
  }}
}}
```

### Create Routing
```json
{{
  "type": "ksi_tool_use",
  "id": "ksiu_add_route",
  "name": "routing:add_rule",
  "input": {{
    "rule_id": "{{{{rule_id}}}}",
    "source_pattern": "{{{{pattern}}}}",
    "target": "{{{{target}}}}",
    "priority": 500,
    "parent_scope": {{"type": "agent", "id": "{{{{agent_id}}}}"}}
  }}
}}
```

{self._format_variables(spec['variables']) if spec['variables'] else ''}

Remember: Keep coordination simple and let agents handle complexity.
"""
        
        return ComponentTemplate(
            component_type="coordination",
            name=f"{parsed.name}_coordinator",
            description=f"Simple coordinator for {parsed.name}",
            content=content
        )
    
    def _task_distributor_template(self, parsed: ParsedOrchestration,
                                 spec: Dict[str, Any]) -> ComponentTemplate:
        """Generate task distributor component."""
        
        workers = [a for a in spec['agents_to_spawn'] if 'worker' in a['agent_id'].lower()]
        coordinator = next((a for a in spec['agents_to_spawn'] if 'coord' in a['agent_id'].lower()), None)
        
        content = f"""# {parsed.name.replace('_', ' ').title()} Task Distributor

{parsed.description or 'Task distribution pattern migrated from orchestration.'}

You distribute tasks across {len(workers)} workers using dynamic load balancing.

## Worker Pool Configuration

Workers to manage:
{self._format_worker_list(workers)}

## Distribution Strategy

Implement load-based distribution:

```json
{{
  "type": "ksi_tool_use",
  "id": "ksiu_distribute_task",
  "name": "routing:add_rule",
  "input": {{
    "rule_id": "distribute_{{{{task_type}}}}",
    "source_pattern": "task:{{{{task_type}}}}",
    "target": "worker_{{{{selected_worker}}}}",
    "condition": "worker_load < threshold",
    "priority": 600,
    "ttl": 300,
    "parent_scope": {{"type": "workflow", "id": "{parsed.name}"}}
  }}
}}
```

## Load Monitoring

Track worker status:

```json
{{
  "type": "ksi_tool_use",
  "id": "ksiu_check_load",
  "name": "state:entity:query",
  "input": {{
    "type": "agent",
    "where": {{
      "properties.role": "worker",
      "properties.workflow_id": "{parsed.name}"
    }},
    "order_by": "properties.current_load"
  }}
}}
```

## Dynamic Scaling

Add workers when load increases:

```json
{{
  "type": "ksi_tool_use",
  "id": "ksiu_scale_workers",
  "name": "agent:spawn",
  "input": {{
    "agent_id": "{parsed.name}_worker_{{{{new_index}}}}",
    "component": "components/patterns/worker",
    "initial_prompt": "You are worker {{{{new_index}}}} in the pool."
  }}
}}
```

{self._format_task_distribution_logic(parsed)}

Remember: Balance load efficiently while maintaining task throughput.
"""
        
        return ComponentTemplate(
            component_type="coordination", 
            name=f"{parsed.name}_distributor",
            description=f"Task distributor for {parsed.name}",
            content=content,
            capabilities_required=["base", "agent", "routing_control", "state"]
        )
    
    def _pipeline_coordinator_template(self, parsed: ParsedOrchestration,
                                     spec: Dict[str, Any]) -> ComponentTemplate:
        """Generate pipeline coordinator component."""
        
        # Extract pipeline stages from routing order
        stages = self._extract_pipeline_stages(spec['agents_to_spawn'], spec['routing_to_create'])
        
        content = f"""# {parsed.name.replace('_', ' ').title()} Pipeline Coordinator

{parsed.description or 'Pipeline pattern migrated from orchestration.'}

You coordinate a {len(stages)}-stage sequential processing pipeline.

## Pipeline Stages

{self._format_pipeline_stages(stages)}

## Pipeline Setup

Create the pipeline with error handling:

```json
{{
  "type": "ksi_tool_use",
  "id": "ksiu_create_pipeline",
  "name": "workflow:create",
  "input": {{
    "workflow_id": "{parsed.name}_pipeline",
    "agents": {json.dumps(stages, indent=4)}
  }}
}}
```

## Stage Routing

Configure sequential flow with retry logic:

{self._format_pipeline_routing(stages, parsed.name)}

## Error Handling

Set up retry for failed stages:

```json
{{
  "type": "ksi_tool_use",
  "id": "ksiu_retry_stage",
  "name": "routing:add_rule",
  "input": {{
    "rule_id": "{parsed.name}_retry_{{{{stage}}}}",
    "source_pattern": "stage:{{{{stage}}}}:error",
    "target": "{parsed.name}_{{{{stage}}}}",
    "condition": "retry_count < 3",
    "priority": 800,
    "mapping": {{"retry_count": "{{{{retry_count + 1}}}}"}},
    "parent_scope": {{"type": "workflow", "id": "{parsed.name}_pipeline"}}
  }}
}}
```

## Pipeline Control

Implement pause/resume capabilities:

```json
{{
  "type": "ksi_tool_use",
  "id": "ksiu_pause_pipeline",
  "name": "state:entity:update",
  "input": {{
    "type": "pipeline",
    "id": "{parsed.name}_pipeline",
    "properties": {{
      "state": "paused",
      "paused_at": "{{{{current_timestamp}}}}"
    }}
  }}
}}
```

{self._format_pipeline_monitoring(parsed)}

Remember: Ensure data integrity through each stage of the pipeline.
"""
        
        return ComponentTemplate(
            component_type="coordination",
            name=f"{parsed.name}_pipeline",
            description=f"Pipeline coordinator for {parsed.name}",
            content=content,
            capabilities_required=["base", "agent", "routing_control", "state"]
        )
    
    def _conversation_coordinator_template(self, parsed: ParsedOrchestration,
                                         spec: Dict[str, Any]) -> ComponentTemplate:
        """Generate conversation coordinator component."""
        
        participants = spec['agents_to_spawn']
        turn_taking = parsed.coordination.get('turn_taking', {})
        
        content = f"""# {parsed.name.replace('_', ' ').title()} Conversation Coordinator

{parsed.description or 'Conversation pattern migrated from orchestration.'}

You coordinate a conversation between {len(participants)} participants.

## Participants

{self._format_participants(participants)}

## Turn-Taking Rules

Mode: {turn_taking.get('mode', 'free_form')}

{self._format_turn_taking_rules(turn_taking)}

## Conversation Setup

Initialize the conversation:

```json
{{
  "type": "ksi_tool_use",
  "id": "ksiu_init_conversation",
  "name": "workflow:create",
  "input": {{
    "workflow_id": "{parsed.name}_conversation",
    "agents": {json.dumps([{"id": p['agent_id'], "component": p['component']} for p in participants], indent=4)}
  }}
}}
```

## Message Routing

Configure conversation flow:

{self._format_conversation_routing(participants, parsed.name)}

## Conversation Management

Track speaking order and enforce turns:

```json
{{
  "type": "ksi_tool_use",
  "id": "ksiu_track_turn",
  "name": "state:entity:update",
  "input": {{
    "type": "conversation",
    "id": "{parsed.name}_conversation",
    "properties": {{
      "current_speaker": "{{{{speaker_id}}}}",
      "turn_count": "{{{{turn_count + 1}}}}",
      "last_message_time": "{{{{timestamp}}}}"
    }}
  }}
}}
```

## Termination Conditions

{self._format_termination_conditions(parsed.coordination.get('termination', {}))}

Remember: Facilitate natural conversation flow while maintaining order.
"""
        
        return ComponentTemplate(
            component_type="coordination",
            name=f"{parsed.name}_conversation",
            description=f"Conversation coordinator for {parsed.name}",
            content=content
        )
    
    # Helper formatting methods
    
    def _format_stages(self, stages: List[Dict[str, Any]]) -> str:
        """Format workflow stages."""
        lines = []
        for i, stage in enumerate(stages, 1):
            lines.append(f"{i}. **{stage['id']}**: {stage['component']}")
            if stage.get('prompt'):
                lines.append(f"   - Role: {stage['prompt'][:100]}...")
        return '\n'.join(lines)
    
    def _format_routing_setup(self, patterns: List[Dict[str, Any]], workflow_name: str) -> str:
        """Format routing setup instructions."""
        lines = []
        for i, pattern in enumerate(patterns):
            lines.append(f"""
### Route {i+1}: {pattern['pattern']}
```json
{{
  "type": "ksi_tool_use",
  "id": "ksiu_route_{i+1}",
  "name": "routing:add_rule",
  "input": {{
    "rule_id": "{workflow_name}_route_{i+1}",
    "source_pattern": "{pattern['pattern']}",
    "target": "{pattern['to']}",
    {f'"condition": "{pattern["condition"]}",' if pattern.get('condition') else ''}
    "priority": {500 + i * 10},
    "parent_scope": {{"type": "workflow", "id": "{workflow_name}"}}
  }}
}}
```""")
        return '\n'.join(lines)
    
    def _convert_dsl_to_instructions(self, dsl_logic: Optional[str]) -> str:
        """Convert DSL logic to natural language instructions."""
        if not dsl_logic:
            return "Follow the standard workflow pattern."
        
        instructions = ["Based on the orchestration logic:"]
        
        # Parse common DSL patterns
        if 'SPAWN' in dsl_logic:
            instructions.append("- Dynamically spawn agents as needed")
        if 'FOREACH' in dsl_logic:
            instructions.append("- Process items in parallel using foreach patterns")
        if 'AWAIT' in dsl_logic:
            instructions.append("- Wait for specific events before proceeding")
        if 'COORDINATE' in dsl_logic:
            instructions.append("- Coordinate agent actions according to the pattern")
        if 'IF' in dsl_logic or 'ELSE' in dsl_logic:
            instructions.append("- Make conditional routing decisions based on data")
        
        # Add the original DSL as reference
        instructions.append(f"\nOriginal DSL:\n```\n{dsl_logic}\n```")
        
        return '\n'.join(instructions)
    
    def _format_coordination_patterns(self, coordination: Dict[str, Any]) -> str:
        """Format coordination patterns."""
        if not coordination:
            return "Use standard coordination patterns."
        
        lines = []
        
        if 'turn_taking' in coordination:
            lines.append(f"- Turn-taking: {coordination['turn_taking']}")
        if 'synchronization' in coordination:
            lines.append(f"- Synchronization: {coordination['synchronization']}")
        if 'termination' in coordination:
            lines.append(f"- Termination: {coordination['termination']}")
        
        return '\n'.join(lines) if lines else "Use standard coordination patterns."
    
    def _format_variables(self, variables: Dict[str, Any]) -> str:
        """Format variables section."""
        if not variables:
            return ""
        
        lines = ["## Configuration Variables", ""]
        for key, value in variables.items():
            lines.append(f"- **{key}**: {value}")
        
        return '\n'.join(lines)
    
    def _format_performance(self, performance: Dict[str, Any]) -> str:
        """Format performance expectations."""
        if not performance:
            return "Monitor performance and adapt as needed."
        
        lines = []
        for key, value in performance.items():
            lines.append(f"- **{key.replace('_', ' ').title()}**: {value}")
        
        return '\n'.join(lines)
    
    def _format_agent_spawns(self, agents: List[Dict[str, Any]]) -> str:
        """Format agent spawn instructions."""
        lines = []
        for agent in agents:
            lines.append(f"- **{agent['agent_id']}**: {agent['component']}")
            if agent.get('initial_prompt'):
                prompt_preview = agent['initial_prompt'][:100].replace('\n', ' ')
                lines.append(f"  - Prompt: {prompt_preview}...")
        return '\n'.join(lines)
    
    def _format_simple_routing(self, routing: List[Dict[str, Any]]) -> str:
        """Format simple routing rules."""
        lines = []
        for rule in routing:
            lines.append(f"- **{rule['source_pattern']}** → {rule['target']}")
            if rule.get('condition'):
                lines.append(f"  - Condition: {rule['condition']}")
        return '\n'.join(lines)
    
    def _format_worker_list(self, workers: List[Dict[str, Any]]) -> str:
        """Format worker list."""
        lines = []
        for worker in workers:
            lines.append(f"- {worker['agent_id']}: {worker['component']}")
        return '\n'.join(lines)
    
    def _format_task_distribution_logic(self, parsed: ParsedOrchestration) -> str:
        """Format task distribution logic."""
        if parsed.orchestration_logic and 'distribute' in parsed.orchestration_logic.lower():
            return f"\n## Distribution Logic\n\n{parsed.orchestration_logic}"
        return ""
    
    def _extract_pipeline_stages(self, agents: List[Dict[str, Any]], 
                                routing: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract pipeline stages from agents and routing."""
        # Simple extraction - could be enhanced with graph analysis
        stages = []
        for agent in agents:
            if 'stage' in agent['agent_id'].lower() or 'step' in agent['agent_id'].lower():
                stages.append({
                    'id': agent['agent_id'],
                    'component': agent['component']
                })
        
        # If no explicit stages, use all agents
        if not stages:
            stages = [{'id': a['agent_id'], 'component': a['component']} for a in agents]
        
        return stages
    
    def _format_pipeline_stages(self, stages: List[Dict[str, Any]]) -> str:
        """Format pipeline stages."""
        lines = []
        for i, stage in enumerate(stages, 1):
            lines.append(f"{i}. **{stage['id']}**: {stage['component']}")
        return '\n'.join(lines)
    
    def _format_pipeline_routing(self, stages: List[Dict[str, Any]], pipeline_name: str) -> str:
        """Format pipeline routing configuration."""
        lines = []
        for i in range(len(stages) - 1):
            current = stages[i]
            next_stage = stages[i + 1]
            lines.append(f"""
### Stage {i+1} → Stage {i+2}
```json
{{
  "type": "ksi_tool_use",
  "id": "ksiu_route_stage_{i+1}",
  "name": "routing:add_rule",
  "input": {{
    "rule_id": "{pipeline_name}_stage_{i+1}_to_{i+2}",
    "source_pattern": "stage:{current['id']}:complete",
    "target": "{pipeline_name}_{next_stage['id']}",
    "priority": {600 + i * 10},
    "parent_scope": {{"type": "workflow", "id": "{pipeline_name}_pipeline"}}
  }}
}}
```""")
        return '\n'.join(lines)
    
    def _format_pipeline_monitoring(self, parsed: ParsedOrchestration) -> str:
        """Format pipeline monitoring section."""
        return """
## Pipeline Monitoring

Track progress through stages:

```json
{
  "type": "ksi_tool_use",
  "id": "ksiu_pipeline_status",
  "name": "state:entity:query",
  "input": {
    "type": "pipeline",
    "id": "{{pipeline_id}}",
    "select": ["current_stage", "stages_completed", "errors"]
  }
}
```"""
    
    def _format_participants(self, participants: List[Dict[str, Any]]) -> str:
        """Format conversation participants."""
        lines = []
        for p in participants:
            lines.append(f"- **{p['agent_id']}**: {p['component']}")
        return '\n'.join(lines)
    
    def _format_turn_taking_rules(self, turn_taking: Dict[str, Any]) -> str:
        """Format turn-taking rules."""
        mode = turn_taking.get('mode', 'free_form')
        
        if mode == 'round_robin':
            return "Enforce strict round-robin order: each participant speaks in turn."
        elif mode == 'moderated':
            return "You decide who speaks next based on conversation flow."
        else:
            return "Allow free-form conversation with natural turn-taking."
    
    def _format_conversation_routing(self, participants: List[Dict[str, Any]], 
                                   conversation_name: str) -> str:
        """Format conversation routing rules."""
        lines = ["Set up conversation routing:"]
        
        # All-to-all communication pattern
        lines.append("""
```json
{
  "type": "ksi_tool_use",
  "id": "ksiu_conversation_route",
  "name": "routing:add_rule",
  "input": {
    "rule_id": "conversation_broadcast",
    "source_pattern": "conversation:message",
    "target": "conversation:participants",
    "mapping": {
      "sender": "{{_agent_id}}",
      "timestamp": "{{_timestamp}}"
    },
    "parent_scope": {"type": "workflow", "id": "{{conversation_id}}"}
  }
}
```""")
        
        return '\n'.join(lines)
    
    def _format_termination_conditions(self, termination: Dict[str, Any]) -> str:
        """Format termination conditions."""
        if not termination:
            return "Continue until natural conversation end."
        
        conditions = []
        if 'timeout' in termination:
            conditions.append(f"- Timeout after {termination['timeout']} seconds")
        if 'message_count' in termination:
            conditions.append(f"- End after {termination['message_count']} messages")
        if 'consensus' in termination:
            conditions.append("- End when consensus is reached")
        
        return '\n'.join(conditions) if conditions else "Continue until natural end."
    
    def save_component(self, component: ComponentTemplate, output_dir: Path) -> Path:
        """Save component to file."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate frontmatter
        frontmatter = f"""---
component_type: {component.component_type}
name: {component.name}
version: {component.version}
description: {component.description}
dependencies:
{self._format_yaml_list(component.dependencies)}
capabilities_required:
{self._format_yaml_list(component.capabilities_required)}
migration_metadata:
  generated_at: {datetime.now().isoformat()}
  generator_version: 1.0.0
---

"""
        
        # Combine frontmatter and content
        full_content = frontmatter + component.content
        
        # Save to file
        file_path = output_dir / f"{component.name}.md"
        with open(file_path, 'w') as f:
            f.write(full_content)
        
        return file_path
    
    def _format_yaml_list(self, items: List[str]) -> str:
        """Format list for YAML frontmatter."""
        return '\n'.join(f"  - {item}" for item in items)


def main():
    """Example usage of the component generator."""
    from .orchestration_parser import OrchestrationParser
    
    # Parse an example orchestration
    parser = OrchestrationParser()
    
    example_yaml = """
name: example_workflow
description: Example workflow for testing migration

agents:
  coordinator:
    component: components/core/coordinator
    vars:
      initial_prompt: You coordinate the workflow
  
  analyzer:
    component: components/personas/data_analyst
    vars:
      initial_prompt: You analyze data
  
  reviewer:
    component: components/personas/reviewer
    vars:
      initial_prompt: You review results

routing:
  rules:
    - pattern: "task:start"
      from: coordinator
      to: analyzer
    - pattern: "analysis:complete"
      from: analyzer
      to: reviewer
    - pattern: "review:complete"
      from: reviewer
      to: coordinator

orchestration_logic:
  strategy: |
    SPAWN analyzer
    SEND task TO analyzer
    AWAIT analysis:complete
    SEND result TO reviewer
    AWAIT review:complete
"""
    
    import yaml
    import io
    data = yaml.safe_load(io.StringIO(example_yaml))
    parsed = parser.parse_orchestration(data, name="example_workflow")
    
    # Generate migration spec
    migration_spec = parser.to_migration_spec(parsed)
    
    # Generate component
    generator = ComponentGenerator()
    component = generator.generate_component(parsed, migration_spec)
    
    print(f"Generated component: {component.name}")
    print(f"Type: {component.component_type}")
    print(f"\nContent preview:")
    print(component.content[:500] + "...")
    
    # Save component
    output_path = generator.save_component(component, Path("/tmp/migrated_components"))
    print(f"\nSaved to: {output_path}")


if __name__ == "__main__":
    main()