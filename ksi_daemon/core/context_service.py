"""Context Gateway Service for External Client Access.

Provides event-based API for external clients to resolve context references
and query context data with field selection and filtering.
"""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

from ksi_daemon.event_system import event_handler, get_router
from ksi_common.event_response_builder import event_response_builder, error_response
from ksi_common.logging import get_bound_logger
from .context_manager import get_context_manager

logger = get_bound_logger("context_service")


@event_handler("context:resolve")
async def handle_context_resolve(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Resolve a context reference to full context data.
    
    Args:
        data: {
            "ref": "ctx_evt_12345",
            "fields": ["_event_id", "_correlation_id"]  # Optional field selection
        }
    
    Returns:
        {
            "ref": "ctx_evt_12345",
            "context": {...},
            "status": "resolved"
        }
    """
    ref = data.get("ref")
    if not ref:
        return error_response("ref parameter is required", context)
    
    fields = data.get("fields")  # Optional field selection
    
    try:
        cm = get_context_manager()
        resolved_context = await cm.get_context(ref)
        
        if resolved_context is None:
            return error_response(f"Context reference {ref} not found", context)
        
        # Apply field selection if requested
        if fields:
            filtered_context = {k: v for k, v in resolved_context.items() if k in fields}
        else:
            filtered_context = resolved_context
        
        return event_response_builder({
            "ref": ref,
            "context": filtered_context,
            "status": "resolved"
        }, context=context)
        
    except Exception as e:
        logger.error(f"Failed to resolve context {ref}: {e}")
        return error_response(f"Failed to resolve context: {str(e)}", context)


@event_handler("context:resolve_batch")
async def handle_context_resolve_batch(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Resolve multiple context references in a single request.
    
    Args:
        data: {
            "refs": ["ctx_evt_12345", "ctx_evt_67890"],
            "fields": ["_event_id", "_correlation_id"]  # Optional field selection
        }
    
    Returns:
        {
            "resolved": [{"ref": "...", "context": {...}}, ...],
            "not_found": ["ctx_evt_xxx"],
            "status": "completed"
        }
    """
    refs = data.get("refs", [])
    if not refs:
        return error_response("refs parameter is required", context)
    
    if not isinstance(refs, list):
        return error_response("refs must be a list", context)
        
    if len(refs) > 100:  # Reasonable batch size limit
        return error_response("Maximum 100 references per batch request", context)
    
    fields = data.get("fields")
    
    try:
        cm = get_context_manager()
        resolved = []
        not_found = []
        
        # Process each reference
        for ref in refs:
            resolved_context = await cm.get_context(ref)
            
            if resolved_context is None:
                not_found.append(ref)
                continue
            
            # Apply field selection if requested
            if fields:
                filtered_context = {k: v for k, v in resolved_context.items() if k in fields}
            else:
                filtered_context = resolved_context
            
            resolved.append({
                "ref": ref,
                "context": filtered_context
            })
        
        return event_response_builder({
            "resolved": resolved,
            "not_found": not_found,
            "total_requested": len(refs),
            "resolved_count": len(resolved),
            "not_found_count": len(not_found),
            "status": "completed"
        }, context=context)
        
    except Exception as e:
        logger.error(f"Failed to resolve context batch: {e}")
        return error_response(f"Failed to resolve context batch: {str(e)}", context)


@event_handler("context:query")
async def handle_context_query(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Query contexts by various criteria.
    
    Args:
        data: {
            "correlation_id": "corr_12345",       # Optional
            "agent_id": "agent_67890",           # Optional  
            "session_id": "session_abc123",      # Optional
            "event_id": "evt_xyz789",           # Optional
            "since": "2025-07-22T10:00:00Z",    # Optional
            "until": "2025-07-22T11:00:00Z",    # Optional
            "limit": 50,                        # Optional, default 20
            "fields": ["_event_id", "_agent_id"] # Optional field selection
        }
    
    Returns:
        {
            "contexts": [{"ref": "...", "context": {...}}, ...],
            "count": 15,
            "status": "success"
        }
    """
    try:
        cm = get_context_manager()
        
        # Extract query parameters
        correlation_id = data.get("correlation_id")
        agent_id = data.get("agent_id")
        session_id = data.get("session_id")
        event_id = data.get("event_id")
        since = data.get("since")
        until = data.get("until")
        limit = data.get("limit", 20)
        fields = data.get("fields")
        
        if limit > 1000:  # Reasonable query limit
            return error_response("Maximum 1000 results per query", context)
        
        # Build SQLite query conditions
        conditions = []
        params = []
        
        if correlation_id:
            conditions.append("correlation_id = ?")
            params.append(correlation_id)
            
        if agent_id:
            conditions.append("agent_id = ?")
            params.append(agent_id)
            
        if session_id:
            conditions.append("session_id = ?")  
            params.append(session_id)
            
        if event_id:
            conditions.append("event_id = ?")
            params.append(event_id)
            
        if since:
            # Convert ISO timestamp to epoch
            since_epoch = int(datetime.fromisoformat(since.replace('Z', '+00:00')).timestamp())
            conditions.append("created_at >= ?")
            params.append(since_epoch)
            
        if until:
            until_epoch = int(datetime.fromisoformat(until.replace('Z', '+00:00')).timestamp())
            conditions.append("created_at <= ?")
            params.append(until_epoch)
        
        # Build query
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"""
            SELECT ref, context_json 
            FROM contexts 
            WHERE {where_clause} 
            ORDER BY created_at DESC 
            LIMIT ?
        """
        params.append(limit)
        
        # Execute query
        db = cm.cold_storage
        rows = db.conn.execute(query, params).fetchall()
        
        contexts = []
        for row in rows:
            ref = row["ref"]
            context_data = __import__('json').loads(row["context_json"])
            
            # Apply field selection if requested
            if fields:
                filtered_context = {k: v for k, v in context_data.items() if k in fields}
            else:
                filtered_context = context_data
            
            contexts.append({
                "ref": ref,
                "context": filtered_context
            })
        
        return event_response_builder({
            "contexts": contexts,
            "count": len(contexts),
            "query": {
                "correlation_id": correlation_id,
                "agent_id": agent_id,
                "session_id": session_id,
                "event_id": event_id,
                "since": since,
                "until": until,
                "limit": limit,
                "fields": fields
            },
            "status": "success"
        }, context=context)
        
    except Exception as e:
        logger.error(f"Failed to query contexts: {e}")
        return error_response(f"Failed to query contexts: {str(e)}", context)


@event_handler("context:stats")
async def handle_context_stats(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get context storage statistics.
    
    Returns:
        {
            "hot_storage": {"count": 1500, "memory_mb": 25},
            "cold_storage": {"count": 50000, "size_mb": 125},
            "total_contexts": 51500,
            "oldest_context": "2025-07-15T10:00:00Z",
            "newest_context": "2025-07-22T14:30:00Z"
        }
    """
    try:
        cm = get_context_manager()
        
        # Get hot storage stats
        hot_count = len(cm.hot_storage.events)
        
        # Get cold storage stats
        db = cm.cold_storage
        cold_stats = db.conn.execute("""
            SELECT 
                COUNT(*) as count,
                MIN(created_at) as oldest,
                MAX(created_at) as newest
            FROM contexts
        """).fetchone()
        
        oldest_ts = datetime.fromtimestamp(cold_stats["oldest"]).isoformat() + "Z" if cold_stats["oldest"] else None
        newest_ts = datetime.fromtimestamp(cold_stats["newest"]).isoformat() + "Z" if cold_stats["newest"] else None
        
        return event_response_builder({
            "hot_storage": {
                "count": hot_count,
                "events": hot_count,
                "contexts_by_ref": len(cm.hot_storage.contexts_by_ref),
                "events_by_correlation": len(cm.hot_storage.events_by_correlation),
                "events_by_agent": len(cm.hot_storage.events_by_agent),
                "event_chains": len(cm.hot_storage.event_chains)
            },
            "cold_storage": {
                "count": cold_stats["count"],
                "contexts": cold_stats["count"]
            },
            "total_contexts": hot_count + cold_stats["count"],
            "oldest_context": oldest_ts,
            "newest_context": newest_ts,
            "status": "success"
        }, context=context)
        
    except Exception as e:
        logger.error(f"Failed to get context stats: {e}")
        return error_response(f"Failed to get context stats: {str(e)}", context)


@event_handler("context:health")
async def handle_context_health(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Check context system health.
    
    Returns:
        {
            "hot_storage": {"status": "healthy", "initialized": true},
            "cold_storage": {"status": "healthy", "initialized": true, "database_exists": true},
            "context_manager": {"initialized": true, "operational": true},
            "overall_status": "healthy"
        }
    """
    try:
        cm = get_context_manager()
        
        # Check hot storage
        hot_healthy = cm.hot_storage is not None and hasattr(cm.hot_storage, 'events')
        
        # Check cold storage
        cold_healthy = (cm.cold_storage is not None and 
                       cm.cold_storage.conn is not None and
                       cm.cold_storage.db_path.exists())
        
        # Test basic operations
        operational = True
        try:
            # Test hot storage
            test_ref = await cm.store_event_with_context({"test": True})
            test_context = await cm.get_context(test_ref)
            if not test_context:
                operational = False
        except Exception:
            operational = False
        
        overall_status = "healthy" if (hot_healthy and cold_healthy and operational) else "degraded"
        
        return event_response_builder({
            "hot_storage": {
                "status": "healthy" if hot_healthy else "unhealthy",
                "initialized": hot_healthy
            },
            "cold_storage": {
                "status": "healthy" if cold_healthy else "unhealthy", 
                "initialized": cold_healthy,
                "database_exists": cm.cold_storage.db_path.exists() if cm.cold_storage else False
            },
            "context_manager": {
                "initialized": cm._initialized,
                "operational": operational
            },
            "overall_status": overall_status,
            "status": "success"
        }, context=context)
        
    except Exception as e:
        logger.error(f"Failed to check context health: {e}")
        return error_response(f"Failed to check context health: {str(e)}", context)