#!/usr/bin/env python3
"""
Certificate-based evaluation index for composition discovery integration.
Indexes YAML certificates for fast SQL queries while keeping certificates as source of truth.

Moved from ksi_daemon.evaluation.certificate_index to ksi_common for reuse by orchestrations.
"""
import sqlite3
import json
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from contextlib import contextmanager

from ksi_common.logging import get_bound_logger
from ksi_common.config import config

logger = get_bound_logger("evaluation_index")


class CertificateIndex:
    """SQLite index for evaluation certificates."""
    
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = config.evaluation_index_db_path
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with proper cleanup."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _init_db(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS evaluation_index (
                    component_hash TEXT PRIMARY KEY,
                    component_path TEXT NOT NULL,
                    component_type TEXT,
                    component_version TEXT,
                    latest_evaluation_date TEXT,
                    latest_status TEXT,
                    performance_class TEXT,
                    models_tested TEXT,  -- JSON array
                    evaluation_summary TEXT,  -- JSON object
                    certificates TEXT,  -- JSON array of certificate metadata
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_eval_component_path 
                    ON evaluation_index(component_path);
                CREATE INDEX IF NOT EXISTS idx_eval_status 
                    ON evaluation_index(latest_status);
                CREATE INDEX IF NOT EXISTS idx_eval_models 
                    ON evaluation_index(models_tested);
            """)
            conn.commit()
    
    def index_certificate(self, cert_path: Path) -> bool:
        """Index a single evaluation certificate."""
        try:
            with open(cert_path, 'r') as f:
                cert = yaml.safe_load(f)
            
            if not cert or 'certificate' not in cert:
                logger.warning(f"Invalid certificate format: {cert_path}")
                return False
            
            component_hash = cert['component']['hash']
            component_path = cert['component']['path']
            
            # Extract summary data - support both old and new formats
            if 'metadata' in cert:
                # Old format
                eval_date = cert['metadata']['created_at'][:10]
                status = cert['results']['status']
                perf_class = cert['results'].get('performance_profile', {}).get('performance_class', 'standard')
                model = cert['environment']['model']
            else:
                # New format from evaluation:run
                eval_date = cert['certificate']['timestamp'][:10]
                status = cert['evaluation']['results'].get('status', 'unknown')
                perf_class = 'standard'  # Default for now
                model = cert['evaluation']['model']
            
            # Get or create component entry
            with self._get_connection() as conn:
                existing = conn.execute(
                    "SELECT * FROM evaluation_index WHERE component_hash = ?",
                    (component_hash,)
                ).fetchone()
                
                if existing:
                    # Update existing entry
                    models = json.loads(existing['models_tested'])
                    if model not in models:
                        models.append(model)
                    
                    certs = json.loads(existing['certificates'])
                    cert_meta = {
                        'id': cert['certificate']['id'],
                        'date': eval_date,
                        'status': status,
                        'model': model,
                        'path': str(cert_path)
                    }
                    certs.append(cert_meta)
                    
                    # Update summary
                    summary = json.loads(existing['evaluation_summary'])
                    summary['total_evaluations'] = len(certs)
                    summary['latest_date'] = max(eval_date, existing['latest_evaluation_date'])
                    
                    conn.execute("""
                        UPDATE evaluation_index SET
                            latest_evaluation_date = ?,
                            latest_status = ?,
                            performance_class = ?,
                            models_tested = ?,
                            certificates = ?,
                            evaluation_summary = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE component_hash = ?
                    """, (
                        summary['latest_date'],
                        status if eval_date >= existing['latest_evaluation_date'] else existing['latest_status'],
                        perf_class if eval_date >= existing['latest_evaluation_date'] else existing['performance_class'],
                        json.dumps(models),
                        json.dumps(certs),
                        json.dumps(summary),
                        component_hash
                    ))
                else:
                    # Create new entry
                    cert_meta = {
                        'id': cert['certificate']['id'],
                        'date': eval_date,
                        'status': status,
                        'model': model,
                        'path': str(cert_path)
                    }
                    
                    summary = {
                        'total_evaluations': 1,
                        'latest_date': eval_date,
                        'passing_count': 1 if status == 'passing' else 0,
                        'models': [model]
                    }
                    
                    conn.execute("""
                        INSERT INTO evaluation_index (
                            component_hash, component_path, component_type,
                            component_version, latest_evaluation_date, latest_status,
                            performance_class, models_tested, certificates,
                            evaluation_summary
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        component_hash,
                        component_path,
                        cert['component'].get('type', 'unknown'),
                        cert['component'].get('version', 'unknown'),
                        eval_date,
                        status,
                        perf_class,
                        json.dumps([model]),
                        json.dumps([cert_meta]),
                        json.dumps(summary)
                    ))
                
                conn.commit()
                logger.info(f"Indexed certificate: {cert_path.name}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to index certificate {cert_path}: {e}")
            return False
    
    def scan_certificates(self, cert_dir: Optional[Path] = None) -> Tuple[int, int]:
        """Scan and index all certificates in directory."""
        if cert_dir is None:
            cert_dir = config.evaluations_dir / "certificates"
        
        if not cert_dir.exists():
            logger.warning(f"Certificate directory not found: {cert_dir}")
            return 0, 0
        
        total = 0
        indexed = 0
        
        for cert_file in cert_dir.rglob("*.yaml"):
            if cert_file.parent.name == "latest":
                continue  # Skip symlinks
            
            total += 1
            if self.index_certificate(cert_file):
                indexed += 1
        
        logger.info(f"Indexed {indexed}/{total} certificates")
        return indexed, total
    
    def get_evaluation_summary(self, component_hash: str) -> Optional[Dict[str, Any]]:
        """Get evaluation summary for a component hash."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM evaluation_index WHERE component_hash = ?",
                (component_hash,)
            ).fetchone()
            
            if not row:
                return None
            
            return {
                'tested': True,
                'latest_status': row['latest_status'],
                'models': json.loads(row['models_tested']),
                'performance_class': row['performance_class'],
                'summary': json.loads(row['evaluation_summary'])
            }
    
    def query_evaluations(self, 
                         tested_on_model: Optional[str] = None,
                         evaluation_status: Optional[str] = None,
                         min_performance_class: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query evaluations with filters."""
        where_clauses = []
        params = []
        
        if tested_on_model:
            where_clauses.append("json_extract(models_tested, '$') LIKE ?")
            params.append(f'%{tested_on_model}%')
        
        if evaluation_status:
            where_clauses.append("latest_status = ?")
            params.append(evaluation_status)
        
        if min_performance_class:
            # Map performance classes to numeric values for comparison
            perf_map = {'fast': 3, 'standard': 2, 'slow': 1}
            min_val = perf_map.get(min_performance_class, 0)
            
            # This is a bit complex in SQL, might need post-filtering
            where_clauses.append("""
                CASE performance_class
                    WHEN 'fast' THEN 3
                    WHEN 'standard' THEN 2
                    WHEN 'slow' THEN 1
                    ELSE 0
                END >= ?
            """)
            params.append(min_val)
        
        query = "SELECT * FROM evaluation_index"
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        
        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            
            results = []
            for row in rows:
                results.append({
                    'component_hash': row['component_hash'],
                    'component_path': row['component_path'],
                    'evaluation': {
                        'tested': True,
                        'latest_status': row['latest_status'],
                        'models': json.loads(row['models_tested']),
                        'performance_class': row['performance_class']
                    }
                })
            
            return results