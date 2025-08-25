#!/usr/bin/env python3
"""
Pre-Certification Validator for components.
Performs structural validation and pattern adaptation before certification.
Integrates with optimization system for performance metrics.
"""
import re
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import subprocess
import json
import yaml

from ksi_common.logging import get_bound_logger
from ksi_common.config import config

logger = get_bound_logger("pre_certification_validator")


class PreCertificationValidator:
    """Validates and adapts components before certification."""
    
    def __init__(self):
        self.validation_results = []
        self.adaptations_made = []
        self.performance_metrics = {}
        
    async def validate_component(self, component_path: str, content: str) -> Dict[str, Any]:
        """
        Perform pre-certification validation on a component.
        
        Returns:
            Dict with validation results, adaptations, and metrics
        """
        result = {
            'component_path': component_path,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'structural_issues': [],
            'adaptations': [],
            'performance_metrics': {},
            'git_version': None,
            'requires_human_validation': False,
            'validation_passed': True,
            'optimization_run': False
        }
        
        # Get git version information
        result['git_version'] = await self._get_git_version(component_path)
        
        # Parse frontmatter
        frontmatter, body = self._parse_component(content)
        
        # Structural validations
        structural_issues = await self._validate_structure(frontmatter, body)
        result['structural_issues'] = structural_issues
        logger.debug(f"Structural validation found {len(structural_issues)} issues")
        
        # Dependency validation
        dependency_issues = await self._validate_dependencies(frontmatter)
        result['structural_issues'].extend(dependency_issues)
        logger.debug(f"Dependency validation found {len(dependency_issues)} issues for deps: {frontmatter.get('dependencies', [])}")
        
        # Pattern adaptation (fix old patterns)
        adapted_content, adaptations = await self._adapt_old_patterns(content, frontmatter, body)
        result['adaptations'] = adaptations
        result['adapted_content'] = adapted_content  # Store adapted content for use in evaluation
        
        # Run minimal optimization for metrics (if optimization service available)
        if adaptations or self._should_optimize(frontmatter):
            metrics = await self._run_optimization_metrics(component_path, adapted_content)
            result['performance_metrics'] = metrics
            result['optimization_run'] = True
        
        # Determine if human validation needed
        result['requires_human_validation'] = self._check_human_validation_needed(
            frontmatter, structural_issues, adaptations
        )
        
        # Overall validation pass/fail (non-blocking per requirements)
        result['validation_passed'] = len(structural_issues) == 0
        
        # Store results for reporting
        self.validation_results.append(result)
        
        return result
    
    async def _get_git_version(self, component_path: str) -> Optional[Dict[str, Any]]:
        """Get git version information for component."""
        try:
            file_path = Path(config.compositions_dir) / component_path.replace('components/', '')
            if not file_path.exists():
                file_path = Path(config.compositions_dir) / component_path
            
            if not file_path.exists():
                return None
            
            # Get current commit hash
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True,
                cwd=str(file_path.parent)
            )
            commit_hash = result.stdout.strip() if result.returncode == 0 else None
            
            # Get last modification info for this file
            result = subprocess.run(
                ['git', 'log', '-1', '--format=%H|%ai|%s', str(file_path.name)],
                capture_output=True,
                text=True,
                cwd=str(file_path.parent)
            )
            
            if result.returncode == 0 and result.stdout:
                parts = result.stdout.strip().split('|')
                return {
                    'current_commit': commit_hash,
                    'file_commit': parts[0],
                    'last_modified': parts[1],
                    'last_message': parts[2] if len(parts) > 2 else ''
                }
            
            return {'current_commit': commit_hash}
            
        except Exception as e:
            logger.warning(f"Could not get git version for {component_path}: {e}")
            return None
    
    def _parse_component(self, content: str) -> Tuple[Dict[str, Any], str]:
        """Parse component frontmatter and body."""
        frontmatter = {}
        body = content
        
        if content.startswith('---'):
            try:
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    body = parts[2].strip()
                    logger.debug(f"Parsed frontmatter: {list(frontmatter.keys())}")
            except yaml.YAMLError as e:
                logger.warning(f"Failed to parse frontmatter: {e}")
        
        return frontmatter, body
    
    async def _validate_structure(self, frontmatter: Dict[str, Any], body: str) -> List[Dict[str, Any]]:
        """Validate component structural requirements."""
        issues = []
        
        # Check required frontmatter fields
        if not frontmatter.get('component_type'):
            issues.append({
                'type': 'missing_field',
                'field': 'component_type',
                'severity': 'error',
                'message': 'Component type is required'
            })
        
        # Check for valid component type
        valid_types = ['core', 'persona', 'behavior', 'workflow', 'evaluation', 'tool', 'agent']
        if frontmatter.get('component_type') not in valid_types:
            issues.append({
                'type': 'invalid_field',
                'field': 'component_type',
                'severity': 'warning',
                'message': f"Component type '{frontmatter.get('component_type')}' not in standard types: {valid_types}"
            })
        
        # Check for template variables in body
        template_vars = re.findall(r'\{\{(\w+)\}\}', body)
        if template_vars:
            # Verify all template vars have defaults or are standard
            standard_vars = ['agent_id', 'session_id', 'prompt', 'parent_id', 'workflow_id']
            missing_defaults = []
            
            for var in template_vars:
                if var not in standard_vars and var not in frontmatter.get('vars', {}):
                    missing_defaults.append(var)
            
            if missing_defaults:
                issues.append({
                    'type': 'template_validation',
                    'severity': 'warning',
                    'message': f"Template variables without defaults: {missing_defaults}"
                })
        
        # Check for deprecated patterns
        if 'extends' in frontmatter and frontmatter['extends'].startswith('components/'):
            issues.append({
                'type': 'deprecated_pattern',
                'field': 'extends',
                'severity': 'error',
                'message': 'Extends path should not include "components/" prefix'
            })
        
        return issues
    
    async def _validate_dependencies(self, frontmatter: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Validate component dependencies."""
        issues = []
        
        dependencies = frontmatter.get('dependencies', [])
        for dep in dependencies:
            # Check for incorrect path prefix
            if dep.startswith('components/'):
                issues.append({
                    'type': 'dependency_path',
                    'dependency': dep,
                    'severity': 'error',
                    'message': f'Dependency "{dep}" should not include "components/" prefix'
                })
            
            # Verify dependency exists
            dep_path = Path(config.compositions_dir) / dep.replace('components/', '')
            if not dep_path.exists() and not (dep_path.parent / f"{dep_path.stem}.md").exists():
                issues.append({
                    'type': 'missing_dependency',
                    'dependency': dep,
                    'severity': 'error',
                    'message': f'Dependency "{dep}" not found'
                })
        
        # Check mixins
        mixins = frontmatter.get('mixins', [])
        for mixin in mixins:
            if mixin.startswith('components/'):
                issues.append({
                    'type': 'mixin_path',
                    'mixin': mixin,
                    'severity': 'error',
                    'message': f'Mixin "{mixin}" should not include "components/" prefix'
                })
        
        return issues
    
    async def _adapt_old_patterns(self, content: str, frontmatter: Dict[str, Any], body: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Adapt old component patterns to current standards."""
        adaptations = []
        adapted_content = content
        
        # Fix dependency paths
        if 'dependencies' in frontmatter:
            new_deps = []
            for dep in frontmatter['dependencies']:
                if dep.startswith('components/'):
                    new_dep = dep.replace('components/', '')
                    new_deps.append(new_dep)
                    adaptations.append({
                        'type': 'dependency_path_fix',
                        'old': dep,
                        'new': new_dep
                    })
                else:
                    new_deps.append(dep)
            
            if adaptations:
                # Update frontmatter in content
                adapted_content = self._update_frontmatter(content, {'dependencies': new_deps})
        
        # Fix extends path
        if 'extends' in frontmatter and frontmatter['extends'].startswith('components/'):
            new_extends = frontmatter['extends'].replace('components/', '')
            adapted_content = self._update_frontmatter(adapted_content, {'extends': new_extends})
            adaptations.append({
                'type': 'extends_path_fix',
                'old': frontmatter['extends'],
                'new': new_extends
            })
        
        # Fix mixin paths
        if 'mixins' in frontmatter:
            new_mixins = []
            for mixin in frontmatter['mixins']:
                if mixin.startswith('components/'):
                    new_mixin = mixin.replace('components/', '')
                    new_mixins.append(new_mixin)
                    adaptations.append({
                        'type': 'mixin_path_fix',
                        'old': mixin,
                        'new': new_mixin
                    })
                else:
                    new_mixins.append(mixin)
            
            if any(a['type'] == 'mixin_path_fix' for a in adaptations):
                adapted_content = self._update_frontmatter(adapted_content, {'mixins': new_mixins})
        
        # Add component_type if missing
        if not frontmatter.get('component_type'):
            # Infer from path
            component_type = self._infer_component_type(frontmatter.get('name', ''))
            if component_type:
                adapted_content = self._update_frontmatter(adapted_content, {'component_type': component_type})
                adaptations.append({
                    'type': 'add_component_type',
                    'value': component_type
                })
        
        return adapted_content, adaptations
    
    def _update_frontmatter(self, content: str, updates: Dict[str, Any]) -> str:
        """Update frontmatter in component content."""
        if not content.startswith('---'):
            # Add frontmatter
            fm_str = yaml.dump(updates, default_flow_style=False)
            return f"---\n{fm_str}---\n{content}"
        
        parts = content.split('---', 2)
        if len(parts) >= 3:
            try:
                fm = yaml.safe_load(parts[1]) or {}
                fm.update(updates)
                fm_str = yaml.dump(fm, default_flow_style=False)
                return f"---\n{fm_str}---\n{parts[2]}"
            except yaml.YAMLError:
                return content
        
        return content
    
    def _infer_component_type(self, name: str) -> Optional[str]:
        """Infer component type from name/path."""
        if 'agents/' in name or name.endswith('_agent'):
            return 'agent'
        elif 'personas/' in name:
            return 'persona'
        elif 'behaviors/' in name:
            return 'behavior'
        elif 'workflows/' in name:
            return 'workflow'
        elif 'evaluations/' in name or 'evaluators/' in name:
            return 'evaluation'
        elif 'core/' in name:
            return 'core'
        elif 'tools/' in name:
            return 'tool'
        return None
    
    def _should_optimize(self, frontmatter: Dict[str, Any]) -> bool:
        """Determine if component should be optimized for metrics."""
        # Optimize agents and personas primarily
        component_type = frontmatter.get('component_type')
        return component_type in ['agent', 'persona', 'workflow']
    
    async def _run_optimization_metrics(self, component_path: str, content: str) -> Dict[str, Any]:
        """Run minimal optimization to collect performance metrics."""
        metrics = {}
        
        try:
            # Get baseline token count
            metrics['baseline_tokens'] = len(content.split())
            
            # Use event system to call optimization:metrics
            from ksi_daemon.event_system import get_router
            router = get_router()
            
            # Run quick performance assessment (not full optimization)
            results = await router.emit('optimization:metrics', {
                'component': component_path,
                'method': 'quick_assessment',
                'content': content
            })
            
            result = results[0] if results else {}
            
            if result.get('status') == 'success':
                metrics.update(result.get('metrics', {}))
                logger.info(f"Collected optimization metrics for {component_path}")
            else:
                logger.debug(f"Could not collect optimization metrics: {result.get('error')}")
                
        except Exception as e:
            logger.debug(f"Optimization metrics collection not available: {e}")
            # Not critical - optimization is optional
        
        return metrics
    
    def _check_human_validation_needed(self, frontmatter: Dict[str, Any], 
                                       structural_issues: List[Dict[str, Any]],
                                       adaptations: List[Dict[str, Any]]) -> bool:
        """Determine if human validation is required."""
        # Currently, we don't require human validation for any components
        # This is a placeholder for future criteria
        
        # Potential future criteria:
        # - Security-critical components
        # - Components with external API access
        # - Components handling sensitive data
        # - Components with complex financial logic
        
        # For now, flag only if there are unresolved critical structural issues
        critical_issues = [i for i in structural_issues if i.get('severity') == 'error']
        return len(critical_issues) > 0 and len(adaptations) == 0
    
    async def generate_validation_report(self) -> Dict[str, Any]:
        """Generate a summary validation report."""
        total = len(self.validation_results)
        passed = sum(1 for r in self.validation_results if r['validation_passed'])
        adapted = sum(1 for r in self.validation_results if r['adaptations'])
        optimized = sum(1 for r in self.validation_results if r['optimization_run'])
        human_needed = sum(1 for r in self.validation_results if r['requires_human_validation'])
        
        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'total_components': total,
            'validation_passed': passed,
            'components_adapted': adapted,
            'optimization_metrics_collected': optimized,
            'human_validation_needed': human_needed,
            'pass_rate': (passed / total * 100) if total > 0 else 0,
            'adaptation_rate': (adapted / total * 100) if total > 0 else 0,
            'results': self.validation_results
        }


# Global instance
pre_certification_validator = PreCertificationValidator()