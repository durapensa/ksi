#!/usr/bin/env python3
"""
Prompt Composition Discovery Module

Provides a unified interface for discovering and exploring compositions and components.
Uses direct file access to avoid circular dependencies with the daemon.
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

# Add path for prompt composer
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from prompts.composer import PromptComposer


@dataclass
class CompositionInfo:
    """Information about a composition"""
    name: str
    version: str
    description: str
    author: str
    required_context: Dict[str, str]
    metadata: Dict[str, Any]
    components: Optional[List[Dict]] = None


class CompositionDiscovery:
    """Discovery interface for prompt compositions - uses direct file access"""
    
    def __init__(self):
        self._cache = {}
        self._composer = PromptComposer()
    
    async def get_all_compositions(self, include_metadata: bool = True, 
                                 category: Optional[str] = None) -> Dict[str, CompositionInfo]:
        """Get all available compositions"""
        compositions = {}
        
        for comp_name in self._composer.list_compositions():
            try:
                comp = self._composer.load_composition(comp_name)
                if category and comp.metadata.get('category') != category:
                    continue
                    
                compositions[comp_name] = CompositionInfo(
                    name=comp.name,
                    version=comp.version,
                    description=comp.description,
                    author=comp.author,
                    required_context=comp.required_context,
                    metadata=comp.metadata if include_metadata else {}
                )
            except Exception:
                continue
                
        return compositions
    
    async def get_composition(self, name: str) -> CompositionInfo:
        """Get detailed information about a specific composition"""
        comp = self._composer.load_composition(name)
        
        return CompositionInfo(
            name=comp.name,
            version=comp.version,
            description=comp.description,
            author=comp.author,
            required_context=comp.required_context,
            metadata=comp.metadata,
            components=[{
                'name': c.name,
                'source': c.source,
                'vars': c.vars,
                'condition': c.condition
            } for c in comp.components]
        )
    
    async def find_compositions_by_capability(self, capability: str) -> List[str]:
        """Find compositions that require or provide a specific capability"""
        all_comps = await self.get_all_compositions()
        matching = []
        
        for name, comp in all_comps.items():
            # Check metadata for capabilities
            caps = comp.metadata.get('capabilities_required', [])
            if capability in caps:
                matching.append(name)
            
            # Check tags
            tags = comp.metadata.get('tags', [])
            if capability in tags:
                matching.append(name)
        
        return list(set(matching))  # Remove duplicates
    
    async def find_compositions_by_role(self, role: str) -> List[str]:
        """Find compositions suitable for a specific agent role"""
        all_comps = await self.get_all_compositions()
        matching = []
        
        for name, comp in all_comps.items():
            # Check if role matches
            comp_role = comp.metadata.get('role')
            if comp_role == role:
                matching.append(name)
            
            # Check use cases
            use_cases = comp.metadata.get('use_cases', [])
            if role in use_cases:
                matching.append(name)
        
        return list(set(matching))
    
    async def validate_context(self, composition_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate context for a composition"""
        comp = await self.get_composition(composition_name)
        missing = []
        
        for key in comp.required_context:
            if key not in context:
                missing.append(key)
        
        if missing:
            return {
                'valid': False,
                'missing_context': missing,
                'required_context': comp.required_context
            }
        else:
            return {'valid': True}
    
    async def suggest_composition(self, task_description: str, agent_role: Optional[str] = None) -> List[str]:
        """Suggest compositions based on task description and role"""
        all_comps = await self.get_all_compositions()
        scores = {}
        
        # Simple keyword matching for now
        keywords = task_description.lower().split()
        
        for name, comp in all_comps.items():
            score = 0
            
            # Check description
            desc_lower = comp.description.lower()
            for keyword in keywords:
                if keyword in desc_lower:
                    score += 2
            
            # Check metadata
            meta_str = json.dumps(comp.metadata).lower()
            for keyword in keywords:
                if keyword in meta_str:
                    score += 1
            
            # Boost score for role match
            if agent_role and comp.metadata.get('role') == agent_role:
                score += 3
            
            if score > 0:
                scores[name] = score
        
        # Sort by score and return top matches
        sorted_comps = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [name for name, _ in sorted_comps[:5]]  # Top 5 matches


async def main():
    """CLI interface for composition discovery"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Discover prompt compositions")
    parser.add_argument("action", choices=['list', 'info', 'find', 'suggest', 'validate'],
                       help="Discovery action")
    parser.add_argument("--name", help="Composition name (for info/validate)")
    parser.add_argument("--capability", help="Find by capability")
    parser.add_argument("--role", help="Find by role")
    parser.add_argument("--task", help="Task description for suggestions")
    parser.add_argument("--context", help="JSON context for validation")
    parser.add_argument("--category", help="Filter by category")
    
    args = parser.parse_args()
    
    discovery = CompositionDiscovery()
    
    if args.action == 'list':
        comps = await discovery.get_all_compositions(category=args.category)
        print(f"Found {len(comps)} compositions:")
        for name, comp in comps.items():
            print(f"\n{name} (v{comp.version}) by {comp.author}")
            print(f"  {comp.description}")
            if comp.metadata.get('tags'):
                print(f"  Tags: {', '.join(comp.metadata['tags'])}")
    
    elif args.action == 'info':
        if not args.name:
            print("Error: --name required for info action")
            return
            
        comp = await discovery.get_composition(args.name)
        print(f"{comp.name} (v{comp.version})")
        print(f"Author: {comp.author}")
        print(f"Description: {comp.description}")
        print(f"\nRequired Context:")
        for key, desc in comp.required_context.items():
            print(f"  - {key}: {desc}")
        print(f"\nMetadata:")
        print(json.dumps(comp.metadata, indent=2))
        if comp.components:
            print(f"\nComponents ({len(comp.components)}):")
            for c in comp.components:
                print(f"  - {c['name']} ({c['source']})")
    
    elif args.action == 'find':
        if args.capability:
            matches = await discovery.find_compositions_by_capability(args.capability)
            print(f"Compositions with capability '{args.capability}':")
        elif args.role:
            matches = await discovery.find_compositions_by_role(args.role)
            print(f"Compositions for role '{args.role}':")
        else:
            print("Error: --capability or --role required for find action")
            return
            
        for name in matches:
            print(f"  - {name}")
    
    elif args.action == 'suggest':
        if not args.task:
            print("Error: --task required for suggest action")
            return
            
        suggestions = await discovery.suggest_composition(args.task, args.role)
        print(f"Suggested compositions for '{args.task}':")
        for name in suggestions:
            comp = await discovery.get_composition(name)
            print(f"  - {name}: {comp.description}")
    
    elif args.action == 'validate':
        if not args.name or not args.context:
            print("Error: --name and --context required for validate action")
            return
            
        context = json.loads(args.context)
        result = await discovery.validate_context(args.name, context)
        
        if result['valid']:
            print(f"✓ Context is valid for {args.name}")
        else:
            print(f"✗ Context is invalid for {args.name}")
            if 'missing_context' in result:
                print(f"  Missing: {', '.join(result['missing_context'])}")


if __name__ == "__main__":
    asyncio.run(main())