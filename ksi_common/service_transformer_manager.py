#!/usr/bin/env python3
"""
Service Transformer Manager - Unified transformer loading and management system.

Eliminates repetitive transformer loading code by providing:
- Auto-discovery of service transformer files
- Centralized configuration
- Standardized error handling
- Dependency-aware loading order
- Hot-reload capabilities
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field

from ksi_common.logging import get_bound_logger
from ksi_common.transformer_loader import load_service_transformers
from ksi_common.event_response_builder import event_response_builder

logger = get_bound_logger("service_transformer_manager", version="1.0.0")

@dataclass
class ServiceTransformerConfig:
    """Configuration for a service's transformer loading."""
    service_name: str
    transformer_files: List[str] = field(default_factory=list)
    auto_discover: bool = True
    dependencies: List[str] = field(default_factory=list)
    critical: bool = True  # Whether loading failure should be treated as critical
    
    def __post_init__(self):
        """Auto-discover transformer files if none specified."""
        if self.auto_discover and not self.transformer_files:
            self.transformer_files = self._discover_transformer_files()
    
    def _discover_transformer_files(self) -> List[str]:
        """Auto-discover transformer files for this service."""
        transformer_dir = Path("var/lib/transformers/services")
        discovered_files = []
        
        # Look for files matching service patterns
        service_patterns = [
            f"{self.service_name}.yaml",
            f"{self.service_name}_routing.yaml", 
            f"{self.service_name}_transformers.yaml",
        ]
        
        # Also look for service-specific directories
        service_dir = transformer_dir / self.service_name
        if service_dir.exists():
            discovered_files.extend([
                f"{self.service_name}/{f.name}" 
                for f in service_dir.glob("*.yaml")
            ])
        
        # Look for direct files matching patterns
        for pattern in service_patterns:
            file_path = transformer_dir / pattern
            if file_path.exists():
                discovered_files.append(pattern)
        
        # Special handling for known service patterns
        service_mappings = {
            "agent_service": ["agent_routing.yaml", "agent_result_routing.yaml"],
            "completion_service": ["completion_routing.yaml"],
            "orchestration_service": ["orchestration_routing.yaml", "hierarchical_routing.yaml"],
            "optimization_service": ["optimization_routing.yaml"],
            "observation_service": ["observation_monitoring.yaml"],
        }
        
        if self.service_name in service_mappings:
            discovered_files.extend(service_mappings[self.service_name])
        
        return list(set(discovered_files))  # Remove duplicates


class ServiceTransformerManager:
    """Centralized transformer loading and management."""
    
    def __init__(self):
        self.service_configs: Dict[str, ServiceTransformerConfig] = {}
        self.loaded_services: Set[str] = set()
        self.loading_in_progress: Set[str] = set()
        self.load_results: Dict[str, Dict[str, Any]] = {}
    
    def register_service(self, config: ServiceTransformerConfig):
        """Register a service for transformer loading."""
        self.service_configs[config.service_name] = config
        logger.debug(f"Registered service {config.service_name} with {len(config.transformer_files)} transformer files")
    
    def register_services_from_config(self, config_path: str = "var/lib/transformers/services.json"):
        """Register services from JSON configuration file."""
        try:
            config_file = Path(config_path)
            if config_file.exists():
                with open(config_file) as f:
                    services_config = json.load(f)
                
                for service_name, service_data in services_config.items():
                    config = ServiceTransformerConfig(
                        service_name=service_name,
                        transformer_files=service_data.get("transformer_files", []),
                        auto_discover=service_data.get("auto_discover", True),
                        dependencies=service_data.get("dependencies", []),
                        critical=service_data.get("critical", True)
                    )
                    self.register_service(config)
                    
                logger.info(f"Registered {len(services_config)} services from config file")
            else:
                logger.info("No services config file found, using auto-discovery")
        except Exception as e:
            logger.warning(f"Failed to load services config: {e}, falling back to auto-discovery")
    
    def auto_register_services(self):
        """Auto-register services based on known patterns."""
        known_services = [
            "agent_service",
            "completion_service", 
            "orchestration_service",
            "optimization_service",
            "observation_service",
            "state_service",
            "config_service",
            "permission_service"
        ]
        
        for service_name in known_services:
            if service_name not in self.service_configs:
                config = ServiceTransformerConfig(service_name=service_name)
                if config.transformer_files:  # Only register if files found
                    self.register_service(config)
    
    async def load_service_transformers(self, service_name: str, event_emitter=None) -> Dict[str, Any]:
        """Load transformers for a specific service."""
        if service_name in self.loading_in_progress:
            logger.warning(f"Service {service_name} transformer loading already in progress")
            return {"status": "in_progress", "service": service_name}
        
        if service_name not in self.service_configs:
            # Try auto-registration
            config = ServiceTransformerConfig(service_name=service_name)
            if config.transformer_files:
                self.register_service(config)
            else:
                return {"status": "no_transformers", "service": service_name}
        
        config = self.service_configs[service_name]
        self.loading_in_progress.add(service_name)
        
        try:
            # Check dependencies
            for dep in config.dependencies:
                if dep not in self.loaded_services:
                    logger.info(f"Loading dependency {dep} for {service_name}")
                    await self.load_service_transformers(dep, event_emitter)
            
            # Load transformer files
            total_loaded = 0
            load_results = []
            
            for transformer_file in config.transformer_files:
                try:
                    result = await load_service_transformers(
                        service_name=service_name,
                        transformer_file=transformer_file,
                        event_emitter=event_emitter
                    )
                    load_results.append(result)
                    if result.get("status") == "success":
                        total_loaded += result.get("loaded", 0)
                except Exception as e:
                    logger.error(f"Failed to load {transformer_file} for {service_name}: {e}")
                    if config.critical:
                        raise
                    load_results.append({"status": "error", "file": transformer_file, "error": str(e)})
            
            self.loaded_services.add(service_name)
            result = {
                "status": "success",
                "service": service_name,
                "total_loaded": total_loaded,
                "files_loaded": len([r for r in load_results if r.get("status") == "success"]),
                "files_failed": len([r for r in load_results if r.get("status") == "error"]),
                "details": load_results
            }
            self.load_results[service_name] = result
            
            logger.info(f"Loaded {total_loaded} transformers from {result['files_loaded']} files for {service_name}")
            return result
            
        except Exception as e:
            error_result = {"status": "error", "service": service_name, "error": str(e)}
            self.load_results[service_name] = error_result
            logger.error(f"Failed to load transformers for {service_name}: {e}")
            return error_result
        finally:
            self.loading_in_progress.discard(service_name)
    
    async def load_all_service_transformers(self, event_emitter=None) -> Dict[str, Any]:
        """Load transformers for all registered services."""
        if not self.service_configs:
            self.auto_register_services()
        
        load_tasks = []
        for service_name in self.service_configs:
            if service_name not in self.loaded_services:
                load_tasks.append(self.load_service_transformers(service_name, event_emitter))
        
        if load_tasks:
            results = await asyncio.gather(*load_tasks, return_exceptions=True)
            
            success_count = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "success")  
            total_transformers = sum(r.get("total_loaded", 0) for r in results if isinstance(r, dict))
            
            return {
                "status": "completed",
                "services_loaded": success_count,
                "total_transformers": total_transformers,
                "services": list(self.service_configs.keys()),
                "results": {
                    service: result for service, result in self.load_results.items()
                }
            }
        else:
            return {"status": "no_services", "message": "No services found to load transformers"}
    
    def get_load_status(self) -> Dict[str, Any]:
        """Get current loading status for all services."""
        return {
            "loaded_services": list(self.loaded_services),
            "registered_services": list(self.service_configs.keys()),
            "loading_in_progress": list(self.loading_in_progress),
            "load_results": self.load_results
        }


# Global instance
_transformer_manager = ServiceTransformerManager()

def get_transformer_manager() -> ServiceTransformerManager:
    """Get the global transformer manager instance."""
    return _transformer_manager

# Convenience functions for common patterns
async def auto_load_service_transformers(service_name: str, event_emitter=None) -> Dict[str, Any]:
    """Auto-load transformers for a service (convenience function)."""
    manager = get_transformer_manager()
    return await manager.load_service_transformers(service_name, event_emitter)

def create_service_ready_handler(service_name: str, additional_tasks: Optional[List[Dict[str, Any]]] = None):
    """Create a standardized system:ready handler for a service."""
    async def handle_ready(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Auto-generated system:ready handler with transformer loading."""
        # Load service transformers
        transformer_result = await auto_load_service_transformers(service_name)
        
        # Build response with service tasks
        response_data = {
            "service": service_name,
            "status": "ready",
            "transformer_result": transformer_result
        }
        
        # Add additional tasks if provided (e.g., background services)
        if additional_tasks:
            response_data["tasks"] = additional_tasks
        
        return event_response_builder(response_data, context)
    
    return handle_ready