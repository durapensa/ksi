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
from ksi_daemon.event_system import event_handler
from .certificate_index import CertificateIndex

logger = get_bound_logger("evaluation_events")


class EvaluationRunData(TypedDict):
    """Run evaluation tests and generate certificate."""
    component_path: str  # Path to component to evaluate
    test_suite: str  # Name of test suite to run
    model: str  # Model being tested (e.g., "claude-sonnet-4")
    test_results: Dict[str, Any]  # Test results to record
    notes: NotRequired[List[str]]  # Additional notes
    _ksi_context: NotRequired[Dict[str, Any]]


@event_handler("evaluation:run")
async def handle_evaluation_run(data: EvaluationRunData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run evaluation and generate certificate."""
    try:
        # Import certificate generation utilities
        import sys
        sys.path.append(str(Path(__file__).parent.parent.parent))
        from ksi_evaluation.generate_certificate import generate_certificate, save_certificate
        
        # Generate certificate
        cert = generate_certificate(
            data['component_path'],
            data['test_results'],
            data['model'],
            notes=data.get('notes')
        )
        
        # Save certificate
        cert_path = save_certificate(cert)
        
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
        cert_dir = Path("var/lib/evaluations/certificates")
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