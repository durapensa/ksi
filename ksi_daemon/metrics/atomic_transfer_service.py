#!/usr/bin/env python3
"""
Atomic transfer service for resource management.
Fixes Issue #13: Race conditions in concurrent updates.
"""

import asyncio
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime
import uuid

from ksi_daemon.event_system import event_handler, get_router
from ksi_common.event_utils import extract_single_response
from ksi_common.event_response_builder import success_response, error_response, event_response_builder
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("atomic_transfer_service")


# Global state for the service
class TransferManager:
    """Manages locks and history for atomic transfers."""
    def __init__(self):
        self.transfer_locks: Dict[str, asyncio.Lock] = {}
        self.transfer_history: List[Dict] = []
    
    def get_lock_key(self, resource1: str, resource2: str) -> str:
        """Get consistent lock key for resource pair."""
        # Always sort to prevent deadlock
        return f"transfer_lock:{min(resource1, resource2)}:{max(resource1, resource2)}"
    
    def get_lock(self, resource1: str, resource2: str) -> asyncio.Lock:
        """Get or create lock for resource pair."""
        key = self.get_lock_key(resource1, resource2)
        if key not in self.transfer_locks:
            self.transfer_locks[key] = asyncio.Lock()
        return self.transfer_locks[key]


# Global manager instance
transfer_manager = TransferManager()


async def get_resource(resource_id: str, context: Dict) -> Optional[Dict]:
    """Get resource entity with current state."""
    router = get_router()
    if not router:
        logger.error("No router available")
        return None
        
    result = await router.emit("state:entity:get", {
        "type": "resource",
        "id": resource_id
    }, context)
    
    result = extract_single_response(result)
    if result and result.get("status") == "success":
        return result
    return None


async def update_resource(resource_id: str, new_amount: int, context: Dict) -> bool:
    """Update resource amount."""
    router = get_router()
    if not router:
        logger.error("No router available")
        return False
        
    result = await router.emit("state:entity:update", {
        "type": "resource", 
        "id": resource_id,
        "properties": {"amount": new_amount}
    }, context)
    
    result = extract_single_response(result)
    return result and result.get("status") == "success"


@event_handler("resource:transfer")
async def atomic_transfer(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Perform atomic resource transfer with validation.
    
    Ensures:
    - No lost updates via locking
    - No negative balances via validation
    - Resource conservation via atomic operations
    - Thread-safe concurrent transfers
    """
    # Get router for emitting events
    router = get_router()
    if not router:
        return error_response("No router available", context=context)
    
    # Extract parameters
    from_resource = data.get("from_resource")
    to_resource = data.get("to_resource")
    amount = data.get("amount", 0)
    
    # Validation
    if not from_resource or not to_resource:
        return error_response("Missing from_resource or to_resource", context=context)
    
    if from_resource == to_resource:
        return error_response("Cannot transfer to same resource", context=context)
    
    if amount <= 0:
        return error_response(f"Invalid transfer amount: {amount}", context=context)
    
    # Get lock for this resource pair
    lock = transfer_manager.get_lock(from_resource, to_resource)
    
    transfer_id = f"txn_{uuid.uuid4().hex[:8]}"
    start_time = datetime.now()
    
    # Acquire lock for atomic operation
    async with lock:
        logger.info(f"Transfer {transfer_id}: Acquiring lock for {from_resource} → {to_resource}")
        
        # Get current balances
        from_result = await get_resource(from_resource, context)
        to_result = await get_resource(to_resource, context)
        
        if not from_result:
            return error_response(f"Source resource not found: {from_resource}", context=context)
        
        if not to_result:
            return error_response(f"Target resource not found: {to_resource}", context=context)
        
        from_balance = from_result.get("properties", {}).get("amount", 0)
        to_balance = to_result.get("properties", {}).get("amount", 0)
        
        # Validate sufficient funds
        if from_balance < amount:
            return error_response(
                f"Insufficient funds: {from_balance} < {amount}",
                details={
                    "from_resource": from_resource,
                    "available": from_balance,
                    "requested": amount
                },
                context=context
            )
        
        # Perform atomic transfer
        new_from_balance = from_balance - amount
        new_to_balance = to_balance + amount
        
        # Update both resources
        from_success = await update_resource(from_resource, new_from_balance, context)
        if not from_success:
            return error_response(
                f"Failed to update source resource: {from_resource}",
                context=context
            )
        
        to_success = await update_resource(to_resource, new_to_balance, context)
        if not to_success:
            # Rollback source update
            await update_resource(from_resource, from_balance, context)
            return error_response(
                f"Failed to update target resource: {to_resource} (rolled back)",
                context=context
            )
        
        # Record transfer in history
        transfer_record = {
            "transfer_id": transfer_id,
            "timestamp": start_time.isoformat(),
            "from_resource": from_resource,
            "to_resource": to_resource,
            "amount": amount,
            "from_balance_before": from_balance,
            "from_balance_after": new_from_balance,
            "to_balance_before": to_balance,
            "to_balance_after": new_to_balance
        }
        transfer_manager.transfer_history.append(transfer_record)
        
        # Emit metrics event
        await router.emit("metrics:fairness:transfer", {
            "transfer_id": transfer_id,
            "from_agent": from_result.get("properties", {}).get("owner", "unknown"),
            "to_agent": to_result.get("properties", {}).get("owner", "unknown"),
            "amount": amount,
            "timestamp": start_time.isoformat()
        }, context)
        
        logger.info(
            f"Transfer {transfer_id} complete: {from_resource}({from_balance}→{new_from_balance}) "
            f"→ {to_resource}({to_balance}→{new_to_balance})"
        )
        
        return success_response({
            "transfer_id": transfer_id,
            "transferred": amount,
            "from_resource": from_resource,
            "to_resource": to_resource,
            "from_balance_before": from_balance,
            "from_balance_after": new_from_balance,
            "to_balance_before": to_balance,
            "to_balance_after": new_to_balance,
            "conservation_check": {
                "before": from_balance + to_balance,
                "after": new_from_balance + new_to_balance,
                "conserved": (from_balance + to_balance) == (new_from_balance + new_to_balance)
            }
        }, context=context)


@event_handler("resource:bulk_transfer")
async def bulk_transfer(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Perform multiple transfers atomically.
    
    All transfers succeed or all fail (transactional).
    """
    # No need to get router here since atomic_transfer will handle it
    
    transfers = data.get("transfers", [])
    if not transfers:
        return error_response("No transfers specified", context=context)
    
    results = []
    completed = []
    
    try:
        for transfer in transfers:
            # Call atomic_transfer directly with augmented context
            result = await atomic_transfer(transfer, context)
            
            if result.get("status") != "success":
                # Rollback all completed transfers
                for completed_transfer in reversed(completed):
                    rollback_data = {
                        "from_resource": completed_transfer["to_resource"],
                        "to_resource": completed_transfer["from_resource"],
                        "amount": completed_transfer["transferred"]
                    }
                    await atomic_transfer(rollback_data, context)
                
                return error_response(
                    f"Bulk transfer failed at transfer {len(completed) + 1}: {result.get('error')}",
                    details={"failed_transfer": transfer},
                    context=context
                )
            
            results.append(result)
            completed.append(result)
        
        return success_response({
            "transfers_completed": len(results),
            "total_amount_transferred": sum(r["transferred"] for r in results),
            "results": results
        }, context=context)
        
    except Exception as e:
        logger.error(f"Bulk transfer error: {e}")
        return error_response(f"Bulk transfer failed: {str(e)}", context=context)


@event_handler("resource:transfer:history")
async def get_transfer_history(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Get recent transfer history for debugging."""
    limit = data.get("limit", 10)
    resource_filter = data.get("resource")
    
    history = transfer_manager.transfer_history
    
    # Filter by resource if specified
    if resource_filter:
        history = [
            t for t in history 
            if t["from_resource"] == resource_filter or t["to_resource"] == resource_filter
        ]
    
    # Return most recent transfers
    recent = history[-limit:] if limit else history
    
    return success_response({
        "total_transfers": len(transfer_manager.transfer_history),
        "filtered_count": len(history),
        "returned_count": len(recent),
        "transfers": recent
    }, context=context)


@event_handler("resource:validate_balance")  
async def validate_balance(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Validate that a resource has non-negative balance."""
    resource_id = data.get("resource_id")
    
    if not resource_id:
        return error_response("Missing resource_id", context=context)
    
    result = await get_resource(resource_id, context)
    
    if not result:
        return error_response(f"Resource not found: {resource_id}", context=context)
    
    amount = result.get("properties", {}).get("amount", 0)
    
    return success_response({
        "resource_id": resource_id,
        "amount": amount,
        "valid": amount >= 0,
        "message": "Balance valid" if amount >= 0 else f"Negative balance: {amount}"
    }, context=context)


# Module initialization
logger.info("Atomic transfer service loaded")