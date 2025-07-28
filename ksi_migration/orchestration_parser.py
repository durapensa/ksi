#!/usr/bin/env python3
"""
Orchestration YAML Parser for Migration to Dynamic Routing

Parses legacy orchestration YAML files and extracts patterns for migration.
"""

import yaml
from typing import Dict, List, Optional, Any, TypedDict
from pathlib import Path
import re
from dataclasses import dataclass, field


class AgentDefinition(TypedDict):
    """Agent definition in orchestration."""
    component: str
    vars: Optional[Dict[str, Any]]
    profile: Optional[str]
    capabilities: Optional[List[str]]


class RoutingRule(TypedDict):
    """Routing rule from orchestration."""
    pattern: str
    from_agent: Optional[str]  # 'from' is reserved
    to: str
    condition: Optional[str]
    mapping: Optional[Dict[str, Any]]


class TransformerDefinition(TypedDict):
    """Inline transformer definition."""
    source: str
    target: str
    condition: Optional[str]
    mapping: Optional[Dict[str, Any]]
    response_route: Optional[Dict[str, Any]]


@dataclass
class ParsedOrchestration:
    """Parsed orchestration structure."""
    name: str
    description: Optional[str] = None
    agents: Dict[str, AgentDefinition] = field(default_factory=dict)
    routing_rules: List[RoutingRule] = field(default_factory=list)
    transformers: List[TransformerDefinition] = field(default_factory=list)
    orchestration_logic: Optional[str] = None
    variables: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    coordination: Dict[str, Any] = field(default_factory=dict)
    performance: Dict[str, Any] = field(default_factory=dict)
    raw_yaml: Optional[Dict[str, Any]] = None


class OrchestrationParser:
    """Parse orchestration YAML files for migration."""
    
    def __init__(self):
        self.dsl_commands = {
            'SPAWN', 'SEND', 'AWAIT', 'FOREACH', 'IF', 'ELSE',
            'COORDINATE', 'TERMINATE', 'CONTINUE', 'AGGREGATE'
        }
    
    def parse_file(self, file_path: Path) -> ParsedOrchestration:
        """Parse an orchestration YAML file."""
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
        
        return self.parse_orchestration(data, name=file_path.stem)
    
    def parse_orchestration(self, data: Dict[str, Any], name: str) -> ParsedOrchestration:
        """Parse orchestration data structure."""
        parsed = ParsedOrchestration(
            name=name,
            description=data.get('description'),
            raw_yaml=data
        )
        
        # Parse agents
        if 'agents' in data:
            parsed.agents = self._parse_agents(data['agents'])
        
        # Parse routing rules
        if 'routing' in data:
            parsed.routing_rules = self._parse_routing(data['routing'])
        
        # Parse inline transformers
        if 'transformers' in data:
            parsed.transformers = self._parse_transformers(data['transformers'])
        
        # Parse orchestration logic (DSL)
        if 'orchestration_logic' in data:
            parsed.orchestration_logic = self._parse_orchestration_logic(data['orchestration_logic'])
        
        # Parse variables
        if 'variables' in data:
            parsed.variables = data['variables']
        
        # Parse metadata
        if 'metadata' in data:
            parsed.metadata = data['metadata']
        
        # Parse coordination
        if 'coordination' in data:
            parsed.coordination = data['coordination']
        
        # Parse performance
        if 'performance' in data:
            parsed.performance = data['performance']
        
        return parsed
    
    def _parse_agents(self, agents_data: Dict[str, Any]) -> Dict[str, AgentDefinition]:
        """Parse agent definitions."""
        agents = {}
        
        for agent_id, agent_config in agents_data.items():
            agent_def: AgentDefinition = {
                'component': agent_config.get('component', 'components/core/base_agent'),
                'vars': agent_config.get('vars'),
                'profile': agent_config.get('profile'),
                'capabilities': agent_config.get('capabilities')
            }
            agents[agent_id] = agent_def
        
        return agents
    
    def _parse_routing(self, routing_data: Any) -> List[RoutingRule]:
        """Parse routing rules."""
        rules = []
        
        if isinstance(routing_data, dict) and 'rules' in routing_data:
            routing_data = routing_data['rules']
        
        if isinstance(routing_data, list):
            for rule in routing_data:
                routing_rule: RoutingRule = {
                    'pattern': rule.get('pattern', '*'),
                    'from_agent': rule.get('from'),
                    'to': rule.get('to', ''),
                    'condition': rule.get('condition'),
                    'mapping': rule.get('mapping')
                }
                rules.append(routing_rule)
        
        return rules
    
    def _parse_transformers(self, transformers_data: List[Dict[str, Any]]) -> List[TransformerDefinition]:
        """Parse inline transformer definitions."""
        transformers = []
        
        for transformer in transformers_data:
            transformer_def: TransformerDefinition = {
                'source': transformer.get('source', ''),
                'target': transformer.get('target', ''),
                'condition': transformer.get('condition'),
                'mapping': transformer.get('mapping'),
                'response_route': transformer.get('response_route')
            }
            transformers.append(transformer_def)
        
        return transformers
    
    def _parse_orchestration_logic(self, logic_data: Any) -> Optional[str]:
        """Parse orchestration logic DSL."""
        if isinstance(logic_data, dict) and 'strategy' in logic_data:
            return logic_data['strategy']
        elif isinstance(logic_data, str):
            return logic_data
        return None
    
    def analyze_patterns(self, parsed: ParsedOrchestration) -> Dict[str, Any]:
        """Analyze patterns in the parsed orchestration for migration."""
        analysis = {
            'has_static_routing': bool(parsed.routing_rules),
            'has_inline_transformers': bool(parsed.transformers),
            'has_dsl_logic': bool(parsed.orchestration_logic),
            'has_coordination_rules': bool(parsed.coordination),
            'agent_count': len(parsed.agents),
            'routing_rule_count': len(parsed.routing_rules),
            'uses_variables': bool(parsed.variables),
            'complexity': 'simple'  # Will be updated based on analysis
        }
        
        # Analyze DSL complexity
        if parsed.orchestration_logic:
            dsl_commands = self._extract_dsl_commands(parsed.orchestration_logic)
            analysis['dsl_commands'] = dsl_commands
            analysis['dsl_command_count'] = len(dsl_commands)
            
            if len(dsl_commands) > 10:
                analysis['complexity'] = 'complex'
            elif len(dsl_commands) > 5:
                analysis['complexity'] = 'medium'
        
        # Check for advanced features
        if parsed.coordination:
            if 'turn_taking' in parsed.coordination:
                analysis['has_turn_taking'] = True
            if 'termination' in parsed.coordination:
                analysis['has_termination_conditions'] = True
        
        # Check for async patterns
        for transformer in parsed.transformers:
            if transformer.get('response_route'):
                analysis['has_async_patterns'] = True
                break
        
        return analysis
    
    def _extract_dsl_commands(self, dsl_text: str) -> List[str]:
        """Extract DSL commands from orchestration logic."""
        commands = []
        
        # Find all uppercase words that match known DSL commands
        pattern = r'\b(' + '|'.join(self.dsl_commands) + r')\b'
        matches = re.findall(pattern, dsl_text, re.IGNORECASE)
        
        return [match.upper() for match in matches]
    
    def to_migration_spec(self, parsed: ParsedOrchestration) -> Dict[str, Any]:
        """Convert parsed orchestration to migration specification."""
        spec = {
            'orchestration_name': parsed.name,
            'description': parsed.description,
            'agents_to_spawn': [],
            'routing_to_create': [],
            'transformers_to_register': [],
            'coordination_component': None,
            'variables': parsed.variables,
            'metadata': parsed.metadata
        }
        
        # Convert agents to spawn specs
        for agent_id, agent_def in parsed.agents.items():
            spawn_spec = {
                'agent_id': agent_id,
                'component': agent_def['component'],
                'initial_prompt': agent_def.get('vars', {}).get('initial_prompt'),
                'profile': agent_def.get('profile'),
                'capabilities': agent_def.get('capabilities'),
                'variables': {k: v for k, v in agent_def.get('vars', {}).items() 
                            if k != 'initial_prompt'}
            }
            spec['agents_to_spawn'].append(spawn_spec)
        
        # Convert routing rules
        for rule in parsed.routing_rules:
            routing_spec = {
                'rule_id': f"{parsed.name}_{rule['pattern'].replace(':', '_').replace('*', 'all')}",
                'source_pattern': rule['pattern'],
                'target': rule['to'],
                'condition': rule.get('condition'),
                'mapping': rule.get('mapping', {}),
                'from_agent': rule.get('from_agent')
            }
            spec['routing_to_create'].append(routing_spec)
        
        # Convert inline transformers
        for transformer in parsed.transformers:
            transformer_spec = {
                'name': f"{parsed.name}_transformer_{len(spec['transformers_to_register'])}",
                'source': transformer['source'],
                'target': transformer['target'],
                'condition': transformer.get('condition'),
                'mapping': transformer.get('mapping', {}),
                'dynamic': True
            }
            spec['transformers_to_register'].append(transformer_spec)
        
        # Determine coordination component type
        analysis = self.analyze_patterns(parsed)
        if analysis['complexity'] == 'complex':
            spec['coordination_component'] = 'workflow_coordinator'
        elif analysis.get('has_turn_taking'):
            spec['coordination_component'] = 'conversation_coordinator'
        elif len(parsed.agents) > 3:
            spec['coordination_component'] = 'task_distributor'
        else:
            spec['coordination_component'] = 'simple_coordinator'
        
        return spec


def main():
    """Example usage of the parser."""
    parser = OrchestrationParser()
    
    # Example: Parse a simple orchestration
    example_yaml = """
name: simple_analysis
description: Simple analysis orchestration

agents:
  coordinator:
    component: components/core/base_agent
    vars:
      initial_prompt: |
        You coordinate the analysis workflow.
  
  analyzer:
    component: components/personas/data_analyst
    profile: analyzer

routing:
  rules:
    - pattern: "task:assign"
      from: coordinator
      to: analyzer
    - pattern: "analysis:complete"
      from: analyzer
      to: coordinator

variables:
  task_description: "Analyze the provided data"
  timeout: 300
"""
    
    # Parse the example
    import io
    data = yaml.safe_load(io.StringIO(example_yaml))
    parsed = parser.parse_orchestration(data, name="example")
    
    # Analyze patterns
    analysis = parser.analyze_patterns(parsed)
    print("Analysis:", analysis)
    
    # Generate migration spec
    migration_spec = parser.to_migration_spec(parsed)
    print("\nMigration Spec:", migration_spec)


if __name__ == "__main__":
    main()