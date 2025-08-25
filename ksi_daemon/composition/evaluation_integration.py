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
            
        if 'component_path' in query:
            conditions.append('ci.file_path = ?')
            params.append(query['component_path'])
        
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
        
        # Build SQL with path-based JOIN (simpler and more reliable)
        # First query: Get compositions without duplicates
        sql = f"""
            SELECT ci.name, ci.component_type, ci.description, ci.version, ci.author, 
                   ci.tags, ci.capabilities, ci.loading_strategy, ci.file_path, ci.file_hash
            FROM composition_index ci
            WHERE {where_clause}
            ORDER BY ci.name{limit_clause}
        """
        
        results = []
        async with self._get_db() as conn:
            cursor = conn.execute(sql, params)
            compositions = []
            for row in cursor:
                comp = {
                    'name': row[0],
                    'component_type': row[1],
                    'description': row[2],
                    'version': row[3],
                    'author': row[4],
                    'tags': json.loads(row[5] or '[]'),
                    'capabilities': json.loads(row[6] or '[]'),
                    'loading_strategy': row[7],
                    'file_path': row[8],
                    'file_hash': row[9],
                    'evaluation': {'tested': False}  # Default
                }
                compositions.append(comp)
            
            # Second query: Get latest evaluations for these compositions
            if compositions:
                file_paths = [c['file_path'] for c in compositions]
                placeholders = ','.join(['?' for _ in file_paths])
                
                eval_sql = f"""
                    SELECT component_path, status, model, performance_class, evaluation_date,
                           certificate_id, tests_passed, tests_total, test_suite
                    FROM evaluations
                    WHERE component_path IN ({placeholders})
                    AND (component_path, evaluation_date) IN (
                        SELECT component_path, MAX(evaluation_date)
                        FROM evaluations
                        WHERE component_path IN ({placeholders})
                        GROUP BY component_path
                    )
                """
                
                eval_cursor = conn.execute(eval_sql, file_paths + file_paths)
                eval_data = {}
                for row in eval_cursor:
                    # Calculate if certification is expired (1 year validity)
                    from datetime import datetime, timedelta, timezone
                    try:
                        if row[4]:
                            # Handle both timezone-aware and naive datetime strings
                            eval_date_str = row[4]
                            if 'Z' in eval_date_str:
                                eval_date = datetime.fromisoformat(eval_date_str.replace('Z', '+00:00'))
                            elif '+' in eval_date_str or '-' in eval_date_str[-6:]:
                                eval_date = datetime.fromisoformat(eval_date_str)
                            else:
                                # Naive datetime - assume UTC
                                eval_date = datetime.fromisoformat(eval_date_str).replace(tzinfo=timezone.utc)
                            
                            expires_at = eval_date + timedelta(days=365)
                            is_expired = datetime.now(timezone.utc) > expires_at
                            expires_at_str = expires_at.isoformat()
                        else:
                            eval_date = None
                            expires_at_str = None
                            is_expired = False
                    except Exception as e:
                        logger.debug(f"Error processing evaluation date: {e}")
                        eval_date = None
                        expires_at_str = None
                        is_expired = False
                    
                    eval_data[row[0]] = {
                        'tested': True,
                        'status': row[1],
                        'model': row[2],
                        'performance_class': row[3] or 'standard',
                        'certificate_id': row[5],
                        'tests_passed': row[6],
                        'tests_total': row[7],
                        'test_suite': row[8],
                        'evaluation_date': row[4],
                        'expires_at': expires_at_str,
                        'expired': is_expired
                    }
                
                # Merge evaluation data into compositions
                for comp in compositions:
                    if comp['file_path'] in eval_data:
                        comp['evaluation'] = eval_data[comp['file_path']]
                
            results = compositions
        
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