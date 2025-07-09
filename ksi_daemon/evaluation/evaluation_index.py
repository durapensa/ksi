#!/usr/bin/env python3
"""Evaluation index for fast discovery without loading all YAML files."""

from pathlib import Path
from typing import Dict, Any, List, Optional
from collections import defaultdict

from ksi_common.logging import get_bound_logger
from ksi_common.config import config
from ksi_common.file_utils import load_yaml_file

logger = get_bound_logger("evaluation_index")


class EvaluationIndex:
    """Fast index for evaluation results."""
    
    def __init__(self):
        self._index: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
        self._loaded = False
    
    def _build_index(self) -> None:
        """Build index from evaluation results directory."""
        results_dir = config.evaluations_dir / "results"
        
        if not results_dir.exists():
            logger.warning(f"Evaluation results directory not found: {results_dir}")
            return
        
        for yaml_file in results_dir.glob("*.yaml"):
            try:
                # Parse filename: {type}_{name}_{eval}_{id}.yaml
                # Need to handle names with dashes properly
                parts = yaml_file.stem.split('_')
                if len(parts) < 4:
                    continue
                
                comp_type = parts[0]
                # Name might contain dashes, so find where eval name starts
                # Look for known test suite names
                eval_start_idx = -1
                for i in range(2, len(parts)-1):
                    if parts[i] in ['basic-effectiveness', 'reasoning-tasks', 'instruction-following']:
                        eval_start_idx = i
                        break
                
                if eval_start_idx == -1:
                    # Fallback: assume structure {type}_{name}_{eval}_{id}
                    comp_name = parts[1]
                    eval_name = parts[2]
                else:
                    # Join parts between type and eval as the name
                    comp_name = '_'.join(parts[1:eval_start_idx])
                    eval_name = parts[eval_start_idx]
                
                # Extract minimal metadata without loading full YAML
                # For now, we'll load just the metadata section
                data = load_yaml_file(yaml_file)
                    
                if 'evaluation' not in data:
                    continue
                
                eval_data = data['evaluation']
                metadata = eval_data.get('metadata', {})
                results = eval_data.get('results', {})
                
                # Build summary info
                summary = {
                    'file': yaml_file.name,
                    'test_suite': metadata.get('test_suite', eval_name),
                    'model': metadata.get('model', 'unknown'),
                    'timestamp': metadata.get('timestamp', ''),
                    'overall_score': results.get('overall_score', 0),
                    'performance_metrics': results.get('performance_metrics', {})
                }
                
                # Index by composition
                comp_key = f"{comp_type}:{comp_name}"
                self._index[comp_key][eval_name].append(summary)
                
            except Exception as e:
                logger.error(f"Failed to index {yaml_file}: {e}")
        
        self._loaded = True
        logger.info(f"Indexed {len(self._index)} compositions with evaluations")
    
    def get_evaluation_info(self, comp_type: str, comp_name: str, 
                           detail_level: str = "minimal") -> Dict[str, Any]:
        """Get evaluation info for a composition at specified detail level.
        
        Detail levels:
        - minimal: Just has_evaluations boolean
        - summary: Count, latest score, latest date
        - detailed: List of all evaluations with scores
        """
        if not self._loaded:
            self._build_index()
        
        comp_key = f"{comp_type}:{comp_name}"
        
        if comp_key not in self._index:
            return {"has_evaluations": False}
        
        all_evals = []
        for test_suite, evals in self._index[comp_key].items():
            all_evals.extend(evals)
        
        if detail_level == "minimal":
            return {"has_evaluations": True}
        
        # Sort by timestamp descending
        all_evals.sort(key=lambda x: x['timestamp'], reverse=True)
        
        if detail_level == "summary":
            latest = all_evals[0] if all_evals else None
            return {
                "has_evaluations": True,
                "evaluation_count": len(all_evals),
                "latest_evaluation": {
                    "score": latest['overall_score'],
                    "test_suite": latest['test_suite'],
                    "timestamp": latest['timestamp'],
                    "model": latest['model']
                } if latest else None
            }
        
        if detail_level == "detailed":
            return {
                "has_evaluations": True,
                "evaluation_count": len(all_evals),
                "evaluations": [
                    {
                        "test_suite": e['test_suite'],
                        "model": e['model'],
                        "score": e['overall_score'],
                        "timestamp": e['timestamp'],
                        "file": e['file']
                    }
                    for e in all_evals
                ]
            }
        
        return {"has_evaluations": False}
    
    def refresh(self) -> None:
        """Refresh the index."""
        self._index.clear()
        self._loaded = False
        self._build_index()


# Global evaluation index instance
evaluation_index = EvaluationIndex()