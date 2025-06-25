#!/usr/bin/env python3
"""
Prompt Composition Engine

A standardized system for composing AI prompts from modular components.
Designed for git-friendly collaboration and community sharing.

Created as part of the ksi project: https://github.com/user/ksi
"""

import yaml
import re
import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import logging

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ksi_daemon.config import config

# Set up logging only if not already configured
def _setup_logging():
    """Configure logging only if root logger has no handlers (i.e., not already configured)"""
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        # Only configure if no other logging setup exists
        logging.basicConfig(level=logging.INFO)

# Configure logging conditionally
_setup_logging()
logger = logging.getLogger(__name__)

@dataclass
class Component:
    """A single prompt component"""
    name: str
    source: str
    vars: Dict[str, Any]
    condition: Optional[str] = None

@dataclass
class Composition:
    """A complete prompt composition recipe"""
    name: str
    version: str
    description: str
    author: str
    components: List[Component]
    required_context: Dict[str, str]
    metadata: Dict[str, Any]

class PromptComposer:
    """Compose prompts from YAML compositions and Markdown components"""
    
    def __init__(self, base_path: str = None):
        # Use config.prompts_dir as default, fallback to "prompts" for backward compatibility
        if base_path is None:
            try:
                self.base_path = config.prompts_dir
            except:
                # Fallback if config is not available
                self.base_path = Path("prompts")
        else:
            self.base_path = Path(base_path)
        
        self.components_path = self.base_path / "components"
        self.compositions_path = self.base_path / "compositions"
        
        # Ensure directories exist
        self.components_path.mkdir(parents=True, exist_ok=True)
        self.compositions_path.mkdir(parents=True, exist_ok=True)
        
    def load_composition(self, composition_name: str) -> Composition:
        """Load a composition from YAML file"""
        composition_file = self.compositions_path / f"{composition_name}.yaml"
        
        if not composition_file.exists():
            available = self.list_compositions()
            raise FileNotFoundError(
                f"Composition not found: {composition_file}\n"
                f"Available compositions: {', '.join(available)}"
            )
        
        with open(composition_file, 'r') as f:
            data = yaml.safe_load(f)
        
        # Parse components
        components = []
        for comp_data in data.get('components', []):
            component = Component(
                name=comp_data['name'],
                source=comp_data['source'],
                vars=comp_data.get('vars', {}),
                condition=comp_data.get('condition')
            )
            components.append(component)
        
        return Composition(
            name=data['name'],
            version=data['version'],
            description=data['description'],
            author=data['author'],
            components=components,
            required_context=data.get('required_context', {}),
            metadata=data.get('metadata', {})
        )
    
    def load_component(self, component_path: str) -> str:
        """Load a component from markdown file"""
        full_path = self.base_path / component_path
        
        if not full_path.exists():
            # Try to provide helpful error message
            parent_dir = full_path.parent
            if parent_dir.exists():
                available = [f.name for f in parent_dir.glob("*.md")]
                raise FileNotFoundError(
                    f"Component not found: {full_path}\n"
                    f"Available in {parent_dir}: {', '.join(available)}"
                )
            else:
                raise FileNotFoundError(
                    f"Component not found: {full_path}\n"
                    f"Directory does not exist: {parent_dir}"
                )
        
        content = full_path.read_text()
        logger.debug(f"Loaded component {component_path} ({len(content)} chars)")
        return content
    
    def evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """Evaluate a condition string against context"""
        if not condition:
            return True
            
        # Simple condition evaluation
        # Format: "{{variable}} in ['value1', 'value2']" or "{{variable}} == 'value'"
        # This is a simplified evaluator - could be expanded
        
        # Replace {{variable}} with actual values
        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"
            if isinstance(value, str):
                condition = condition.replace(placeholder, f"'{value}'")
            else:
                condition = condition.replace(placeholder, str(value))
        
        try:
            # Simple evaluation - in production, would want safer evaluation
            return eval(condition)
        except:
            logger.warning(f"Could not evaluate condition: {condition}")
            return True
    
    def substitute_variables(self, text: str, variables: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Substitute variables in text using {{variable}} syntax"""
        # Combine component variables and context, with context taking precedence
        all_vars = {**variables, **context}
        
        # Replace {{variable}} patterns
        for key, value in all_vars.items():
            placeholder = f"{{{{{key}}}}}"
            text = text.replace(placeholder, str(value))
        
        return text
    
    def compose(self, composition_name: str, context: Dict[str, Any]) -> str:
        """Compose a complete prompt from composition recipe and context"""
        
        logger.info(f"Composing prompt: {composition_name}")
        
        # Load composition
        composition = self.load_composition(composition_name)
        
        # Validate required context
        missing_context = []
        for required_key in composition.required_context.keys():
            if required_key not in context:
                missing_context.append(required_key)
        
        if missing_context:
            provided_keys = list(context.keys())
            raise ValueError(
                f"Missing required context: {missing_context}\n"
                f"Required: {list(composition.required_context.keys())}\n"
                f"Provided: {provided_keys}"
            )
        
        # Compose prompt from components
        prompt_parts = []
        
        for component in composition.components:
            # Check condition
            if not self.evaluate_condition(component.condition, context):
                logger.info(f"Skipping component {component.name} due to condition: {component.condition}")
                continue
            
            try:
                # Load component content
                component_content = self.load_component(component.source)
                
                # Log variable substitution details
                all_vars = {**component.vars, **context}
                logger.debug(f"Substituting variables for {component.name}: {list(all_vars.keys())}")
                
                # Substitute variables
                final_content = self.substitute_variables(component_content, component.vars, context)
                
                prompt_parts.append(final_content)
                logger.info(f"Added component: {component.name} ({len(final_content)} chars)")
                
            except Exception as e:
                logger.error(f"Failed to process component {component.name}: {e}")
                raise ValueError(f"Error processing component {component.name} from {component.source}: {e}")
        
        # Join all parts
        final_prompt = "\n\n".join(prompt_parts)
        
        logger.info(f"Composed prompt with {len(composition.components)} components")
        return final_prompt
    
    def list_compositions(self) -> List[str]:
        """List available compositions"""
        return [f.stem for f in self.compositions_path.glob("*.yaml")]
    
    def list_components(self) -> List[str]:
        """List available components"""
        return [str(f.relative_to(self.components_path)) for f in self.components_path.rglob("*.md")]
    
    def validate_composition(self, composition_name: str) -> Dict[str, List[str]]:
        """Validate a composition and return any issues"""
        issues = {"missing_components": [], "invalid_conditions": []}
        
        try:
            composition = self.load_composition(composition_name)
            
            # Check if all referenced components exist
            for component in composition.components:
                component_path = self.base_path / component.source
                if not component_path.exists():
                    issues["missing_components"].append(component.source)
            
        except Exception as e:
            issues["composition_errors"] = [str(e)]
        
        return {k: v for k, v in issues.items() if v}  # Only return non-empty issues

def main():
    """CLI interface for prompt composition"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Compose AI prompts from modular components")
    parser.add_argument("composition", nargs="?", help="Composition name to build")
    parser.add_argument("--context", type=str, help="JSON context for composition")
    parser.add_argument("--list", action="store_true", help="List available compositions")
    parser.add_argument("--components", action="store_true", help="List available components")
    parser.add_argument("--validate", type=str, help="Validate a composition")
    parser.add_argument("--output", "-o", type=str, help="Output file for composed prompt")
    
    args = parser.parse_args()
    
    composer = PromptComposer()
    
    if args.list:
        compositions = composer.list_compositions()
        print("Available compositions:")
        for comp in compositions:
            print(f"  - {comp}")
    
    if args.components:
        components = composer.list_components()
        print("Available components:")
        for comp in components:
            print(f"  - {comp}")
    
    if args.validate:
        issues = composer.validate_composition(args.validate)
        if issues:
            print(f"Issues with composition '{args.validate}':")
            for issue_type, items in issues.items():
                print(f"  {issue_type}: {items}")
        else:
            print(f"Composition '{args.validate}' is valid")
    
    if args.composition:
        import json
        context = json.loads(args.context) if args.context else {}
        
        try:
            prompt = composer.compose(args.composition, context)
            
            if args.output:
                Path(args.output).write_text(prompt)
                print(f"Prompt written to {args.output}")
            else:
                print("=== COMPOSED PROMPT ===")
                print(prompt)
                
        except Exception as e:
            print(f"Error composing prompt: {e}")

if __name__ == "__main__":
    main()