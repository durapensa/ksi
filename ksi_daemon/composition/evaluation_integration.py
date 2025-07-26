#!/usr/bin/env python3
"""
Integration between composition discovery and evaluation certificates.
Enhances composition:discover with evaluation data and filters.
"""
from typing import Dict, Any, List, Optional
from pathlib import Path

from ksi_common.logging import get_bound_logger
from ksi_daemon.evaluation.certificate_index import CertificateIndex

logger = get_bound_logger("evaluation_integration")


class EvaluationIntegration:
    """Integrates evaluation data with composition discovery."""
    
    def __init__(self):
        self.cert_index = CertificateIndex()
    
    def enhance_discovery_query(self, query: Dict[str, Any]) -> tuple[List[str], List[Any]]:
        """
        Add evaluation filters to discovery SQL query.
        Returns additional WHERE clauses and parameters.
        """
        conditions = []
        params = []
        
        # Filter by model tested
        if tested_model := query.get('tested_on_model'):
            # This requires a JOIN with evaluation_index
            conditions.append("""
                EXISTS (
                    SELECT 1 FROM evaluation_index e 
                    WHERE e.component_hash = composition_index.file_hash
                    AND json_extract(e.models_tested, '$') LIKE ?
                )
            """)
            params.append(f'%{tested_model}%')
        
        # Filter by evaluation status
        if eval_status := query.get('evaluation_status'):
            conditions.append("""
                EXISTS (
                    SELECT 1 FROM evaluation_index e
                    WHERE e.component_hash = composition_index.file_hash
                    AND e.latest_status = ?
                )
            """)
            params.append(eval_status)
        
        # Filter by minimum performance class
        if min_perf := query.get('min_performance_class'):
            perf_values = {'fast': 3, 'standard': 2, 'slow': 1}
            min_value = perf_values.get(min_perf, 0)
            
            conditions.append(f"""
                EXISTS (
                    SELECT 1 FROM evaluation_index e
                    WHERE e.component_hash = composition_index.file_hash
                    AND CASE e.performance_class
                        WHEN 'fast' THEN 3
                        WHEN 'standard' THEN 2
                        WHEN 'slow' THEN 1
                        ELSE 0
                    END >= ?
                )
            """)
            params.append(min_value)
        
        return conditions, params
    
    def enhance_results(self, 
                       compositions: List[Dict[str, Any]], 
                       query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Add evaluation data to composition results based on query parameters.
        """
        # Determine evaluation detail level
        include_eval = query.get('include_evaluation', True)
        eval_detail = query.get('evaluation_detail', 'minimal')
        
        if not include_eval:
            return compositions
        
        # Enhance each composition with evaluation data
        enhanced = []
        for comp in compositions:
            # Skip if no file_hash
            if 'file_hash' not in comp:
                enhanced.append(comp)
                continue
            
            # Get evaluation summary
            eval_summary = self.cert_index.get_evaluation_summary(comp['file_hash'])
            
            if eval_summary:
                # Add evaluation data based on detail level
                if eval_detail == 'minimal':
                    comp['evaluation'] = {
                        'tested': True,
                        'latest_status': eval_summary['latest_status'],
                        'models': eval_summary['models'],
                        'performance_class': eval_summary['performance_class']
                    }
                elif eval_detail == 'summary':
                    comp['evaluation'] = eval_summary
                elif eval_detail == 'detailed':
                    # Include full evaluation summary with certificate references
                    comp['evaluation'] = eval_summary
                    comp['evaluation']['certificates'] = self._get_certificate_details(comp['file_hash'])
            else:
                comp['evaluation'] = {'tested': False}
            
            enhanced.append(comp)
        
        return enhanced
    
    def _get_certificate_details(self, component_hash: str) -> List[Dict[str, Any]]:
        """Get detailed certificate information for a component."""
        # This would query the evaluation_index for certificate paths
        # and potentially load certificate details if needed
        # For now, return basic info from the index
        return []
    
    async def rebuild_evaluation_index(self) -> Dict[str, Any]:
        """Rebuild evaluation index from certificates directory."""
        indexed, total = self.cert_index.scan_certificates()
        
        return {
            'status': 'success',
            'certificates_found': total,
            'certificates_indexed': indexed,
            'index_path': str(self.cert_index.db_path)
        }


# Global instance for use in composition service
evaluation_integration = EvaluationIntegration()