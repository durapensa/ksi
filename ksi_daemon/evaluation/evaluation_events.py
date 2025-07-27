#!/usr/bin/env python3
"""
Evaluation events for agents to interact with the certificate-based evaluation system.
"""
from typing import Dict, Any, List, Optional
from typing_extensions import TypedDict, NotRequired
from pathlib import Path
import yaml
import json
import hashlib
import subprocess
from datetime import datetime, timedelta, timezone

from ksi_common.logging import get_bound_logger
from ksi_common.event_response_builder import event_response_builder, error_response
from ksi_common.config import config
from ksi_daemon.event_system import event_handler
from .certificate_index import CertificateIndex
from .component_hasher import hash_component_at_path

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


def get_instance_id() -> str:
    """Generate or retrieve instance ID for this KSI installation."""
    # For now, use a hash of the working directory
    # In future, this should be stored in KSI configuration
    cwd = Path.cwd().absolute()
    instance_hash = hashlib.sha256(str(cwd).encode()).hexdigest()[:12]
    return f"ksi_instance_{instance_hash}"


def get_ksi_version() -> Dict[str, str]:
    """Get KSI version information."""
    try:
        # Get git commit hash
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], 
                                       universal_newlines=True).strip()[:12]
    except:
        commit = "unknown"
    
    return {
        "ksi_version": "2.0.0",  # TODO: Read from version file
        "ksi_commit": commit,
        "python_version": "3.11.5"  # TODO: Get actual version
    }


def generate_certificate(
    component_path: str,
    test_results: Dict,
    model: str,
    model_version_date: str = "2025-05-14",
    notes: Optional[List[str]] = None
) -> Dict:
    """Generate evaluation certificate for a component."""
    
    # Hash the component
    component_info = hash_component_at_path(component_path)
    
    # Get environment info
    ksi_info = get_ksi_version()
    instance_id = get_instance_id()
    
    # Generate certificate ID
    timestamp = datetime.now(timezone.utc)
    cert_id = f"eval_{timestamp:%Y_%m_%d}_{component_info['hash'][-8:]}"
    
    certificate = {
        "certificate": {
            "id": cert_id,
            "version": "1.0"
        },
        "component": {
            "hash": component_info['hash'],
            "path": component_path,
            "version": component_info['version'] or "unknown",
            "type": component_info['type']
        },
        "evaluator": {
            "instance_id": instance_id,
            "tester": "claude_code"
        },
        "environment": {
            "model": model,
            "model_version_date": model_version_date,
            "test_framework": "ksi_component_test_v1",
            **ksi_info
        },
        "results": test_results,
        "metadata": {
            "created_at": timestamp.isoformat(),
            "expires_at": (timestamp + timedelta(days=365)).isoformat(),
            "test_session_id": f"test_session_{timestamp:%Y%m%d_%H%M%S}",
        }
    }
    
    if notes:
        certificate["results"]["notes"] = notes
    
    return certificate


def save_certificate(certificate: Dict, output_dir: Path = None) -> Path:
    """Save certificate to appropriate location."""
    if output_dir is None:
        output_dir = config.evaluations_dir / "certificates"
    
    # Create date directory
    date_str = datetime.now().strftime("%Y-%m-%d")
    date_dir = output_dir / date_str
    date_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename from component
    component_name = Path(certificate["component"]["path"]).stem
    cert_id = certificate["certificate"]["id"]
    filename = f"{component_name}_{cert_id[-8:]}.yaml"
    
    filepath = date_dir / filename
    
    # Save certificate
    with open(filepath, 'w') as f:
        yaml.dump(certificate, f, default_flow_style=False, sort_keys=False)
    
    # Create symlink in latest
    latest_dir = output_dir / "latest"
    latest_dir.mkdir(exist_ok=True)
    latest_link = latest_dir / filename
    
    # Remove old symlink if exists
    if latest_link.exists() or latest_link.is_symlink():
        latest_link.unlink()
    
    # Create new symlink
    latest_link.symlink_to(f"../{date_str}/{filename}")
    
    return filepath


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
        # Validate component path
        component_path = data['component_path']
        if not component_path.startswith('components/'):
            component_path = f"components/{component_path}"
            
        full_path = Path(config.compositions_dir) / component_path
        if full_path.suffix != '.md':
            full_path = full_path.with_suffix('.md')
            
        if not full_path.exists():
            raise ValueError(f"Component not found: {full_path}")
        
        # Extract model version date if provided, otherwise use default
        model_version_date = "2025-05-14"  # Default for claude models
        if 'model_version_date' in data:
            model_version_date = data['model_version_date']
        
        # Use test_results if provided, otherwise create minimal results
        test_results = data.get('test_results', {
            'status': 'unknown',
            'test_suite': data['test_suite'],
            'tests': {}
        })
        
        # Generate certificate using the migrated function
        certificate = generate_certificate(
            component_path=str(full_path),
            test_results=test_results,
            model=data['model'],
            model_version_date=model_version_date,
            notes=data.get('notes')
        )
        
        # Save certificate using the migrated function
        cert_path = save_certificate(certificate)
        
        # Index in SQLite
        cert_index = CertificateIndex()
        indexed = cert_index.index_certificate(cert_path)
        
        # Also update registry.yaml for backward compatibility
        try:
            registry_path = config.evaluations_dir / "registry.yaml"
            if registry_path.exists():
                with open(registry_path, 'r') as f:
                    registry = yaml.safe_load(f) or {}
                
                # Add to registry
                component_hash = certificate['component']['hash']
                if 'components' not in registry:
                    registry['components'] = {}
                    
                if component_hash not in registry['components']:
                    registry['components'][component_hash] = {
                        'path': component_path,
                        'version': certificate['component']['version'],
                        'evaluations': []
                    }
                
                # Add evaluation summary
                eval_summary = {
                    'certificate_id': certificate['certificate']['id'],
                    'date': certificate['metadata']['created_at'][:10],
                    'model': certificate['environment']['model'],
                    'status': certificate['results'].get('status', 'unknown'),
                    'test_suite': data['test_suite']
                }
                
                registry['components'][component_hash]['evaluations'].append(eval_summary)
                registry['last_updated'] = datetime.now(timezone.utc).isoformat()
                
                # Save registry
                with open(registry_path, 'w') as f:
                    yaml.dump(registry, f, default_flow_style=False, sort_keys=False)
                    
        except Exception as e:
            logger.warning(f"Failed to update registry.yaml: {e}")
        
        return event_response_builder({
            'status': 'success',
            'certificate_id': certificate['certificate']['id'],
            'certificate_path': str(cert_path),
            'indexed': indexed,
            'component_hash': certificate['component']['hash']
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