#!/usr/bin/env python3
"""
Melting Pot Services Registration
==================================

Registers all general-purpose services needed for Melting Pot scenarios.
These services are general enough to benefit many KSI use cases.
"""

import logging
from typing import Optional, Dict, Any

# Import service implementations
from ksi_daemon.spatial.spatial_service import SpatialService
from ksi_daemon.resources.resource_service import ResourceService  
from ksi_daemon.episode.episode_service import EpisodeService
from ksi_daemon.metrics.game_theory_metrics import GameTheoryMetricsService
from ksi_daemon.scheduler.scheduled_event_service import ScheduledEventService

# Import validators
from ksi_daemon.validators.movement_validator import MovementValidator
from ksi_daemon.validators.resource_validator import ResourceTransferValidator
from ksi_daemon.validators.interaction_validator import InteractionValidator

logger = logging.getLogger(__name__)


class MeltingPotServicesManager:
    """Manages registration and lifecycle of Melting Pot services."""
    
    def __init__(self):
        self.services = {}
        self.validators = {}
        self.initialized = False
        
    def register_all_services(self, daemon) -> Dict[str, Any]:
        """Register all Melting Pot services with the daemon."""
        
        results = {}
        
        try:
            # Create service instances
            logger.info("Creating Melting Pot service instances...")
            
            spatial_service = SpatialService()
            resource_service = ResourceService()
            episode_service = EpisodeService()
            metrics_service = GameTheoryMetricsService()
            scheduler_service = ScheduledEventService()
            
            # Register with daemon
            logger.info("Registering services with daemon...")
            
            services_to_register = [
                ("spatial", spatial_service),
                ("resource", resource_service),
                ("episode", episode_service),
                ("metrics", metrics_service),
                ("scheduler", scheduler_service)
            ]
            
            for name, service in services_to_register:
                try:
                    daemon.register_service(service)
                    self.services[name] = service
                    results[name] = "registered"
                    logger.info(f"✓ Registered {name} service")
                except Exception as e:
                    results[name] = f"failed: {e}"
                    logger.error(f"✗ Failed to register {name}: {e}")
            
            # Initialize validators
            logger.info("Initializing validators...")
            self._initialize_validators()
            
            # Connect validators to services
            self._connect_validators_to_services()
            
            self.initialized = True
            logger.info("Melting Pot services initialization complete")
            
        except Exception as e:
            logger.error(f"Error during service registration: {e}")
            results["error"] = str(e)
        
        return results
    
    def _initialize_validators(self):
        """Initialize validation components."""
        
        try:
            # Create validator instances
            self.validators["movement"] = MovementValidator()
            self.validators["resource"] = ResourceTransferValidator()
            self.validators["interaction"] = InteractionValidator()
            
            logger.info(f"Initialized {len(self.validators)} validators")
            
        except Exception as e:
            logger.error(f"Error initializing validators: {e}")
    
    def _connect_validators_to_services(self):
        """Connect validators to their respective services."""
        
        # Connect movement validator to spatial service
        if "spatial" in self.services and "movement" in self.validators:
            self.services["spatial"].set_validator(self.validators["movement"])
            logger.info("Connected movement validator to spatial service")
        
        # Connect resource validator to resource service
        if "resource" in self.services and "resource" in self.validators:
            self.services["resource"].set_validator(self.validators["resource"])
            logger.info("Connected resource validator to resource service")
        
        # Connect interaction validator to spatial service (for spatial:interact)
        if "spatial" in self.services and "interaction" in self.validators:
            self.services["spatial"].set_interaction_validator(self.validators["interaction"])
            logger.info("Connected interaction validator to spatial service")
    
    def health_check(self) -> Dict[str, Any]:
        """Check health of all services."""
        
        health = {
            "initialized": self.initialized,
            "services": {},
            "validators": {}
        }
        
        # Check each service
        for name, service in self.services.items():
            try:
                # Most services should have a health check method
                if hasattr(service, 'health_check'):
                    health["services"][name] = service.health_check()
                else:
                    health["services"][name] = {"status": "running"}
            except Exception as e:
                health["services"][name] = {"status": "error", "error": str(e)}
        
        # Check validators
        for name, validator in self.validators.items():
            health["validators"][name] = {"status": "initialized"}
        
        return health
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get statistics from all services."""
        
        stats = {}
        
        # Spatial service stats
        if "spatial" in self.services:
            spatial = self.services["spatial"]
            stats["spatial"] = {
                "environments": len(spatial.environments),
                "total_entities": sum(len(env.entities) for env in spatial.environments.values())
            }
        
        # Resource service stats  
        if "resource" in self.services:
            resource = self.services["resource"]
            stats["resource"] = {
                "total_resources": len(resource.resources),
                "resource_types": len(set(r.resource_type for r in resource.resources.values()))
            }
        
        # Episode service stats
        if "episode" in self.services:
            episode = self.services["episode"]
            stats["episode"] = {
                "active_episodes": len(episode.episodes),
                "total_participants": sum(len(e.participants) for e in episode.episodes.values())
            }
        
        # Metrics service stats
        if "metrics" in self.services:
            metrics = self.services["metrics"]
            stats["metrics"] = {
                "tracked_episodes": len(metrics.episodes),
                "total_interactions": len(metrics.interaction_history)
            }
        
        # Scheduler service stats
        if "scheduler" in self.services:
            scheduler = self.services["scheduler"]
            stats["scheduler"] = {
                "scheduled_events": len(scheduler.scheduled_events),
                "active_episodes": len(scheduler.episode_schedules)
            }
        
        return stats
    
    def shutdown(self):
        """Gracefully shutdown all services."""
        
        logger.info("Shutting down Melting Pot services...")
        
        for name, service in self.services.items():
            try:
                if hasattr(service, 'shutdown'):
                    service.shutdown()
                logger.info(f"Shut down {name} service")
            except Exception as e:
                logger.error(f"Error shutting down {name}: {e}")
        
        self.services.clear()
        self.validators.clear()
        self.initialized = False
        
        logger.info("Melting Pot services shutdown complete")


# Singleton instance
_manager = None


def get_manager() -> MeltingPotServicesManager:
    """Get the singleton manager instance."""
    global _manager
    if _manager is None:
        _manager = MeltingPotServicesManager()
    return _manager


def register_melting_pot_services(daemon) -> Dict[str, Any]:
    """Register all Melting Pot services with the daemon.
    
    This is the main entry point for service registration.
    """
    manager = get_manager()
    return manager.register_all_services(daemon)


def health_check() -> Dict[str, Any]:
    """Check health of all Melting Pot services."""
    manager = get_manager()
    return manager.health_check()


def get_stats() -> Dict[str, Any]:
    """Get statistics from all services."""
    manager = get_manager()
    return manager.get_service_stats()


def shutdown():
    """Shutdown all services."""
    manager = get_manager()
    manager.shutdown()


# Export key functions
__all__ = [
    'register_melting_pot_services',
    'health_check',
    'get_stats',
    'shutdown',
    'get_manager'
]