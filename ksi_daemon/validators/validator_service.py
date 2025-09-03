#!/usr/bin/env python3
"""
Validator Service
=================

Exposes Melting Pot validators through KSI's event system.
Makes validators accessible for testing and production use.
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import asdict

from ksi_daemon.event_system import event_handler, emit_event
from ksi_common.event_response_builder import error_response

# Import validators
from .movement_validator import (
    MovementValidator, MovementRequest, Position
)
from .resource_validator import (
    ResourceTransferValidator, ResourceTransferRequest, TransferType
)
from .interaction_validator import (
    InteractionValidator, InteractionRequest, InteractionType
)

logger = logging.getLogger(__name__)

# Initialize validator instances
movement_validator = MovementValidator()
resource_validator = ResourceTransferValidator()
interaction_validator = InteractionValidator()


# ==================== Movement Validation ====================

@event_handler("validator:movement:validate")
async def validate_movement(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a movement request."""
    try:
        # Debug: Log raw data received
        logger.info(f"Raw data received: {data}")
        
        # Support both array format and individual coordinate format
        # Priority: array format > individual coordinates > defaults
        
        # Extract from_position
        if 'from_position' in data:
            # Array format: [x, y] or [x, y, z]
            pos = data['from_position']
            if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                from_x = float(pos[0])
                from_y = float(pos[1])
            else:
                from_x = float(data.get('from_x', 0.0))
                from_y = float(data.get('from_y', 0.0))
        else:
            # Individual coordinates
            from_x = float(data.get('from_x', 0.0))
            from_y = float(data.get('from_y', 0.0))
        
        # Extract to_position
        if 'to_position' in data:
            # Array format: [x, y] or [x, y, z]
            pos = data['to_position']
            if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                to_x = float(pos[0])
                to_y = float(pos[1])
            else:
                to_x = float(data.get('to_x', 0.0))
                to_y = float(data.get('to_y', 0.0))
        else:
            # Individual coordinates
            to_x = float(data.get('to_x', 0.0))
            to_y = float(data.get('to_y', 0.0))
        
        movement_type = str(data.get('movement_type', 'walk'))
        entity_capacity = float(data.get('entity_capacity', 5.0))
        environment = data.get('environment')
        
        logger.info(f"Converted values: from_x={from_x}, from_y={from_y}, to_x={to_x}, to_y={to_y}")
        
        # Create request (movement_type is a string)
        request = MovementRequest(
            entity_id="test_entity",
            entity_type="agent",
            from_position=Position(from_x, from_y),
            to_position=Position(to_x, to_y),
            movement_type=movement_type.lower(),
            speed=1.0,
            capabilities=[]
        )
        
        # Validate
        result = movement_validator.validate_movement(request, environment)
        
        # Map ValidationResult to response dict
        response = {
            "valid": result.valid,
            "reason": result.reason,
            "warnings": result.warnings if result.warnings else []
        }
        
        # Add path cost if available (ValidationResult has 'cost' not 'path_cost')
        if hasattr(result, 'cost'):
            response["path_cost"] = result.cost
        
        # Add actual distance if available (not in ValidationResult)
        response["actual_distance"] = request.from_position.distance_to(request.to_position)
        
        # Add suggested path if available
        if result.suggested_path:
            response["suggested_path"] = [
                {"x": pos.x, "y": pos.y} for pos in result.suggested_path
            ]
        
        return response
        
    except Exception as e:
        logger.error(f"Movement validation error: {e}")
        return error_response(f"Movement validation failed: {str(e)}")


@event_handler("validator:movement:add_obstacle")
async def add_obstacle(data: Dict[str, Any]) -> Dict[str, Any]:
    """Add an obstacle to the movement validator."""
    try:
        x = int(data.get('x', 0))
        y = int(data.get('y', 0))
        # The add_obstacle method expects a dict, not a tuple
        movement_validator.add_obstacle({"x": x, "y": y})
        return {"status": "success", "obstacle": {"x": x, "y": y}}
    except Exception as e:
        return error_response(f"Failed to add obstacle: {str(e)}")


@event_handler("validator:movement:clear_obstacles")
async def clear_obstacles(data: Dict[str, Any]) -> Dict[str, Any]:
    """Clear all obstacles from the movement validator."""
    try:
        movement_validator.clear_obstacles()
        return {"status": "success", "message": "All obstacles cleared"}
    except Exception as e:
        return error_response(f"Failed to clear obstacles: {str(e)}")


# ==================== Resource Validation ====================

@event_handler("validator:resource:validate")
async def validate_resource_transfer(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a resource transfer request."""
    try:
        # Extract parameters from data dictionary with type conversion
        from_entity = str(data.get('from_entity', ''))
        to_entity = str(data.get('to_entity', ''))
        resource_type = str(data.get('resource_type', ''))
        amount = float(data.get('amount', 0.0))
        transfer_type = str(data.get('transfer_type', 'trade'))
        metadata = data.get('metadata')
        context = data.get('context')
        
        # Map common transfer types to valid enum values
        transfer_mapping = {
            "cooperation_reward": "gift",  # Rewards are gifts
            "redistribution": "tax",  # Redistribution is like taxation
            "cleanup": "consumption",  # Cleanup consumes pollution
            "production_byproduct": "production",
            "public_good": "gift",  # Public goods are like gifts to all
            "pickup": "harvest",  # Picking up is harvesting
            "serve": "trade",  # Serving food is a trade
            "harvest": "harvest"  # Harvest is already a valid type
        }
        
        # Try to map the transfer type
        mapped_type = transfer_mapping.get(transfer_type.lower(), transfer_type)
        
        # Try to get the enum value
        try:
            transfer_enum = TransferType[mapped_type.upper()]
        except KeyError:
            # If still not found, default to trade and log
            logger.warning(f"Unknown transfer type '{transfer_type}', defaulting to TRADE")
            transfer_enum = TransferType.TRADE
        
        # Create request
        request = ResourceTransferRequest(
            from_entity=from_entity,
            to_entity=to_entity,
            resource_type=resource_type,
            amount=amount,
            transfer_type=transfer_enum,
            metadata=metadata or {}
        )
        
        # Validate
        result = resource_validator.validate_transfer(request, context)
        
        response = {
            "valid": result.valid,
            "reason": result.reason,
            "suggested_amount": result.suggested_amount,
            "alternative_transfers": result.alternative_transfers
        }
        
        # Add consent info if present
        if result.consent:
            response["consent"] = {
                "consented": result.consent.consented,
                "reason": result.consent.reason,
                "negotiated_amount": result.consent.negotiated_amount,
                "conditions": result.consent.conditions
            }
        
        # Add fairness info if present
        if result.fairness:
            response["fairness"] = {
                "fair": result.fairness.fair,
                "gini_impact": result.fairness.gini_impact,
                "monopoly_risk": result.fairness.monopoly_risk,
                "exploitation_risk": result.fairness.exploitation_risk,
                "sustainability_impact": result.fairness.sustainability_impact,
                "warnings": result.fairness.warnings
            }
        
        return response
        
    except Exception as e:
        logger.error(f"Resource validation error: {e}")
        return error_response(f"Resource validation failed: {str(e)}")


@event_handler("validator:resource:update_ownership")
async def update_resource_ownership(data: Dict[str, Any]) -> Dict[str, Any]:
    """Update resource ownership for an entity."""
    try:
        entity = str(data.get('entity', ''))
        resource_type = str(data.get('resource_type', ''))
        amount = float(data.get('amount', 0.0))
        
        resource_validator.update_ownership(entity, resource_type, amount)
        new_wealth = resource_validator.get_entity_wealth(entity)
        
        # Also update metrics service for tracking
        episode_id = data.get('episode_id', 'default')
        await emit_event("metrics:update_resources", {
            "episode_id": episode_id,
            "entity": entity,
            "resource_type": resource_type,
            "amount": amount
        })
        
        return {
            "status": "success",
            "entity": entity,
            "resource_type": resource_type,
            "new_amount": resource_validator.resource_ownership.get(entity, {}).get(resource_type, 0),
            "total_wealth": new_wealth
        }
    except Exception as e:
        return error_response(f"Failed to update ownership: {str(e)}")


@event_handler("validator:resource:get_wealth")
async def get_entity_wealth(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get total wealth of an entity."""
    try:
        entity = str(data.get('entity', ''))
        wealth = resource_validator.get_entity_wealth(entity)
        resources = resource_validator.resource_ownership.get(entity, {})
        
        return {
            "entity": entity,
            "total_wealth": wealth,
            "resources": resources
        }
    except Exception as e:
        return error_response(f"Failed to get wealth: {str(e)}")


@event_handler("validator:resource:calculate_gini")
async def calculate_gini_coefficient(data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate current Gini coefficient of wealth distribution."""
    try:
        gini = resource_validator._calculate_gini()
        
        # Get wealth distribution
        wealth_by_entity = {}
        for entity, resources in resource_validator.resource_ownership.items():
            wealth_by_entity[entity] = sum(resources.values())
        
        return {
            "gini_coefficient": gini,
            "wealth_distribution": wealth_by_entity,
            "entity_count": len(wealth_by_entity)
        }
    except Exception as e:
        return error_response(f"Failed to calculate Gini: {str(e)}")


# ==================== Interaction Validation ====================

@event_handler("validator:interaction:validate")
async def validate_interaction(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate an interaction request."""
    try:
        # Extract parameters from data dictionary with type conversion
        actor_id = str(data.get('actor_id', ''))
        target_id = str(data.get('target_id', ''))
        interaction_type = str(data.get('interaction_type', 'cooperate'))
        actor_x = float(data.get('actor_x', 0.0))
        actor_y = float(data.get('actor_y', 0.0))
        target_x = float(data.get('target_x', 0.0))
        target_y = float(data.get('target_y', 0.0))
        range_limit = float(data.get('range_limit', 0.0))
        capabilities = data.get('capabilities')
        parameters = data.get('parameters')
        context = data.get('context')
        
        # Map common interaction types to valid enum values
        interaction_mapping = {
            "defect": "compete",  # Defection is a form of competition
            "coordinate": "cooperate",  # Coordination is cooperation
            "coordinate_cooking": "cooperate",
            "harvest": "collect",
            "cleanup": "help",
            "mind_meld": "communicate"  # Unknown types default to communicate
        }
        
        # Try to map the interaction type
        mapped_type = interaction_mapping.get(interaction_type.lower(), interaction_type)
        
        # Try to get the enum value
        try:
            interaction_enum = InteractionType[mapped_type.upper()]
        except KeyError:
            # If still not found, default to a safe type and log
            logger.warning(f"Unknown interaction type '{interaction_type}', defaulting to COMMUNICATE")
            interaction_enum = InteractionType.COMMUNICATE
        
        # Create request
        request = InteractionRequest(
            actor_id=actor_id,
            target_id=target_id,
            interaction_type=interaction_enum,
            range_limit=range_limit,
            position_actor=(actor_x, actor_y),
            position_target=(target_x, target_y),
            capabilities=capabilities or [],
            parameters=parameters or {}
        )
        
        # Validate
        result = interaction_validator.validate_interaction(request, context)
        
        return {
            "valid": result.valid,
            "reason": result.reason,
            "required_participants": result.required_participants,
            "missing_capabilities": result.missing_capabilities,
            "suggested_position": result.suggested_position,
            "cooperation_score": result.cooperation_score,
            "warnings": result.warnings
        }
        
    except Exception as e:
        logger.error(f"Interaction validation error: {e}")
        return error_response(f"Interaction validation failed: {str(e)}")


@event_handler("validator:interaction:get_relationship")
async def get_relationship_score(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get relationship/trust score between two entities."""
    try:
        entity1 = str(data.get('entity1', ''))
        entity2 = str(data.get('entity2', ''))
        score = interaction_validator.get_relationship_score(entity1, entity2)
        
        return {
            "entity1": entity1,
            "entity2": entity2,
            "trust_score": score,
            "relationship_quality": "high" if score > 0.7 else "medium" if score > 0.4 else "low"
        }
    except Exception as e:
        return error_response(f"Failed to get relationship: {str(e)}")


@event_handler("validator:interaction:update_relationship")
async def update_relationship(data: Dict[str, Any]) -> Dict[str, Any]:
    """Update relationship score between entities."""
    try:
        entity1 = str(data.get('entity1', ''))
        entity2 = str(data.get('entity2', ''))
        trust_score = float(data.get('trust_score', 0.5))
        
        # Clamp score to [0, 1]
        trust_score = max(0, min(1, trust_score))
        
        # Update both directions
        interaction_validator.entity_relationships[(entity1, entity2)] = trust_score
        interaction_validator.entity_relationships[(entity2, entity1)] = trust_score
        
        return {
            "status": "success",
            "entity1": entity1,
            "entity2": entity2,
            "trust_score": trust_score
        }
    except Exception as e:
        return error_response(f"Failed to update relationship: {str(e)}")


# ==================== Batch Validation ====================

@event_handler("validator:batch:validate_all")
async def validate_batch(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate multiple requests in batch."""
    results = {
        "movement": [],
        "resource": [],
        "interaction": []
    }
    
    try:
        movement_requests = data.get('movement_requests')
        resource_requests = data.get('resource_requests')
        interaction_requests = data.get('interaction_requests')
        
        # Process movement requests
        if movement_requests:
            for req in movement_requests:
                result = await validate_movement(req)
                results["movement"].append(result)
        
        # Process resource requests
        if resource_requests:
            for req in resource_requests:
                result = await validate_resource_transfer(req)
                results["resource"].append(result)
        
        # Process interaction requests
        if interaction_requests:
            for req in interaction_requests:
                result = await validate_interaction(req)
                results["interaction"].append(result)
        
        # Calculate summary statistics
        total_requests = (
            len(results["movement"]) + 
            len(results["resource"]) + 
            len(results["interaction"])
        )
        
        valid_count = (
            sum(1 for r in results["movement"] if r.get("valid")) +
            sum(1 for r in results["resource"] if r.get("valid")) +
            sum(1 for r in results["interaction"] if r.get("valid"))
        )
        
        return {
            "results": results,
            "summary": {
                "total_requests": total_requests,
                "valid_count": valid_count,
                "pass_rate": valid_count / total_requests if total_requests > 0 else 0
            }
        }
        
    except Exception as e:
        logger.error(f"Batch validation error: {e}")
        return error_response(f"Batch validation failed: {str(e)}")


# ==================== Service Info ====================

@event_handler("validator:info")
async def get_validator_info(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get information about the validator service."""
    return {
        "service": "validator",
        "version": "1.0.0",
        "validators": {
            "movement": {
                "obstacle_count": len(movement_validator.obstacles),
                "movement_types": list(movement_validator.movement_rules.keys())
            },
            "resource": {
                "entity_count": len(resource_validator.resource_ownership),
                "transfer_history_size": len(resource_validator.transfer_history),
                "gini_coefficient": resource_validator._calculate_gini()
            },
            "interaction": {
                "relationship_count": len(interaction_validator.entity_relationships),
                "interaction_history_size": len(interaction_validator.interaction_history),
                "interaction_types": [t.value for t in InteractionType]
            }
        }
    }


# Export for discovery
__all__ = [
    'validate_movement',
    'validate_resource_transfer', 
    'validate_interaction',
    'validate_batch',
    'get_validator_info'
]