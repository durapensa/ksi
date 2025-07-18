# Add these methods to composition_index.py


async def get_unique_component_types() -> List[str]:
    """Get all unique component types from the index."""
    try:
        async with _get_db() as conn:
            # First try to get component_type from JSON metadata
            async with conn.execute("""
                SELECT DISTINCT 
                    COALESCE(
                        json_extract(full_metadata, '$.component_type'),
                        type
                    ) as comp_type
                FROM composition_index 
                WHERE comp_type IS NOT NULL
            """) as cursor:
                types = [row[0] for row in await cursor.fetchall() if row[0]]
                return types if types else ['component']
    except Exception as e:
        logger.error(f"Failed to get unique component types: {e}")
        return ['component']  # Fallback


async def filter_by_component_type(component_type: str) -> List[Dict[str, Any]]:
    """Filter components by their component_type attribute."""
    try:
        async with _get_db() as conn:
            async with conn.execute("""
                SELECT * FROM composition_index
                WHERE json_extract(full_metadata, '$.component_type') = ?
                OR (type = ? AND json_extract(full_metadata, '$.component_type') IS NULL)
            """, (component_type, component_type)) as cursor:
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in await cursor.fetchall()]
    except Exception as e:
        logger.error(f"Failed to filter by component type {component_type}: {e}")
        return []


def normalize_component_path(name: str, component_type: str = 'component') -> str:
    """Normalize component path based on type and naming convention."""
    # Map component types to default directories
    type_dirs = {
        'core': 'core',
        'persona': 'personas',
        'behavior': 'behaviors', 
        'orchestration': 'orchestrations',
        'evaluation': 'evaluations',
        'evaluation_suite': 'evaluations/suites',
        'tool': 'tools',
        'example': 'examples'
    }
    
    # If path already contains directory, use as-is
    if '/' in name:
        return name
        
    # Otherwise, organize by type
    if component_type in type_dirs:
        return f"{type_dirs[component_type]}/{name}"
    
    # Default to type-based directory
    return f"{component_type}/{name}"


async def update_component_type_in_index(full_name: str, component_type: str) -> bool:
    """Update component_type in the index metadata."""
    try:
        async with _get_db() as conn:
            # Get current metadata
            async with conn.execute(
                'SELECT full_metadata FROM composition_index WHERE full_name = ?', 
                (full_name,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return False
                
                metadata = json.loads(row[0]) if row[0] else {}
                metadata['component_type'] = component_type
                
                # Update metadata
                await conn.execute(
                    'UPDATE composition_index SET full_metadata = ? WHERE full_name = ?',
                    (json.dumps(metadata), full_name)
                )
                await conn.commit()
                return True
                
    except Exception as e:
        logger.error(f"Failed to update component type for {full_name}: {e}")
        return False