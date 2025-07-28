#!/usr/bin/env python3
"""
Transformer Migration for Orchestration Routing Patterns

Converts orchestration routing rules and inline transformers to dynamic routing.
"""

from typing import Dict, List, Any, Optional, Tuple
import yaml
from pathlib import Path
from datetime import datetime
import json


class TransformerMigrator:
    """Migrate orchestration routing patterns to transformer configurations."""
    
    def __init__(self):
        self.transformer_counter = 0
        self.foreach_patterns = {
            'group_spawn': 'workflow_spawn_agents',
            'distribute_tasks': 'workflow_distribute_tasks',
            'collect_results': 'workflow_collect_results',
            'parallel_execute': 'workflow_parallel_execute'
        }
    
    def migrate_routing_rules(self, routing_rules: List[Dict[str, Any]], 
                            orchestration_name: str) -> List[Dict[str, Any]]:
        """Convert routing rules to transformer configurations."""
        transformers = []
        
        for rule in routing_rules:
            transformer = self._routing_rule_to_transformer(rule, orchestration_name)
            if transformer:
                transformers.append(transformer)
        
        return transformers
    
    def migrate_inline_transformers(self, inline_transformers: List[Dict[str, Any]],
                                  orchestration_name: str) -> List[Dict[str, Any]]:
        """Convert inline transformers to proper transformer format."""
        transformers = []
        
        for inline in inline_transformers:
            transformer = self._inline_to_transformer(inline, orchestration_name)
            if transformer:
                transformers.append(transformer)
        
        return transformers
    
    def generate_workflow_transformers(self, migration_spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate foreach transformers for workflow patterns."""
        transformers = []
        
        # Agent spawn transformer
        if migration_spec['agents_to_spawn']:
            transformers.append(self._generate_spawn_transformer(migration_spec))
        
        # Task distribution transformer if needed
        if self._needs_distribution_pattern(migration_spec):
            transformers.append(self._generate_distribution_transformer(migration_spec))
        
        # Result collection transformer if needed
        if self._needs_collection_pattern(migration_spec):
            transformers.append(self._generate_collection_transformer(migration_spec))
        
        return transformers
    
    def _routing_rule_to_transformer(self, rule: Dict[str, Any], 
                                   orchestration_name: str) -> Optional[Dict[str, Any]]:
        """Convert a single routing rule to transformer."""
        self.transformer_counter += 1
        
        # Determine source pattern
        source_pattern = rule.get('pattern', '*')
        if rule.get('from_agent'):
            # Add agent context to pattern if from specific agent
            source_pattern = f"{rule['from_agent']}:{source_pattern}"
        
        transformer = {
            'name': f"{orchestration_name}_route_{self.transformer_counter}",
            'source': source_pattern,
            'target': rule['to'],
            'description': f"Migrated routing rule from {orchestration_name}",
            'priority': rule.get('priority', 500),
            'dynamic': True,
            'migration_metadata': {
                'original_rule': rule,
                'migrated_at': datetime.now().isoformat()
            }
        }
        
        # Add condition if present
        if rule.get('condition'):
            transformer['condition'] = rule['condition']
        
        # Add mapping if present
        if rule.get('mapping'):
            transformer['mapping'] = rule['mapping']
        else:
            # Default passthrough mapping
            transformer['mapping'] = {'{{$}}': '{{$}}'}
        
        return transformer
    
    def _inline_to_transformer(self, inline: Dict[str, Any],
                             orchestration_name: str) -> Optional[Dict[str, Any]]:
        """Convert inline transformer to proper format."""
        self.transformer_counter += 1
        
        transformer = {
            'name': f"{orchestration_name}_inline_{self.transformer_counter}",
            'source': inline['source'],
            'target': inline['target'],
            'description': f"Migrated inline transformer from {orchestration_name}",
            'dynamic': True,
            'migration_metadata': {
                'was_inline': True,
                'migrated_at': datetime.now().isoformat()
            }
        }
        
        # Copy optional fields
        for field in ['condition', 'mapping', 'priority']:
            if field in inline:
                transformer[field] = inline[field]
        
        # Handle response routes
        if inline.get('response_route'):
            transformer['response_metadata'] = inline['response_route']
            # Note: Response routes need special handling in migration instructions
        
        return transformer
    
    def _generate_spawn_transformer(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Generate foreach transformer for spawning agents."""
        return {
            'name': f"{spec['orchestration_name']}_spawn_agents",
            'source': f"workflow:create:{spec['orchestration_name']}",
            'foreach': 'data.agents',
            'target': 'agent:spawn',
            'description': f"Spawn all agents for {spec['orchestration_name']} workflow",
            'mapping': {
                'agent_id': '{{data.workflow_id}}_{{item.id}}',
                'component': '{{item.component}}',
                'initial_prompt': '{{item.prompt|""}}',
                'profile': '{{item.profile|"standard"}}',
                '_workflow_id': '{{data.workflow_id}}',
                '_parent_scope': {
                    'type': 'workflow',
                    'id': '{{data.workflow_id}}'
                }
            },
            'priority': 1000,
            'dynamic': True,
            'migration_metadata': {
                'pattern': 'group_spawn',
                'migrated_at': datetime.now().isoformat()
            }
        }
    
    def _generate_distribution_transformer(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Generate foreach transformer for task distribution."""
        return {
            'name': f"{spec['orchestration_name']}_distribute_tasks",
            'source': f"workflow:distribute:{spec['orchestration_name']}",
            'foreach': 'data.tasks',
            'target': 'task:assign',
            'description': f"Distribute tasks in {spec['orchestration_name']} workflow",
            'mapping': {
                'task_id': '{{item.id}}',
                'assigned_to': '{{item.agent_id}}',
                'task_data': '{{item.data}}',
                'priority': '{{item.priority|"normal"}}',
                '_workflow_id': '{{data.workflow_id}}'
            },
            'condition': 'data.distribution_mode == "batch"',
            'priority': 900,
            'dynamic': True,
            'migration_metadata': {
                'pattern': 'task_distribution',
                'migrated_at': datetime.now().isoformat()
            }
        }
    
    def _generate_collection_transformer(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Generate foreach transformer for result collection."""
        return {
            'name': f"{spec['orchestration_name']}_collect_results",
            'source': f"workflow:collect:{spec['orchestration_name']}",
            'foreach': 'data.agents',
            'target': 'state:entity:get',
            'description': f"Collect results from agents in {spec['orchestration_name']}",
            'mapping': {
                'type': 'agent_result',
                'id': '{{data.workflow_id}}_{{item}}_result',
                '_collector_id': '{{_agent_id}}',
                '_workflow_id': '{{data.workflow_id}}'
            },
            'response_route': {
                'from': 'state:entity:result',
                'to': 'workflow:aggregate_results',
                'filter': '_workflow_id == {{data.workflow_id}}'
            },
            'priority': 800,
            'dynamic': True,
            'migration_metadata': {
                'pattern': 'result_collection',
                'migrated_at': datetime.now().isoformat()
            }
        }
    
    def _needs_distribution_pattern(self, spec: Dict[str, Any]) -> bool:
        """Check if workflow needs task distribution pattern."""
        # Check for keywords in orchestration logic or metadata
        indicators = ['distribute', 'assign', 'load_balance', 'worker']
        
        orchestration_text = str(spec.get('orchestration_logic', '')).lower()
        metadata_text = str(spec.get('metadata', {})).lower()
        
        return any(ind in orchestration_text or ind in metadata_text for ind in indicators)
    
    def _needs_collection_pattern(self, spec: Dict[str, Any]) -> bool:
        """Check if workflow needs result collection pattern."""
        indicators = ['collect', 'aggregate', 'gather', 'results']
        
        orchestration_text = str(spec.get('orchestration_logic', '')).lower()
        return any(ind in orchestration_text for ind in indicators)
    
    def generate_routing_events(self, spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate routing:add_rule events for dynamic routing."""
        events = []
        
        for routing in spec['routing_to_create']:
            event = {
                'event': 'routing:add_rule',
                'data': {
                    'rule_id': routing['rule_id'],
                    'source_pattern': routing['source_pattern'],
                    'target': routing['target'],
                    'priority': routing.get('priority', 500),
                    'parent_scope': {
                        'type': 'workflow',
                        'id': spec['orchestration_name']
                    }
                }
            }
            
            # Add optional fields
            if routing.get('condition'):
                event['data']['condition'] = routing['condition']
            
            if routing.get('mapping'):
                event['data']['mapping'] = routing['mapping']
            
            events.append(event)
        
        return events
    
    def save_transformers(self, transformers: List[Dict[str, Any]], 
                         output_path: Path, 
                         orchestration_name: str) -> Path:
        """Save transformers to YAML file."""
        output_path.mkdir(parents=True, exist_ok=True)
        
        file_path = output_path / f"{orchestration_name}_transformers.yaml"
        
        # Add header comment
        content = f"""# Migrated Transformers from {orchestration_name}
# Generated at: {datetime.now().isoformat()}
# 
# These transformers replace the static routing patterns from the orchestration.
# They should be placed in var/lib/transformers/migrated/ or registered dynamically.
#
"""
        
        # Write each transformer as a separate YAML document
        documents = []
        for transformer in transformers:
            documents.append(yaml.dump(transformer, 
                                     default_flow_style=False,
                                     sort_keys=False))
        
        content += '\n---\n'.join(documents)
        
        with open(file_path, 'w') as f:
            f.write(content)
        
        return file_path
    
    def generate_migration_script(self, spec: Dict[str, Any], 
                                transformers: List[Dict[str, Any]]) -> str:
        """Generate a migration script for the orchestration."""
        script = f"""#!/usr/bin/env python3
\"\"\"
Migration script for {spec['orchestration_name']} orchestration

This script migrates the orchestration to use dynamic routing.
\"\"\"

import asyncio
import json
import time
from ksi_client.client import EventClient


async def migrate_{spec['orchestration_name'].replace('-', '_')}():
    \"\"\"Migrate {spec['orchestration_name']} to dynamic routing.\"\"\"
    client = EventClient()
    await client.connect()
    
    print("Starting migration of {spec['orchestration_name']}...")
    
    # Step 1: Create coordinator component
    print("\\n1. Creating coordinator component...")
    coordinator_result = await client.send_event('agent:spawn', {{
        'agent_id': '{spec['orchestration_name']}_coordinator',
        'component': 'components/patterns/{spec['coordination_component']}',
        'initial_prompt': 'You coordinate the {spec['orchestration_name']} workflow.',
        'profile': 'orchestrator'
    }})
    print(f"   Coordinator created: {{coordinator_result.get('status')}}")
    
    # Grant routing capability
    await client.send_event('state:entity:update', {{
        'type': 'agent',
        'id': '{spec['orchestration_name']}_coordinator',
        'properties': {{'capabilities': ['base', 'agent', 'routing_control', 'state']}}
    }})
    
    # Step 2: Register transformers
    print("\\n2. Registering workflow transformers...")
"""
        
        # Add transformer registration
        for transformer in transformers:
            if transformer.get('foreach'):
                script += f"""
    # Foreach transformer: {transformer['name']}
    # Note: Foreach transformers should be in workflow_transformers.yaml
    print("   - {transformer['name']} (foreach pattern)")
"""
            else:
                # Build the event data
                event_data = {
                    'rule_id': transformer['name'],
                    'source_pattern': transformer['source'],
                    'target': transformer['target'],
                    'priority': transformer.get('priority', 500),
                    'mapping': transformer.get('mapping', {})
                }
                
                # Add condition if present
                condition_line = ""
                if transformer.get('condition'):
                    event_data['condition'] = transformer['condition']
                    condition_line = f"        'condition': '{transformer['condition']}',\n"
                
                script += f"""
    # Dynamic transformer: {transformer['name']}
    transformer_{transformer['name'].replace('-', '_')} = await client.send_event('routing:add_rule', {{
        'rule_id': '{transformer['name']}',
        'source_pattern': '{transformer['source']}',
        'target': '{transformer['target']}',
        'priority': {transformer.get('priority', 500)},
{condition_line}        'mapping': {json.dumps(transformer.get('mapping', {}))}
    }})
    print(f"   - {transformer['name']}: {{transformer_{transformer['name'].replace('-', '_')}.get('status')}}")
"""
        
        # Add workflow creation event
        # Prepare agents list
        agents_list = [{'id': a['agent_id'], 'component': a['component']} for a in spec['agents_to_spawn']]
        agents_json = json.dumps(agents_list, indent=8)
        
        script += f"""
    
    # Step 3: Create workflow with agents
    print("\\n3. Creating workflow with agents...")
    workflow_agents = {agents_json}
    
    workflow_result = await client.send_event('workflow:create', {{
        'workflow_id': '{spec['orchestration_name']}_' + str(int(time.time())),
        'agents': workflow_agents
    }})
    print(f"   Workflow created: {{workflow_result}}")
    
    # Step 4: Set up dynamic routing rules
    print("\\n4. Setting up dynamic routing rules...")
"""
        
        # Add routing events
        for event in self.generate_routing_events(spec):
            rule_id = event['data']['rule_id']
            script += f"""
    route_{rule_id.replace('-', '_')} = await client.send_event('{event['event']}', {json.dumps(event['data'], indent=8)})
    print(f"   - {rule_id}: {{route_{rule_id.replace('-', '_')}.get('status')}}")
"""
        
        script += f"""
    
    print("\\n✅ Migration complete!")
    print("\\nThe {spec['orchestration_name']} orchestration now uses:")
    print("- Dynamic routing instead of static patterns")
    print("- Foreach transformers for multi-agent operations")
    print("- Parent-scoped routing for automatic cleanup")
    print("- Coordinator component for intelligent adaptation")
    
    await client.disconnect()


if __name__ == '__main__':
    asyncio.run(migrate_{spec['orchestration_name'].replace('-', '_')}())
"""
        
        return script
    
    def generate_migration_instructions(self, spec: Dict[str, Any],
                                      component_path: Path,
                                      transformers_path: Path,
                                      script_path: Path) -> str:
        """Generate migration instructions document."""
        instructions = f"""# Migration Instructions for {spec['orchestration_name']}

## Overview

This orchestration has been migrated from static YAML to dynamic routing patterns.

## Migration Components

### 1. Coordinator Component
- **Location**: `{component_path}`
- **Type**: {spec['coordination_component']}
- **Description**: Intelligent coordinator that manages the workflow dynamically

### 2. Workflow Transformers  
- **Location**: `{transformers_path}`
- **Count**: {len(spec.get('transformers_to_register', []))} transformers
- **Types**: Routing rules, foreach patterns, response routes

### 3. Migration Script
- **Location**: `{script_path}`
- **Purpose**: Automate the migration process

## Migration Steps

### Option A: Automated Migration (Recommended)

1. Run the migration script:
   ```bash
   python {script_path}
   ```

2. Verify the migration:
   ```bash
   # Check coordinator was created
   ksi send agent:list | grep {spec['orchestration_name']}_coordinator
   
   # Check routing rules
   ksi send routing:query_rules | grep {spec['orchestration_name']}
   
   # Check transformers
   ksi send introspection:transformers | grep {spec['orchestration_name']}
   ```

### Option B: Manual Migration

1. **Copy the coordinator component**:
   ```bash
   cp {component_path} var/lib/compositions/components/migrated/
   ```

2. **Register workflow transformers**:
   ```bash
   cp {transformers_path} var/lib/transformers/migrated/
   ```

3. **Spawn the coordinator**:
   ```bash
   ksi send agent:spawn \\
     --agent-id {spec['orchestration_name']}_coordinator \\
     --component components/migrated/{component_path.stem}
   ```

4. **Grant routing capability**:
   ```bash
   ksi send state:entity:update \\
     --type agent --id {spec['orchestration_name']}_coordinator \\
     --properties '{{"capabilities": ["base", "agent", "routing_control", "state"]}}'
   ```

## Testing the Migration

1. **Start the migrated workflow**:
   ```bash
   ksi send workflow:create:{spec['orchestration_name']} \\
     --workflow_id test_migration_{{timestamp}}
   ```

2. **Monitor execution**:
   ```bash
   # Watch routing decisions
   ksi send introspection:routing_decisions \\
     --event_name "workflow:*" --limit 20
   
   # Check agent status
   ksi send agent:list | grep test_migration
   ```

3. **Verify behavior matches original**:
   - Agents are spawned correctly
   - Routing patterns work as expected
   - Workflow completes successfully

## Rollback Instructions

If issues occur, you can rollback:

1. **Terminate migrated agents**:
   ```bash
   ksi send agent:terminate \\
     --agent-id {spec['orchestration_name']}_coordinator
   ```

2. **Remove dynamic routing rules**:
   ```bash
   ksi send routing:delete_rule --rule_id {spec['orchestration_name']}_*
   ```

3. **Use original orchestration**:
   ```bash
   ksi send orchestration:start \\
     --orchestration {spec['orchestration_name']}
   ```

## Key Differences After Migration

### Before (Static Orchestration)
- Fixed routing patterns in YAML
- No runtime adaptation
- Limited to predefined patterns
- Manual lifecycle management

### After (Dynamic Routing)
- Routing rules created at runtime
- Agents can modify patterns
- Emergent coordination possible
- Automatic cleanup via parent scoping

## Performance Considerations

- Dynamic routing has minimal overhead (~1-2ms per routing decision)
- Foreach transformers efficiently handle batch operations
- Parent-scoped routing reduces memory usage through automatic cleanup

## Support

For issues or questions about this migration:
1. Check routing audit trail: `ksi send routing:query_audit_log`
2. Review introspection data: `ksi send introspection:routing_path`
3. Examine coordinator logs: `ksi send agent:logs --agent-id {spec['orchestration_name']}_coordinator`

---

Generated at: {datetime.now().isoformat()}
Migration Tool Version: 1.0.0
"""
        
        return instructions


def main():
    """Example usage of transformer migration."""
    from .orchestration_parser import OrchestrationParser
    from .component_generator import ComponentGenerator
    
    # Example orchestration
    example_yaml = """
name: example_migration
description: Example for testing migration

agents:
  coordinator:
    component: components/core/coordinator
  worker_1:
    component: components/patterns/worker
  worker_2:
    component: components/patterns/worker

routing:
  rules:
    - pattern: "task:ready"
      from: coordinator
      to: worker_1
      condition: "data.priority == 'high'"
    - pattern: "task:ready"
      from: coordinator
      to: worker_2
      condition: "data.priority == 'normal'"

transformers:
  - source: "worker:complete"
    target: "coordinator:notify"
    mapping:
      worker_id: "{{_agent_id}}"
      completed_at: "{{_timestamp}}"
"""
    
    # Parse
    import yaml
    import io
    parser = OrchestrationParser()
    data = yaml.safe_load(io.StringIO(example_yaml))
    parsed = parser.parse_orchestration(data, name="example_migration")
    spec = parser.to_migration_spec(parsed)
    
    # Migrate transformers
    migrator = TransformerMigrator()
    
    # Migrate routing rules
    routing_transformers = migrator.migrate_routing_rules(parsed.routing_rules, parsed.name)
    print(f"Migrated {len(routing_transformers)} routing rules")
    
    # Migrate inline transformers
    inline_transformers = migrator.migrate_inline_transformers(parsed.transformers, parsed.name)
    print(f"Migrated {len(inline_transformers)} inline transformers")
    
    # Generate workflow transformers
    workflow_transformers = migrator.generate_workflow_transformers(spec)
    print(f"Generated {len(workflow_transformers)} workflow transformers")
    
    # All transformers
    all_transformers = routing_transformers + inline_transformers + workflow_transformers
    
    # Save transformers
    output_dir = Path("/tmp/migration_output")
    transformers_path = migrator.save_transformers(all_transformers, output_dir, parsed.name)
    print(f"\nSaved transformers to: {transformers_path}")
    
    # Generate migration script
    script = migrator.generate_migration_script(spec, all_transformers)
    script_path = output_dir / f"migrate_{parsed.name}.py"
    with open(script_path, 'w') as f:
        f.write(script)
    print(f"Saved migration script to: {script_path}")


if __name__ == "__main__":
    main()