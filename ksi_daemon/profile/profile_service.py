#!/usr/bin/env python3
"""
Profile Discovery Service Module

Provides profile discovery and management using the state system's EAV pattern.
Integrates with the composition system for loading and Git for storage.
"""

import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, TypedDict
from typing_extensions import NotRequired, Required

from ksi_daemon.event_system import event_handler, get_router
from ksi_common.logging import get_bound_logger
from ksi_common.config import config
from ksi_common.timestamps import timestamp_utc
from ksi_common.file_utils import load_yaml_file
from ksi_common.event_response_builder import event_response_builder, error_response

logger = get_bound_logger("profile_service", version="1.0.0")

# Profile entity type in state system
PROFILE_ENTITY_TYPE = "agent_profile"

# Standard profile attributes for EAV storage
PROFILE_ATTRIBUTES = {
    "name": "The profile name without path",
    "category": "Directory path like 'provider_base' or 'system'", 
    "extends": "Parent profile name (if any)",
    "capability": "Capabilities granted (multi-value)",
    "tag": "Tags for discovery (multi-value)",
    "git_ref": "Git reference/version",
    "file_hash": "SHA256 hash of file content",
    "file_path": "Relative path from compositions directory",
    "compatible_provider": "Compatible LLM providers (multi-value)",
    "version": "Profile version",
    "description": "Profile description",
    "indexed_at": "When profile was indexed"
}

# Module state
event_emitter = None


# TypedDict definitions for event handlers

class ProfileSetAttributeData(TypedDict):
    """Set a single attribute on a profile."""
    name: Required[str]  # Profile name (e.g. "system/orchestrator")
    attribute: Required[str]  # Attribute name
    value: Required[Any]  # Attribute value
    

class ProfileGetAttributesData(TypedDict):
    """Get specific attributes for a profile."""
    name: Required[str]  # Profile name
    attributes: NotRequired[List[str]]  # Specific attributes (default: all)


class ProfileQueryByAttributeData(TypedDict):
    """Query profiles by attribute value."""
    attribute: Required[str]  # Attribute name
    value: Required[Any]  # Attribute value to match
    

class ProfileDiscoverData(TypedDict):
    """Discover profiles with multi-attribute filtering."""
    where: NotRequired[Dict[str, Any]]  # Attribute filters
    include_inherited: NotRequired[bool]  # Include parent profiles
    category: NotRequired[str]  # Filter by category
    limit: NotRequired[int]  # Result limit


class ProfileListData(TypedDict):
    """List profiles with optional filtering."""
    category: NotRequired[str]  # Filter by category
    limit: NotRequired[int]  # Result limit


class ProfileGetMetadataData(TypedDict):
    """Get profile metadata."""
    name: Required[str]  # Profile name
    attributes: NotRequired[List[str]]  # Specific attributes


class ProfileResolveInheritanceData(TypedDict):
    """Resolve profile inheritance chain."""
    name: Required[str]  # Profile name


class ProfileRegisterData(TypedDict):
    """Register/update profile in index."""
    name: Required[str]  # Profile name
    path: Required[str]  # File path
    attributes: Required[Dict[str, Any]]  # Profile attributes


class ProfileComposeData(TypedDict):
    """Compose profile with inheritance resolution."""
    name: Required[str]  # Profile name
    variables: NotRequired[Dict[str, Any]]  # Template variables


class ProfileRebuildIndexData(TypedDict):
    """Rebuild profile index from Git."""
    clear_existing: NotRequired[bool]  # Clear before rebuild


# System event handlers

@event_handler("system:context")
async def handle_context(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:
    """Receive module context with event emitter."""
    global event_emitter
    router = get_router()
    event_emitter = router.emit
    logger.info("Profile service received context")


@event_handler("system:startup")
async def handle_startup(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Initialize profile service on startup."""
    logger.info("Profile service starting up...")
    
    # Trigger index rebuild in background
    if event_emitter:
        asyncio.create_task(rebuild_index_async())
    
    return event_response_builder(
        {"status": "profile_service_ready"},
        context=context
    )


# Profile-specific state management

@event_handler("profile:set_attribute")
async def handle_set_attribute(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Set a single attribute on a profile using EAV pattern."""
    from ksi_common.event_parser import event_format_linter
    data = event_format_linter(raw_data, ProfileSetAttributeData)
    
    if not event_emitter:
        return error_response("Event system not initialized", context)
    
    profile_id = f"profile:{data['name']}"
    
    # For multi-value attributes (like capabilities), we need special handling
    multi_value_attrs = ["capability", "tag", "compatible_provider"]
    
    if data['attribute'] in multi_value_attrs:
        # First get existing values
        existing = await event_emitter("state:entity:get", {
            "id": profile_id,
            "include": ["properties"]
        })
        
        if existing and isinstance(existing, list):
            existing = existing[0] if existing else {}
            
        current_values = []
        if existing and "properties" in existing:
            # Collect all values for this attribute
            attr_key = data['attribute']
            props = existing['properties']
            if isinstance(props.get(attr_key), list):
                current_values = props[attr_key]
            elif attr_key in props:
                current_values = [props[attr_key]]
        
        # Add new value if not already present
        if data['value'] not in current_values:
            current_values.append(data['value'])
            
        # Store as list in properties
        properties = {data['attribute']: current_values}
    else:
        # Single-value attribute
        properties = {data['attribute']: data['value']}
    
    # Update entity properties
    result = await event_emitter("state:entity:update", {
        "id": profile_id,
        "properties": properties
    })
    
    if result and isinstance(result, list):
        result = result[0] if result else {}
    
    if result and "error" not in result:
        logger.debug(f"Set attribute {data['attribute']} on profile {data['name']}")
        return event_response_builder(
            {"status": "success", "profile": data['name'], "attribute": data['attribute']},
            context=context
        )
    else:
        return error_response(
            f"Failed to set attribute: {result.get('error', 'Unknown error')}",
            context=context
        )


@event_handler("profile:get_attributes")
async def handle_get_attributes(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get specific attributes for a profile."""
    from ksi_common.event_parser import event_format_linter
    data = event_format_linter(raw_data, ProfileGetAttributesData)
    
    if not event_emitter:
        return error_response("Event system not initialized", context)
    
    profile_id = f"profile:{data['name']}"
    
    # Get entity with properties
    result = await event_emitter("state:entity:get", {
        "id": profile_id,
        "include": ["properties"]
    })
    
    if result and isinstance(result, list):
        result = result[0] if result else {}
    
    if result and "properties" in result:
        properties = result['properties']
        
        # Filter to requested attributes if specified
        if 'attributes' in data and data['attributes']:
            filtered = {k: v for k, v in properties.items() if k in data['attributes']}
            properties = filtered
        
        return event_response_builder(
            {"profile": data['name'], "attributes": properties},
            context=context
        )
    else:
        return error_response(
            f"Profile not found: {data['name']}",
            context=context
        )


@event_handler("profile:query_by_attribute") 
async def handle_query_by_attribute(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Find profiles with specific attribute value."""
    from ksi_common.event_parser import event_format_linter
    data = event_format_linter(raw_data, ProfileQueryByAttributeData)
    
    if not event_emitter:
        return error_response("Event system not initialized", context)
    
    # Query entities by property
    result = await event_emitter("state:entity:query", {
        "type": PROFILE_ENTITY_TYPE,
        "where": {data['attribute']: data['value']},
        "include": ["properties"]
    })
    
    if result and isinstance(result, list):
        result = result[0] if result else {}
    
    if result and "entities" in result:
        profiles = []
        for entity in result['entities']:
            # Extract profile name from entity ID
            profile_name = entity['id'].replace('profile:', '')
            profiles.append({
                "name": profile_name,
                "attributes": entity.get('properties', {})
            })
        
        return event_response_builder(
            {"profiles": profiles, "count": len(profiles)},
            context=context
        )
    else:
        return event_response_builder(
            {"profiles": [], "count": 0},
            context=context
        )


# Profile discovery

@event_handler("profile:discover")
async def handle_discover(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Smart profile discovery with multi-attribute filtering."""
    from ksi_common.event_parser import event_format_linter
    data = event_format_linter(raw_data, ProfileDiscoverData)
    
    if not event_emitter:
        return error_response("Event system not initialized", context)
    
    where = data.get('where', {})
    include_inherited = data.get('include_inherited', False)
    
    # Handle multi-value attributes specially
    # For capabilities, tags, etc. we need to check if ANY value matches
    multi_value_attrs = ["capability", "tag", "compatible_provider"]
    
    # Start with all profiles of type
    all_result = await event_emitter("state:entity:query", {
        "type": PROFILE_ENTITY_TYPE,
        "include": ["properties"],
        "limit": data.get('limit', 100)
    })
    
    if all_result and isinstance(all_result, list):
        all_result = all_result[0] if all_result else {}
    
    if not all_result or "entities" not in all_result:
        return event_response_builder({"profiles": [], "count": 0}, context=context)
    
    # Filter by attributes
    matching_profiles = []
    
    for entity in all_result['entities']:
        props = entity.get('properties', {})
        profile_name = entity['id'].replace('profile:', '')
        
        # Check category filter
        if 'category' in data and props.get('category') != data['category']:
            continue
        
        # Check where conditions
        matches = True
        for attr, value in where.items():
            if attr in multi_value_attrs:
                # Check if value is in the list
                attr_values = props.get(attr, [])
                if not isinstance(attr_values, list):
                    attr_values = [attr_values]
                if value not in attr_values:
                    matches = False
                    break
            else:
                # Direct comparison
                if props.get(attr) != value:
                    matches = False
                    break
        
        if matches:
            matching_profiles.append({
                "name": profile_name,
                "category": props.get('category', ''),
                "extends": props.get('extends'),
                "capabilities": props.get('capability', []),
                "tags": props.get('tag', []),
                "description": props.get('description', ''),
                "version": props.get('version', '')
            })
    
    # Handle inheritance expansion if requested
    if include_inherited and matching_profiles:
        expanded = set()
        for profile in matching_profiles:
            expanded.add(profile['name'])
            # Get inheritance chain
            chain = await resolve_inheritance_chain(profile['name'])
            expanded.update(chain)
        
        # Reload full data for expanded set
        # TODO: Implement this if needed
    
    return event_response_builder(
        {"profiles": matching_profiles, "count": len(matching_profiles)},
        context=context
    )


@event_handler("profile:list")
async def handle_list(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """List all profiles with optional category filter."""
    from ksi_common.event_parser import event_format_linter
    data = event_format_linter(raw_data, ProfileListData)
    
    # Use discover with simplified query
    discover_data = {
        "limit": data.get('limit', 100)
    }
    
    if 'category' in data:
        discover_data['category'] = data['category']
    
    return await handle_discover(discover_data, context)


@event_handler("profile:get_metadata")
async def handle_get_metadata(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get profile metadata (wrapper around get_attributes)."""
    from ksi_common.event_parser import event_format_linter
    data = event_format_linter(raw_data, ProfileGetMetadataData)
    
    # Use get_attributes
    return await handle_get_attributes({
        "name": data['name'],
        "attributes": data.get('attributes')
    }, context)


@event_handler("profile:resolve_inheritance") 
async def handle_resolve_inheritance(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Resolve profile inheritance chain."""
    from ksi_common.event_parser import event_format_linter
    data = event_format_linter(raw_data, ProfileResolveInheritanceData)
    
    chain = await resolve_inheritance_chain(data['name'])
    
    return event_response_builder(
        {"profile": data['name'], "inheritance_chain": chain},
        context=context
    )


# Profile management

@event_handler("profile:register")
async def handle_register(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Register/update profile in state index."""
    from ksi_common.event_parser import event_format_linter
    data = event_format_linter(raw_data, ProfileRegisterData)
    
    if not event_emitter:
        return error_response("Event system not initialized", context)
    
    profile_id = f"profile:{data['name']}"
    
    # Ensure entity exists
    create_result = await event_emitter("state:entity:create", {
        "id": profile_id,
        "type": PROFILE_ENTITY_TYPE,
        "properties": {}
    })
    
    # Update all attributes
    properties = data['attributes'].copy()
    properties['indexed_at'] = timestamp_utc()
    
    update_result = await event_emitter("state:entity:update", {
        "id": profile_id,
        "properties": properties
    })
    
    if update_result and isinstance(update_result, list):
        update_result = update_result[0] if update_result else {}
    
    if update_result and "error" not in update_result:
        logger.info(f"Registered profile {data['name']}")
        return event_response_builder(
            {"status": "registered", "profile": data['name']},
            context=context
        )
    else:
        return error_response(
            f"Failed to register profile: {update_result.get('error', 'Unknown error')}",
            context=context
        )


@event_handler("profile:rebuild_index")
async def handle_rebuild_index(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Rebuild profile index from Git repository."""
    from ksi_common.event_parser import event_format_linter
    data = event_format_linter(raw_data, ProfileRebuildIndexData)
    
    count = await rebuild_index_async(clear_existing=data.get('clear_existing', True))
    
    return event_response_builder(
        {"status": "rebuilt", "profiles_indexed": count},
        context=context
    )


# Helper functions

async def resolve_inheritance_chain(profile_name: str) -> List[str]:
    """Recursively resolve profile inheritance chain."""
    chain = []
    current = profile_name
    visited = set()
    
    while current and current not in visited:
        visited.add(current)
        chain.append(current)
        
        # Get extends attribute
        result = await event_emitter("profile:get_attributes", {
            "name": current,
            "attributes": ["extends"]
        })
        
        # Handle event response format (list wrapper)
        if result and isinstance(result, list) and len(result) > 0:
            result = result[0]
            
        if result and "attributes" in result and "extends" in result['attributes']:
            current = result['attributes']['extends']
        else:
            break
    
    return chain


async def rebuild_index_async(clear_existing: bool = True) -> int:
    """Rebuild profile index by scanning Git repository."""
    if not event_emitter:
        logger.error("Cannot rebuild index: event system not initialized")
        return 0
    
    profiles_dir = Path(config.compositions_dir) / "profiles"
    if not profiles_dir.exists():
        logger.warning(f"Profiles directory does not exist: {profiles_dir}")
        return 0
    
    # Clear existing if requested
    if clear_existing:
        # Query all existing profiles
        existing = await event_emitter("state:entity:query", {
            "type": PROFILE_ENTITY_TYPE,
            "include": []
        })
        
        if existing and isinstance(existing, list):
            existing = existing[0] if existing else {}
        
        if existing and "entities" in existing:
            for entity in existing['entities']:
                await event_emitter("state:entity:delete", {"id": entity['id']})
            logger.info(f"Cleared {len(existing['entities'])} existing profiles")
    
    # Scan and index profiles
    indexed_count = 0
    
    for yaml_file in profiles_dir.rglob("*.yaml"):
        try:
            # Load profile data
            profile_data = load_yaml_file(yaml_file)
            if not isinstance(profile_data, dict) or 'name' not in profile_data:
                continue
            
            # Extract metadata
            name = profile_data['name']
            relative_path = yaml_file.relative_to(profiles_dir)
            category = str(relative_path.parent) if relative_path.parent != Path('.') else 'root'
            
            # Calculate file hash
            import hashlib
            content = yaml_file.read_text()
            file_hash = hashlib.sha256(content.encode()).hexdigest()
            
            # Build attributes
            attributes = {
                "name": name,
                "category": category,
                "file_path": str(relative_path),
                "file_hash": file_hash,
                "version": profile_data.get('version', '1.0.0'),
                "description": profile_data.get('description', ''),
                "indexed_at": timestamp_utc()
            }
            
            # Add optional attributes
            if 'extends' in profile_data:
                attributes['extends'] = profile_data['extends']
            
            # Extract metadata section
            metadata = profile_data.get('metadata', {})
            
            # Multi-value attributes
            for attr in ['capability', 'tag', 'compatible_provider']:
                if attr == 'capability':
                    # Handle capability extraction from multiple sources
                    values = []
                    
                    # Get from metadata.capabilities (list format)
                    metadata_caps = metadata.get('capabilities', [])
                    if isinstance(metadata_caps, list):
                        values.extend(metadata_caps)
                    elif metadata_caps:
                        values.append(metadata_caps)
                    
                    # Get from profile.capabilities (dict format) 
                    profile_caps = profile_data.get('capabilities', {})
                    if isinstance(profile_caps, dict):
                        # Extract capability names where value is True
                        for cap_name, cap_value in profile_caps.items():
                            if cap_value and cap_name not in values:
                                values.append(cap_name)
                    elif isinstance(profile_caps, list):
                        # Handle list format as well
                        values.extend(profile_caps)
                    
                    if values:
                        attributes[attr] = values
                else:
                    # Handle other multi-value attributes normally
                    source_key = attr + 's'
                    values = profile_data.get(source_key, []) or metadata.get(source_key, [])
                    if values:
                        attributes[attr] = values if isinstance(values, list) else [values]
            
            # Register profile
            await event_emitter("profile:register", {
                "name": f"{category}/{name}" if category != 'root' else name,
                "path": str(yaml_file),
                "attributes": attributes
            })
            
            indexed_count += 1
            
        except Exception as e:
            logger.error(f"Failed to index {yaml_file}: {e}")
    
    logger.info(f"Profile index rebuilt: {indexed_count} profiles indexed")
    return indexed_count


# Smart Router Pattern: Profile/Composition Integration
# These handlers provide unified APIs that route to appropriate systems

class ProfileGetFullData(TypedDict):
    """Get full composed profile via composition system."""
    name: Required[str]  # Profile name
    variables: NotRequired[Dict[str, Any]]  # Variables for composition
    include_trace: NotRequired[bool]  # Include component tracing info

class ProfileCreateData(TypedDict):
    """Create profile via composition system."""
    name: Required[str]  # Profile name
    content: Required[Dict[str, Any]]  # Profile content
    category: NotRequired[str]  # Category for organization
    overwrite: NotRequired[bool]  # Overwrite existing


@event_handler("profile:get_full")
async def handle_get_full_profile(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Route to composition system for full profile with inheritance and component tracing."""
    from ksi_common.event_parser import event_format_linter
    data = event_format_linter(raw_data, ProfileGetFullData)
    
    if not event_emitter:
        return error_response("Event system not initialized", context)
    
    # Route to composition system
    composition_data = {
        "name": data['name'],
        "variables": data.get('variables', {})
    }
    
    result = await event_emitter("composition:profile", composition_data)
    
    # Handle event response format
    if result and isinstance(result, list) and len(result) > 0:
        result = result[0]
    
    if result and "profile" in result:
        # Add component tracing if requested
        if data.get('include_trace', False):
            result['profile']['_component_trace'] = await _get_component_trace(data['name'])
        
        # Add discovery metadata
        metadata = await event_emitter("profile:get_attributes", {
            "name": data['name']
        })
        
        if metadata and isinstance(metadata, list) and len(metadata) > 0:
            metadata = metadata[0]
            
        if metadata and "attributes" in metadata:
            result['profile']['_discovery_metadata'] = metadata['attributes']
        
        return event_response_builder(
            {
                "status": "success",
                "profile": result['profile'],
                "source": "composition_system"
            },
            context=context
        )
    else:
        return error_response(
            f"Failed to compose profile: {result.get('error', 'Unknown error') if result else 'No result'}",
            context=context
        )


@event_handler("profile:create")
async def handle_create_profile(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Route to composition system for profile creation with auto-index update."""
    from ksi_common.event_parser import event_format_linter
    data = event_format_linter(raw_data, ProfileCreateData)
    
    if not event_emitter:
        return error_response("Event system not initialized", context)
    
    # Route to composition system
    composition_data = {
        "composition": data['content'],
        "overwrite": data.get('overwrite', False)
    }
    
    result = await event_emitter("composition:save", composition_data)
    
    # Handle event response format
    if result and isinstance(result, list) and len(result) > 0:
        result = result[0]
    
    if result and result.get('status') == 'success':
        # Auto-update profile index
        await _auto_update_profile_index(data['name'], result.get('path'))
        
        return event_response_builder(
            {
                "status": "success",
                "name": data['name'],
                "path": result.get('path'),
                "indexed": True
            },
            context=context
        )
    else:
        return error_response(
            f"Failed to create profile: {result.get('error', 'Unknown error') if result else 'No result'}",
            context=context
        )


# Auto-sync hooks for composition system events

@event_handler("composition:saved")
async def handle_composition_saved(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Auto-update profile index when composition is saved."""
    data = raw_data
    
    # Only handle profile compositions
    if data.get('type') == 'profile':
        await _auto_update_profile_index(data.get('name'), data.get('path'))
        logger.info(f"Auto-updated profile index for {data.get('name')}")
    
    return event_response_builder({"status": "handled"}, context=context)


@event_handler("composition:updated")
async def handle_composition_updated(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Auto-update profile index when composition is updated."""
    data = raw_data
    
    # Only handle profile compositions
    if data.get('type') == 'profile':
        await _auto_update_profile_index(data.get('name'), data.get('path'))
        logger.info(f"Auto-updated profile index for {data.get('name')}")
    
    return event_response_builder({"status": "handled"}, context=context)


# Helper functions for integration

async def _get_component_trace(profile_name: str) -> Dict[str, Any]:
    """Get component tracing information for a profile."""
    trace = {
        "inheritance_chain": await resolve_inheritance_chain(profile_name),
        "components": [],
        "source_files": []
    }
    
    # Get full composition data to analyze components
    result = await event_emitter("composition:get", {"name": profile_name})
    
    if result and isinstance(result, list) and len(result) > 0:
        result = result[0]
    
    if result and "composition" in result:
        composition = result['composition']
        
        # Extract component information
        if 'components' in composition:
            for component in composition['components']:
                trace['components'].append({
                    "name": component.get('name'),
                    "source": component.get('source'),
                    "type": "inline" if component.get('inline') else "external"
                })
        
        # Extract source file information
        if 'metadata' in composition:
            trace['source_files'].append({
                "path": composition['metadata'].get('file_path'),
                "hash": composition['metadata'].get('file_hash')
            })
    
    return trace


async def _auto_update_profile_index(profile_name: str, file_path: str) -> None:
    """Auto-update profile index when a profile is saved."""
    if not event_emitter or not profile_name:
        return
    
    try:
        # Load the profile file to extract metadata
        if file_path:
            profile_path = Path(file_path)
            if profile_path.exists():
                profile_data = load_yaml_file(profile_path)
                
                if profile_data and 'name' in profile_data:
                    # Extract category from path
                    profiles_dir = Path(config.compositions_dir) / "profiles"
                    relative_path = profile_path.relative_to(profiles_dir)
                    category = str(relative_path.parent) if relative_path.parent != Path('.') else 'root'
                    
                    # Calculate file hash
                    import hashlib
                    content = profile_path.read_text()
                    file_hash = hashlib.sha256(content.encode()).hexdigest()
                    
                    # Build attributes
                    attributes = {
                        "name": profile_data['name'],
                        "category": category,
                        "file_path": str(relative_path),
                        "file_hash": file_hash,
                        "version": profile_data.get('version', '1.0.0'),
                        "description": profile_data.get('description', ''),
                        "indexed_at": timestamp_utc()
                    }
                    
                    # Add optional attributes
                    if 'extends' in profile_data:
                        attributes['extends'] = profile_data['extends']
                    
                    # Extract metadata section
                    metadata = profile_data.get('metadata', {})
                    
                    # Multi-value attributes
                    for attr in ['capability', 'tag', 'compatible_provider']:
                        if attr == 'capability':
                            # Handle capability extraction from multiple sources
                            values = []
                            
                            # Get from metadata.capabilities (list format)
                            metadata_caps = metadata.get('capabilities', [])
                            if isinstance(metadata_caps, list):
                                values.extend(metadata_caps)
                            elif metadata_caps:
                                values.append(metadata_caps)
                            
                            # Get from profile.capabilities (dict format) 
                            profile_caps = profile_data.get('capabilities', {})
                            if isinstance(profile_caps, dict):
                                # Extract capability names where value is True
                                for cap_name, cap_value in profile_caps.items():
                                    if cap_value and cap_name not in values:
                                        values.append(cap_name)
                            elif isinstance(profile_caps, list):
                                # Handle list format as well
                                values.extend(profile_caps)
                            
                            if values:
                                attributes[attr] = values
                        else:
                            # Handle other multi-value attributes normally
                            source_key = attr + 's'
                            values = profile_data.get(source_key, []) or metadata.get(source_key, [])
                            if values:
                                attributes[attr] = values if isinstance(values, list) else [values]
                    
                    # Register profile
                    await event_emitter("profile:register", {
                        "name": f"{category}/{profile_data['name']}" if category != 'root' else profile_data['name'],
                        "path": str(profile_path),
                        "attributes": attributes
                    })
                    
                    logger.debug(f"Auto-indexed profile: {profile_name}")
                    
    except Exception as e:
        logger.error(f"Failed to auto-update profile index for {profile_name}: {e}")


# Capability System Implementation

# Module-level capability cache
_capability_cache = {}

class CapabilityDefinition:
    """A capability definition loaded from YAML."""
    def __init__(self, name: str, data: Dict[str, Any]):
        self.name = name
        self.data = data
        self.extends = data.get('extends')
        self.permissions = data.get('permissions', {})
        self.knowledge = data.get('knowledge', {})
        self.metadata = data.get('metadata', {})
        self.validation = data.get('validation', {})
        self.compatibility = data.get('compatibility', {})
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert capability to dictionary."""
        return {
            "name": self.name,
            "extends": self.extends,
            "permissions": self.permissions,
            "knowledge": self.knowledge,
            "metadata": self.metadata,
            "validation": self.validation,
            "compatibility": self.compatibility
        }
    
    async def resolve_permissions(self, capability_loader) -> Dict[str, List[str]]:
        """Recursively resolve all permissions including inherited."""
        permissions = {}
        
        # Load parent capability if exists
        if self.extends:
            parent_cap = await capability_loader(self.extends)
            if parent_cap:
                parent_permissions = await parent_cap.resolve_permissions(capability_loader)
                permissions.update(parent_permissions)
        
        # Merge own permissions
        for perm_type, perm_list in self.permissions.items():
            if perm_type in permissions:
                # Merge lists, avoiding duplicates
                combined = list(set(permissions[perm_type] + perm_list))
                permissions[perm_type] = combined
            else:
                permissions[perm_type] = perm_list[:]
        
        return permissions
    
    async def resolve_knowledge(self, capability_loader) -> Dict[str, str]:
        """Recursively resolve all knowledge including inherited."""
        knowledge = {}
        
        # Load parent capability if exists
        if self.extends:
            parent_cap = await capability_loader(self.extends)
            if parent_cap:
                parent_knowledge = await parent_cap.resolve_knowledge(capability_loader)
                knowledge.update(parent_knowledge)
        
        # Merge own knowledge
        knowledge.update(self.knowledge)
        
        return knowledge


class CapabilityLoadData(TypedDict):
    """Load and resolve a capability definition."""
    name: Required[str]  # Capability name
    resolve_inheritance: NotRequired[bool]  # Whether to resolve inheritance chain


class ProfileResolveCapabilitiesData(TypedDict):
    """Resolve all capabilities for a profile including inherited."""
    name: Required[str]  # Profile name
    include_permissions: NotRequired[bool]  # Include resolved permissions
    include_knowledge: NotRequired[bool]  # Include resolved knowledge


@event_handler("capability:load")
async def handle_load_capability(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Load and resolve a capability definition."""
    from ksi_common.event_parser import event_format_linter
    data = event_format_linter(raw_data, CapabilityLoadData)
    
    if not event_emitter:
        return error_response("Event system not initialized", context)
    
    capability_name = data['name']
    resolve_inheritance = data.get('resolve_inheritance', True)
    
    # Check cache first
    if capability_name in _capability_cache:
        capability = _capability_cache[capability_name]
        logger.debug(f"Loaded capability {capability_name} from cache")
    else:
        # Load from file
        capability_path = Path(config.compositions_dir) / "capabilities" / f"{capability_name}.yaml"
        
        if not capability_path.exists():
            return error_response(f"Capability not found: {capability_name}", context)
        
        try:
            capability_data = load_yaml_file(capability_path)
            capability = CapabilityDefinition(capability_name, capability_data)
            
            # Cache the capability
            _capability_cache[capability_name] = capability
            
            logger.debug(f"Loaded capability {capability_name} from file")
            
        except Exception as e:
            return error_response(f"Failed to load capability {capability_name}: {e}", context)
    
    # Resolve inheritance if requested
    result = capability.to_dict()
    
    if resolve_inheritance:
        try:
            # Create a loader function for recursive resolution
            async def capability_loader(name: str) -> Optional[CapabilityDefinition]:
                load_result = await event_emitter("capability:load", {
                    "name": name,
                    "resolve_inheritance": False  # Avoid infinite recursion
                })
                
                if load_result and isinstance(load_result, list):
                    load_result = load_result[0]
                
                if load_result and not load_result.get('error'):
                    # Reconstruct capability from result
                    return CapabilityDefinition(name, load_result)
                return None
            
            # Resolve permissions and knowledge
            resolved_permissions = await capability.resolve_permissions(capability_loader)
            resolved_knowledge = await capability.resolve_knowledge(capability_loader)
            
            result['resolved_permissions'] = resolved_permissions
            result['resolved_knowledge'] = resolved_knowledge
            
        except Exception as e:
            logger.error(f"Failed to resolve inheritance for capability {capability_name}: {e}")
            # Return basic capability without inheritance resolution
    
    return event_response_builder(result, context=context)


@event_handler("profile:resolve_capabilities")
async def handle_resolve_capabilities(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Resolve all capabilities for a profile including inherited."""
    from ksi_common.event_parser import event_format_linter
    data = event_format_linter(raw_data, ProfileResolveCapabilitiesData)
    
    if not event_emitter:
        return error_response("Event system not initialized", context)
    
    profile_name = data['name']
    include_permissions = data.get('include_permissions', True)
    include_knowledge = data.get('include_knowledge', True)
    
    try:
        # Get profile's declared capabilities
        attr_result = await event_emitter("profile:get_attributes", {
            "name": profile_name,
            "attributes": ["capability"]
        })
        
        if attr_result and isinstance(attr_result, list):
            attr_result = attr_result[0] if attr_result else {}
        
        if not attr_result or "attributes" not in attr_result:
            return event_response_builder({
                "profile": profile_name,
                "capabilities": [],
                "resolved_permissions": {},
                "resolved_knowledge": {}
            }, context=context)
        
        declared_capabilities = attr_result["attributes"].get("capability", [])
        if not isinstance(declared_capabilities, list):
            declared_capabilities = [declared_capabilities] if declared_capabilities else []
        
        # Resolve each capability
        resolved_capabilities = {}
        merged_permissions = {}
        merged_knowledge = {}
        
        for capability_name in declared_capabilities:
            # Load capability with inheritance resolution
            cap_result = await event_emitter("capability:load", {
                "name": capability_name,
                "resolve_inheritance": True
            })
            
            if cap_result and isinstance(cap_result, list):
                cap_result = cap_result[0]
            
            if cap_result and not cap_result.get('error'):
                resolved_capabilities[capability_name] = cap_result
                
                # Merge permissions
                if include_permissions and 'resolved_permissions' in cap_result:
                    for perm_type, perm_list in cap_result['resolved_permissions'].items():
                        if perm_type in merged_permissions:
                            merged_permissions[perm_type] = list(set(merged_permissions[perm_type] + perm_list))
                        else:
                            merged_permissions[perm_type] = perm_list[:]
                
                # Merge knowledge
                if include_knowledge and 'resolved_knowledge' in cap_result:
                    merged_knowledge.update(cap_result['resolved_knowledge'])
            else:
                logger.warning(f"Failed to resolve capability {capability_name} for profile {profile_name}")
        
        result = {
            "profile": profile_name,
            "capabilities": resolved_capabilities,
            "declared_capabilities": declared_capabilities
        }
        
        if include_permissions:
            result["resolved_permissions"] = merged_permissions
        
        if include_knowledge:
            result["resolved_knowledge"] = merged_knowledge
        
        return event_response_builder(result, context=context)
        
    except Exception as e:
        return error_response(f"Failed to resolve capabilities for profile {profile_name}: {e}", context)


@event_handler("capability:list")
async def handle_list_capabilities(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """List all available capabilities."""
    if not event_emitter:
        return error_response("Event system not initialized", context)
    
    capabilities_dir = Path(config.compositions_dir) / "capabilities"
    if not capabilities_dir.exists():
        return event_response_builder({"capabilities": []}, context=context)
    
    try:
        capabilities = []
        for yaml_file in capabilities_dir.glob("*.yaml"):
            try:
                capability_data = load_yaml_file(yaml_file)
                if capability_data and 'name' in capability_data:
                    capabilities.append({
                        "name": capability_data['name'],
                        "description": capability_data.get('description', ''),
                        "extends": capability_data.get('extends'),
                        "category": capability_data.get('metadata', {}).get('category', 'unknown'),
                        "tags": capability_data.get('metadata', {}).get('tags', [])
                    })
            except Exception as e:
                logger.warning(f"Failed to load capability from {yaml_file}: {e}")
                continue
        
        return event_response_builder({"capabilities": capabilities}, context=context)
        
    except Exception as e:
        return error_response(f"Failed to list capabilities: {e}", context)


@event_handler("capability:validate")
async def handle_validate_capability(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Validate a capability definition."""
    from ksi_common.event_parser import event_format_linter
    data = event_format_linter(raw_data, CapabilityLoadData)
    
    if not event_emitter:
        return error_response("Event system not initialized", context)
    
    capability_name = data['name']
    
    try:
        # Load capability
        cap_result = await event_emitter("capability:load", {
            "name": capability_name,
            "resolve_inheritance": True
        })
        
        if cap_result and isinstance(cap_result, list):
            cap_result = cap_result[0]
        
        if cap_result and cap_result.get('error'):
            return event_response_builder({
                "capability": capability_name,
                "valid": False,
                "errors": [cap_result['error']]
            }, context=context)
        
        # Validation checks
        errors = []
        warnings = []
        
        if not cap_result:
            errors.append("Capability could not be loaded")
        else:
            # Check required fields
            required_fields = ['name', 'permissions']
            for field in required_fields:
                if field not in cap_result:
                    errors.append(f"Missing required field: {field}")
            
            # Check permissions format
            if 'permissions' in cap_result:
                permissions = cap_result['permissions']
                if not isinstance(permissions, dict):
                    errors.append("Permissions must be a dictionary")
                else:
                    for perm_type, perm_list in permissions.items():
                        if not isinstance(perm_list, list):
                            errors.append(f"Permission {perm_type} must be a list")
            
            # Check inheritance chain
            if 'extends' in cap_result and cap_result['extends']:
                parent_result = await event_emitter("capability:load", {
                    "name": cap_result['extends'],
                    "resolve_inheritance": False
                })
                
                if parent_result and isinstance(parent_result, list):
                    parent_result = parent_result[0]
                
                if not parent_result or parent_result.get('error'):
                    errors.append(f"Parent capability not found: {cap_result['extends']}")
        
        is_valid = len(errors) == 0
        
        result = {
            "capability": capability_name,
            "valid": is_valid,
            "errors": errors,
            "warnings": warnings
        }
        
        return event_response_builder(result, context=context)
        
    except Exception as e:
        return error_response(f"Failed to validate capability {capability_name}: {e}", context)