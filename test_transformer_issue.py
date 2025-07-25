#!/usr/bin/env python3
"""
Test script to debug why transformers aren't being applied to agent:spawned events.
"""
import asyncio
import json
import time
from pathlib import Path

# Add KSI to path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from ksi_daemon.event_system import get_router, event_handler
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("test_transformer_issue")

# Track what events we see
events_seen = []

@event_handler("monitor:agent_created")
async def handle_monitor_agent_created(data, context=None):
    """Handler that should be triggered by transformer."""
    logger.info(f"✅ TRANSFORMER WORKED! monitor:agent_created received: {data}")
    events_seen.append(("monitor:agent_created", data, context))
    return {"status": "received"}

@event_handler("state:entity:create")
async def handle_state_entity_create(data, context=None):
    """Handler that should be triggered by transformer."""
    logger.info(f"✅ TRANSFORMER WORKED! state:entity:create received: {data}")
    events_seen.append(("state:entity:create", data, context))
    return {"status": "created", "entity_id": data.get("id")}

@event_handler("agent:spawned")
async def handle_agent_spawned(data, context=None):
    """Direct handler for agent:spawned events."""
    logger.info(f"📍 agent:spawned handler received: {data}")
    logger.info(f"📍 Context: {context}")
    events_seen.append(("agent:spawned", data, context))
    return {"status": "acknowledged"}

async def test_transformer_behavior():
    """Test transformer application with different emission patterns."""
    router = get_router()
    
    # Load transformers manually
    logger.info("Loading agent routing transformers...")
    transformer_config = {
        "transformers": [
            {
                "name": "agent_spawned_monitor",
                "source": "agent:spawned",
                "target": "monitor:agent_created",
                "mapping": {
                    "agent_id": "{{agent_id}}",
                    "profile": "{{profile}}",
                    "timestamp": "{{timestamp_utc()}}"
                }
            },
            {
                "name": "agent_spawned_state_create",
                "source": "agent:spawned",
                "target": "state:entity:create",
                "mapping": {
                    "type": "agent",
                    "id": "{{agent_id}}",
                    "properties": {
                        "agent_id": "{{agent_id}}",
                        "status": "active",
                        "sandbox_uuid": "{{sandbox_uuid}}"
                    }
                }
            }
        ]
    }
    
    # Register transformers
    for transformer in transformer_config["transformers"]:
        await router.emit("router:register_transformer", {"transformer": transformer})
    
    await asyncio.sleep(0.1)  # Let registration complete
    
    # Test 1: Direct emission (like CLI)
    logger.info("\n=== TEST 1: Direct emission (CLI-style) ===")
    events_seen.clear()
    
    result = await router.emit("agent:spawned", {
        "agent_id": "test_agent_1",
        "profile": "base_agent",
        "sandbox_uuid": "uuid-123"
    })
    
    await asyncio.sleep(0.5)  # Let transformers run
    logger.info(f"Direct emission result: {result}")
    logger.info(f"Events seen: {[e[0] for e in events_seen]}")
    
    # Test 2: Emission with context (like agent service)
    logger.info("\n=== TEST 2: Emission with context (agent service-style) ===")
    events_seen.clear()
    
    result = await router.emit("agent:spawned", {
        "agent_id": "test_agent_2",
        "profile": "base_agent",
        "sandbox_uuid": "uuid-456"
    }, {"_agent_id": "spawning_agent"})
    
    await asyncio.sleep(0.5)  # Let transformers run
    logger.info(f"Context emission result: {result}")
    logger.info(f"Events seen: {[e[0] for e in events_seen]}")
    
    # Test 3: Check transformer registration
    logger.info("\n=== TEST 3: Checking transformer registration ===")
    logger.info(f"Transformers for agent:spawned: {len(router._transformers.get('agent:spawned', []))}")
    for t in router._transformers.get('agent:spawned', []):
        logger.info(f"  - {t.get('name')}: {t.get('source')} -> {t.get('target')}")

if __name__ == "__main__":
    asyncio.run(test_transformer_behavior())