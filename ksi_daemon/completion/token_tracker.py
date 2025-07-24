#!/usr/bin/env python3
"""
Completion Token Tracker

Tracks token usage across providers, agents, and sessions for analytics
and cost monitoring. Provides aggregated statistics and usage patterns.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import aiofiles

from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import timestamp_utc
from ksi_common.config import config
from ksi_common.task_management import create_tracked_task


logger = get_bound_logger("completion.token_tracker")


class TokenUsageRecord:
    """Represents a single token usage record."""
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize from usage data."""
        self.timestamp = timestamp_utc()
        self.request_id = data.get("request_id")
        self.session_id = data.get("session_id")
        self.agent_id = data.get("agent_id")
        self.model = data.get("model")
        self.provider = data.get("provider")
        
        # Token counts
        self.input_tokens = data.get("input_tokens", 0)
        self.output_tokens = data.get("output_tokens", 0)
        self.total_tokens = self.input_tokens + self.output_tokens
        
        # Cache tokens (for Claude)
        self.cache_creation_tokens = data.get("cache_creation_tokens", 0)
        self.cache_read_tokens = data.get("cache_read_tokens", 0)
        
        # MCP metadata
        self.has_mcp = data.get("has_mcp", False)
        
        # Cost estimation (simplified, would need real pricing data)
        self.estimated_cost = self._estimate_cost()
    
    def _estimate_cost(self) -> float:
        """Estimate cost based on token usage (placeholder implementation)."""
        # Simplified cost calculation - would need actual pricing data
        base_cost = (self.input_tokens * 0.00001) + (self.output_tokens * 0.00003)
        cache_discount = self.cache_read_tokens * 0.000009  # 90% discount for cache reads
        return base_cost - cache_discount
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "timestamp": self.timestamp,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "model": self.model,
            "provider": self.provider,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cache_creation_tokens": self.cache_creation_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "has_mcp": self.has_mcp,
            "estimated_cost": self.estimated_cost
        }


class TokenTracker:
    """Tracks and analyzes token usage across the system."""
    
    def __init__(self):
        """Initialize the token tracker."""
        self._usage_log_path = config.tool_usage_log_file
        self._in_memory_records: List[TokenUsageRecord] = []
        self._max_memory_records = 10000
        
        # Aggregated statistics
        self._agent_totals: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"input": 0, "output": 0, "cache": 0, "requests": 0}
        )
        self._model_totals: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"input": 0, "output": 0, "cache": 0, "requests": 0}
        )
        self._session_totals: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"input": 0, "output": 0, "cache": 0, "requests": 0}
        )
        
        # MCP statistics
        self._mcp_overhead = {
            "total_requests": 0,
            "mcp_requests": 0,
            "total_overhead_tokens": 0,
            "cache_savings": 0
        }
        
        # Load historical data on startup
        self._load_recent_history()
    
    def _load_recent_history(self, hours: int = 24) -> None:
        """Load recent usage history from log file."""
        # For initialization, we'll accept synchronous loading
        # since it happens once at startup
        if not self._usage_log_path.exists():
            return
        
        cutoff = datetime.now() - timedelta(hours=hours)
        loaded = 0
        
        try:
            with open(self._usage_log_path, 'r') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        # Skip non-token-usage entries
                        if data.get("event") != "token_usage":
                            continue
                        
                        # Check timestamp
                        timestamp_str = data.get("timestamp", "")
                        if timestamp_str:
                            timestamp = datetime.fromisoformat(
                                timestamp_str.replace('Z', '+00:00')
                            )
                            if timestamp < cutoff:
                                continue
                        
                        # Create record and update aggregates
                        record = TokenUsageRecord(data)
                        self._update_aggregates(record)
                        loaded += 1
                        
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.debug(f"Skipping invalid log entry: {e}")
        
        except Exception as e:
            logger.error(f"Failed to load usage history: {e}")
        
        logger.info(f"Loaded {loaded} recent token usage records")
    
    def record_usage(self, usage_data: Dict[str, Any]) -> None:
        """
        Record token usage from a completion.
        
        Args:
            usage_data: Dictionary containing usage information
        """
        # Create record
        record = TokenUsageRecord(usage_data)
        
        # Add to memory
        self._in_memory_records.append(record)
        if len(self._in_memory_records) > self._max_memory_records:
            self._in_memory_records.pop(0)
        
        # Update aggregates
        self._update_aggregates(record)
        
        # Log to file
        self._append_to_log(record)
        
        # Log significant usage
        if record.total_tokens > 10000:
            logger.warning(
                f"High token usage detected",
                request_id=record.request_id,
                total_tokens=record.total_tokens,
                model=record.model
            )
        
        # Track MCP overhead
        if record.has_mcp:
            self._update_mcp_stats(record)
    
    def _update_aggregates(self, record: TokenUsageRecord) -> None:
        """Update aggregated statistics."""
        # Agent totals
        if record.agent_id:
            agent_stats = self._agent_totals[record.agent_id]
            agent_stats["input"] += record.input_tokens
            agent_stats["output"] += record.output_tokens
            agent_stats["cache"] += record.cache_read_tokens
            agent_stats["requests"] += 1
        
        # Model totals
        if record.model:
            model_stats = self._model_totals[record.model]
            model_stats["input"] += record.input_tokens
            model_stats["output"] += record.output_tokens
            model_stats["cache"] += record.cache_read_tokens
            model_stats["requests"] += 1
        
        # Session totals
        if record.session_id:
            session_stats = self._session_totals[record.session_id]
            session_stats["input"] += record.input_tokens
            session_stats["output"] += record.output_tokens
            session_stats["cache"] += record.cache_read_tokens
            session_stats["requests"] += 1
    
    def _update_mcp_stats(self, record: TokenUsageRecord) -> None:
        """Update MCP-specific statistics."""
        self._mcp_overhead["mcp_requests"] += 1
        self._mcp_overhead["total_requests"] += 1
        
        # Estimate MCP overhead (cache creation tokens are often MCP tools)
        if record.cache_creation_tokens > 0:
            self._mcp_overhead["total_overhead_tokens"] += record.cache_creation_tokens
        
        # Track cache savings
        if record.cache_read_tokens > 0:
            # Cache reads save ~90% of token cost
            savings = record.cache_read_tokens * 0.9
            self._mcp_overhead["cache_savings"] += int(savings)
    
    def _append_to_log(self, record: TokenUsageRecord) -> None:
        """Append usage record to log file."""
        # Non-blocking file I/O using tracked task
        create_tracked_task("token_tracker", self._append_to_log_async(record), task_name="append_log")
    
    async def _append_to_log_async(self, record: TokenUsageRecord) -> None:
        """Async helper for non-blocking file write."""
        try:
            log_entry = {
                "event": "token_usage",
                **record.to_dict()
            }
            
            # Use aiofiles for true async file I/O
            async with aiofiles.open(self._usage_log_path, 'a') as f:
                await f.write(json.dumps(log_entry) + '\n')
        
        except Exception as e:
            logger.error(f"Failed to log token usage: {e}")
    
    def get_agent_usage(self, agent_id: str, 
                       time_window_hours: Optional[int] = None) -> Dict[str, Any]:
        """
        Get token usage statistics for an agent.
        
        Args:
            agent_id: Agent identifier
            time_window_hours: Optional time window filter
            
        Returns:
            Usage statistics
        """
        if time_window_hours:
            # Filter records by time window
            cutoff = datetime.now() - timedelta(hours=time_window_hours)
            records = [
                r for r in self._in_memory_records
                if r.agent_id == agent_id and 
                datetime.fromisoformat(r.timestamp.replace('Z', '+00:00')) > cutoff
            ]
            
            # Calculate stats from filtered records
            stats = {
                "input_tokens": sum(r.input_tokens for r in records),
                "output_tokens": sum(r.output_tokens for r in records),
                "cache_tokens": sum(r.cache_read_tokens for r in records),
                "total_tokens": sum(r.total_tokens for r in records),
                "request_count": len(records),
                "estimated_cost": sum(r.estimated_cost for r in records)
            }
        else:
            # Use aggregated stats
            agent_stats = self._agent_totals.get(agent_id, {})
            stats = {
                "input_tokens": agent_stats.get("input", 0),
                "output_tokens": agent_stats.get("output", 0),
                "cache_tokens": agent_stats.get("cache", 0),
                "total_tokens": agent_stats.get("input", 0) + agent_stats.get("output", 0),
                "request_count": agent_stats.get("requests", 0)
            }
        
        # Add average tokens per request
        if stats["request_count"] > 0:
            stats["avg_tokens_per_request"] = stats["total_tokens"] / stats["request_count"]
        else:
            stats["avg_tokens_per_request"] = 0
        
        return {
            "agent_id": agent_id,
            "usage": stats,
            "time_window_hours": time_window_hours
        }
    
    def get_model_usage(self, model: Optional[str] = None) -> Dict[str, Any]:
        """Get token usage statistics by model."""
        if model:
            model_stats = self._model_totals.get(model, {})
            return {
                "model": model,
                "usage": {
                    "input_tokens": model_stats.get("input", 0),
                    "output_tokens": model_stats.get("output", 0),
                    "cache_tokens": model_stats.get("cache", 0),
                    "request_count": model_stats.get("requests", 0)
                }
            }
        else:
            # Return all models
            models = {}
            for model_name, stats in self._model_totals.items():
                models[model_name] = {
                    "input_tokens": stats["input"],
                    "output_tokens": stats["output"],
                    "cache_tokens": stats["cache"],
                    "request_count": stats["requests"]
                }
            
            return {"models": models}
    
    def get_mcp_statistics(self) -> Dict[str, Any]:
        """Get MCP-specific usage statistics."""
        overhead_pct = 0
        if self._mcp_overhead["mcp_requests"] > 0:
            overhead_pct = (
                self._mcp_overhead["total_overhead_tokens"] / 
                self._mcp_overhead["mcp_requests"]
            )
        
        return {
            "total_requests": self._mcp_overhead["total_requests"],
            "mcp_enabled_requests": self._mcp_overhead["mcp_requests"],
            "mcp_percentage": (
                self._mcp_overhead["mcp_requests"] / self._mcp_overhead["total_requests"] * 100
                if self._mcp_overhead["total_requests"] > 0 else 0
            ),
            "total_overhead_tokens": self._mcp_overhead["total_overhead_tokens"],
            "avg_overhead_per_request": overhead_pct,
            "cache_tokens_saved": self._mcp_overhead["cache_savings"]
        }
    
    def get_usage_trends(self, hours: int = 24, 
                        bucket_size_minutes: int = 60) -> Dict[str, Any]:
        """
        Get token usage trends over time.
        
        Args:
            hours: Number of hours to analyze
            bucket_size_minutes: Size of time buckets
            
        Returns:
            Usage trends by time bucket
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        buckets = defaultdict(lambda: {
            "input": 0, "output": 0, "requests": 0
        })
        
        # Process recent records
        for record in self._in_memory_records:
            record_time = datetime.fromisoformat(
                record.timestamp.replace('Z', '+00:00')
            )
            if record_time < cutoff:
                continue
            
            # Calculate bucket
            bucket_idx = int(
                (record_time - cutoff).total_seconds() / 
                (bucket_size_minutes * 60)
            )
            bucket_time = cutoff + timedelta(
                minutes=bucket_idx * bucket_size_minutes
            )
            bucket_key = bucket_time.isoformat()
            
            buckets[bucket_key]["input"] += record.input_tokens
            buckets[bucket_key]["output"] += record.output_tokens
            buckets[bucket_key]["requests"] += 1
        
        return {
            "hours": hours,
            "bucket_size_minutes": bucket_size_minutes,
            "trends": dict(buckets)
        }
    
    def get_summary_statistics(self) -> Dict[str, Any]:
        """Get overall usage summary."""
        total_input = sum(s["input"] for s in self._agent_totals.values())
        total_output = sum(s["output"] for s in self._agent_totals.values())
        total_cache = sum(s["cache"] for s in self._agent_totals.values())
        total_requests = sum(s["requests"] for s in self._agent_totals.values())
        
        return {
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_cache_tokens": total_cache,
            "total_tokens": total_input + total_output,
            "total_requests": total_requests,
            "active_agents": len(self._agent_totals),
            "active_models": len(self._model_totals),
            "active_sessions": len(self._session_totals),
            "mcp_statistics": self.get_mcp_statistics()
        }