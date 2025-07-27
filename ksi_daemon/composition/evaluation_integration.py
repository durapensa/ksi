#!/usr/bin/env python3
"""
Integration between composition discovery and evaluation certificates.
Enhances composition:discover with evaluation data and filters using unified index.
"""
from typing import Dict, Any, List, Optional
from pathlib import Path
import sqlite3
import json
from contextlib import asynccontextmanager

from ksi_common.logging import get_bound_logger
from ksi_common.config import config

logger = get_bound_logger("evaluation_integration")


class EvaluationIntegration:
    """Integrates evaluation data with composition discovery using unified index."""
    
    @asynccontextmanager
    async def _get_db(self):
        """Get database connection to unified composition index."""
        db_path = config.composition_index_db_path
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    async def discover_with_evaluations(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Discover compositions with evaluation data using unified index.
        """
        conditions = []
        params = []
        
        # Standard composition filters
        if 'component_type' in query:
            conditions.append('ci.component_type = ?')
            params.append(query['component_type'])
            
        if 'name' in query:
            conditions.append('ci.name LIKE ?')
            params.append(f"%{query['name']}%")
        
        # Evaluation filters
        if 'evaluation_status' in query:
            conditions.append('e.status = ?')
            params.append(query['evaluation_status'])
            
        if 'tested_on_model' in query:
            conditions.append('e.model = ?')
            params.append(query['tested_on_model'])
            
        if 'performance_class' in query:
            conditions.append('e.performance_class = ?')
            params.append(query['performance_class'])
        
        where_clause = ' AND '.join(conditions) if conditions else '1=1'
        
        # Add LIMIT clause if specified
        limit_clause = ""
        if 'limit' in query and isinstance(query['limit'], int) and query['limit'] > 0:
            limit_clause = f" LIMIT {query['limit']}"
        
        # Build SQL with proper JOIN
        sql = f"""
            SELECT DISTINCT ci.name, ci.component_type, ci.description, ci.version, ci.author, 
                   ci.tags, ci.capabilities, ci.loading_strategy, ci.file_path, ci.file_hash,
                   e.status as eval_status, e.model as eval_model, e.performance_class
            FROM composition_index ci
            LEFT JOIN evaluations e ON ci.file_hash = REPLACE(e.component_hash, 'sha256:', '')
            WHERE {where_clause}
            ORDER BY ci.name{limit_clause}
        """
        
        results = []
        async with self._get_db() as conn:
            cursor = conn.execute(sql, params)
            for row in cursor:
                result = {
                    'name': row[0],
                    'component_type': row[1],
                    'description': row[2],
                    'version': row[3],
                    'author': row[4],
                    'tags': json.loads(row[5] or '[]'),
                    'capabilities': json.loads(row[6] or '[]'),
                    'loading_strategy': row[7],
                    'file_path': row[8],
                    'file_hash': row[9]
                }
                
                # Add evaluation data
                if row[10]:  # eval_status
                    result['evaluation'] = {
                        'tested': True,
                        'latest_status': row[10],
                        'model': row[11],
                        'performance_class': row[12] or 'standard'
                    }
                else:
                    result['evaluation'] = {'tested': False}
                
                results.append(result)
        
        return results
    
    async def get_certificate_details(self, component_hash: str) -> List[Dict[str, Any]]:
        """Get detailed certificate information for a component from unified index."""
        async with self._get_db() as conn:
            cursor = conn.execute("""
                SELECT certificate_id, evaluation_date, status, model, test_suite, 
                       tests_passed, tests_total, performance_class
                FROM evaluations 
                WHERE component_hash = ? OR component_hash = ?
                ORDER BY evaluation_date DESC
            """, (component_hash, f"sha256:{component_hash}"))
            
            certificates = []
            for row in cursor:
                certificates.append({
                    'certificate_id': row[0],
                    'date': row[1],
                    'status': row[2],
                    'model': row[3],
                    'test_suite': row[4],
                    'tests_passed': row[5],
                    'tests_total': row[6],
                    'performance_class': row[7]
                })
            
            return certificates
    
    async def rebuild_evaluation_index(self) -> Dict[str, Any]:
        """Rebuild evaluation index using unified composition system."""
        from . import composition_index
        result = await composition_index.rebuild()
        
        return {
            'status': 'success',
            'evaluations_indexed': result.get('evaluations_indexed', 0),
            'compositions_indexed': result.get('compositions_indexed', 0),
            'message': 'Using unified composition index (CertificateIndex deprecated)'
        }


# Global instance for use in composition service
evaluation_integration = EvaluationIntegration()