#!/usr/bin/env python3
"""
Certificate-based evaluation index for composition discovery integration.
Indexes YAML certificates for fast SQL queries while keeping certificates as source of truth.
Also maintains registry.yaml for backward compatibility.

Moved from ksi_daemon.evaluation.certificate_index to ksi_common for reuse by orchestrations.
"""
import sqlite3
import json
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from contextlib import contextmanager
from collections import defaultdict

from ksi_common.logging import get_bound_logger
from ksi_common.config import config
from .component_hasher import get_instance_id

logger = get_bound_logger("evaluation_index")


class CertificateIndex:
    """SQLite index for evaluation certificates with registry.yaml support."""
    
    def __init__(self, db_path: Optional[Path] = None, registry_path: Optional[Path] = None):
        if db_path is None:
            db_path = config.evaluation_index_db_path
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        if registry_path is None:
            registry_path = config.evaluations_dir / "registry.yaml"
        self.registry_path = registry_path
        self.registry = self._load_registry()
        
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
                
                # Also update registry.yaml
                self._update_registry_from_certificate(cert_path, cert)
                
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
    
    def _load_registry(self) -> Dict:
        """Load or create registry.yaml."""
        if self.registry_path.exists():
            with open(self.registry_path, 'r') as f:
                return yaml.safe_load(f) or self._create_empty_registry()
        return self._create_empty_registry()
    
    def _create_empty_registry(self) -> Dict:
        """Create empty registry structure."""
        return {
            "registry_version": "1.0.0",
            "last_updated": datetime.utcnow().isoformat(),
            "instance": {
                "id": get_instance_id(),
                "name": "KSI Development Instance"
            },
            "components": {}
        }
    
    def _save_registry(self):
        """Save registry to disk."""
        self.registry["last_updated"] = datetime.utcnow().isoformat()
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.registry_path, 'w') as f:
            yaml.dump(self.registry, f, default_flow_style=False, sort_keys=False)
    
    def _update_registry_from_certificate(self, cert_path: Path, cert: Dict):
        """Update registry.yaml from a certificate."""
        try:
            component_hash = cert["component"]["hash"]
            
            # Create component entry if needed
            if component_hash not in self.registry["components"]:
                self.registry["components"][component_hash] = {
                    "path": cert["component"]["path"],
                    "version": cert["component"].get("version", "unknown"),
                    "evaluations": []
                }
            
            # Extract evaluation summary based on certificate format
            if "metadata" in cert:
                # New format with full test results
                eval_summary = {
                    "certificate_id": cert["certificate"]["id"],
                    "date": cert["metadata"]["created_at"][:10],
                    "model": cert["environment"]["model"],
                    "status": cert["results"].get("status", "unknown"),
                    "tests_passed": sum(1 for t in cert["results"].get("tests", {}).values() 
                                      if t.get("status") == "pass"),
                    "tests_total": len(cert["results"].get("tests", {})),
                    "performance_class": cert["results"].get("performance_profile", {}).get("performance_class", "standard")
                }
            else:
                # Simplified format from evaluation:run
                eval_summary = {
                    "certificate_id": cert["certificate"]["id"],
                    "date": cert["certificate"]["timestamp"][:10] if "timestamp" in cert["certificate"] else datetime.utcnow().isoformat()[:10],
                    "model": cert["evaluation"]["model"],
                    "status": cert["evaluation"]["results"].get("status", "unknown"),
                    "test_suite": cert["evaluation"]["test_suite"]
                }
            
            # Add to evaluations
            self.registry["components"][component_hash]["evaluations"].append(eval_summary)
            
            # Sort evaluations by date (newest first)
            self.registry["components"][component_hash]["evaluations"].sort(
                key=lambda x: x["date"], 
                reverse=True
            )
            
            self._save_registry()
            
        except Exception as e:
            logger.warning(f"Failed to update registry for {cert_path}: {e}")
    
    def get_registry_summary(self) -> Dict:
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
                status_counts[eval_data.get("status", "unknown")] += 1
                model_counts[eval_data.get("model", "unknown")] += 1
        
        return {
            "total_components": total_components,
            "total_evaluations": total_evaluations,
            "status_breakdown": dict(status_counts),
            "models_tested": dict(model_counts),
            "last_updated": self.registry["last_updated"]
        }
    
    def find_registry_evaluations(self, 
                                 component_path: Optional[str] = None,
                                 model: Optional[str] = None,
                                 status: Optional[str] = None) -> List[Dict]:
        """Find evaluations in registry matching criteria."""
        results = []
        
        for hash_key, component in self.registry["components"].items():
            # Filter by path if specified
            if component_path and not component["path"].endswith(component_path):
                continue
            
            for eval_data in component["evaluations"]:
                # Filter by model
                if model and eval_data.get("model") != model:
                    continue
                
                # Filter by status
                if status and eval_data.get("status") != status:
                    continue
                
                results.append({
                    "component": component["path"],
                    "hash": hash_key,
                    "version": component["version"],
                    **eval_data
                })
        
        return results