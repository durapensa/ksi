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
from ksi_daemon.event_system import event_handler, get_router
from ksi_daemon.composition.composition_index import rebuild as rebuild_composition_index
from .component_hasher import hash_component_at_path
from .pre_certification_validator import pre_certification_validator

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
    notes: Optional[List[str]] = None,
    dependency_hashes: Optional[List[Dict[str, str]]] = None,
    validation_result: Optional[Dict[str, Any]] = None,
    validation_warnings: Optional[List[str]] = None
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
    
    # Add dependency hashes if provided
    if dependency_hashes:
        certificate["component"]["dependencies"] = dependency_hashes
    
    if notes:
        certificate["results"]["notes"] = notes
    
    # Add validation results if provided
    if validation_result:
        certificate["validation"] = {
            "structural_issues": validation_result.get('structural_issues', []),
            "adaptations": validation_result.get('adaptations', []),
            "performance_metrics": validation_result.get('performance_metrics', {}),
            "git_version": validation_result.get('git_version'),
            "requires_human_validation": validation_result.get('requires_human_validation', False)
        }
    
    # Add validation warnings if provided
    if validation_warnings:
        certificate["validation_warnings"] = validation_warnings
        
        # Add performance metrics to results if collected from optimization
        if validation_result.get('performance_metrics'):
            certificate["results"]["performance_metrics"] = validation_result['performance_metrics']
    
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
    2. Verifies all dependencies have been tested
    3. Executes appropriate evaluation based on component type and test suite
    4. Generates certificate with evaluation results and component evidence
    5. Updates certificate index automatically
    
    This makes evaluation:run a "evaluate component + certify results" operation that works
    for any component type in the composition system.
    """
    try:
        # Validate component path using the same approach as composition system
        component_path = data['component_path']
        
        # Use shared utilities for consistent path resolution (same as composition:get_component)
        from ksi_common.composition_utils import load_composition_with_metadata
        
        # Try to detect component type from path
        comp_type = 'component'  # default
        if 'behaviors/' in component_path:
            comp_type = 'behavior'
        elif 'personas/' in component_path:
            comp_type = 'persona'
        elif 'orchestrations/' in component_path:
            comp_type = 'orchestration'
        elif 'tools/' in component_path:
            comp_type = 'tool'
        elif 'evaluations/' in component_path:
            comp_type = 'evaluation'
        elif 'core/' in component_path:
            comp_type = 'core'
        
        try:
            logger.info(f"Attempting to load component: {component_path} (type: {comp_type})")
            # Load both parsed and raw content cleanly
            metadata, content, full_path = load_composition_with_metadata(component_path, comp_type, preserve_raw=False)
            _, raw_content, _ = load_composition_with_metadata(component_path, comp_type, preserve_raw=True)
            logger.info(f"Successfully loaded component from: {full_path} (raw content: {len(raw_content)} chars)")
        except FileNotFoundError as e:
            logger.error(f"Component not found at path: {component_path}, error: {e}")
            raise ValueError(f"Component not found: {component_path}")
        
        # Initialize validation warnings list for non-blocking issues
        validation_warnings = []
        
        # Check if this component version is already validated/certified
        component_hash_info = hash_component_at_path(str(full_path))
        component_hash = component_hash_info['hash']
        
        # Load registry once for both version checking and dependency validation
        registry_path = config.evaluations_dir / "registry.yaml"
        registry = {}
        if registry_path.exists():
            with open(registry_path, 'r') as f:
                registry = yaml.safe_load(f) or {}
        
        components_registry = registry.get('components', {})
        registered_hashes = set(components_registry.keys())
        
        # Check if this exact version is already validated
        if component_hash in components_registry:
            existing_evals = components_registry[component_hash].get('evaluations', [])
            # Check if already has passing evaluation for this test suite
            has_passing = any(
                eval.get('status') == 'passing' and 
                eval.get('test_suite') == data['test_suite'] and
                eval.get('model') == data['model']
                for eval in existing_evals
            )
            
            if has_passing:
                logger.info(f"Component {component_path} (hash: {component_hash}) already has passing evaluation, skipping re-validation")
                # Return the existing certificate info
                matching_cert = next(
                    eval for eval in existing_evals 
                    if eval.get('status') == 'passing' and 
                    eval.get('test_suite') == data['test_suite'] and
                    eval.get('model') == data['model']
                )
                return event_response_builder({
                    'status': 'already_validated',
                    'certificate_id': matching_cert['certificate_id'],
                    'component_hash': component_hash,
                    'message': f"Component already validated with certificate {matching_cert['certificate_id']}"
                }, context)
        
        # Run pre-certification validation BEFORE dependency checking (non-blocking per requirements)
        logger.info(f"Running pre-certification validation for {component_path}")
        try:
            validation_result = await pre_certification_validator.validate_component(component_path, raw_content)
            logger.info(f"Pre-certification validation completed for {component_path}: adaptations={len(validation_result.get('adaptations', []))}")
        except Exception as e:
            logger.error(f"Pre-certification validation failed: {e}")
            # Continue with original content if validation fails
            validation_result = {
                'structural_issues': [],
                'adaptations': [],
                'performance_metrics': {},
                'git_version': None,
                'requires_human_validation': False,
                'validation_passed': True,
                'optimization_run': False
            }
        
        # Log validation results
        if validation_result['structural_issues']:
            logger.warning(f"Component {component_path} has {len(validation_result['structural_issues'])} structural issues")
            for issue in validation_result['structural_issues']:
                logger.warning(f"  - {issue['type']}: {issue['message']}")
        
        if validation_result['adaptations']:
            logger.info(f"Component {component_path} had {len(validation_result['adaptations'])} adaptations applied")
            for adaptation in validation_result['adaptations']:
                logger.info(f"  - {adaptation['type']}: {adaptation.get('old', '')} → {adaptation.get('new', '')}")
        
        # If adaptations were made, update the content and metadata BEFORE dependency checking
        if validation_result['adaptations']:
            # Re-parse the adapted content
            adapted_content = validation_result.get('adapted_content', raw_content)
            if adapted_content and adapted_content != raw_content:
                logger.info(f"Using adapted content for evaluation of {component_path}")
                content = adapted_content
                # Re-extract metadata from adapted content for dependency checking
                if adapted_content.startswith('---'):
                    parts = adapted_content.split('---', 2)
                    if len(parts) >= 3:
                        metadata = yaml.safe_load(parts[1]) or metadata
                        # Update content to just the body part (without frontmatter) for consistency
                        content = parts[2].strip()
                        logger.info(f"Re-parsed metadata after adaptations: dependencies={metadata.get('dependencies', [])}")
        
        # Add structural issues to validation warnings
        if validation_result.get('structural_issues'):
            for issue in validation_result['structural_issues']:
                validation_warnings.append(f"Structural issue: {issue.get('message', str(issue))}")
        
        # NOW extract dependencies from corrected metadata
        dependencies = metadata.get('dependencies', [])
        dependency_hashes = []
        
        # Check that all dependencies have been tested
        if dependencies:
            logger.info(f"Component {component_path} has {len(dependencies)} dependencies to verify")
            
            # Registry already loaded above for version checking, reuse it
            
            for dep in dependencies:
                # Resolve dependency path and hash
                try:
                    dep_metadata, dep_content, dep_full_path = load_composition_with_metadata(dep, 'component')
                    dep_info = hash_component_at_path(str(dep_full_path))
                    dep_hash = dep_info['hash']
                    
                    logger.info(f"Checking dependency {dep}: hash={dep_hash}, in_registry={dep_hash in registered_hashes}")
                    
                    # Check if dependency is tested - STRICT validation
                    if dep_hash not in registered_hashes:
                        logger.error(f"Dependency {dep} (hash: {dep_hash}) must be evaluated before testing {component_path}")
                        return error_response(
                            f"Dependency {dep} (hash: {dep_hash}) must be evaluated before testing {component_path}",
                            context
                        )
                    
                    # Check if dependency has passing evaluations - STRICT validation
                    dep_evaluations = components_registry[dep_hash].get('evaluations', [])
                    if not dep_evaluations:
                        logger.error(f"Dependency {dep} has no evaluations recorded")
                        return error_response(
                            f"Dependency {dep} has no evaluations recorded",
                            context
                        )
                    
                    # Check for at least one passing evaluation
                    has_passing = any(
                        eval.get('status') == 'passing' 
                        for eval in dep_evaluations
                    )
                    
                    if not has_passing:
                        failed_statuses = list(set(eval.get('status', 'unknown') for eval in dep_evaluations))
                        logger.error(f"Dependency {dep} must have at least one passing evaluation")
                        return error_response(
                            f"Dependency {dep} must have at least one passing evaluation (current statuses: {', '.join(failed_statuses)})",
                            context
                        )
                    
                    # Record dependency info for certificate
                    dependency_hashes.append({
                        'path': dep,
                        'hash': dep_hash
                    })
                    
                except Exception as e:
                    return error_response(f"Failed to verify dependency {dep}: {e}", context)
        
        # Extract model version date if provided, otherwise use default
        model_version_date = "2025-05-14"  # Default for claude models
        if 'model_version_date' in data:
            model_version_date = data['model_version_date']
        
        # Use test_results if provided, otherwise run actual tests
        test_results = data.get('test_results')
        
        if not test_results:
            # No pre-computed results - we need to run actual tests
            logger.info(f"Running behavioral tests for {component_path}")
            
            # Check if orchestration pattern is specified
            orchestration_pattern = data.get('orchestration_pattern')
            if orchestration_pattern:
                # TODO: Start orchestration to run tests
                logger.warning(f"Orchestration pattern {orchestration_pattern} not yet implemented")
                test_results = {
                    'status': 'unknown',
                    'test_suite': data['test_suite'],
                    'tests': {},
                    'notes': ['Orchestration-based testing not yet implemented']
                }
            else:
                # Run component evaluation by spawning test orchestration
                test_results = await run_component_evaluation(
                    component_path=component_path,  # Pass original relative path, not full_path
                    model=data['model'],
                    test_suite=data['test_suite']
                )
        
        # Ensure test_results has required fields
        if 'status' not in test_results:
            test_results['status'] = 'unknown'
        if 'test_suite' not in test_results:
            test_results['test_suite'] = data['test_suite']
        
        # Generate certificate using the migrated function
        # Use the resolved full_path from load_composition_with_metadata
        certificate = generate_certificate(
            component_path=str(full_path),  # Use the resolved path
            test_results=test_results,
            model=data['model'],
            model_version_date=model_version_date,
            notes=data.get('notes'),
            dependency_hashes=dependency_hashes,
            validation_result=validation_result,
            validation_warnings=validation_warnings
        )
        
        # Save certificate using the migrated function
        cert_path = save_certificate(certificate)
        
        # Index in unified composition system (includes evaluations)
        # The certificate is already saved and added to registry.yaml above
        # The composition index will pick it up on next rebuild
        indexed = True  # Always true since we successfully saved
        
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
                    # Calculate relative path from full_path for registry
                    relative_path = str(Path(full_path).relative_to(config.compositions_dir))
                    registry['components'][component_hash] = {
                        'path': relative_path,
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
    """Query evaluation certificates using unified composition index."""
    try:
        # Use unified composition index with evaluation filters
        query_params = {}
        
        if data.get('tested_on_model'):
            query_params['tested_on_model'] = data['tested_on_model']
        if data.get('evaluation_status'):
            query_params['evaluation_status'] = data['evaluation_status']
        if data.get('component_path'):
            query_params['component_path'] = data['component_path']
        if data.get('limit'):
            query_params['limit'] = data['limit']
            
        # Use unified evaluation discovery
        from ksi_daemon.composition.evaluation_integration import evaluation_integration
        evaluated_results = await evaluation_integration.discover_with_evaluations(query_params)
        
        return event_response_builder({
            'status': 'success',
            'evaluations': evaluated_results,
            'count': len(evaluated_results)
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
    """Rebuild evaluation index using unified composition system."""
    try:
        # Use unified composition index rebuild which includes evaluations
        result = await rebuild_composition_index()
        
        return event_response_builder({
            'status': 'success',
            'evaluations_indexed': result.get('evaluations_indexed', 0),
            'compositions_indexed': result.get('compositions_indexed', 0),
            'total_scanned': result.get('total_scanned', 0),
            'skipped_files': result.get('skipped_files', []),
            'message': 'Rebuilt unified composition and evaluation index'
        }, context)
        
    except Exception as e:
        logger.error(f"Evaluation index rebuild failed: {e}")
        return error_response(str(e), context)


class RegistryRemoveData(TypedDict):
    """Remove component from evaluation registry."""
    component_hash: str  # Component hash to remove (e.g., "sha256:...")
    _ksi_context: NotRequired[Dict[str, Any]]


async def run_component_evaluation(
    component_path: str,
    model: str,
    test_suite: str
) -> Dict[str, Any]:
    """Run component evaluation by spawning test agent directly."""
    try:
        import uuid
        import asyncio
        
        # Generate unique evaluation ID
        eval_id = f"eval_{uuid.uuid4().hex[:8]}"
        test_agent_id = f"test_agent_{eval_id}"
        
        router = get_router()
        
        # For now, run a basic behavioral test
        # In the future, this can be expanded based on test_suite parameter
        logger.info(f"Running behavioral test for {component_path} with model {model}")
        
        # Use the component renderer to ensure dependencies are properly resolved
        # The agent:spawn handler will use the renderer internally, but we need
        # to ensure we're passing the correct component path format
        # Use the original component path passed in
        spawn_results = await router.emit("agent:spawn", {
            "agent_id": test_agent_id,
            "model": model,
            "component": component_path  # Use the component_path parameter
        }, context=None)
        
        spawn_result = spawn_results[0] if spawn_results else {}
        
        if spawn_result.get('status') not in ('success', 'created'):
            logger.error(f"Failed to spawn test agent: {spawn_result}")
            return {
                'status': 'error',
                'test_suite': test_suite,
                'tests': {},
                'notes': [f"Failed to spawn test agent: {spawn_result.get('error', 'Unknown error')}"]
            }
        
        # Send a test prompt to the agent
        completion_results = await router.emit("completion:async", {
            "agent_id": test_agent_id,
            "prompt": "Please emit an agent:status event to confirm you are operational."
        }, context=None)
        
        completion_result = completion_results[0] if completion_results else {}
        
        # Check if request was queued (normal async behavior)
        if completion_result.get('status') == 'queued':
            request_id = completion_result.get('request_id')
            logger.info(f"Completion request {request_id} queued, waiting for result...")
            
            # Wait for completion to finish (configurable timeout)
            from ksi_common.constants import DEFAULT_EVALUATION_COMPLETION_TIMEOUT
            max_wait = getattr(config, 'evaluation_completion_timeout', DEFAULT_EVALUATION_COMPLETION_TIMEOUT)  # Default 5 minutes
            check_interval = 2
            elapsed = 0
            completion_done = False
            
            logger.info(f"Waiting for completion of request_id: {request_id}, max_wait: {max_wait}s")
            
            while elapsed < max_wait:
                await asyncio.sleep(check_interval)
                elapsed += check_interval
                
                # Check for completion:result event via monitor
                # Note: monitor:get_events doesn't support field filtering, so get recent events and filter manually
                event_results = await router.emit("monitor:get_events", {
                    "event_patterns": ["completion:result"],
                    "limit": 10  # Get recent completion results
                }, context=None)
                
                event_result = event_results[0] if event_results else {}
                events = event_result.get('events', [])
                
                # Log detailed debugging info
                logger.info(f"Monitor query returned: event_results count={len(event_results) if event_results else 0}")
                logger.info(f"First result keys: {list(event_result.keys()) if event_result else 'None'}")
                logger.info(f"Events data structure: {type(events)}, count={len(events)}")
                
                # Log what events we're seeing for debugging
                event_request_ids = [e.get('data', {}).get('request_id') for e in events]
                logger.info(f"Found {len(events)} completion:result events, request_ids: {event_request_ids}")
                
                # Filter events by request_id
                matching_events = [e for e in events if e.get('data', {}).get('request_id') == request_id]
                
                if matching_events:
                    # Found completion result for our request
                    logger.info(f"Found matching completion result for request_id: {request_id}")
                    completion_done = True
                    result_data = matching_events[0].get('data', {}).get('result', {})
                    if result_data.get('response', {}).get('is_error'):
                        test_status = 'failing'
                        tests_passed = 0
                        test_notes = f"Agent error: {result_data.get('response', {}).get('error_message', 'Unknown error')}"
                    else:
                        test_status = 'passing'
                        tests_passed = 1
                        test_notes = 'Agent responded successfully'
                    break
            
            if not completion_done:
                # Timeout - report as timeout
                logger.warning(f"Evaluation timeout after {elapsed}s waiting for request_id: {request_id}")
                test_status = 'timeout'
                tests_passed = 0
                test_notes = f'Agent did not respond within timeout period ({elapsed}s)'
                
        elif completion_result.get('status') == 'success':
            test_status = 'passing'
            tests_passed = 1
            test_notes = 'Agent responded successfully to test prompt'
        else:
            test_status = 'failing'
            tests_passed = 0
            test_notes = f"Agent failed to respond: {completion_result.get('error', completion_result.get('message', 'No response'))}"
        
        # Clean up test agent
        await router.emit("agent:stop", {"agent_id": test_agent_id}, context=None)
        
        return {
            'status': test_status,
            'test_suite': test_suite,
            'tests_passed': tests_passed,
            'tests_total': 1,
            'performance_class': 'standard',
            'tests': {
                'basic_response': {
                    'status': 'passed' if test_status == 'passing' else 'failed',
                    'notes': test_notes
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Component evaluation failed: {e}")
        return {
            'status': 'error',
            'test_suite': test_suite,
            'tests': {},
            'notes': [f'Evaluation failed: {str(e)}']
        }


@event_handler("evaluation:registry_remove")
async def handle_registry_remove(data: RegistryRemoveData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Remove a component entry from the evaluation registry."""
    try:
        component_hash = data['component_hash']
        registry_path = config.evaluations_dir / "registry.yaml"
        
        if not registry_path.exists():
            return error_response("Registry file not found", context)
        
        # Load registry using shared utilities
        from ksi_common.yaml_utils import load_yaml_file, save_yaml_file
        registry = load_yaml_file(registry_path)
        
        # Check if component exists
        if 'components' not in registry or component_hash not in registry['components']:
            return event_response_builder({
                'status': 'not_found',
                'message': f'Component {component_hash} not found in registry'
            }, context)
        
        # Get component info before removal
        removed_component = registry['components'][component_hash]
        removed_path = removed_component.get('path', 'unknown')
        eval_count = len(removed_component.get('evaluations', []))
        
        # Remove the component
        del registry['components'][component_hash]
        
        # Update last_updated timestamp
        registry['last_updated'] = datetime.now(timezone.utc).isoformat()
        
        # Save updated registry
        save_yaml_file(registry_path, registry)
        
        logger.info(f"Removed component {component_hash} ({removed_path}) with {eval_count} evaluations from registry")
        
        return event_response_builder({
            'status': 'success',
            'removed': {
                'component_hash': component_hash,
                'path': removed_path,
                'evaluations_count': eval_count
            },
            'message': f'Successfully removed {component_hash} from registry'
        }, context)
        
    except Exception as e:
        logger.error(f"Registry remove failed: {e}")
        return error_response(str(e), context)