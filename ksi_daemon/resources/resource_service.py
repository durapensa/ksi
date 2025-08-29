#!/usr/bin/env python3
"""
Resource Service for KSI - General-purpose resource management.
Handles creation, transfer, transformation, and tracking of any resource types.
"""

import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict
import uuid

from ksi_common.event import Event
from ksi_common.service import Service, EventHandler
from ksi_common.logging import get_bound_logger

logger = get_bound_logger(__name__)


@dataclass
class Resource:
    """Represents a resource in the system."""
    resource_id: str
    resource_type: str
    amount: float
    owner: str  # Entity that owns this resource
    properties: Dict[str, Any] = field(default_factory=dict)
    location: Optional[Dict[str, float]] = None  # Optional spatial location
    
    def split(self, split_amount: float) -> Optional['Resource']:
        """Split resource into two parts."""
        if split_amount > self.amount:
            return None
            
        self.amount -= split_amount
        
        return Resource(
            resource_id=f"{self.resource_id}_split_{uuid.uuid4().hex[:8]}",
            resource_type=self.resource_type,
            amount=split_amount,
            owner=self.owner,
            properties=self.properties.copy(),
            location=self.location.copy() if self.location else None
        )


@dataclass 
class TransformationRecipe:
    """Recipe for transforming resources."""
    recipe_id: str
    inputs: List[Dict[str, Any]]  # [{"type": "wood", "amount": 10}, ...]
    outputs: List[Dict[str, Any]]  # [{"type": "plank", "amount": 5}, ...]
    requirements: Dict[str, Any] = field(default_factory=dict)  # Tool requirements, etc.
    properties: Dict[str, Any] = field(default_factory=dict)


class ResourceService(Service):
    """Service for resource management in KSI."""
    
    def __init__(self):
        super().__init__()
        self.resources: Dict[str, Resource] = {}
        self.owner_index: Dict[str, List[str]] = defaultdict(list)
        self.type_index: Dict[str, List[str]] = defaultdict(list)
        self.recipes: Dict[str, TransformationRecipe] = {}
        self.resource_limits: Dict[str, Dict[str, float]] = {}  # Entity limits
        
    @EventHandler("resource:create")
    async def handle_resource_create(self, event: Event) -> Dict:
        """Create new resource in the system.
        
        Event data:
        - resource_type: Type of resource
        - amount: Amount to create
        - owner: Entity that owns resource (default: "environment")
        - location: Optional spatial location
        - properties: Resource properties (decay_rate, max_stack, etc.)
        - resource_id: Optional specific ID
        """
        data = event.data
        
        # Generate ID if not provided
        resource_id = data.get("resource_id", f"resource_{uuid.uuid4().hex}")
        
        # Create resource
        resource = Resource(
            resource_id=resource_id,
            resource_type=data["resource_type"],
            amount=data["amount"],
            owner=data.get("owner", "environment"),
            properties=data.get("properties", {}),
            location=data.get("location")
        )
        
        # Add to indices
        self.resources[resource_id] = resource
        self.owner_index[resource.owner].append(resource_id)
        self.type_index[resource.resource_type].append(resource_id)
        
        # Create state entity
        await self.emit_event("state:entity:create", {
            "type": "resource",
            "id": resource_id,
            "properties": {
                "resource_type": resource.resource_type,
                "amount": resource.amount,
                "owner": resource.owner,
                **resource.properties
            }
        })
        
        # Emit creation event
        await self.emit_event("resource:created", {
            "resource_id": resource_id,
            "resource_type": resource.resource_type,
            "amount": resource.amount,
            "owner": resource.owner
        })
        
        logger.info(f"Created resource: {resource_id} ({resource.resource_type}: {resource.amount})")
        
        return {
            "status": "created",
            "resource_id": resource_id,
            "amount": resource.amount
        }
    
    @EventHandler("resource:transfer")
    async def handle_resource_transfer(self, event: Event) -> Dict:
        """Transfer resources between entities.
        
        Event data:
        - from_entity: Source entity
        - to_entity: Target entity
        - resource_type: Type of resource to transfer
        - amount: Amount to transfer
        - transfer_type: trade|gift|steal|tax
        - validate_consent: Check if transfer is allowed
        - atomic: If true, all or nothing transfer
        """
        data = event.data
        from_entity = data["from_entity"]
        to_entity = data["to_entity"]
        resource_type = data["resource_type"]
        amount = data["amount"]
        
        # Check consent if required
        if data.get("validate_consent", False):
            consent_result = await self._check_transfer_consent(
                from_entity, to_entity, resource_type, amount,
                transfer_type=data.get("transfer_type", "trade")
            )
            
            if not consent_result["allowed"]:
                return {
                    "status": "refused",
                    "reason": consent_result.get("reason", "Transfer not consented")
                }
        
        # Find resources to transfer
        available_resources = self._get_entity_resources(from_entity, resource_type)
        total_available = sum(self.resources[rid].amount for rid in available_resources)
        
        if total_available < amount:
            if data.get("atomic", True):
                return {
                    "status": "failed",
                    "reason": f"Insufficient resources (has {total_available}, needs {amount})"
                }
            else:
                # Transfer what's available
                amount = total_available
        
        # Check recipient limits
        if to_entity in self.resource_limits:
            limit = self.resource_limits[to_entity].get(resource_type, float('inf'))
            current = sum(self.resources[rid].amount 
                         for rid in self._get_entity_resources(to_entity, resource_type))
            
            if current + amount > limit:
                if data.get("atomic", True):
                    return {
                        "status": "failed",
                        "reason": f"Would exceed recipient limit ({limit})"
                    }
                else:
                    amount = min(amount, limit - current)
        
        # Perform transfer
        transferred = 0.0
        transferred_resources = []
        
        for resource_id in available_resources:
            if transferred >= amount:
                break
                
            resource = self.resources[resource_id]
            transfer_amount = min(resource.amount, amount - transferred)
            
            if transfer_amount == resource.amount:
                # Transfer entire resource
                resource.owner = to_entity
                self.owner_index[from_entity].remove(resource_id)
                self.owner_index[to_entity].append(resource_id)
                transferred_resources.append(resource_id)
            else:
                # Split resource
                new_resource = resource.split(transfer_amount)
                if new_resource:
                    new_resource.owner = to_entity
                    self.resources[new_resource.resource_id] = new_resource
                    self.owner_index[to_entity].append(new_resource.resource_id)
                    self.type_index[resource_type].append(new_resource.resource_id)
                    transferred_resources.append(new_resource.resource_id)
            
            transferred += transfer_amount
        
        # Update state entities
        for resource_id in transferred_resources:
            resource = self.resources[resource_id]
            await self.emit_event("state:entity:update", {
                "type": "resource",
                "id": resource_id,
                "changes": {
                    "owner": resource.owner,
                    "amount": resource.amount
                }
            })
        
        # Emit transfer event
        await self.emit_event("resource:transferred", {
            "from_entity": from_entity,
            "to_entity": to_entity,
            "resource_type": resource_type,
            "amount": transferred,
            "transfer_type": data.get("transfer_type", "trade"),
            "resource_ids": transferred_resources
        })
        
        logger.info(f"Transferred {transferred} {resource_type} from {from_entity} to {to_entity}")
        
        return {
            "status": "success",
            "amount_transferred": transferred,
            "resource_ids": transferred_resources
        }
    
    @EventHandler("resource:transform")
    async def handle_resource_transform(self, event: Event) -> Dict:
        """Transform resources using a recipe.
        
        Event data:
        - entity_id: Entity performing transformation
        - recipe: Recipe ID or inline recipe definition
        - inputs: Override recipe inputs (optional)
        - outputs: Override recipe outputs (optional)
        - validate_requirements: Check if entity can perform transformation
        """
        data = event.data
        entity_id = data["entity_id"]
        
        # Get or create recipe
        if isinstance(data["recipe"], str):
            recipe_id = data["recipe"]
            if recipe_id not in self.recipes:
                return {"status": "failed", "reason": f"Recipe {recipe_id} not found"}
            recipe = self.recipes[recipe_id]
        else:
            # Inline recipe definition
            recipe = TransformationRecipe(
                recipe_id=f"inline_{uuid.uuid4().hex[:8]}",
                inputs=data.get("inputs", data["recipe"].get("inputs", [])),
                outputs=data.get("outputs", data["recipe"].get("outputs", [])),
                requirements=data["recipe"].get("requirements", {})
            )
        
        # Override inputs/outputs if provided
        inputs = data.get("inputs", recipe.inputs)
        outputs = data.get("outputs", recipe.outputs)
        
        # Validate requirements
        if data.get("validate_requirements", True):
            validation = await self._validate_transformation_requirements(
                entity_id, recipe.requirements
            )
            if not validation["valid"]:
                return {
                    "status": "failed",
                    "reason": validation.get("reason", "Requirements not met")
                }
        
        # Check input availability
        for input_spec in inputs:
            resource_type = input_spec["type"]
            required_amount = input_spec["amount"]
            
            available = sum(self.resources[rid].amount 
                          for rid in self._get_entity_resources(entity_id, resource_type))
            
            if available < required_amount:
                return {
                    "status": "failed",
                    "reason": f"Insufficient {resource_type} (has {available}, needs {required_amount})"
                }
        
        # Consume inputs
        consumed_resources = []
        for input_spec in inputs:
            resource_type = input_spec["type"]
            amount_to_consume = input_spec["amount"]
            
            resources = self._get_entity_resources(entity_id, resource_type)
            consumed = 0.0
            
            for resource_id in resources:
                if consumed >= amount_to_consume:
                    break
                    
                resource = self.resources[resource_id]
                consume_amount = min(resource.amount, amount_to_consume - consumed)
                
                resource.amount -= consume_amount
                consumed += consume_amount
                
                if resource.amount <= 0:
                    # Remove depleted resource
                    del self.resources[resource_id]
                    self.owner_index[entity_id].remove(resource_id)
                    self.type_index[resource_type].remove(resource_id)
                    
                    await self.emit_event("state:entity:delete", {
                        "type": "resource",
                        "id": resource_id
                    })
                else:
                    await self.emit_event("state:entity:update", {
                        "type": "resource",
                        "id": resource_id,
                        "changes": {"amount": resource.amount}
                    })
                
                consumed_resources.append({
                    "resource_id": resource_id,
                    "type": resource_type,
                    "amount": consume_amount
                })
        
        # Create outputs
        created_resources = []
        for output_spec in outputs:
            result = await self.handle_resource_create(Event(
                event="resource:create",
                data={
                    "resource_type": output_spec["type"],
                    "amount": output_spec["amount"],
                    "owner": entity_id,
                    "properties": output_spec.get("properties", {})
                }
            ))
            created_resources.append(result["resource_id"])
        
        # Emit transformation event
        await self.emit_event("resource:transformed", {
            "entity_id": entity_id,
            "recipe_id": recipe.recipe_id,
            "consumed": consumed_resources,
            "created": created_resources
        })
        
        logger.info(f"Entity {entity_id} transformed resources using recipe {recipe.recipe_id}")
        
        return {
            "status": "success",
            "consumed": consumed_resources,
            "created": created_resources
        }
    
    @EventHandler("resource:query")
    async def handle_resource_query(self, event: Event) -> Dict:
        """Query resources in the system.
        
        Event data:
        - query_type: by_owner|by_type|by_location
        - parameters: Query-specific parameters
        """
        data = event.data
        query_type = data["query_type"]
        params = data.get("parameters", {})
        
        if query_type == "by_owner":
            owner = params["owner"]
            resource_ids = self.owner_index.get(owner, [])
            resources = [self.resources[rid] for rid in resource_ids if rid in self.resources]
            
        elif query_type == "by_type":
            resource_type = params["resource_type"]
            resource_ids = self.type_index.get(resource_type, [])
            resources = [self.resources[rid] for rid in resource_ids if rid in self.resources]
            
        elif query_type == "by_location":
            # Query resources near a location
            location = params["location"]
            radius = params.get("radius", 10)
            
            resources = []
            for resource in self.resources.values():
                if resource.location:
                    distance = ((resource.location["x"] - location["x"])**2 + 
                              (resource.location["y"] - location["y"])**2)**0.5
                    if distance <= radius:
                        resources.append(resource)
        else:
            return {"error": f"Unknown query type: {query_type}"}
        
        # Format results
        return {
            "resources": [
                {
                    "resource_id": r.resource_id,
                    "resource_type": r.resource_type,
                    "amount": r.amount,
                    "owner": r.owner,
                    "location": r.location
                }
                for r in resources
            ],
            "count": len(resources),
            "total_amount": sum(r.amount for r in resources)
        }
    
    @EventHandler("resource:set_limit")
    async def handle_set_limit(self, event: Event) -> Dict:
        """Set resource limits for an entity.
        
        Event data:
        - entity_id: Entity to set limits for
        - limits: Dict of resource_type -> max_amount
        """
        data = event.data
        entity_id = data["entity_id"]
        
        if entity_id not in self.resource_limits:
            self.resource_limits[entity_id] = {}
            
        self.resource_limits[entity_id].update(data["limits"])
        
        logger.info(f"Set resource limits for {entity_id}: {data['limits']}")
        
        return {"status": "limits_set", "entity_id": entity_id}
    
    @EventHandler("resource:recipe:register")
    async def handle_recipe_register(self, event: Event) -> Dict:
        """Register a transformation recipe.
        
        Event data:
        - recipe_id: Unique recipe identifier
        - inputs: List of input specifications
        - outputs: List of output specifications
        - requirements: Optional requirements dict
        """
        data = event.data
        
        recipe = TransformationRecipe(
            recipe_id=data["recipe_id"],
            inputs=data["inputs"],
            outputs=data["outputs"],
            requirements=data.get("requirements", {}),
            properties=data.get("properties", {})
        )
        
        self.recipes[recipe.recipe_id] = recipe
        
        logger.info(f"Registered recipe: {recipe.recipe_id}")
        
        return {"status": "registered", "recipe_id": recipe.recipe_id}
    
    def _get_entity_resources(self, entity_id: str, resource_type: Optional[str] = None) -> List[str]:
        """Get resource IDs owned by entity, optionally filtered by type."""
        resource_ids = self.owner_index.get(entity_id, [])
        
        if resource_type:
            resource_ids = [rid for rid in resource_ids 
                          if rid in self.resources and 
                          self.resources[rid].resource_type == resource_type]
        
        return resource_ids
    
    async def _check_transfer_consent(self, from_entity: str, to_entity: str,
                                     resource_type: str, amount: float,
                                     transfer_type: str) -> Dict:
        """Check if resource transfer is consented."""
        
        # Check permission system
        permission_result = await self.emit_event("permission:check", {
            "actor": to_entity,  # Receiver initiates
            "target": from_entity,  # Owner must consent
            "action": f"resource:transfer:{transfer_type}",
            "context": {
                "resource_type": resource_type,
                "amount": amount
            }
        })
        
        # For POC, simplified consent logic
        # In production, would wait for and parse permission response
        
        # Always allow environment transfers
        if from_entity == "environment":
            return {"allowed": True}
        
        # Always allow self-transfers
        if from_entity == to_entity:
            return {"allowed": True}
        
        # Check transfer type
        if transfer_type == "steal":
            # Stealing requires special permission or bypassing consent
            return {"allowed": False, "reason": "Stealing not permitted"}
        elif transfer_type == "tax":
            # Tax transfers might have special rules
            return {"allowed": True}  # Simplified for POC
        
        # Default: allow trades and gifts
        return {"allowed": True}
    
    async def _validate_transformation_requirements(self, entity_id: str, 
                                                   requirements: Dict) -> Dict:
        """Validate if entity meets transformation requirements."""
        
        # Check tool requirements
        if "tools" in requirements:
            for tool in requirements["tools"]:
                # Check if entity has required tool
                tool_resources = self._get_entity_resources(entity_id, tool)
                if not tool_resources:
                    return {
                        "valid": False,
                        "reason": f"Missing required tool: {tool}"
                    }
        
        # Check skill requirements
        if "skills" in requirements:
            # Would query entity capabilities/skills
            # Simplified for POC
            pass
        
        # Check location requirements
        if "location" in requirements:
            # Would check if entity is at required location type
            # Simplified for POC
            pass
        
        return {"valid": True}


if __name__ == "__main__":
    # Example usage
    async def test_resource_service():
        service = ResourceService()
        
        # Create resources
        result1 = await service.handle_resource_create(Event(
            event="resource:create",
            data={
                "resource_type": "wood",
                "amount": 100,
                "owner": "player_1"
            }
        ))
        
        result2 = await service.handle_resource_create(Event(
            event="resource:create",
            data={
                "resource_type": "stone",
                "amount": 50,
                "owner": "player_1"
            }
        ))
        
        # Register recipe
        await service.handle_recipe_register(Event(
            event="resource:recipe:register",
            data={
                "recipe_id": "craft_tool",
                "inputs": [
                    {"type": "wood", "amount": 10},
                    {"type": "stone", "amount": 5}
                ],
                "outputs": [
                    {"type": "tool", "amount": 1}
                ]
            }
        ))
        
        # Transform resources
        result3 = await service.handle_resource_transform(Event(
            event="resource:transform",
            data={
                "entity_id": "player_1",
                "recipe": "craft_tool"
            }
        ))
        
        print(f"Transformation result: {result3}")
        
        # Query resources
        result4 = await service.handle_resource_query(Event(
            event="resource:query",
            data={
                "query_type": "by_owner",
                "parameters": {"owner": "player_1"}
            }
        ))
        
        print(f"Player resources: {result4}")
    
    asyncio.run(test_resource_service())