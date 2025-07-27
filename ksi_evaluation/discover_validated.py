#!/usr/bin/env python3
"""
Discover validated components for a specific use case.
Helps find previously tested components that match requirements.
"""
import yaml
from pathlib import Path
from typing import List, Dict, Optional

def discover_validated_components(
    component_type: Optional[str] = None,
    capabilities_needed: Optional[List[str]] = None,
    model: Optional[str] = None,
    min_performance_class: Optional[str] = "standard"
) -> List[Dict]:
    """
    Discover validated components matching criteria.
    
    Args:
        component_type: Type of component (e.g., "agents", "behaviors")
        capabilities_needed: List of required capabilities
        model: Specific model to check compatibility with
        min_performance_class: Minimum performance level (fast/standard/slow)
    
    Returns:
        List of matching components with evaluation details
    """
    from ksi_common.config import config
    registry_path = config.evaluations_dir / "registry.yaml"
    if not registry_path.exists():
        print("No evaluation registry found. Run 'python ksi_evaluation/registry_manager.py scan' first.")
        return []
    
    with open(registry_path, 'r') as f:
        registry = yaml.safe_load(f)
    
    performance_ranks = {"fast": 3, "standard": 2, "slow": 1, "unknown": 0}
    min_rank = performance_ranks.get(min_performance_class, 0)
    
    matches = []
    
    for component_hash, component_data in registry["components"].items():
        # Filter by component type
        if component_type:
            path_parts = component_data["path"].split("/")
            if component_type not in path_parts:
                continue
        
        # Check evaluations
        for eval_data in component_data["evaluations"]:
            # Filter by model if specified
            if model and eval_data["model"] != model:
                continue
            
            # Filter by performance
            perf_rank = performance_ranks.get(eval_data["performance_class"], 0)
            if perf_rank < min_rank:
                continue
            
            # Filter by status
            if eval_data["status"] != "passing":
                continue
            
            # Load certificate to check capabilities
            cert_id = eval_data["certificate_id"]
            # Search for certificate by ID suffix (last 8 chars)
            cert_path = None
            cert_dir = config.evaluations_dir / "certificates"
            for cert_file in cert_dir.rglob(f"*_{cert_id[-8:]}.yaml"):
                cert_path = cert_file
                break
            
            if cert_path and cert_path.exists():
                with open(cert_path, 'r') as f:
                    cert = yaml.safe_load(f)
                
                # Check required capabilities
                if capabilities_needed:
                    cert_caps = cert["results"].get("capabilities_required", [])
                    if not all(cap in cert_caps for cap in capabilities_needed):
                        continue
                
                matches.append({
                    "path": component_data["path"],
                    "version": component_data["version"],
                    "hash": component_hash,
                    "evaluation": eval_data,
                    "certificate": cert
                })
            else:
                # Still include if certificate not found
                matches.append({
                    "path": component_data["path"],
                    "version": component_data["version"],
                    "hash": component_hash,
                    "evaluation": eval_data,
                    "certificate": None
                })
    
    return matches

def print_discovery_results(matches: List[Dict]):
    """Print discovery results in a readable format."""
    if not matches:
        print("No validated components found matching criteria.")
        return
    
    print(f"Found {len(matches)} validated components:\n")
    
    for match in matches:
        print(f"📦 {match['path']}")
        print(f"   Version: {match['version']}")
        print(f"   Status: ✅ {match['evaluation']['status']}")
        print(f"   Model: {match['evaluation']['model']}")
        print(f"   Tests: {match['evaluation']['tests_passed']}/{match['evaluation']['tests_total']}")
        print(f"   Performance: {match['evaluation']['performance_class']}")
        
        if match['certificate']:
            cert = match['certificate']
            if "notes" in cert["results"]:
                print("   Notes:")
                for note in cert["results"]["notes"]:
                    print(f"     - {note}")
            
            deps = cert["results"].get("dependencies_verified", [])
            if deps:
                print("   Verified Dependencies:")
                for dep in deps:
                    print(f"     - {dep}")
        
        print()

def discover_dsl_components():
    """Find components for DSL execution."""
    print("=== Discovering DSL Execution Components ===\n")
    
    matches = discover_validated_components(
        component_type="agents",
        model="claude-sonnet-4-20250514"
    )
    
    print_discovery_results(matches)
    
    print("\n=== Discovering Behavioral Overrides ===\n")
    
    behavior_matches = discover_validated_components(
        component_type="behaviors",
        model="claude-sonnet-4-20250514",
        min_performance_class="fast"
    )
    
    print_discovery_results(behavior_matches)

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "dsl":
        discover_dsl_components()
    else:
        # General discovery
        all_matches = discover_validated_components()
        print_discovery_results(all_matches)