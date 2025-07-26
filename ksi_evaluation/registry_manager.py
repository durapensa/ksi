#!/usr/bin/env python3
"""
Registry manager for component evaluation tracking.
Maintains index of all evaluated components and their test status.
"""
import json
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

from hash_component import hash_component_at_path

class EvaluationRegistry:
    def __init__(self, registry_path: Path = None):
        if registry_path is None:
            registry_path = Path("var/lib/evaluations/registry.yaml")
        self.registry_path = registry_path
        self.registry = self._load_registry()
    
    def _load_registry(self) -> Dict:
        """Load or create registry."""
        if self.registry_path.exists():
            with open(self.registry_path, 'r') as f:
                return yaml.safe_load(f) or self._create_empty_registry()
        return self._create_empty_registry()
    
    def _create_empty_registry(self) -> Dict:
        """Create empty registry structure."""
        from generate_certificate import get_instance_id
        
        return {
            "registry_version": "1.0.0",
            "last_updated": datetime.utcnow().isoformat(),
            "instance": {
                "id": get_instance_id(),
                "name": "KSI Development Instance"
            },
            "components": {}
        }
    
    def save(self):
        """Save registry to disk."""
        self.registry["last_updated"] = datetime.utcnow().isoformat()
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.registry_path, 'w') as f:
            yaml.dump(self.registry, f, default_flow_style=False, sort_keys=False)
    
    def add_evaluation(self, certificate_path: Path):
        """Add evaluation from certificate to registry."""
        with open(certificate_path, 'r') as f:
            cert = yaml.safe_load(f)
        
        component_hash = cert["component"]["hash"]
        
        # Create component entry if needed
        if component_hash not in self.registry["components"]:
            self.registry["components"][component_hash] = {
                "path": cert["component"]["path"],
                "version": cert["component"]["version"],
                "evaluations": []
            }
        
        # Extract key evaluation data
        eval_summary = {
            "certificate_id": cert["certificate"]["id"],
            "date": cert["metadata"]["created_at"][:10],
            "model": cert["environment"]["model"],
            "status": cert["results"]["status"],
            "tests_passed": sum(1 for t in cert["results"]["tests"].values() 
                              if t["status"] == "pass"),
            "tests_total": len(cert["results"]["tests"]),
            "performance_class": self._classify_performance(cert["results"])
        }
        
        # Add to evaluations
        self.registry["components"][component_hash]["evaluations"].append(eval_summary)
        
        # Sort evaluations by date (newest first)
        self.registry["components"][component_hash]["evaluations"].sort(
            key=lambda x: x["date"], 
            reverse=True
        )
        
        self.save()
    
    def _classify_performance(self, results: Dict) -> str:
        """Classify performance as fast/standard/slow."""
        if "performance_profile" not in results:
            return "unknown"
        
        p95 = results["performance_profile"].get("response_time_p95", 0)
        if p95 < 5000:
            return "fast"
        elif p95 < 15000:
            return "standard"
        else:
            return "slow"
    
    def find_evaluations(self, 
                        component_path: Optional[str] = None,
                        model: Optional[str] = None,
                        status: Optional[str] = None) -> List[Dict]:
        """Find evaluations matching criteria."""
        results = []
        
        for hash_key, component in self.registry["components"].items():
            # Filter by path if specified
            if component_path and not component["path"].endswith(component_path):
                continue
            
            for eval_data in component["evaluations"]:
                # Filter by model
                if model and eval_data["model"] != model:
                    continue
                
                # Filter by status
                if status and eval_data["status"] != status:
                    continue
                
                results.append({
                    "component": component["path"],
                    "hash": hash_key,
                    "version": component["version"],
                    **eval_data
                })
        
        return results
    
    def get_summary(self) -> Dict:
        """Get registry summary statistics."""
        total_components = len(self.registry["components"])
        total_evaluations = sum(
            len(c["evaluations"]) 
            for c in self.registry["components"].values()
        )
        
        # Count by status
        status_counts = defaultdict(int)
        model_counts = defaultdict(int)
        
        for component in self.registry["components"].values():
            for eval_data in component["evaluations"]:
                status_counts[eval_data["status"]] += 1
                model_counts[eval_data["model"]] += 1
        
        return {
            "total_components": total_components,
            "total_evaluations": total_evaluations,
            "status_breakdown": dict(status_counts),
            "models_tested": dict(model_counts),
            "last_updated": self.registry["last_updated"]
        }

def scan_certificates(cert_dir: Path = None):
    """Scan certificate directory and update registry."""
    if cert_dir is None:
        cert_dir = Path("var/lib/evaluations/certificates")
    
    registry = EvaluationRegistry()
    
    # Find all certificate files
    cert_files = list(cert_dir.rglob("*.yaml"))
    
    for cert_file in cert_files:
        if cert_file.parent.name == "latest":
            continue  # Skip symlinks
        
        print(f"Processing: {cert_file}")
        try:
            registry.add_evaluation(cert_file)
        except Exception as e:
            print(f"  Error: {e}")
    
    print(f"\nRegistry updated with {len(cert_files)} certificates")
    print(f"Summary: {registry.get_summary()}")

def query_registry(component: Optional[str] = None,
                  model: Optional[str] = None,
                  status: Optional[str] = None):
    """Query the registry for evaluations."""
    registry = EvaluationRegistry()
    
    results = registry.find_evaluations(
        component_path=component,
        model=model,
        status=status
    )
    
    if not results:
        print("No evaluations found matching criteria")
        return
    
    # Group by component
    by_component = defaultdict(list)
    for result in results:
        by_component[result["component"]].append(result)
    
    # Display results
    for component_path, evaluations in by_component.items():
        print(f"\n{component_path}")
        print("-" * len(component_path))
        
        for eval_data in evaluations:
            status_icon = "✅" if eval_data["status"] == "passing" else "❌"
            print(f"  {status_icon} {eval_data['model']} ({eval_data['date']})")
            print(f"     Tests: {eval_data['tests_passed']}/{eval_data['tests_total']}")
            print(f"     Performance: {eval_data['performance_class']}")
            print(f"     Certificate: {eval_data['certificate_id']}")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "scan":
            scan_certificates()
        elif command == "query":
            # Simple query interface
            component = sys.argv[2] if len(sys.argv) > 2 else None
            query_registry(component=component)
        elif command == "summary":
            registry = EvaluationRegistry()
            summary = registry.get_summary()
            print(json.dumps(summary, indent=2))
    else:
        print("Usage:")
        print("  python registry_manager.py scan     - Scan certificates and update registry")
        print("  python registry_manager.py query    - Query all evaluations")
        print("  python registry_manager.py query <component> - Query specific component")
        print("  python registry_manager.py summary  - Show registry statistics")