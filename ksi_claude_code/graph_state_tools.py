"""
Graph state management tools leveraging KSI's graph database capabilities.

KSI's state system is a full-featured graph database with:
- Entity-Attribute-Value (EAV) model
- Directed relationships with metadata
- Graph traversal algorithms
- Temporal tracking
- Bulk operations
"""

from typing import List, Dict, Any, Optional, Tuple, Set
import json
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from .ksi_base_tool import KSIBaseTool


class RelationshipType(Enum):
    """Common relationship types in KSI"""
    SPAWNED = "spawned"
    OBSERVES = "observes"
    OWNS = "owns"
    DEPENDS_ON = "depends_on"
    COMMUNICATES_WITH = "communicates_with"
    PART_OF = "part_of"
    PRODUCES = "produces"
    CONSUMES = "consumes"
    TRIGGERS = "triggers"
    BLOCKS = "blocks"


@dataclass
class Entity:
    """Graph entity representation"""
    id: str
    type: str
    properties: Dict[str, Any]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Relationship:
    """Graph relationship representation"""
    id: str
    type: str
    from_entity: str
    to_entity: str
    properties: Dict[str, Any]
    created_at: Optional[datetime] = None


@dataclass
class GraphTraversal:
    """Result of a graph traversal"""
    entities: Dict[str, Entity]
    relationships: List[Relationship]
    paths: List[List[str]]  # Lists of entity IDs forming paths


class GraphStateTool(KSIBaseTool):
    """Advanced state management using KSI's graph database"""
    
    async def create_entity(
        self,
        entity_type: str,
        properties: Dict[str, Any],
        entity_id: Optional[str] = None
    ) -> Entity:
        """
        Create an entity in the graph.
        
        Args:
            entity_type: Type of entity (e.g., "agent", "task", "resource")
            properties: Entity properties
            entity_id: Optional custom ID
            
        Returns:
            Created entity
        """
        event_data = {
            "event": "state:entity:create",
            "data": {
                "type": entity_type,
                "properties": properties
            }
        }
        
        if entity_id:
            event_data["data"]["id"] = entity_id
        
        result = await self.send_event(event_data)
        
        return Entity(
            id=result["entity"]["id"],
            type=result["entity"]["type"],
            properties=result["entity"]["properties"],
            created_at=result["entity"].get("created_at"),
            updated_at=result["entity"].get("updated_at")
        )
    
    async def update_entity(
        self,
        entity_id: str,
        properties: Dict[str, Any],
        merge: bool = True
    ) -> Entity:
        """
        Update an entity's properties.
        
        Args:
            entity_id: Entity to update
            properties: New properties
            merge: If True, merge with existing; if False, replace
            
        Returns:
            Updated entity
        """
        result = await self.send_event({
            "event": "state:entity:update",
            "data": {
                "id": entity_id,
                "properties": properties,
                "merge": merge
            }
        })
        
        return Entity(
            id=result["entity"]["id"],
            type=result["entity"]["type"],
            properties=result["entity"]["properties"],
            updated_at=result["entity"].get("updated_at")
        )
    
    async def get_entity(
        self,
        entity_id: str,
        include_relationships: bool = False
    ) -> Optional[Entity]:
        """
        Get an entity by ID.
        
        Args:
            entity_id: Entity ID
            include_relationships: Include related entities
            
        Returns:
            Entity if found
        """
        event_data = {
            "event": "state:entity:get",
            "data": {
                "id": entity_id
            }
        }
        
        if include_relationships:
            event_data["data"]["include"] = ["relationships"]
        
        try:
            result = await self.send_event(event_data)
            
            if result.get("entity"):
                return Entity(
                    id=result["entity"]["id"],
                    type=result["entity"]["type"],
                    properties=result["entity"]["properties"],
                    created_at=result["entity"].get("created_at"),
                    updated_at=result["entity"].get("updated_at")
                )
        except:
            return None
    
    async def query_entities(
        self,
        entity_type: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        limit: int = 100
    ) -> List[Entity]:
        """
        Query entities by type and properties.
        
        Args:
            entity_type: Filter by type
            properties: Filter by properties (exact match)
            limit: Maximum results
            
        Returns:
            List of matching entities
        """
        filters = {}
        if entity_type:
            filters["type"] = entity_type
        if properties:
            filters["properties"] = properties
        
        result = await self.send_event({
            "event": "state:entity:list",
            "data": {
                "filters": filters,
                "limit": limit
            }
        })
        
        entities = []
        for e in result.get("entities", []):
            entities.append(Entity(
                id=e["id"],
                type=e["type"],
                properties=e["properties"],
                created_at=e.get("created_at"),
                updated_at=e.get("updated_at")
            ))
        
        return entities
    
    async def create_relationship(
        self,
        from_entity: str,
        to_entity: str,
        relationship_type: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> Relationship:
        """
        Create a relationship between entities.
        
        Args:
            from_entity: Source entity ID
            to_entity: Target entity ID
            relationship_type: Type of relationship
            properties: Optional relationship properties
            
        Returns:
            Created relationship
        """
        result = await self.send_event({
            "event": "state:relationship:create",
            "data": {
                "from": from_entity,
                "to": to_entity,
                "type": relationship_type,
                "properties": properties or {}
            }
        })
        
        return Relationship(
            id=result["relationship"]["id"],
            type=result["relationship"]["type"],
            from_entity=result["relationship"]["from"],
            to_entity=result["relationship"]["to"],
            properties=result["relationship"].get("properties", {}),
            created_at=result["relationship"].get("created_at")
        )
    
    async def get_relationships(
        self,
        entity_id: str,
        direction: str = "both",
        relationship_type: Optional[str] = None
    ) -> List[Relationship]:
        """
        Get relationships for an entity.
        
        Args:
            entity_id: Entity to query
            direction: "incoming", "outgoing", or "both"
            relationship_type: Filter by type
            
        Returns:
            List of relationships
        """
        filters = {}
        
        if direction in ["outgoing", "both"]:
            filters["from"] = entity_id
        if direction in ["incoming", "both"]:
            filters["to"] = entity_id
        if relationship_type:
            filters["type"] = relationship_type
        
        result = await self.send_event({
            "event": "state:relationship:list",
            "data": {
                "filters": filters
            }
        })
        
        relationships = []
        for r in result.get("relationships", []):
            relationships.append(Relationship(
                id=r["id"],
                type=r["type"],
                from_entity=r["from"],
                to_entity=r["to"],
                properties=r.get("properties", {}),
                created_at=r.get("created_at")
            ))
        
        return relationships
    
    async def traverse_graph(
        self,
        start_entity: str,
        max_depth: int = 3,
        direction: str = "outgoing",
        relationship_types: Optional[List[str]] = None,
        include_data: bool = True
    ) -> GraphTraversal:
        """
        Traverse the graph from a starting entity.
        
        Args:
            start_entity: Starting entity ID
            max_depth: Maximum traversal depth
            direction: "incoming", "outgoing", or "both"
            relationship_types: Filter by relationship types
            include_data: Include entity data in results
            
        Returns:
            Graph traversal results
        """
        event_data = {
            "event": "state:graph:traverse",
            "data": {
                "start_entity": start_entity,
                "max_depth": max_depth,
                "direction": direction,
                "include_data": include_data
            }
        }
        
        if relationship_types:
            event_data["data"]["relationship_types"] = relationship_types
        
        result = await self.send_event(event_data)
        
        # Parse entities
        entities = {}
        for e in result.get("entities", []):
            entities[e["id"]] = Entity(
                id=e["id"],
                type=e["type"],
                properties=e.get("properties", {}),
                created_at=e.get("created_at"),
                updated_at=e.get("updated_at")
            )
        
        # Parse relationships
        relationships = []
        for r in result.get("relationships", []):
            relationships.append(Relationship(
                id=r["id"],
                type=r["type"],
                from_entity=r["from"],
                to_entity=r["to"],
                properties=r.get("properties", {}),
                created_at=r.get("created_at")
            ))
        
        # Extract paths (simplified - would parse from traversal structure)
        paths = result.get("paths", [])
        
        return GraphTraversal(
            entities=entities,
            relationships=relationships,
            paths=paths
        )
    
    async def bulk_create_entities(
        self,
        entities: List[Dict[str, Any]]
    ) -> List[Entity]:
        """
        Create multiple entities atomically.
        
        Args:
            entities: List of entity definitions
            
        Returns:
            List of created entities
        """
        result = await self.send_event({
            "event": "state:entity:bulk_create",
            "data": {
                "entities": entities
            }
        })
        
        created = []
        for e in result.get("entities", []):
            created.append(Entity(
                id=e["id"],
                type=e["type"],
                properties=e["properties"],
                created_at=e.get("created_at")
            ))
        
        return created
    
    # Higher-level graph operations
    
    async def create_agent_hierarchy(
        self,
        coordinator_id: str,
        worker_ids: List[str]
    ) -> List[Relationship]:
        """
        Create a coordinator-worker hierarchy.
        
        Args:
            coordinator_id: Coordinator entity ID
            worker_ids: Worker entity IDs
            
        Returns:
            Created relationships
        """
        relationships = []
        
        for worker_id in worker_ids:
            rel = await self.create_relationship(
                from_entity=coordinator_id,
                to_entity=worker_id,
                relationship_type=RelationshipType.SPAWNED.value,
                properties={"role": "worker"}
            )
            relationships.append(rel)
        
        return relationships
    
    async def create_workflow_graph(
        self,
        workflow_name: str,
        stages: List[Tuple[str, str, Dict[str, Any]]]  # (id, name, properties)
    ) -> Tuple[Entity, List[Entity], List[Relationship]]:
        """
        Create a workflow as a graph.
        
        Args:
            workflow_name: Name of the workflow
            stages: List of (id, name, properties) tuples
            
        Returns:
            Workflow entity, stage entities, relationships
        """
        # Create workflow entity
        workflow = await self.create_entity(
            entity_type="workflow",
            properties={"name": workflow_name, "status": "created"}
        )
        
        # Create stage entities
        stage_entities = []
        for stage_id, stage_name, props in stages:
            stage = await self.create_entity(
                entity_type="workflow_stage",
                properties={
                    "name": stage_name,
                    "workflow_id": workflow.id,
                    **props
                },
                entity_id=stage_id
            )
            stage_entities.append(stage)
            
            # Link to workflow
            await self.create_relationship(
                from_entity=workflow.id,
                to_entity=stage.id,
                relationship_type=RelationshipType.PART_OF.value
            )
        
        # Create stage dependencies (linear for now)
        relationships = []
        for i in range(len(stage_entities) - 1):
            rel = await self.create_relationship(
                from_entity=stage_entities[i].id,
                to_entity=stage_entities[i + 1].id,
                relationship_type=RelationshipType.TRIGGERS.value,
                properties={"order": i}
            )
            relationships.append(rel)
        
        return workflow, stage_entities, relationships
    
    async def find_connected_components(
        self,
        entity_type: Optional[str] = None
    ) -> List[Set[str]]:
        """
        Find connected components in the graph.
        
        Args:
            entity_type: Filter by entity type
            
        Returns:
            List of sets of connected entity IDs
        """
        # Get all entities
        entities = await self.query_entities(entity_type=entity_type)
        
        # Build adjacency list
        adjacency = {e.id: set() for e in entities}
        
        for entity in entities:
            rels = await self.get_relationships(entity.id, direction="both")
            for rel in rels:
                if rel.from_entity in adjacency:
                    adjacency[rel.from_entity].add(rel.to_entity)
                if rel.to_entity in adjacency:
                    adjacency[rel.to_entity].add(rel.from_entity)
        
        # Find components using DFS
        visited = set()
        components = []
        
        def dfs(node: str, component: Set[str]):
            visited.add(node)
            component.add(node)
            for neighbor in adjacency.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, component)
        
        for entity_id in adjacency:
            if entity_id not in visited:
                component = set()
                dfs(entity_id, component)
                components.append(component)
        
        return components
    
    async def get_agent_network(
        self,
        root_agent_id: str
    ) -> Dict[str, Any]:
        """
        Get the full network of agents spawned from a root agent.
        
        Args:
            root_agent_id: Root agent entity ID
            
        Returns:
            Network structure with agents and relationships
        """
        traversal = await self.traverse_graph(
            start_entity=root_agent_id,
            max_depth=10,
            direction="outgoing",
            relationship_types=[RelationshipType.SPAWNED.value]
        )
        
        # Build network structure
        network = {
            "root": root_agent_id,
            "agents": {},
            "relationships": [],
            "levels": {}
        }
        
        # Organize by levels
        level_map = {root_agent_id: 0}
        queue = [(root_agent_id, 0)]
        
        while queue:
            current_id, level = queue.pop(0)
            
            if level not in network["levels"]:
                network["levels"][level] = []
            network["levels"][level].append(current_id)
            
            # Add agent info
            if current_id in traversal.entities:
                network["agents"][current_id] = traversal.entities[current_id]
            
            # Find children
            for rel in traversal.relationships:
                if rel.from_entity == current_id and rel.to_entity not in level_map:
                    level_map[rel.to_entity] = level + 1
                    queue.append((rel.to_entity, level + 1))
                    network["relationships"].append(rel)
        
        return network