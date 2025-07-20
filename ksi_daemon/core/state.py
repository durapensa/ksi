#!/usr/bin/env python3
"""
Universal Graph Database State Management

A clean graph database model for all KSI state, replacing the legacy key-value system.
Everything is an entity with properties and relationships.

Core concepts:
- Entities: Any object in the system (agents, sessions, configs, etc.)
- Properties: Attributes of entities stored as key-value pairs
- Relationships: Connections between entities (spawned_by, observes, owns, etc.)

All state operations go through a minimal set of event handlers.
"""

import asyncio
import json
import aiosqlite
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Union, TypedDict, Literal
from typing_extensions import NotRequired, Required

from ksi_daemon.event_system import event_handler, shutdown_handler, get_router
from ksi_common.config import config
from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import timestamp_utc, numeric_to_iso
from ksi_common.event_parser import extract_system_handler_data
from ksi_common.event_response_builder import event_response_builder, success_response, error_response, list_response


logger = get_bound_logger("graph_state", version="2.0.0")


class GraphStateManager:
    """Universal graph database state manager using entity-property-relationship model."""
    
    def __init__(self):
        self.logger = logger
        self.db_path = str(config.db_path)
        # Initialization is now async - call from startup
        self._initialized = False
    
    async def _init_database(self):
        """Initialize the graph database schema."""
        if self._initialized:
            return
            
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        async with aiosqlite.connect(self.db_path) as conn:
            # Enable WAL mode for better concurrency
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA synchronous=NORMAL")
            
            # Core entities table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            
            # Properties table (EAV pattern)
            await conn.execute("""
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
            await conn.execute("""
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
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_created ON entities(created_at DESC)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_properties_entity ON properties(entity_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_relationships_from ON relationships(from_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_relationships_to ON relationships(to_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_relationships_type ON relationships(relation_type)")
            
            await conn.commit()
            
        self._initialized = True
        self.logger.info(f"Graph state initialized at {self.db_path}")
    
    @asynccontextmanager
    async def _get_db(self):
        """Get database connection with proper cleanup."""
        await self._init_database()  # Ensure initialized
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        try:
            yield conn
        finally:
            await conn.close()
    
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
    
    async def create_entity(self, entity_id: str, entity_type: str, 
                           properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new entity with properties."""
        current_time = time.time()
        
        async with self._get_db() as conn:
            # Create entity
            await conn.execute(
                "INSERT INTO entities (id, type, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (entity_id, entity_type, current_time, current_time)
            )
            
            # Add properties if provided
            if properties:
                for prop, value in properties.items():
                    serialized, value_type = self._serialize_value(value)
                    await conn.execute(
                        "INSERT INTO properties (entity_id, property, value, value_type) VALUES (?, ?, ?, ?)",
                        (entity_id, prop, serialized, value_type)
                    )
            
            await conn.commit()
            
        self.logger.debug(f"Created entity {entity_id} of type {entity_type}")
        
        return {
            "id": entity_id,
            "type": entity_type,
            "created_at": current_time,
            "updated_at": current_time,
            "properties": properties or {}
        }
    
    async def update_entity(self, entity_id: str, properties: Dict[str, Any]) -> bool:
        """Update entity properties."""
        current_time = time.time()
        
        async with self._get_db() as conn:
            # Check entity exists
            async with conn.execute("SELECT 1 FROM entities WHERE id = ?", (entity_id,)) as cursor:
                if not await cursor.fetchone():
                    return False
            
            # Update timestamp
            await conn.execute(
                "UPDATE entities SET updated_at = ? WHERE id = ?",
                (current_time, entity_id)
            )
            
            # Update properties
            for prop, value in properties.items():
                if value is None:
                    # Delete property
                    await conn.execute(
                        "DELETE FROM properties WHERE entity_id = ? AND property = ?",
                        (entity_id, prop)
                    )
                else:
                    # Upsert property
                    serialized, value_type = self._serialize_value(value)
                    await conn.execute(
                        "INSERT OR REPLACE INTO properties (entity_id, property, value, value_type) VALUES (?, ?, ?, ?)",
                        (entity_id, prop, serialized, value_type)
                    )
            
            await conn.commit()
            
        self.logger.debug(f"Updated entity {entity_id}")
        return True
    
    async def delete_entity(self, entity_id: str) -> bool:
        """Delete an entity and all its properties/relationships."""
        async with self._get_db() as conn:
            cursor = await conn.execute("DELETE FROM entities WHERE id = ?", (entity_id,))
            await conn.commit()
            deleted = cursor.rowcount > 0
            
        if deleted:
            self.logger.debug(f"Deleted entity {entity_id}")
        return deleted
    
    async def get_entity(self, entity_id: str, include: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """Get an entity with optional includes."""
        include = include or ['properties']
        
        async with self._get_db() as conn:
            # Get entity
            async with conn.execute(
                "SELECT * FROM entities WHERE id = ?",
                (entity_id,)
            ) as cursor:
                row = await cursor.fetchone()
            
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
                async with conn.execute(
                    "SELECT property, value, value_type FROM properties WHERE entity_id = ?",
                    (entity_id,)
                ) as cursor:
                    async for prop_row in cursor:
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
                async with conn.execute(
                    "SELECT to_id, relation_type, metadata, created_at FROM relationships WHERE from_id = ?",
                    (entity_id,)
                ) as cursor:
                    async for rel_row in cursor:
                        rel = {
                            "to_id": rel_row['to_id'],
                            "relation_type": rel_row['relation_type'],
                            "created_at": rel_row['created_at'],
                            "created_at_iso": numeric_to_iso(rel_row['created_at'])
                        }
                        if rel_row['metadata']:
                            rel['metadata'] = json.loads(rel_row['metadata'])
                        rels['from'].append(rel)
                
                # Incoming relationships
                async with conn.execute(
                    "SELECT from_id, relation_type, metadata, created_at FROM relationships WHERE to_id = ?",
                    (entity_id,)
                ) as cursor:
                    async for rel_row in cursor:
                        rel = {
                            "from_id": rel_row['from_id'],
                            "relation_type": rel_row['relation_type'],
                            "created_at": rel_row['created_at'],
                            "created_at_iso": numeric_to_iso(rel_row['created_at'])
                        }
                        if rel_row['metadata']:
                            rel['metadata'] = json.loads(rel_row['metadata'])
                        rels['to'].append(rel)
                
                result['relationships'] = rels
            
            return result
    
    async def query_entities(self, entity_type: Optional[str] = None,
                      where: Optional[Dict[str, Any]] = None,
                      include: Optional[List[str]] = None,
                      order_by: Optional[str] = None,
                      limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Query entities with filters."""
        include = include or ['properties']
        
        try:
            # Add timeout protection
            return await asyncio.wait_for(
                self._query_entities_impl(entity_type, where, include, order_by, limit), 
                timeout=10.0
            )
        except asyncio.TimeoutError:
            self.logger.error(f"Query entities timed out after 10 seconds - type:{entity_type}, where:{where}")
            raise Exception("Query timed out - check query complexity and database performance")
    
    async def _query_entities_impl(self, entity_type: Optional[str] = None,
                           where: Optional[Dict[str, Any]] = None,
                           include: Optional[List[str]] = None,
                           order_by: Optional[str] = None,
                           limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Internal implementation of query_entities using JSON aggregation for optimal performance."""
        include = include or ['properties']
        
        async with self._get_db() as conn:
            # Build optimized single query using JSON aggregation
            base_query = """
            SELECT 
                e.id as entity_id,
                e.type,
                e.created_at,
                e.updated_at
            """
            
            # Add JSON aggregation for properties if requested
            if 'properties' in include:
                base_query += """,
                json_group_object(
                    p.property, 
                    json_object('value', p.value, 'type', p.value_type)
                ) FILTER (WHERE p.property IS NOT NULL) as properties_json"""
            
            # Add JSON aggregation for relationships if requested
            if 'relationships' in include:
                base_query += """,
                json_group_array(
                    json_object(
                        'relation_type', r.relation_type,
                        'to_id', r.to_id,
                        'metadata', r.metadata,
                        'created_at', r.created_at
                    )
                ) FILTER (WHERE r.relation_type IS NOT NULL) as relationships_json"""
            
            # FROM clause with necessary joins
            from_clause = "\nFROM entities e"
            if 'properties' in include or where:
                from_clause += "\nLEFT JOIN properties p ON e.id = p.entity_id"
            if 'relationships' in include:
                from_clause += "\nLEFT JOIN relationships r ON e.id = r.from_id"
            
            query = base_query + from_clause
            
            # Build WHERE conditions
            conditions = []
            params = []
            
            if entity_type:
                conditions.append("e.type = ?")
                params.append(entity_type)
            
            # For property filters, we need a subquery approach
            if where:
                for prop, value in where.items():
                    # Create a subquery for each property filter
                    conditions.append("""
                        e.id IN (
                            SELECT entity_id FROM properties 
                            WHERE property = ? AND value = ?
                        )
                    """)
                    serialized, _ = self._serialize_value(value)
                    params.extend([prop, serialized])
            
            if conditions:
                query += "\nWHERE " + " AND ".join(conditions)
            
            # GROUP BY for aggregation
            query += "\nGROUP BY e.id, e.type, e.created_at, e.updated_at"
            
            # Add ordering
            if order_by:
                query += f"\nORDER BY e.{order_by}"
            else:
                query += "\nORDER BY e.created_at DESC"
            
            # Add limit
            if limit:
                query += f"\nLIMIT {limit}"
            
            self.logger.debug(f"Executing optimized query: {query} with params: {params}")
            
            # Execute the single optimized query
            try:
                cursor = await asyncio.wait_for(conn.execute(query, params), timeout=5.0)
                results = []
                
                async with cursor:
                    async for row in cursor:
                        # Build entity dict from row
                        entity = {
                            'entity_id': row['entity_id'],  # This is e.id from the query
                            'entity_type': row['type'],
                            'created_at': row['created_at'],
                            'updated_at': row['updated_at']
                        }
                        
                        # Parse JSON properties if included
                        if 'properties' in include:
                            properties_json = row['properties_json'] if 'properties_json' in row.keys() else None
                            if properties_json:
                                try:
                                    props_data = json.loads(properties_json)
                                    entity['properties'] = {}
                                    for prop_name, prop_info in props_data.items():
                                        entity['properties'][prop_name] = self._deserialize_value(
                                            prop_info['value'], 
                                            prop_info['type']
                                        )
                                except json.JSONDecodeError:
                                    self.logger.warning(f"Failed to parse properties JSON for entity {entity['entity_id']}")
                                    entity['properties'] = {}
                            else:
                                entity['properties'] = {}
                        
                        # Parse JSON relationships if included
                        if 'relationships' in include:
                            relationships_json = row['relationships_json'] if 'relationships_json' in row.keys() else None
                            if relationships_json:
                                try:
                                    rels_data = json.loads(relationships_json)
                                    entity['relationships'] = []
                                    for rel in rels_data:
                                        # Deserialize metadata if it's JSON
                                        if rel.get('metadata'):
                                            try:
                                                rel['metadata'] = json.loads(rel['metadata'])
                                            except:
                                                pass  # Keep as string if not valid JSON
                                        entity['relationships'].append(rel)
                                except json.JSONDecodeError:
                                    self.logger.warning(f"Failed to parse relationships JSON for entity {entity['entity_id']}")
                                    entity['relationships'] = []
                            else:
                                entity['relationships'] = []
                        
                        results.append(entity)
                
                self.logger.info(f"Query returned {len(results)} entities in single query (was N+1 before)")
                return results
                
            except asyncio.TimeoutError:
                self.logger.error(f"Database query timed out: {query}")
                raise Exception("Database query timed out - query may be too complex")
            except Exception as e:
                self.logger.error(f"Database error executing query: {e}")
                raise Exception(f"Database error: {str(e)}")
    
    async def create_relationship(self, from_id: str, to_id: str, relation_type: str,
                          metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Create a relationship between entities."""
        current_time = time.time()
        
        async with self._get_db() as conn:
            try:
                await conn.execute(
                    """
                    INSERT INTO relationships (from_id, to_id, relation_type, metadata, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (from_id, to_id, relation_type, json.dumps(metadata) if metadata else None, current_time)
                )
                await conn.commit()
                
                self.logger.debug(f"Created relationship {from_id} -{relation_type}-> {to_id}")
                return True
                
            except aiosqlite.IntegrityError:
                self.logger.warning(f"Relationship already exists or entities not found")
                return False
    
    async def delete_relationship(self, from_id: str, to_id: str, relation_type: str) -> bool:
        """Delete a specific relationship."""
        async with self._get_db() as conn:
            cursor = await conn.execute(
                "DELETE FROM relationships WHERE from_id = ? AND to_id = ? AND relation_type = ?",
                (from_id, to_id, relation_type)
            )
            await conn.commit()
            deleted = cursor.rowcount > 0
            
        if deleted:
            self.logger.debug(f"Deleted relationship {from_id} -{relation_type}-> {to_id}")
        return deleted
    
    async def query_relationships(self, from_id: Optional[str] = None,
                          to_id: Optional[str] = None,
                          relation_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query relationships with filters."""
        async with self._get_db() as conn:
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
            async with conn.execute(query, params) as cursor:
                
                # Build results
                results = []
                async for row in cursor:
                    rel = {
                        "from_id": row['from_id'],
                        "to_id": row['to_id'],
                        "relation_type": row['relation_type'],
                        "created_at": row['created_at'],
                        "created_at_iso": numeric_to_iso(row['created_at'])
                    }
                    if row['metadata']:
                        rel['metadata'] = json.loads(row['metadata'])
                    results.append(rel)
            
            return results


# Global state manager instance
state_manager: Optional[GraphStateManager] = None


def get_state_manager() -> GraphStateManager:
    """Get the global state manager instance."""
    if state_manager is None:
        raise RuntimeError("State manager not initialized")
    return state_manager


def initialize_state() -> GraphStateManager:
    """Initialize the global state manager."""
    global state_manager
    if state_manager is None:
        state_manager = GraphStateManager()
        logger.info("Graph state manager initialized")
    return state_manager


# Event Handlers - Clean graph database API

@event_handler("system:context")
async def handle_context(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:
    """Receive infrastructure context."""
    if state_manager:
        logger.info("Graph state manager connected to event system")
    else:
        logger.error("State manager not available")


class EntityCreateData(TypedDict):
    """Create a new entity."""
    id: NotRequired[str]  # Entity ID (optional, will generate if not provided)
    type: Required[str]  # Entity type (required)
    properties: NotRequired[Dict[str, Any]]  # Initial properties (optional)


@event_handler("state:entity:create")
async def handle_entity_create(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create a new entity."""
    if not state_manager:
        return error_response(
            "State infrastructure not available",
            context=context
        )
    
    # Extract clean business data and system metadata (SYSTEM_METADATA_FIELDS is source of truth)
    clean_data, system_metadata = extract_system_handler_data(raw_data)
    
    # Handle properties parameter if it's a JSON string
    from ksi_common.json_utils import parse_json_parameter
    parse_json_parameter(clean_data, 'properties')
    
    entity_type = clean_data.get("type")
    if not entity_type:
        return error_response(
            "Entity type is required",
            context=context
        )
    
    entity_id = clean_data.get("id") or f"{entity_type}_{uuid.uuid4().hex[:8]}"
    properties = clean_data.get("properties", {})
    
    try:
        entity = await state_manager.create_entity(entity_id, entity_type, properties)
        return event_response_builder(
            entity,
            context=context
        )
    except Exception as e:
        logger.error(f"Error creating entity: {e}")
        return error_response(
            str(e),
            context=context
        )


class EntityUpdateData(TypedDict):
    """Update entity properties."""
    id: Required[str]  # Entity ID (required)
    properties: Required[Dict[str, Any]]  # Properties to update (set to None to delete)


@event_handler("state:entity:update")
async def handle_entity_update(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Update entity properties."""
    if not state_manager:
        return error_response(
            "State infrastructure not available",
            context=context
        )
    
    # Extract clean business data and system metadata (SYSTEM_METADATA_FIELDS is source of truth)
    clean_data, system_metadata = extract_system_handler_data(raw_data)
    
    # Handle properties parameter if it's a JSON string
    from ksi_common.json_utils import parse_json_parameter
    parse_json_parameter(clean_data, 'properties')
    
    entity_id = clean_data.get("id")
    if not entity_id:
        return error_response(
            "Entity ID is required",
            context=context
        )
    
    properties = clean_data.get("properties", {})
    
    try:
        success = await state_manager.update_entity(entity_id, properties)
        if success:
            return success_response(
                {"id": entity_id},
                context=context,
                message="Entity updated successfully"
            )
        else:
            return error_response(
                "Entity not found",
                context=context,
                details={"id": entity_id}
            )
    except Exception as e:
        logger.error(f"Error updating entity: {e}")
        return {"error": str(e)}


class EntityDeleteData(TypedDict):
    """Delete an entity."""
    id: Required[str]  # Entity ID (required)


@event_handler("state:entity:delete")
async def handle_entity_delete(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Delete an entity."""
    if not state_manager:
        return error_response(
            "State infrastructure not available",
            context=context
        )
    
    # Extract clean business data and system metadata (SYSTEM_METADATA_FIELDS is source of truth)
    clean_data, system_metadata = extract_system_handler_data(raw_data)
    
    entity_id = clean_data.get("id")
    if not entity_id:
        return error_response(
            "Entity ID is required",
            context=context
        )
    
    try:
        success = await state_manager.delete_entity(entity_id)
        if success:
            return success_response(
                {"id": entity_id},
                context=context,
                message="Entity deleted successfully"
            )
        else:
            return error_response(
                "Entity not found",
                context=context,
                details={"id": entity_id}
            )
    except Exception as e:
        logger.error(f"Error deleting entity: {e}")
        return error_response(
            str(e),
            context=context
        )


class EntityGetData(TypedDict):
    """Get an entity."""
    id: Required[str]  # Entity ID (required)
    include: NotRequired[List[Literal['properties', 'relationships']]]  # What to include (default: ['properties'])


@event_handler("state:entity:get")
async def handle_entity_get(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get an entity."""
    if not state_manager:
        return error_response(
            "State infrastructure not available",
            context=context
        )
    
    # Extract clean business data and system metadata (SYSTEM_METADATA_FIELDS is source of truth)
    clean_data, system_metadata = extract_system_handler_data(raw_data)
    
    entity_id = clean_data.get("id")
    if not entity_id:
        return error_response(
            "Entity ID is required",
            context=context
        )
    
    include = clean_data.get("include", ["properties"])
    
    try:
        entity = await state_manager.get_entity(entity_id, include=include)
        if entity:
            return event_response_builder(
                entity,
                context=context
            )
        else:
            return error_response(
                "Entity not found",
                context=context,
                details={"id": entity_id}
            )
    except Exception as e:
        logger.error(f"Error getting entity: {e}")
        return error_response(
            str(e),
            context=context
        )


class EntityQueryData(TypedDict):
    """Query entities."""
    type: NotRequired[str]  # Filter by entity type (optional)
    where: NotRequired[Dict[str, Any]]  # Filter by properties (optional)
    include: NotRequired[List[Literal['properties', 'relationships']]]  # What to include (default: ['properties'])
    order_by: NotRequired[str]  # Order by field (default: created_at DESC)
    limit: NotRequired[int]  # Limit results (optional)


@event_handler("state:entity:query")
async def handle_entity_query(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Query entities."""
    if not state_manager:
        return error_response(
            "State infrastructure not available",
            context=context
        )
    
    # Extract clean business data and system metadata (SYSTEM_METADATA_FIELDS is source of truth)
    clean_data, system_metadata = extract_system_handler_data(raw_data)
    
    # Debug logging
    logger.info(f"Entity query received - type: {clean_data.get('type')}, where: {clean_data.get('where')}")
    
    try:
        # Add timeout at handler level too
        entities = await asyncio.wait_for(
            state_manager.query_entities(
                entity_type=clean_data.get("type"),
                where=clean_data.get("where"),
                include=clean_data.get("include", ["properties"]),
                order_by=clean_data.get("order_by"),
                limit=clean_data.get("limit")
            ),
            timeout=15.0
        )
        return list_response(
            entities,
            context=context,
            count_field="count",
            items_field="entities"
        )
    except asyncio.TimeoutError:
        logger.error(f"Entity query timed out - type: {clean_data.get('type')}, where: {clean_data.get('where')}")
        return error_response(
            "Query timed out after 15 seconds",
            context=context
        )
    except Exception as e:
        logger.error(f"Error querying entities: {e}")
        return error_response(
            str(e),
            context=context
        )


class RelationshipCreateData(TypedDict):
    """Create a relationship between entities."""
    from_id: Required[str]  # Source entity ID (required)
    to_id: Required[str]  # Target entity ID (required) 
    relation_type: Required[str]  # Relationship type (required)
    metadata: NotRequired[Dict[str, Any]]  # Additional metadata (optional)


@event_handler("state:relationship:create")
async def handle_relationship_create(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create a relationship between entities."""
    if not state_manager:
        return error_response(
            "State infrastructure not available",
            context=context
        )
    
    # Extract clean business data and system metadata (SYSTEM_METADATA_FIELDS is source of truth)
    clean_data, system_metadata = extract_system_handler_data(raw_data)
    
    # Handle metadata parameter if it's a JSON string
    from ksi_common.json_utils import parse_json_parameter
    parse_json_parameter(clean_data, 'metadata')
    
    from_id = clean_data.get("from_id")
    to_id = clean_data.get("to_id")
    relation_type = clean_data.get("relation_type")
    
    if not all([from_id, to_id, relation_type]):
        return error_response(
            "from, to, and type are required",
            context=context
        )
    
    metadata = clean_data.get("metadata")
    
    try:
        success = await state_manager.create_relationship(from_id, to_id, relation_type, metadata)
        if success:
            return event_response_builder(
                {
                    "status": "created",
                    "from_id": from_id,
                    "to_id": to_id,
                    "relation_type": relation_type
                },
                context=context
            )
        else:
            return error_response(
                "Failed to create relationship (already exists or entities not found)",
                context=context
            )
    except Exception as e:
        logger.error(f"Error creating relationship: {e}")
        return error_response(
            str(e),
            context=context
        )


class RelationshipDeleteData(TypedDict):
    """Delete a relationship."""
    from_id: Required[str]  # Source entity ID (required)
    to_id: Required[str]  # Target entity ID (required)
    relation_type: Required[str]  # Relationship type (required)


@event_handler("state:relationship:delete")
async def handle_relationship_delete(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Delete a relationship."""
    if not state_manager:
        return error_response(
            "State infrastructure not available",
            context=context
        )
    
    # Extract clean business data and system metadata (SYSTEM_METADATA_FIELDS is source of truth)
    clean_data, system_metadata = extract_system_handler_data(raw_data)
    
    from_id = clean_data.get("from_id")
    to_id = clean_data.get("to_id")
    relation_type = clean_data.get("relation_type")
    
    if not all([from_id, to_id, relation_type]):
        return error_response(
            "from, to, and type are required",
            context=context
        )
    
    try:
        success = await state_manager.delete_relationship(from_id, to_id, relation_type)
        if success:
            return event_response_builder(
                {
                    "status": "deleted",
                    "from_id": from_id,
                    "to_id": to_id,
                    "relation_type": relation_type
                },
                context=context
            )
        else:
            return error_response(
                "Relationship not found",
                context=context
            )
    except Exception as e:
        logger.error(f"Error deleting relationship: {e}")
        return error_response(
            str(e),
            context=context
        )


class RelationshipQueryData(TypedDict):
    """Query relationships."""
    from_id: NotRequired[str]  # Filter by source entity (optional)
    to_id: NotRequired[str]  # Filter by target entity (optional)
    relation_type: NotRequired[str]  # Filter by relationship type (optional)


@event_handler("state:relationship:query")
async def handle_relationship_query(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Query relationships."""
    if not state_manager:
        return error_response(
            "State infrastructure not available",
            context=context
        )
    
    # Extract clean business data and system metadata (SYSTEM_METADATA_FIELDS is source of truth)
    clean_data, system_metadata = extract_system_handler_data(raw_data)
    
    try:
        relationships = await state_manager.query_relationships(
            from_id=clean_data.get("from_id"),
            to_id=clean_data.get("to_id"),
            relation_type=clean_data.get("relation_type")
        )
        return list_response(
            relationships,
            context=context,
            count_field="count",
            items_field="relationships"
        )
    except Exception as e:
        logger.error(f"Error querying relationships: {e}")
        return error_response(
            str(e),
            context=context
        )


class GraphTraverseData(TypedDict):
    """Traverse the graph from an entity following relationships."""
    from_id: Required[str]  # Starting entity ID (required)
    direction: NotRequired[Literal['outgoing', 'incoming', 'both']]  # Traversal direction (default: 'outgoing')
    types: NotRequired[List[str]]  # Filter by relationship types (optional)
    depth: NotRequired[int]  # Maximum traversal depth (default: 1, max: 5)
    include_entities: NotRequired[bool]  # Include full entity data (default: False)


@event_handler("state:graph:traverse")
async def handle_graph_traverse(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Traverse the graph from an entity following relationships."""
    if not state_manager:
        return error_response(
            "State infrastructure not available",
            context=context
        )
    
    # Extract clean business data and system metadata (SYSTEM_METADATA_FIELDS is source of truth)
    clean_data, system_metadata = extract_system_handler_data(raw_data)
    
    from_id = clean_data.get("from_id")
    if not from_id:
        return error_response(
            "from entity ID is required",
            context=context
        )
    
    direction = clean_data.get("direction", "outgoing")
    rel_types = clean_data.get("types", [])
    depth = min(clean_data.get("depth", 1), 5)  # Limit depth to prevent runaway queries
    include_entities = clean_data.get("include_entities", False)
    
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
                entity = await state_manager.get_entity(current_id, include=["properties"])
                if entity:
                    result["nodes"][current_id] = entity
            else:
                result["nodes"][current_id] = {"id": current_id}
            
            if current_depth < depth:
                # Get relationships based on direction
                if direction in ["outgoing", "both"]:
                    rels = await state_manager.query_relationships(from_id=current_id)
                    for rel in rels:
                        if not rel_types or rel["relation_type"] in rel_types:
                            result["edges"].append(rel)
                            queue.append((rel["to_id"], current_depth + 1))
                
                if direction in ["incoming", "both"]:
                    rels = await state_manager.query_relationships(to_id=current_id)
                    for rel in rels:
                        if not rel_types or rel["relation_type"] in rel_types:
                            result["edges"].append(rel)
                            queue.append((rel["from_id"], current_depth + 1))
        
        result["node_count"] = len(result["nodes"])
        result["edge_count"] = len(result["edges"])
        
        return event_response_builder(
            result,
            context=context
        )
        
    except Exception as e:
        logger.error(f"Error traversing graph: {e}")
        return error_response(
            str(e),
            context=context
        )


class EntityBulkCreateData(TypedDict):
    """Create multiple entities in a single operation."""
    entities: Required[List[EntityCreateData]]  # List of entity definitions


@event_handler("state:entity:bulk_create")
async def handle_entity_bulk_create(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create multiple entities in a single operation."""
    if not state_manager:
        return error_response(
            "State infrastructure not available",
            context=context
        )
    
    # Extract clean business data and system metadata (SYSTEM_METADATA_FIELDS is source of truth)
    clean_data, system_metadata = extract_system_handler_data(raw_data)
    
    entities = clean_data.get("entities", [])
    if not entities:
        return error_response(
            "entities list is required",
            context=context
        )
    
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
            
            entity = await state_manager.create_entity(entity_id, entity_type, properties)
            results.append(entity)
            success_count += 1
            
        except Exception as e:
            results.append({"error": str(e)})
    
    return event_response_builder(
        {
            "results": results,
            "total": len(entities),
            "success": success_count,
            "failed": len(entities) - success_count
        },
        context=context
    )


class AggregateCountData(TypedDict):
    """Count entities or relationships with grouping."""
    target: Required[Literal['entities', 'relationships']]  # What to count (required)
    group_by: NotRequired[str]  # Field to group by (optional)
    where: NotRequired[Dict[str, Any]]  # Filter conditions (optional)


@event_handler("state:aggregate:count")
async def handle_aggregate_count(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Count entities or relationships with grouping."""
    if not state_manager:
        return error_response(
            "State infrastructure not available",
            context=context
        )
    
    # Extract clean business data and system metadata (SYSTEM_METADATA_FIELDS is source of truth)
    clean_data, system_metadata = extract_system_handler_data(raw_data)
    
    target = clean_data.get("target")
    if target not in ["entities", "relationships"]:
        return error_response(
            "target must be 'entities' or 'relationships'",
            context=context
        )
    
    group_by = clean_data.get("group_by")
    where = clean_data.get("where", {})
    
    try:
        async with state_manager._get_db() as conn:
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
                    
                async with conn.execute(query) as cursor:
                    
                    if group_by:
                        results = {}
                        async for row in cursor:
                            results[row[0]] = row[1]
                        return event_response_builder(
                            {"counts": results, "grouped_by": group_by},
                            context=context
                        )
                    else:
                        row = await cursor.fetchone()
                        return event_response_builder(
                            {"total": row[0]},
                            context=context
                        )
                    
            else:  # relationships
                if group_by == "type":
                    query = "SELECT relation_type, COUNT(*) as count FROM relationships GROUP BY relation_type"
                else:
                    query = "SELECT COUNT(*) as total FROM relationships"
                    
                async with conn.execute(query) as cursor:
                    
                    if group_by:
                        results = {}
                        async for row in cursor:
                            results[row[0]] = row[1]
                        return event_response_builder(
                            {"counts": results, "grouped_by": "relation_type"},
                            context=context
                        )
                    else:
                        row = await cursor.fetchone()
                        return event_response_builder(
                            {"total": row[0]},
                            context=context
                        )
                    
    except Exception as e:
        logger.error(f"Error in aggregate count: {e}")
        return error_response(
            str(e),
            context=context
        )


@shutdown_handler("state_service")
async def handle_shutdown(data: Dict[str, Any]) -> None:
    """Ensure all database operations complete before shutdown."""
    if state_manager:
        # Force any pending operations to complete by accessing the database
        logger.info("State service shutting down, ensuring database operations complete...")
        try:
            # Do a simple query to ensure any pending writes are flushed
            async with state_manager._get_db() as conn:
                await conn.execute("SELECT COUNT(*) FROM entities")
                await conn.commit()
            logger.info("State service database operations completed")
        except Exception as e:
            logger.error(f"Error during state service shutdown: {e}")
    
    # Acknowledge shutdown
    router = get_router()
    await router.acknowledge_shutdown("state_service")