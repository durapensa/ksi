#!/usr/bin/env python3
"""
Universal Relational State Management

A clean relational model for all KSI state, replacing the legacy key-value system.
Everything is an entity with properties and relationships.

Core concepts:
- Entities: Any object in the system (agents, sessions, configs, etc.)
- Properties: Attributes of entities stored as key-value pairs
- Relationships: Connections between entities (spawned_by, observes, owns, etc.)

All state operations go through a minimal set of event handlers.
"""

import asyncio
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Union

from ksi_daemon.event_system import event_handler
from ksi_common.config import config
from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import timestamp_utc, numeric_to_iso


logger = get_bound_logger("relational_state", version="2.0.0")


class RelationalStateManager:
    """Universal relational state manager using entity-property-relationship model."""
    
    def __init__(self):
        self.logger = logger
        self.db_path = str(config.db_path)
        self._init_database()
    
    def _init_database(self):
        """Initialize the relational database schema."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            # Core entities table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            
            # Properties table (EAV pattern)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS properties (
                    entity_id TEXT NOT NULL,
                    property TEXT NOT NULL,
                    value TEXT,
                    value_type TEXT DEFAULT 'string',
                    PRIMARY KEY (entity_id, property),
                    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE
                )
            """)
            
            # Relationships table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS relationships (
                    from_id TEXT NOT NULL,
                    to_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    metadata TEXT,
                    created_at REAL NOT NULL,
                    PRIMARY KEY (from_id, to_id, relation_type),
                    FOREIGN KEY (from_id) REFERENCES entities(id) ON DELETE CASCADE,
                    FOREIGN KEY (to_id) REFERENCES entities(id) ON DELETE CASCADE
                )
            """)
            
            # Indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_created ON entities(created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_properties_entity ON properties(entity_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_relationships_from ON relationships(from_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_relationships_to ON relationships(to_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_relationships_type ON relationships(relation_type)")
            
            conn.commit()
            
        self.logger.info(f"Relational state initialized at {self.db_path}")
    
    @contextmanager
    def _get_db(self):
        """Get database connection with proper cleanup."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _serialize_value(self, value: Any, value_type: str = None) -> Tuple[str, str]:
        """Serialize a value for storage."""
        if value is None:
            return (None, 'null')
        elif isinstance(value, (dict, list)):
            return (json.dumps(value), 'json')
        elif isinstance(value, bool):
            return (str(value).lower(), 'boolean')
        elif isinstance(value, (int, float)):
            return (str(value), 'number')
        else:
            return (str(value), value_type or 'string')
    
    def _deserialize_value(self, value: str, value_type: str) -> Any:
        """Deserialize a value from storage."""
        if value is None or value_type == 'null':
            return None
        elif value_type == 'json':
            return json.loads(value)
        elif value_type == 'boolean':
            return value.lower() == 'true'
        elif value_type == 'number':
            return float(value) if '.' in value else int(value)
        else:
            return value
    
    def create_entity(self, entity_id: str, entity_type: str, 
                     properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new entity with properties."""
        current_time = time.time()
        
        with self._get_db() as conn:
            # Create entity
            conn.execute(
                "INSERT INTO entities (id, type, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (entity_id, entity_type, current_time, current_time)
            )
            
            # Add properties if provided
            if properties:
                for prop, value in properties.items():
                    serialized, value_type = self._serialize_value(value)
                    conn.execute(
                        "INSERT INTO properties (entity_id, property, value, value_type) VALUES (?, ?, ?, ?)",
                        (entity_id, prop, serialized, value_type)
                    )
            
            conn.commit()
            
        self.logger.debug(f"Created entity {entity_id} of type {entity_type}")
        
        return {
            "id": entity_id,
            "type": entity_type,
            "created_at": current_time,
            "updated_at": current_time,
            "properties": properties or {}
        }
    
    def update_entity(self, entity_id: str, properties: Dict[str, Any]) -> bool:
        """Update entity properties."""
        current_time = time.time()
        
        with self._get_db() as conn:
            # Check entity exists
            cursor = conn.execute("SELECT 1 FROM entities WHERE id = ?", (entity_id,))
            if not cursor.fetchone():
                return False
            
            # Update timestamp
            conn.execute(
                "UPDATE entities SET updated_at = ? WHERE id = ?",
                (current_time, entity_id)
            )
            
            # Update properties
            for prop, value in properties.items():
                if value is None:
                    # Delete property
                    conn.execute(
                        "DELETE FROM properties WHERE entity_id = ? AND property = ?",
                        (entity_id, prop)
                    )
                else:
                    # Upsert property
                    serialized, value_type = self._serialize_value(value)
                    conn.execute(
                        "INSERT OR REPLACE INTO properties (entity_id, property, value, value_type) VALUES (?, ?, ?, ?)",
                        (entity_id, prop, serialized, value_type)
                    )
            
            conn.commit()
            
        self.logger.debug(f"Updated entity {entity_id}")
        return True
    
    def delete_entity(self, entity_id: str) -> bool:
        """Delete an entity and all its properties/relationships."""
        with self._get_db() as conn:
            cursor = conn.execute("DELETE FROM entities WHERE id = ?", (entity_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            
        if deleted:
            self.logger.debug(f"Deleted entity {entity_id}")
        return deleted
    
    def get_entity(self, entity_id: str, include: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """Get an entity with optional includes."""
        include = include or ['properties']
        
        with self._get_db() as conn:
            # Get entity
            cursor = conn.execute(
                "SELECT * FROM entities WHERE id = ?",
                (entity_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            result = {
                "id": row['id'],
                "type": row['type'],
                "created_at": row['created_at'],
                "created_at_iso": numeric_to_iso(row['created_at']),
                "updated_at": row['updated_at'],
                "updated_at_iso": numeric_to_iso(row['updated_at'])
            }
            
            # Include properties
            if 'properties' in include:
                props = {}
                cursor = conn.execute(
                    "SELECT property, value, value_type FROM properties WHERE entity_id = ?",
                    (entity_id,)
                )
                for prop_row in cursor.fetchall():
                    props[prop_row['property']] = self._deserialize_value(
                        prop_row['value'], prop_row['value_type']
                    )
                result['properties'] = props
            
            # Include relationships
            if 'relationships' in include:
                rels = {
                    'from': [],  # This entity points to others
                    'to': []     # Others point to this entity
                }
                
                # Outgoing relationships
                cursor = conn.execute(
                    "SELECT to_id, relation_type, metadata, created_at FROM relationships WHERE from_id = ?",
                    (entity_id,)
                )
                for rel_row in cursor.fetchall():
                    rel = {
                        "to": rel_row['to_id'],
                        "type": rel_row['relation_type'],
                        "created_at": rel_row['created_at'],
                        "created_at_iso": numeric_to_iso(rel_row['created_at'])
                    }
                    if rel_row['metadata']:
                        rel['metadata'] = json.loads(rel_row['metadata'])
                    rels['from'].append(rel)
                
                # Incoming relationships
                cursor = conn.execute(
                    "SELECT from_id, relation_type, metadata, created_at FROM relationships WHERE to_id = ?",
                    (entity_id,)
                )
                for rel_row in cursor.fetchall():
                    rel = {
                        "from": rel_row['from_id'],
                        "type": rel_row['relation_type'],
                        "created_at": rel_row['created_at'],
                        "created_at_iso": numeric_to_iso(rel_row['created_at'])
                    }
                    if rel_row['metadata']:
                        rel['metadata'] = json.loads(rel_row['metadata'])
                    rels['to'].append(rel)
                
                result['relationships'] = rels
            
            return result
    
    def query_entities(self, entity_type: Optional[str] = None,
                      where: Optional[Dict[str, Any]] = None,
                      include: Optional[List[str]] = None,
                      order_by: Optional[str] = None,
                      limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Query entities with filters."""
        include = include or ['properties']
        
        with self._get_db() as conn:
            # Build query
            query = "SELECT DISTINCT e.* FROM entities e"
            conditions = []
            params = []
            
            # Join properties if filtering by them
            if where:
                query += " LEFT JOIN properties p ON e.id = p.entity_id"
            
            # Add type filter
            if entity_type:
                conditions.append("e.type = ?")
                params.append(entity_type)
            
            # Add property filters
            if where:
                for prop, value in where.items():
                    conditions.append("(p.property = ? AND p.value = ?)")
                    serialized, _ = self._serialize_value(value)
                    params.extend([prop, serialized])
            
            # Apply conditions
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            # Add ordering
            if order_by:
                query += f" ORDER BY e.{order_by}"
            else:
                query += " ORDER BY e.created_at DESC"
            
            # Add limit
            if limit:
                query += f" LIMIT {limit}"
            
            # Execute query
            cursor = conn.execute(query, params)
            
            # Build results
            results = []
            for row in cursor.fetchall():
                entity = self.get_entity(row['id'], include=include)
                if entity:
                    results.append(entity)
            
            return results
    
    def create_relationship(self, from_id: str, to_id: str, relation_type: str,
                          metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Create a relationship between entities."""
        current_time = time.time()
        
        with self._get_db() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO relationships (from_id, to_id, relation_type, metadata, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (from_id, to_id, relation_type, json.dumps(metadata) if metadata else None, current_time)
                )
                conn.commit()
                
                self.logger.debug(f"Created relationship {from_id} -{relation_type}-> {to_id}")
                return True
                
            except sqlite3.IntegrityError:
                self.logger.warning(f"Relationship already exists or entities not found")
                return False
    
    def delete_relationship(self, from_id: str, to_id: str, relation_type: str) -> bool:
        """Delete a specific relationship."""
        with self._get_db() as conn:
            cursor = conn.execute(
                "DELETE FROM relationships WHERE from_id = ? AND to_id = ? AND relation_type = ?",
                (from_id, to_id, relation_type)
            )
            conn.commit()
            deleted = cursor.rowcount > 0
            
        if deleted:
            self.logger.debug(f"Deleted relationship {from_id} -{relation_type}-> {to_id}")
        return deleted
    
    def query_relationships(self, from_id: Optional[str] = None,
                          to_id: Optional[str] = None,
                          relation_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query relationships with filters."""
        with self._get_db() as conn:
            # Build query
            query = "SELECT * FROM relationships WHERE 1=1"
            params = []
            
            if from_id:
                query += " AND from_id = ?"
                params.append(from_id)
            
            if to_id:
                query += " AND to_id = ?"
                params.append(to_id)
            
            if relation_type:
                query += " AND relation_type = ?"
                params.append(relation_type)
            
            query += " ORDER BY created_at DESC"
            
            # Execute query
            cursor = conn.execute(query, params)
            
            # Build results
            results = []
            for row in cursor.fetchall():
                rel = {
                    "from": row['from_id'],
                    "to": row['to_id'],
                    "type": row['relation_type'],
                    "created_at": row['created_at'],
                    "created_at_iso": numeric_to_iso(row['created_at'])
                }
                if row['metadata']:
                    rel['metadata'] = json.loads(row['metadata'])
                results.append(rel)
            
            return results


# Global state manager instance
state_manager: Optional[RelationalStateManager] = None


def get_state_manager() -> RelationalStateManager:
    """Get the global state manager instance."""
    if state_manager is None:
        raise RuntimeError("State manager not initialized")
    return state_manager


def initialize_state() -> RelationalStateManager:
    """Initialize the global state manager."""
    global state_manager
    if state_manager is None:
        state_manager = RelationalStateManager()
        logger.info("Relational state manager initialized")
    return state_manager


# Event Handlers - Clean relational API

@event_handler("system:context")
async def handle_context(context: Dict[str, Any]) -> None:
    """Receive infrastructure context."""
    if state_manager:
        logger.info("Relational state manager connected to event system")
    else:
        logger.error("State manager not available")


@event_handler("state:entity:create")
async def handle_entity_create(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new entity.
    
    Args:
        id (str): Entity ID (optional, will generate if not provided)
        type (str): Entity type (required)
        properties (dict): Initial properties (optional)
    
    Returns:
        The created entity
    
    Example:
        {
            "type": "agent",
            "id": "agent_123",  # Optional
            "properties": {
                "status": "active",
                "model": "sonnet"
            }
        }
    """
    if not state_manager:
        return {"error": "State infrastructure not available"}
    
    entity_type = data.get("type")
    if not entity_type:
        return {"error": "Entity type is required"}
    
    entity_id = data.get("id") or f"{entity_type}_{uuid.uuid4().hex[:8]}"
    properties = data.get("properties", {})
    
    try:
        entity = state_manager.create_entity(entity_id, entity_type, properties)
        return entity
    except Exception as e:
        logger.error(f"Error creating entity: {e}")
        return {"error": str(e)}


@event_handler("state:entity:update")
async def handle_entity_update(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update entity properties.
    
    Args:
        id (str): Entity ID (required)
        properties (dict): Properties to update (set to None to delete)
    
    Returns:
        Success status
    
    Example:
        {
            "id": "agent_123",
            "properties": {
                "status": "terminated",
                "old_property": None  # This deletes the property
            }
        }
    """
    if not state_manager:
        return {"error": "State infrastructure not available"}
    
    entity_id = data.get("id")
    if not entity_id:
        return {"error": "Entity ID is required"}
    
    properties = data.get("properties", {})
    
    try:
        success = state_manager.update_entity(entity_id, properties)
        if success:
            return {"status": "updated", "id": entity_id}
        else:
            return {"error": "Entity not found", "id": entity_id}
    except Exception as e:
        logger.error(f"Error updating entity: {e}")
        return {"error": str(e)}


@event_handler("state:entity:delete")
async def handle_entity_delete(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Delete an entity.
    
    Args:
        id (str): Entity ID (required)
    
    Returns:
        Success status
    """
    if not state_manager:
        return {"error": "State infrastructure not available"}
    
    entity_id = data.get("id")
    if not entity_id:
        return {"error": "Entity ID is required"}
    
    try:
        success = state_manager.delete_entity(entity_id)
        if success:
            return {"status": "deleted", "id": entity_id}
        else:
            return {"error": "Entity not found", "id": entity_id}
    except Exception as e:
        logger.error(f"Error deleting entity: {e}")
        return {"error": str(e)}


@event_handler("state:entity:get")
async def handle_entity_get(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get an entity.
    
    Args:
        id (str): Entity ID (required)
        include (list): What to include - properties, relationships (default: ['properties'])
    
    Returns:
        The entity or None
    
    Example:
        {
            "id": "agent_123",
            "include": ["properties", "relationships"]
        }
    """
    if not state_manager:
        return {"error": "State infrastructure not available"}
    
    entity_id = data.get("id")
    if not entity_id:
        return {"error": "Entity ID is required"}
    
    include = data.get("include", ["properties"])
    
    try:
        entity = state_manager.get_entity(entity_id, include=include)
        if entity:
            return entity
        else:
            return {"error": "Entity not found", "id": entity_id}
    except Exception as e:
        logger.error(f"Error getting entity: {e}")
        return {"error": str(e)}


@event_handler("state:entity:query")
async def handle_entity_query(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Query entities.
    
    Args:
        type (str): Filter by entity type (optional)
        where (dict): Filter by properties (optional)
        include (list): What to include (default: ['properties'])
        order_by (str): Order by field (default: created_at DESC)
        limit (int): Limit results (optional)
    
    Returns:
        List of matching entities
    
    Example:
        {
            "type": "agent",
            "where": {"status": "active"},
            "include": ["properties", "relationships"],
            "limit": 10
        }
    """
    if not state_manager:
        return {"error": "State infrastructure not available"}
    
    try:
        entities = state_manager.query_entities(
            entity_type=data.get("type"),
            where=data.get("where"),
            include=data.get("include", ["properties"]),
            order_by=data.get("order_by"),
            limit=data.get("limit")
        )
        return {
            "entities": entities,
            "count": len(entities)
        }
    except Exception as e:
        logger.error(f"Error querying entities: {e}")
        return {"error": str(e)}


@event_handler("state:relationship:create")
async def handle_relationship_create(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a relationship between entities.
    
    Args:
        from (str): Source entity ID (required)
        to (str): Target entity ID (required)
        type (str): Relationship type (required)
        metadata (dict): Additional metadata (optional)
    
    Returns:
        Success status
    
    Example:
        {
            "from": "originator_1",
            "to": "construct_1",
            "type": "spawned",
            "metadata": {"purpose": "observer"}
        }
    """
    if not state_manager:
        return {"error": "State infrastructure not available"}
    
    from_id = data.get("from")
    to_id = data.get("to")
    relation_type = data.get("type")
    
    if not all([from_id, to_id, relation_type]):
        return {"error": "from, to, and type are required"}
    
    metadata = data.get("metadata")
    
    try:
        success = state_manager.create_relationship(from_id, to_id, relation_type, metadata)
        if success:
            return {
                "status": "created",
                "from": from_id,
                "to": to_id,
                "type": relation_type
            }
        else:
            return {"error": "Failed to create relationship (already exists or entities not found)"}
    except Exception as e:
        logger.error(f"Error creating relationship: {e}")
        return {"error": str(e)}


@event_handler("state:relationship:delete")
async def handle_relationship_delete(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Delete a relationship.
    
    Args:
        from (str): Source entity ID (required)
        to (str): Target entity ID (required)
        type (str): Relationship type (required)
    
    Returns:
        Success status
    """
    if not state_manager:
        return {"error": "State infrastructure not available"}
    
    from_id = data.get("from")
    to_id = data.get("to")
    relation_type = data.get("type")
    
    if not all([from_id, to_id, relation_type]):
        return {"error": "from, to, and type are required"}
    
    try:
        success = state_manager.delete_relationship(from_id, to_id, relation_type)
        if success:
            return {
                "status": "deleted",
                "from": from_id,
                "to": to_id,
                "type": relation_type
            }
        else:
            return {"error": "Relationship not found"}
    except Exception as e:
        logger.error(f"Error deleting relationship: {e}")
        return {"error": str(e)}


@event_handler("state:relationship:query")
async def handle_relationship_query(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Query relationships.
    
    Args:
        from (str): Filter by source entity (optional)
        to (str): Filter by target entity (optional)
        type (str): Filter by relationship type (optional)
    
    Returns:
        List of matching relationships
    
    Example:
        {
            "from": "originator_1",
            "type": "spawned"
        }
    """
    if not state_manager:
        return {"error": "State infrastructure not available"}
    
    try:
        relationships = state_manager.query_relationships(
            from_id=data.get("from"),
            to_id=data.get("to"),
            relation_type=data.get("type")
        )
        return {
            "relationships": relationships,
            "count": len(relationships)
        }
    except Exception as e:
        logger.error(f"Error querying relationships: {e}")
        return {"error": str(e)}


@event_handler("state:graph:traverse")
async def handle_graph_traverse(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Traverse the graph from an entity following relationships.
    
    Args:
        from (str): Starting entity ID (required)
        direction (str): "outgoing", "incoming", or "both" (default: "outgoing")
        types (list): Filter by relationship types (optional)
        depth (int): Maximum traversal depth (default: 1)
        include_entities (bool): Include full entity data (default: False)
    
    Returns:
        Graph traversal results with entities and relationships
    
    Example:
        {
            "from": "originator_1",
            "direction": "outgoing",
            "types": ["spawned"],
            "depth": 2,
            "include_entities": true
        }
    """
    if not state_manager:
        return {"error": "State infrastructure not available"}
    
    from_id = data.get("from")
    if not from_id:
        return {"error": "from entity ID is required"}
    
    direction = data.get("direction", "outgoing")
    rel_types = data.get("types", [])
    depth = min(data.get("depth", 1), 5)  # Limit depth to prevent runaway queries
    include_entities = data.get("include_entities", False)
    
    try:
        visited = set()
        result = {
            "root": from_id,
            "nodes": {},
            "edges": []
        }
        
        # Breadth-first traversal
        queue = [(from_id, 0)]
        
        while queue:
            current_id, current_depth = queue.pop(0)
            
            if current_id in visited or current_depth > depth:
                continue
                
            visited.add(current_id)
            
            # Get entity data if requested
            if include_entities:
                entity = state_manager.get_entity(current_id, include=["properties"])
                if entity:
                    result["nodes"][current_id] = entity
            else:
                result["nodes"][current_id] = {"id": current_id}
            
            if current_depth < depth:
                # Get relationships based on direction
                if direction in ["outgoing", "both"]:
                    rels = state_manager.query_relationships(from_id=current_id)
                    for rel in rels:
                        if not rel_types or rel["type"] in rel_types:
                            result["edges"].append(rel)
                            queue.append((rel["to"], current_depth + 1))
                
                if direction in ["incoming", "both"]:
                    rels = state_manager.query_relationships(to_id=current_id)
                    for rel in rels:
                        if not rel_types or rel["type"] in rel_types:
                            result["edges"].append(rel)
                            queue.append((rel["from"], current_depth + 1))
        
        result["node_count"] = len(result["nodes"])
        result["edge_count"] = len(result["edges"])
        
        return result
        
    except Exception as e:
        logger.error(f"Error traversing graph: {e}")
        return {"error": str(e)}


@event_handler("state:entity:bulk_create")
async def handle_entity_bulk_create(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create multiple entities in a single operation.
    
    Args:
        entities (list): List of entity definitions
    
    Returns:
        Results for each entity creation
    
    Example:
        {
            "entities": [
                {"type": "agent", "id": "agent_1", "properties": {...}},
                {"type": "agent", "id": "agent_2", "properties": {...}}
            ]
        }
    """
    if not state_manager:
        return {"error": "State infrastructure not available"}
    
    entities = data.get("entities", [])
    if not entities:
        return {"error": "entities list is required"}
    
    results = []
    success_count = 0
    
    for entity_data in entities:
        try:
            entity_type = entity_data.get("type")
            if not entity_type:
                results.append({"error": "Entity type is required"})
                continue
            
            entity_id = entity_data.get("id") or f"{entity_type}_{uuid.uuid4().hex[:8]}"
            properties = entity_data.get("properties", {})
            
            entity = state_manager.create_entity(entity_id, entity_type, properties)
            results.append(entity)
            success_count += 1
            
        except Exception as e:
            results.append({"error": str(e)})
    
    return {
        "results": results,
        "total": len(entities),
        "success": success_count,
        "failed": len(entities) - success_count
    }


@event_handler("state:aggregate:count")
async def handle_aggregate_count(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Count entities or relationships with grouping.
    
    Args:
        target (str): "entities" or "relationships" (required)
        group_by (str): Field to group by (optional)
        where (dict): Filter conditions (optional)
    
    Returns:
        Count results, optionally grouped
    
    Example:
        {
            "target": "entities",
            "group_by": "type",
            "where": {"status": "active"}
        }
    """
    if not state_manager:
        return {"error": "State infrastructure not available"}
    
    target = data.get("target")
    if target not in ["entities", "relationships"]:
        return {"error": "target must be 'entities' or 'relationships'"}
    
    group_by = data.get("group_by")
    where = data.get("where", {})
    
    try:
        with state_manager._get_db() as conn:
            if target == "entities":
                if group_by == "type":
                    query = "SELECT type, COUNT(*) as count FROM entities"
                    if where:
                        # Simple type filter for now
                        if "type" in where:
                            query += f" WHERE type = '{where['type']}'"
                    query += " GROUP BY type"
                else:
                    query = "SELECT COUNT(*) as total FROM entities"
                    
                cursor = conn.execute(query)
                
                if group_by:
                    results = {}
                    for row in cursor.fetchall():
                        results[row[0]] = row[1]
                    return {"counts": results, "grouped_by": group_by}
                else:
                    return {"total": cursor.fetchone()[0]}
                    
            else:  # relationships
                if group_by == "type":
                    query = "SELECT relation_type, COUNT(*) as count FROM relationships GROUP BY relation_type"
                else:
                    query = "SELECT COUNT(*) as total FROM relationships"
                    
                cursor = conn.execute(query)
                
                if group_by:
                    results = {}
                    for row in cursor.fetchall():
                        results[row[0]] = row[1]
                    return {"counts": results, "grouped_by": "relation_type"}
                else:
                    return {"total": cursor.fetchone()[0]}
                    
    except Exception as e:
        logger.error(f"Error in aggregate count: {e}")
        return {"error": str(e)}