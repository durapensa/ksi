#!/usr/bin/env python3
"""
Memory Discovery System for KSI

Provides programmatic access to the memory system for Claude instances.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

class KSIMemory:
    def __init__(self, base_path: str = "memory"):
        self.base_path = Path(base_path)
        self.memory_stores = {
            "claude_code": "Knowledge for Claude Code interactive sessions",
            "spawned_agents": "Instructions for autonomous Claude agents",
            "session_patterns": "Patterns for daemon-spawned instances", 
            "workflow_patterns": "System engineering and workflow patterns"
        }
    
    def discover_memories(self) -> Dict[str, List[str]]:
        """Discover all available memory files"""
        memories = {}
        
        for store_name in self.memory_stores:
            store_path = self.base_path / store_name
            if store_path.exists():
                memory_files = [f.name for f in store_path.glob("*.md")]
                memories[store_name] = memory_files
            else:
                memories[store_name] = []
                
        return memories
    
    def read_memory(self, store: str, filename: str) -> Optional[str]:
        """Read a specific memory file"""
        file_path = self.base_path / store / filename
        if file_path.exists():
            return file_path.read_text()
        return None
    
    def get_recommendations(self, context: str = None) -> List[str]:
        """Get memory reading recommendations based on context"""
        recommendations = ["Always start with memory/README.md"]
        
        if context == "claude_code":
            recommendations.extend([
                "Read memory/claude_code/project_knowledge.md",
                "Check for any build/test specific memories"
            ])
        elif context == "spawned_agent":
            recommendations.extend([
                "Read memory/spawned_agents/workspace_requirements.md", 
                "Check for experiment-specific patterns"
            ])
        elif context == "daemon_session":
            recommendations.extend([
                "Read memory/session_patterns/daemon_protocol.md",
                "Check for communication patterns"
            ])
        elif context == "system_engineering":
            recommendations.extend([
                "Read memory/workflow_patterns/system_engineering.md",
                "Check all stores for cross-cutting concerns"
            ])
        else:
            recommendations.append("Read memory/README.md to identify your context")
            
        return recommendations
    
    def validate_memory_integrity(self) -> Dict[str, List[str]]:
        """Validate memory system integrity"""
        issues = {"missing_stores": [], "empty_stores": [], "missing_readme": []}
        
        # Check if main README exists
        if not (self.base_path / "README.md").exists():
            issues["missing_readme"].append("memory/README.md missing")
            
        # Check each memory store
        for store_name in self.memory_stores:
            store_path = self.base_path / store_name
            if not store_path.exists():
                issues["missing_stores"].append(store_name)
            elif not list(store_path.glob("*.md")):
                issues["empty_stores"].append(store_name)
                
        return {k: v for k, v in issues.items() if v}  # Only return non-empty issues

def main():
    """CLI interface for memory discovery"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Discover KSI memory system")
    parser.add_argument("--context", choices=["claude_code", "spawned_agent", "daemon_session", "system_engineering"],
                       help="Context for memory recommendations")
    parser.add_argument("--validate", action="store_true", help="Validate memory integrity")
    parser.add_argument("--list", action="store_true", help="List all available memories")
    
    args = parser.parse_args()
    
    memory = KSIMemory()
    
    if args.validate:
        issues = memory.validate_memory_integrity()
        if issues:
            print("Memory System Issues:")
            for issue_type, items in issues.items():
                print(f"  {issue_type}: {items}")
        else:
            print("Memory system integrity: OK")
            
    if args.list:
        memories = memory.discover_memories()
        print("Available Memories:")
        for store, files in memories.items():
            print(f"  {store}/: {files}")
            
    if args.context:
        recommendations = memory.get_recommendations(args.context)
        print(f"Memory Recommendations for {args.context}:")
        for rec in recommendations:
            print(f"  - {rec}")

if __name__ == "__main__":
    main()