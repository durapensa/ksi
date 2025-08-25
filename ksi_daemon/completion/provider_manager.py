#!/usr/bin/env python3
"""
Completion Provider Manager

Manages completion providers with intelligent routing, failover support,
and circuit breaker patterns. Tracks provider health and performance.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from collections import defaultdict

from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import timestamp_utc


logger = get_bound_logger("completion.provider_manager")


class ProviderCircuitBreaker:
    """Circuit breaker for individual providers."""
    
    def __init__(self, failure_threshold: int = 5, timeout_minutes: int = 5):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            timeout_minutes: How long to keep circuit open
        """
        self.failure_threshold = failure_threshold
        self.timeout_minutes = timeout_minutes
        self.failures: List[datetime] = []
        self.circuit_open_until: Optional[datetime] = None
        self.last_success: Optional[datetime] = None
        
    def record_success(self) -> None:
        """Record a successful provider call."""
        self.failures = []
        self.last_success = datetime.now()
        if self.circuit_open_until and datetime.now() > self.circuit_open_until:
            self.circuit_open_until = None
            logger.info("Circuit breaker closed after successful call")
    
    def record_failure(self) -> None:
        """Record a failed provider call."""
        now = datetime.now()
        self.failures.append(now)
        
        # Keep only recent failures
        cutoff = now - timedelta(minutes=self.timeout_minutes)
        self.failures = [f for f in self.failures if f > cutoff]
        
        # Check if we should open the circuit
        if len(self.failures) >= self.failure_threshold:
            self.circuit_open_until = now + timedelta(minutes=self.timeout_minutes)
            logger.warning(
                f"Circuit breaker opened until {self.circuit_open_until}",
                failures=len(self.failures)
            )
    
    def is_open(self) -> bool:
        """Check if circuit is currently open."""
        if not self.circuit_open_until:
            return False
        
        if datetime.now() > self.circuit_open_until:
            # Circuit timeout expired, try to close it
            self.circuit_open_until = None
            return False
        
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status."""
        return {
            "is_open": self.is_open(),
            "recent_failures": len(self.failures),
            "open_until": self.circuit_open_until.isoformat() if self.circuit_open_until else None,
            "last_success": self.last_success.isoformat() if self.last_success else None
        }


class ProviderManager:
    """Manages completion providers with failover and health tracking."""
    
    def __init__(self):
        """Initialize the provider manager."""
        # Provider configuration
        self._providers: Dict[str, Dict[str, Any]] = {
            "claude-cli": {
                "type": "claude-cli",
                "models": ["claude-cli/sonnet", "claude-cli/haiku", "claude-cli/opus"],
                "priority": 1,
                "supports_streaming": True,
                "supports_mcp": True
            },
            "litellm": {
                "type": "litellm",
                "models": ["*"],  # Supports all models
                "priority": 2,
                "supports_streaming": True,
                "supports_mcp": False
            }
        }
        
        # Circuit breakers per provider
        self._circuit_breakers: Dict[str, ProviderCircuitBreaker] = {
            provider: ProviderCircuitBreaker() 
            for provider in self._providers
        }
        
        # Performance tracking
        self._call_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_latency_ms": 0,
            "last_call": None
        })
        
        # Model to provider mapping cache
        self._model_provider_cache: Dict[str, str] = {}
    
    def select_provider(self, model: str, 
                       require_mcp: bool = False,
                       prefer_streaming: bool = False) -> Tuple[str, Dict[str, Any]]:
        """
        Select the best available provider for a model.
        
        Args:
            model: The model identifier
            require_mcp: Whether MCP support is required
            prefer_streaming: Whether streaming is preferred
            
        Returns:
            Tuple of (provider_name, provider_config)
            
        Raises:
            ValueError: If no suitable provider is available
        """
        # Check cache first
        if not require_mcp and model in self._model_provider_cache:
            cached_provider = self._model_provider_cache[model]
            if not self._circuit_breakers[cached_provider].is_open():
                return cached_provider, self._providers[cached_provider]
        
        # Find suitable providers
        candidates = []
        
        for name, config in self._providers.items():
            # Skip if circuit is open
            if self._circuit_breakers[name].is_open():
                continue
            
            # Check MCP requirement
            if require_mcp and not config.get("supports_mcp", False):
                continue
            
            # Check model support
            if "*" in config["models"] or model in config["models"]:
                candidates.append((name, config))
            # Special handling for Claude models that should use CLI
            elif name == "claude-cli" and model.startswith("claude-"):
                # Map claude-* models to claude-cli/sonnet
                # This ensures evaluation with claude-sonnet-4-20250514 uses CLI
                candidates.append((name, config))
        
        if not candidates:
            # Check if any circuits are open
            open_circuits = [
                name for name, cb in self._circuit_breakers.items() 
                if cb.is_open()
            ]
            if open_circuits:
                raise ValueError(
                    f"No available providers (circuits open: {open_circuits})"
                )
            else:
                raise ValueError(f"No provider supports model '{model}'")
        
        # Sort by priority and streaming preference
        candidates.sort(key=lambda x: (
            x[1]["priority"],
            -int(x[1].get("supports_streaming", False) and prefer_streaming)
        ))
        
        # Select best candidate
        selected_name, selected_config = candidates[0]
        
        # Cache the selection
        if not require_mcp:
            self._model_provider_cache[model] = selected_name
        
        logger.debug(
            f"Selected provider {selected_name} for model {model}",
            require_mcp=require_mcp,
            prefer_streaming=prefer_streaming
        )
        
        return selected_name, selected_config
    
    def record_success(self, provider: str, latency_ms: int) -> None:
        """
        Record a successful provider call.
        
        Args:
            provider: Provider name
            latency_ms: Call latency in milliseconds
        """
        if provider in self._circuit_breakers:
            self._circuit_breakers[provider].record_success()
        
        stats = self._call_stats[provider]
        stats["total_calls"] += 1
        stats["successful_calls"] += 1
        stats["total_latency_ms"] += latency_ms
        stats["last_call"] = timestamp_utc()
        
        avg_latency = stats["total_latency_ms"] / stats["successful_calls"]
        logger.info(
            f"Provider {provider} call succeeded",
            latency_ms=latency_ms,
            avg_latency_ms=avg_latency
        )
    
    def record_failure(self, provider: str, error: str) -> None:
        """
        Record a failed provider call.
        
        Args:
            provider: Provider name
            error: Error message
        """
        if provider in self._circuit_breakers:
            self._circuit_breakers[provider].record_failure()
        
        stats = self._call_stats[provider]
        stats["total_calls"] += 1
        stats["failed_calls"] += 1
        stats["last_call"] = timestamp_utc()
        stats["last_error"] = error
        
        logger.warning(
            f"Provider {provider} call failed",
            error=error,
            total_failures=stats["failed_calls"]
        )
    
    def get_provider_status(self, provider: str) -> Dict[str, Any]:
        """
        Get detailed status for a specific provider.
        
        Args:
            provider: Provider name
            
        Returns:
            Provider status information
        """
        if provider not in self._providers:
            return {"error": f"Unknown provider: {provider}"}
        
        config = self._providers[provider]
        circuit_status = self._circuit_breakers[provider].get_status()
        stats = dict(self._call_stats[provider])
        
        # Calculate success rate
        if stats["total_calls"] > 0:
            stats["success_rate"] = stats["successful_calls"] / stats["total_calls"]
            stats["avg_latency_ms"] = (
                stats["total_latency_ms"] / stats["successful_calls"]
                if stats["successful_calls"] > 0 else 0
            )
        else:
            stats["success_rate"] = 0
            stats["avg_latency_ms"] = 0
        
        return {
            "provider": provider,
            "config": config,
            "circuit_breaker": circuit_status,
            "stats": stats
        }
    
    def get_all_provider_status(self) -> Dict[str, Any]:
        """Get status for all providers."""
        providers = {}
        available_count = 0
        
        for provider in self._providers:
            status = self.get_provider_status(provider)
            providers[provider] = status
            
            if not status["circuit_breaker"]["is_open"]:
                available_count += 1
        
        return {
            "total_providers": len(self._providers),
            "available_providers": available_count,
            "providers": providers
        }
    
    def reset_provider(self, provider: str) -> Dict[str, Any]:
        """
        Reset a provider's circuit breaker and stats.
        
        Args:
            provider: Provider name
            
        Returns:
            Reset confirmation
        """
        if provider not in self._providers:
            return {"error": f"Unknown provider: {provider}"}
        
        # Reset circuit breaker
        self._circuit_breakers[provider] = ProviderCircuitBreaker()
        
        # Clear cache entries for this provider
        self._model_provider_cache = {
            k: v for k, v in self._model_provider_cache.items()
            if v != provider
        }
        
        logger.info(f"Reset provider {provider}")
        
        return {
            "provider": provider,
            "reset": True,
            "status": "available"
        }
    
    def add_provider(self, name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add or update a provider configuration.
        
        Args:
            name: Provider name
            config: Provider configuration
            
        Returns:
            Addition confirmation
        """
        self._providers[name] = config
        
        if name not in self._circuit_breakers:
            self._circuit_breakers[name] = ProviderCircuitBreaker()
        
        logger.info(f"Added/updated provider {name}", config=config)
        
        return {
            "provider": name,
            "action": "added" if name not in self._providers else "updated",
            "config": config
        }