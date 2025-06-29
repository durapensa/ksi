#!/usr/bin/env python3
"""
Validate all compositions in var/lib using KSI's composition service
"""

import asyncio
import sys
import os
import yaml
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ksi_client import EventBasedClient


class CompositionValidator:
    """Validate KSI compositions for correctness and federation readiness"""
    
    def __init__(self):
        self.client = None
        self.compositions_dir = Path("var/lib/compositions")
        self.errors = []
        self.warnings = []
        self.validated = 0
        self.dependencies = {}  # Track composition dependencies
        
    async def connect(self):
        """Connect to KSI daemon"""
        self.client = EventBasedClient()
        await self.client.connect()
        
    async def disconnect(self):
        """Disconnect from daemon"""
        if self.client:
            await self.client.disconnect()
    
    def discover_compositions(self) -> List[Path]:
        """Find all YAML compositions"""
        compositions = []
        for pattern in ["**/*.yaml", "**/*.yml"]:
            compositions.extend(self.compositions_dir.glob(pattern))
        # Exclude experiments by default
        compositions = [c for c in compositions if "experiments" not in str(c)]
        return sorted(compositions)
    
    def validate_yaml(self, path: Path) -> Tuple[bool, Dict]:
        """Validate YAML syntax"""
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            return True, data
        except Exception as e:
            self.errors.append(f"{path}: Invalid YAML - {e}")
            return False, {}
    
    def validate_structure(self, path: Path, data: Dict) -> bool:
        """Validate composition structure"""
        # Required fields
        required = ["name", "type", "version", "description"]
        missing = [field for field in required if field not in data]
        
        if missing:
            self.errors.append(f"{path}: Missing required fields: {missing}")
            return False
        
        # Valid types
        valid_types = ["profile", "prompt", "orchestration", "system"]
        if data["type"] not in valid_types:
            self.errors.append(f"{path}: Invalid type '{data['type']}', must be one of {valid_types}")
            return False
        
        return True
    
    def extract_dependencies(self, data: Dict) -> Set[str]:
        """Extract all composition dependencies"""
        deps = set()
        
        # Direct dependencies
        if "extends" in data:
            deps.add(data["extends"])
        
        if "mixins" in data:
            deps.update(data["mixins"])
        
        # Component dependencies
        for component in data.get("components", []):
            if "composition" in component:
                deps.add(component["composition"])
        
        return deps
    
    def validate_dependencies(self, name: str, deps: Set[str], all_compositions: Set[str]) -> bool:
        """Validate all dependencies exist"""
        missing = deps - all_compositions
        if missing:
            self.errors.append(f"{name}: Missing dependencies: {missing}")
            return False
        return True
    
    def detect_circular_dependencies(self) -> bool:
        """Detect circular dependency chains"""
        def has_cycle(node: str, visited: Set[str], rec_stack: Set[str]) -> bool:
            visited.add(node)
            rec_stack.add(node)
            
            for dep in self.dependencies.get(node, []):
                if dep not in visited:
                    if has_cycle(dep, visited, rec_stack):
                        return True
                elif dep in rec_stack:
                    self.errors.append(f"Circular dependency: {node} -> {dep}")
                    return True
            
            rec_stack.remove(node)
            return False
        
        visited = set()
        for comp in self.dependencies:
            if comp not in visited:
                if has_cycle(comp, visited, set()):
                    return True
        return False
    
    def validate_metadata(self, path: Path, data: Dict) -> None:
        """Validate and warn about metadata"""
        metadata = data.get("metadata", {})
        
        # Check federation readiness
        if metadata.get("federation_ready"):
            # Check for hardcoded paths
            content = str(data)
            if "/Users/" in content or "/home/" in content:
                self.warnings.append(f"{path}: Contains hardcoded paths, not federation ready")
        
        # Check deprecation
        if metadata.get("deprecated"):
            if "replacement" not in metadata:
                self.warnings.append(f"{path}: Deprecated but no replacement specified")
        
        # Check contracts
        if "provides" in metadata or "requires" in metadata:
            provides = metadata.get("provides", [])
            requires = metadata.get("requires", [])
            
            # Standard capabilities we recognize
            standard_caps = {
                "web_search", "document_analysis", "event_client",
                "information_gathering", "source_validation", "fact_checking",
                "argumentation", "critical_thinking", "creativity",
                "peer_coordination", "self_modification"
            }
            
            # Check for non-standard capabilities
            non_standard_provides = set(provides) - standard_caps
            non_standard_requires = set(requires) - standard_caps
            
            if non_standard_provides:
                self.warnings.append(f"{path}: Non-standard capabilities provided: {non_standard_provides}")
            if non_standard_requires:
                self.warnings.append(f"{path}: Non-standard capabilities required: {non_standard_requires}")
    
    async def validate_resolution(self, name: str, comp_type: str) -> bool:
        """Validate composition resolves correctly via daemon"""
        try:
            # Try to compose
            event = f"composition:{comp_type}" if comp_type in ["profile", "prompt"] else "composition:compose"
            
            result = await self.client.request_event(event, {
                "name": name,
                "variables": {}  # Empty variables to test defaults
            })
            
            if result.get("error"):
                self.errors.append(f"{name}: Failed to resolve - {result['error']}")
                return False
            
            # Check sensibility
            if comp_type == "profile":
                profile = result.get("profile", {})
                if not profile.get("model"):
                    self.warnings.append(f"{name}: Profile missing model specification")
                    
            elif comp_type == "prompt":
                prompt = result.get("prompt", "")
                if not prompt or len(prompt.strip()) < 10:
                    self.warnings.append(f"{name}: Prompt seems too short or empty")
            
            return True
            
        except Exception as e:
            self.errors.append(f"{name}: Resolution error - {e}")
            return False
    
    async def validate_all(self):
        """Run all validations"""
        print("Discovering compositions...")
        compositions = self.discover_compositions()
        print(f"Found {len(compositions)} compositions to validate\n")
        
        # Phase 1: Basic validation and dependency extraction
        print("Phase 1: Structure validation")
        valid_compositions = {}
        all_names = set()
        
        for path in compositions:
            rel_path = path.relative_to(self.compositions_dir)
            print(f"  Checking {rel_path}...", end="")
            
            # YAML validation
            valid, data = self.validate_yaml(path)
            if not valid:
                print(" ❌ (invalid YAML)")
                continue
            
            # Structure validation
            if not self.validate_structure(path, data):
                print(" ❌ (invalid structure)")
                continue
            
            name = data["name"]
            all_names.add(name)
            valid_compositions[name] = (path, data)
            
            # Extract dependencies
            deps = self.extract_dependencies(data)
            if deps:
                self.dependencies[name] = deps
            
            print(" ✓")
        
        # Phase 2: Dependency validation
        print("\nPhase 2: Dependency validation")
        for name, (path, data) in valid_compositions.items():
            deps = self.dependencies.get(name, set())
            if deps:
                if not self.validate_dependencies(name, deps, all_names):
                    print(f"  {name}: ❌ (missing dependencies)")
                else:
                    print(f"  {name}: ✓ ({len(deps)} dependencies)")
        
        # Check for circular dependencies
        if self.detect_circular_dependencies():
            print("  ❌ Circular dependencies detected!")
        
        # Phase 3: Metadata validation
        print("\nPhase 3: Metadata validation")
        for name, (path, data) in valid_compositions.items():
            self.validate_metadata(path, data)
        
        # Phase 4: Resolution validation (requires daemon)
        print("\nPhase 4: Resolution validation")
        try:
            await self.connect()
            
            for name, (path, data) in valid_compositions.items():
                print(f"  Resolving {name}...", end="")
                if await self.validate_resolution(name, data["type"]):
                    print(" ✓")
                    self.validated += 1
                else:
                    print(" ❌")
                    
        except Exception as e:
            print(f"\n⚠️  Could not connect to daemon: {e}")
            print("   Skipping resolution validation")
        finally:
            await self.disconnect()
        
        # Summary
        print("\n" + "="*60)
        print("VALIDATION SUMMARY")
        print("="*60)
        print(f"Total compositions: {len(compositions)}")
        print(f"Valid structure: {len(valid_compositions)}")
        print(f"Resolved successfully: {self.validated}")
        print(f"Errors: {len(self.errors)}")
        print(f"Warnings: {len(self.warnings)}")
        
        if self.errors:
            print("\nERRORS:")
            for error in self.errors:
                print(f"  ❌ {error}")
        
        if self.warnings:
            print("\nWARNINGS:")
            for warning in self.warnings:
                print(f"  ⚠️  {warning}")
        
        return len(self.errors) == 0


async def main():
    """Run composition validation"""
    validator = CompositionValidator()
    success = await validator.validate_all()
    
    if not success:
        print("\n❌ Validation failed!")
        sys.exit(1)
    else:
        print("\n✅ All validations passed!")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())