#!/usr/bin/env python3
"""
Spatial Service for KSI - General-purpose spatial operations.
Provides spatial queries, movement, and interactions for any 2D/3D environment.
"""

import asyncio
import numpy as np
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
import heapq
from collections import defaultdict

from ksi_common.event import Event
from ksi_common.service import Service, EventHandler
from ksi_common.logging import get_bound_logger

logger = get_bound_logger(__name__)


@dataclass
class SpatialEntity:
    """Entity with spatial properties."""
    entity_id: str
    entity_type: str
    x: float
    y: float
    z: float = 0.0
    properties: Dict[str, Any] = field(default_factory=dict)
    
    def distance_to(self, other: 'SpatialEntity', metric: str = "euclidean") -> float:
        """Calculate distance to another entity."""
        if metric == "euclidean":
            return np.sqrt((self.x - other.x)**2 + (self.y - other.y)**2 + (self.z - other.z)**2)
        elif metric == "manhattan":
            return abs(self.x - other.x) + abs(self.y - other.y) + abs(self.z - other.z)
        else:
            raise ValueError(f"Unknown distance metric: {metric}")


class SpatialIndex:
    """Efficient spatial indexing for queries."""
    
    def __init__(self, dimensions: int = 2, grid_size: float = 10.0):
        """Initialize spatial index.
        
        Args:
            dimensions: 2D or 3D space
            grid_size: Size of grid cells for bucketing
        """
        self.dimensions = dimensions
        self.grid_size = grid_size
        self.entities: Dict[str, SpatialEntity] = {}
        self.grid_index: Dict[Tuple, Set[str]] = defaultdict(set)
        self.type_index: Dict[str, Set[str]] = defaultdict(set)
        
    def _get_grid_cell(self, x: float, y: float, z: float = 0) -> Tuple:
        """Get grid cell for coordinates."""
        cell_x = int(x / self.grid_size)
        cell_y = int(y / self.grid_size)
        if self.dimensions == 3:
            cell_z = int(z / self.grid_size)
            return (cell_x, cell_y, cell_z)
        return (cell_x, cell_y)
    
    def add_entity(self, entity: SpatialEntity):
        """Add entity to spatial index."""
        # Remove old position if exists
        if entity.entity_id in self.entities:
            self.remove_entity(entity.entity_id)
            
        # Add to indices
        self.entities[entity.entity_id] = entity
        grid_cell = self._get_grid_cell(entity.x, entity.y, entity.z)
        self.grid_index[grid_cell].add(entity.entity_id)
        self.type_index[entity.entity_type].add(entity.entity_id)
        
    def remove_entity(self, entity_id: str):
        """Remove entity from spatial index."""
        if entity_id not in self.entities:
            return
            
        entity = self.entities[entity_id]
        grid_cell = self._get_grid_cell(entity.x, entity.y, entity.z)
        
        self.grid_index[grid_cell].discard(entity_id)
        self.type_index[entity.entity_type].discard(entity_id)
        del self.entities[entity_id]
        
    def update_position(self, entity_id: str, x: float, y: float, z: float = 0):
        """Update entity position efficiently."""
        if entity_id not in self.entities:
            return
            
        entity = self.entities[entity_id]
        old_cell = self._get_grid_cell(entity.x, entity.y, entity.z)
        new_cell = self._get_grid_cell(x, y, z)
        
        # Update grid index if cell changed
        if old_cell != new_cell:
            self.grid_index[old_cell].discard(entity_id)
            self.grid_index[new_cell].add(entity_id)
            
        # Update position
        entity.x, entity.y, entity.z = x, y, z
        
    def query_radius(self, x: float, y: float, z: float = 0, 
                    radius: float = 10.0, entity_types: Optional[List[str]] = None,
                    max_results: Optional[int] = None) -> List[SpatialEntity]:
        """Query entities within radius."""
        results = []
        center = SpatialEntity("query", "query", x, y, z)
        
        # Calculate grid cells to check
        cells_to_check = set()
        cell_radius = int(radius / self.grid_size) + 1
        center_cell = self._get_grid_cell(x, y, z)
        
        for dx in range(-cell_radius, cell_radius + 1):
            for dy in range(-cell_radius, cell_radius + 1):
                if self.dimensions == 3:
                    for dz in range(-cell_radius, cell_radius + 1):
                        cells_to_check.add((center_cell[0] + dx, 
                                          center_cell[1] + dy,
                                          center_cell[2] + dz))
                else:
                    cells_to_check.add((center_cell[0] + dx, center_cell[1] + dy))
                    
        # Check entities in relevant cells
        checked_entities = set()
        for cell in cells_to_check:
            for entity_id in self.grid_index.get(cell, set()):
                if entity_id in checked_entities:
                    continue
                checked_entities.add(entity_id)
                
                entity = self.entities[entity_id]
                
                # Type filter
                if entity_types and entity.entity_type not in entity_types:
                    continue
                    
                # Distance check
                if entity.distance_to(center) <= radius:
                    results.append(entity)
                    
                    # Result limit
                    if max_results and len(results) >= max_results:
                        return results
                        
        return results
    
    def query_rectangle(self, x_min: float, y_min: float, x_max: float, y_max: float,
                       z_min: float = 0, z_max: float = 0,
                       entity_types: Optional[List[str]] = None) -> List[SpatialEntity]:
        """Query entities within rectangle/box."""
        results = []
        
        # Calculate grid cells to check
        cells_to_check = set()
        min_cell = self._get_grid_cell(x_min, y_min, z_min)
        max_cell = self._get_grid_cell(x_max, y_max, z_max)
        
        for x in range(min_cell[0], max_cell[0] + 1):
            for y in range(min_cell[1], max_cell[1] + 1):
                if self.dimensions == 3:
                    for z in range(min_cell[2], max_cell[2] + 1):
                        cells_to_check.add((x, y, z))
                else:
                    cells_to_check.add((x, y))
                    
        # Check entities
        for cell in cells_to_check:
            for entity_id in self.grid_index.get(cell, set()):
                entity = self.entities[entity_id]
                
                # Type filter
                if entity_types and entity.entity_type not in entity_types:
                    continue
                    
                # Bounds check
                if (x_min <= entity.x <= x_max and 
                    y_min <= entity.y <= y_max and
                    (self.dimensions == 2 or z_min <= entity.z <= z_max)):
                    results.append(entity)
                    
        return results
    
    def query_nearest_k(self, x: float, y: float, z: float = 0, k: int = 5,
                       entity_types: Optional[List[str]] = None) -> List[SpatialEntity]:
        """Query k nearest entities."""
        center = SpatialEntity("query", "query", x, y, z)
        heap = []
        
        # Use type index if filtering by type
        if entity_types:
            candidates = set()
            for entity_type in entity_types:
                candidates.update(self.type_index.get(entity_type, set()))
        else:
            candidates = set(self.entities.keys())
            
        # Find k nearest
        for entity_id in candidates:
            entity = self.entities[entity_id]
            distance = entity.distance_to(center)
            
            if len(heap) < k:
                heapq.heappush(heap, (-distance, entity))
            elif distance < -heap[0][0]:
                heapq.heapreplace(heap, (-distance, entity))
                
        # Extract results
        results = [entity for _, entity in sorted(heap, key=lambda x: -x[0])]
        return results


class SpatialService(Service):
    """Service for spatial operations in KSI."""
    
    def __init__(self):
        super().__init__()
        self.spatial_indices: Dict[str, SpatialIndex] = {}
        self.movement_validators: Dict[str, Any] = {}  # Validator agents/functions
        
    @EventHandler("spatial:initialize")
    async def handle_spatial_initialize(self, event: Event) -> Dict:
        """Initialize a spatial environment.
        
        Event data:
        - environment_id: Unique identifier
        - dimensions: 2 or 3
        - bounds: Optional boundary limits
        - grid_size: Grid cell size for indexing
        """
        data = event.data
        env_id = data["environment_id"]
        
        self.spatial_indices[env_id] = SpatialIndex(
            dimensions=data.get("dimensions", 2),
            grid_size=data.get("grid_size", 10.0)
        )
        
        logger.info(f"Initialized spatial environment: {env_id}")
        return {"status": "initialized", "environment_id": env_id}
    
    @EventHandler("spatial:entity:add")
    async def handle_entity_add(self, event: Event) -> Dict:
        """Add entity to spatial environment.
        
        Event data:
        - environment_id: Which environment
        - entity_id: Unique entity ID
        - entity_type: Type of entity
        - position: {x, y, [z]}
        - properties: Optional entity properties
        """
        data = event.data
        env_id = data["environment_id"]
        
        if env_id not in self.spatial_indices:
            return {"error": f"Environment {env_id} not initialized"}
            
        entity = SpatialEntity(
            entity_id=data["entity_id"],
            entity_type=data["entity_type"],
            x=data["position"]["x"],
            y=data["position"]["y"],
            z=data["position"].get("z", 0),
            properties=data.get("properties", {})
        )
        
        self.spatial_indices[env_id].add_entity(entity)
        
        # Also update state system
        await self.emit_event("state:entity:update", {
            "type": f"spatial_{data['entity_type']}",
            "id": data["entity_id"],
            "changes": {
                "x": entity.x,
                "y": entity.y,
                "z": entity.z,
                "environment_id": env_id
            }
        })
        
        return {"status": "added", "entity_id": data["entity_id"]}
    
    @EventHandler("spatial:query")
    async def handle_spatial_query(self, event: Event) -> Dict:
        """Query entities spatially.
        
        Event data:
        - environment_id: Which environment
        - query_type: radius|rectangle|nearest_k|line_of_sight
        - reference_point: {x, y, [z]} or reference_entity
        - parameters: Query-specific parameters
        - batch: Optional list of queries to batch
        """
        data = event.data
        env_id = data["environment_id"]
        
        if env_id not in self.spatial_indices:
            return {"error": f"Environment {env_id} not found"}
            
        index = self.spatial_indices[env_id]
        
        # Handle batch queries
        if "batch" in data:
            results = []
            for query in data["batch"]:
                result = await self._execute_single_query(index, query)
                results.append(result)
            return {"results": results, "batch_size": len(results)}
            
        # Single query
        result = await self._execute_single_query(index, data)
        return result
    
    async def _execute_single_query(self, index: SpatialIndex, query_data: Dict) -> Dict:
        """Execute a single spatial query."""
        query_type = query_data["query_type"]
        
        # Get reference point
        if "reference_entity" in query_data:
            ref_entity = index.entities.get(query_data["reference_entity"])
            if not ref_entity:
                return {"error": "Reference entity not found"}
            x, y, z = ref_entity.x, ref_entity.y, ref_entity.z
        else:
            ref_point = query_data["reference_point"]
            x = ref_point["x"]
            y = ref_point["y"]
            z = ref_point.get("z", 0)
            
        params = query_data.get("parameters", {})
        
        # Execute query
        if query_type == "radius":
            entities = index.query_radius(
                x, y, z,
                radius=params.get("radius", 10),
                entity_types=params.get("entity_types"),
                max_results=params.get("max_results")
            )
            
        elif query_type == "rectangle":
            entities = index.query_rectangle(
                x - params.get("width", 10) / 2,
                y - params.get("height", 10) / 2,
                x + params.get("width", 10) / 2,
                y + params.get("height", 10) / 2,
                z - params.get("depth", 0) / 2,
                z + params.get("depth", 0) / 2,
                entity_types=params.get("entity_types")
            )
            
        elif query_type == "nearest_k":
            entities = index.query_nearest_k(
                x, y, z,
                k=params.get("k", 5),
                entity_types=params.get("entity_types")
            )
            
        elif query_type == "line_of_sight":
            entities = await self._check_line_of_sight(
                index, x, y, z,
                target_x=params["target_x"],
                target_y=params["target_y"],
                target_z=params.get("target_z", 0)
            )
        else:
            return {"error": f"Unknown query type: {query_type}"}
            
        # Format results
        return {
            "entities": [
                {
                    "entity_id": e.entity_id,
                    "entity_type": e.entity_type,
                    "position": {"x": e.x, "y": e.y, "z": e.z},
                    "distance": e.distance_to(SpatialEntity("ref", "ref", x, y, z))
                }
                for e in entities
            ],
            "count": len(entities)
        }
    
    @EventHandler("spatial:move")
    async def handle_spatial_move(self, event: Event) -> Dict:
        """Handle entity movement with validation.
        
        Event data:
        - environment_id: Which environment
        - entity_id: Entity to move
        - to: {x, y, [z]} target position
        - movement_type: walk|teleport|fly
        - validate_path: Whether to validate movement
        - validation_agent: Optional agent to perform validation
        """
        data = event.data
        env_id = data["environment_id"]
        
        if env_id not in self.spatial_indices:
            return {"error": f"Environment {env_id} not found"}
            
        index = self.spatial_indices[env_id]
        entity_id = data["entity_id"]
        
        if entity_id not in index.entities:
            return {"error": f"Entity {entity_id} not found"}
            
        entity = index.entities[entity_id]
        target = data["to"]
        target_x, target_y = target["x"], target["y"]
        target_z = target.get("z", 0)
        
        # Validate movement if requested
        if data.get("validate_path", False):
            validation_result = await self._validate_movement(
                env_id, entity, target_x, target_y, target_z,
                movement_type=data.get("movement_type", "walk"),
                validation_agent=data.get("validation_agent")
            )
            
            if not validation_result["valid"]:
                return {
                    "status": "blocked",
                    "reason": validation_result.get("reason", "Movement invalid"),
                    "actual_position": {"x": entity.x, "y": entity.y, "z": entity.z}
                }
                
        # Update position
        old_x, old_y, old_z = entity.x, entity.y, entity.z
        index.update_position(entity_id, target_x, target_y, target_z)
        
        # Emit movement event
        await self.emit_event("spatial:entity:moved", {
            "environment_id": env_id,
            "entity_id": entity_id,
            "from": {"x": old_x, "y": old_y, "z": old_z},
            "to": {"x": target_x, "y": target_y, "z": target_z},
            "movement_type": data.get("movement_type", "walk")
        })
        
        # Update state system
        await self.emit_event("state:entity:update", {
            "type": f"spatial_{entity.entity_type}",
            "id": entity_id,
            "changes": {"x": target_x, "y": target_y, "z": target_z}
        })
        
        return {
            "status": "moved",
            "entity_id": entity_id,
            "position": {"x": target_x, "y": target_y, "z": target_z}
        }
    
    async def _validate_movement(self, env_id: str, entity: SpatialEntity,
                                target_x: float, target_y: float, target_z: float,
                                movement_type: str, validation_agent: Optional[str]) -> Dict:
        """Validate movement using agent or rules."""
        
        # Use validation agent if specified
        if validation_agent:
            validation_prompt = f"""
            Validate movement request:
            - Entity: {entity.entity_id} (type: {entity.entity_type})
            - Current position: ({entity.x}, {entity.y}, {entity.z})
            - Target position: ({target_x}, {target_y}, {target_z})
            - Movement type: {movement_type}
            - Distance: {entity.distance_to(SpatialEntity('target', 'target', target_x, target_y, target_z)):.2f}
            
            Check for:
            1. Obstacles in path
            2. Movement speed limits
            3. Terrain restrictions
            4. Entity capabilities
            
            Respond with JSON: {{"valid": true/false, "reason": "explanation if invalid"}}
            """
            
            # Request validation from agent
            response = await self.emit_event("completion:async", {
                "agent_id": validation_agent,
                "prompt": validation_prompt,
                "extract_json": True
            })
            
            # Wait for response (simplified for POC)
            await asyncio.sleep(0.1)
            
            # In real implementation, would parse agent response
            return {"valid": True}  # Default for now
            
        # Basic rule-based validation
        distance = entity.distance_to(SpatialEntity("target", "target", target_x, target_y, target_z))
        
        # Check movement limits
        if movement_type == "walk" and distance > 10:
            return {"valid": False, "reason": "Walking distance too far"}
        elif movement_type == "fly" and distance > 50:
            return {"valid": False, "reason": "Flying distance too far"}
            
        # Check for collisions (simplified)
        index = self.spatial_indices[env_id]
        nearby = index.query_radius(target_x, target_y, target_z, radius=1)
        
        for other in nearby:
            if other.entity_id != entity.entity_id and other.properties.get("solid", False):
                return {"valid": False, "reason": f"Collision with {other.entity_id}"}
                
        return {"valid": True}
    
    @EventHandler("spatial:interact")
    async def handle_spatial_interact(self, event: Event) -> Dict:
        """Handle spatial interaction between entities.
        
        Event data:
        - environment_id: Which environment
        - actor_id: Acting entity
        - target_id: Target entity  
        - interaction_type: collect|exchange|attack|communicate|observe
        - range: Maximum interaction range
        - parameters: Interaction-specific parameters
        - require_consent: Whether target must consent
        """
        data = event.data
        env_id = data["environment_id"]
        
        if env_id not in self.spatial_indices:
            return {"error": f"Environment {env_id} not found"}
            
        index = self.spatial_indices[env_id]
        
        # Get entities
        actor = index.entities.get(data["actor_id"])
        target = index.entities.get(data["target_id"])
        
        if not actor or not target:
            return {"error": "Actor or target not found"}
            
        # Check range
        distance = actor.distance_to(target)
        max_range = data.get("range", 2.0)
        
        if distance > max_range:
            return {
                "status": "failed",
                "reason": f"Out of range (distance: {distance:.2f}, max: {max_range})"
            }
            
        # Check consent if required
        if data.get("require_consent", False):
            consent_result = await self._check_consent(
                actor_id=data["actor_id"],
                target_id=data["target_id"],
                interaction_type=data["interaction_type"],
                parameters=data.get("parameters", {})
            )
            
            if not consent_result["consented"]:
                return {
                    "status": "refused",
                    "reason": consent_result.get("reason", "Consent denied")
                }
                
        # Execute interaction based on type
        interaction_type = data["interaction_type"]
        params = data.get("parameters", {})
        
        if interaction_type == "collect":
            # Transfer resource from target to actor
            await self.emit_event("resource:transfer", {
                "from_entity": data["target_id"],
                "to_entity": data["actor_id"],
                "resource_type": params.get("resource_type", "generic"),
                "amount": params.get("amount", 1)
            })
            
        elif interaction_type == "exchange":
            # Bidirectional resource transfer
            await self.emit_event("resource:transfer", {
                "from_entity": data["actor_id"],
                "to_entity": data["target_id"],
                "resource_type": params.get("give_type"),
                "amount": params.get("give_amount")
            })
            await self.emit_event("resource:transfer", {
                "from_entity": data["target_id"],
                "to_entity": data["actor_id"],
                "resource_type": params.get("receive_type"),
                "amount": params.get("receive_amount")
            })
            
        elif interaction_type == "communicate":
            # Send message between entities
            await self.emit_event("communication:send", {
                "from": data["actor_id"],
                "to": data["target_id"],
                "message": params.get("message", "")
            })
            
        # Emit interaction event
        await self.emit_event("spatial:interaction:complete", {
            "environment_id": env_id,
            "actor_id": data["actor_id"],
            "target_id": data["target_id"],
            "interaction_type": interaction_type,
            "distance": distance,
            "success": True
        })
        
        return {
            "status": "success",
            "interaction_type": interaction_type,
            "distance": distance
        }
    
    async def _check_consent(self, actor_id: str, target_id: str,
                            interaction_type: str, parameters: Dict) -> Dict:
        """Check if target consents to interaction."""
        
        # Check capabilities/permissions
        permission_event = await self.emit_event("permission:check", {
            "actor": actor_id,
            "target": target_id,
            "action": f"spatial:{interaction_type}",
            "context": parameters
        })
        
        # In real implementation, would wait for and parse response
        # For now, simplified consent logic
        
        # Always allow collection from environment resources
        if target_id.startswith("resource_"):
            return {"consented": True}
            
        # Check if target has consent capability
        # This would query the actual capability system
        return {"consented": True}  # Default for POC
    
    async def _check_line_of_sight(self, index: SpatialIndex,
                                  x1: float, y1: float, z1: float,
                                  target_x: float, target_y: float, target_z: float) -> List[SpatialEntity]:
        """Check line of sight between two points."""
        # Simplified line of sight - just check if obstacles block
        # In production, would use proper raycasting
        
        entities_in_line = []
        
        # Get all entities between points
        min_x, max_x = min(x1, target_x), max(x1, target_x)
        min_y, max_y = min(y1, target_y), max(y1, target_y)
        min_z, max_z = min(z1, target_z), max(z1, target_z)
        
        candidates = index.query_rectangle(min_x, min_y, max_x, max_y, min_z, max_z)
        
        for entity in candidates:
            # Check if entity is actually on the line (simplified)
            # In production, would use proper line-point distance calculation
            entities_in_line.append(entity)
            
        return entities_in_line


if __name__ == "__main__":
    # Example usage
    async def test_spatial_service():
        service = SpatialService()
        
        # Initialize environment
        await service.handle_spatial_initialize(Event(
            event="spatial:initialize",
            data={"environment_id": "test_env", "dimensions": 2}
        ))
        
        # Add entities
        await service.handle_entity_add(Event(
            event="spatial:entity:add",
            data={
                "environment_id": "test_env",
                "entity_id": "agent_1",
                "entity_type": "agent",
                "position": {"x": 10, "y": 20}
            }
        ))
        
        # Query nearby
        result = await service.handle_spatial_query(Event(
            event="spatial:query",
            data={
                "environment_id": "test_env",
                "query_type": "radius",
                "reference_point": {"x": 15, "y": 25},
                "parameters": {"radius": 10}
            }
        ))
        
        print(f"Query result: {result}")
        
    asyncio.run(test_spatial_service())