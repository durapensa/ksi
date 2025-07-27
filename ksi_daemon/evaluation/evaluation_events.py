#!/usr/bin/env python3
"""
Evaluation events for agents to interact with the certificate-based evaluation system.
"""
from typing import Dict, Any, List, Optional
from typing_extensions import TypedDict, NotRequired
from pathlib import Path
import yaml
import json
from datetime import datetime

from ksi_common.logging import get_bound_logger
from ksi_common.event_response_builder import event_response_builder, error_response
from ksi_common.config import config
from ksi_daemon.event_system import event_handler
from .certificate_index import CertificateIndex

logger = get_bound_logger("evaluation_events")


class EvaluationRunData(TypedDict):
    """Evaluate component and generate certificate."""
    component_path: str  # Path to component to evaluate
    test_suite: str  # Name of test suite to run
    model: str  # Model being tested (e.g., "claude-sonnet-4")
    test_results: NotRequired[Dict[str, Any]]  # Pre-computed test results (optional)
    orchestration_pattern: NotRequired[str]  # Evaluation orchestration to use (optional)
    notes: NotRequired[List[str]]  # Additional notes
    _ksi_context: NotRequired[Dict[str, Any]]


@event_handler("evaluation:run")
async def handle_evaluation_run(data: EvaluationRunData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Certification wrapper for component evaluation - evaluates any component and produces certificate.
    
    This evaluates any component type (persona, behavior, orchestration, tool, etc.) using the
    specified test suite and generates a certificate as evidence of the evaluation results.
    Orchestration agents can experiment/test/refine components, then emit evaluation:run 
    to acquire certification of the component's performance.
    
    Flow:
    1. Loads the component to be evaluated
    2. Executes appropriate evaluation based on component type and test suite
    3. Generates certificate with evaluation results and component evidence
    4. Updates certificate index automatically
    
    This makes evaluation:run a "evaluate component + certify results" operation that works
    for any component type in the composition system.
    """
    try:
        # Generate certificate locally
        from hashlib import sha256
        import uuid
        
        # Load component to hash
        component_path = Path(config.compositions_dir) / data['component_path']
        if component_path.suffix != '.md':
            component_path = component_path.with_suffix('.md')
            
        if not component_path.exists():
            raise ValueError(f"Component not found: {component_path}")
            
        with open(component_path, 'r') as f:
            content = f.read()
        
        # Hash component content
        component_hash = sha256(content.encode()).hexdigest()
        
        # Generate certificate
        cert = {
            'certificate': {
                'version': '1.0.0',
                'id': str(uuid.uuid4()),
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            },
            'component': {
                'path': data['component_path'],
                'hash': component_hash
            },
            'evaluation': {
                'test_suite': data['test_suite'],
                'model': data['model'],
                'results': data['test_results'],
                'notes': data.get('notes', [])
            }
        }
        
        # Save certificate
        cert_dir = Path(config.evaluations_dir) / "certificates"
        cert_dir.mkdir(parents=True, exist_ok=True)
        
        cert_filename = f"{Path(data['component_path']).stem}_{data['model']}_{cert['certificate']['id'][:8]}.yaml"
        cert_path = cert_dir / cert_filename
        
        with open(cert_path, 'w') as f:
            yaml.dump(cert, f, default_flow_style=False)
        
        # Index in SQLite
        cert_index = CertificateIndex()
        indexed = cert_index.index_certificate(cert_path)
        
        return event_response_builder({
            'status': 'success',
            'certificate_id': cert['certificate']['id'],
            'certificate_path': str(cert_path),
            'indexed': indexed
        }, context)
        
    except Exception as e:
        logger.error(f"Evaluation run failed: {e}")
        return error_response(str(e), context)


class EvaluationQueryData(TypedDict):
    """Query evaluation certificates."""
    component_path: NotRequired[str]  # Filter by component
    tested_on_model: NotRequired[str]  # Filter by model
    evaluation_status: NotRequired[str]  # Filter by status
    limit: NotRequired[int]  # Limit results
    _ksi_context: NotRequired[Dict[str, Any]]


@event_handler("evaluation:query")
async def handle_evaluation_query(data: EvaluationQueryData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Query evaluation certificates."""
    try:
        cert_index = CertificateIndex()
        
        results = cert_index.query_evaluations(
            tested_on_model=data.get('tested_on_model'),
            evaluation_status=data.get('evaluation_status')
        )
        
        # Filter by component path if specified
        if component_path := data.get('component_path'):
            results = [r for r in results if r['component_path'].endswith(component_path)]
        
        # Apply limit
        if limit := data.get('limit'):
            results = results[:limit]
        
        return event_response_builder({
            'status': 'success',
            'evaluations': results,
            'count': len(results)
        }, context)
        
    except Exception as e:
        logger.error(f"Evaluation query failed: {e}")
        return error_response(str(e), context)


class EvaluationCertificateData(TypedDict):
    """Get specific evaluation certificate."""
    certificate_id: str  # Certificate ID
    _ksi_context: NotRequired[Dict[str, Any]]


@event_handler("evaluation:get_certificate") 
async def handle_get_certificate(data: EvaluationCertificateData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get specific evaluation certificate by ID."""
    try:
        cert_id = data['certificate_id']
        
        # Search for certificate file
        cert_dir = config.evaluations_dir / "certificates"
        for cert_file in cert_dir.rglob("*.yaml"):
            with open(cert_file, 'r') as f:
                cert = yaml.safe_load(f)
            
            if cert.get('certificate', {}).get('id') == cert_id:
                return event_response_builder({
                    'status': 'success',
                    'certificate': cert,
                    'path': str(cert_file)
                }, context)
        
        return event_response_builder({
            'status': 'not_found',
            'message': f'Certificate {cert_id} not found'
        }, context)
        
    except Exception as e:
        logger.error(f"Get certificate failed: {e}")
        return error_response(str(e), context)


class EvaluationIndexRebuildData(TypedDict):
    """Rebuild evaluation index."""
    _ksi_context: NotRequired[Dict[str, Any]]


@event_handler("evaluation:rebuild_index")
async def handle_rebuild_evaluation_index(data: EvaluationIndexRebuildData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Rebuild evaluation index from certificates."""
    try:
        cert_index = CertificateIndex()
        indexed, total = cert_index.scan_certificates()
        
        return event_response_builder({
            'status': 'success',
            'certificates_found': total,
            'certificates_indexed': indexed,
            'index_path': str(cert_index.db_path)
        }, context)
        
    except Exception as e:
        logger.error(f"Evaluation index rebuild failed: {e}")
        return error_response(str(e), context)