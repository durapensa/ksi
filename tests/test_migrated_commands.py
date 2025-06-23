#!/usr/bin/env python3
"""
Test script for migrated daemon commands
Tests the new command registry pattern implementation
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CommandTester:
    """Test harness for daemon commands"""
    
    def __init__(self, socket_path: str = "sockets/claude_daemon.sock"):
        self.socket_path = socket_path
        self.results = {}
        
    async def send_command(self, command_name: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a command to the daemon and return the response"""
        try:
            reader, writer = await asyncio.open_unix_connection(self.socket_path)
            
            command = {
                "command": command_name,
                "version": "2.0",
                "parameters": parameters or {}
            }
            
            logger.info(f"Sending command: {command_name}")
            writer.write(json.dumps(command).encode() + b'\n')
            await writer.drain()
            
            response_data = await reader.readline()
            response = json.loads(response_data.decode())
            
            writer.close()
            await writer.wait_closed()
            
            return response
            
        except Exception as e:
            logger.error(f"Error sending command {command_name}: {e}")
            return {"status": "error", "error": str(e)}
    
    async def test_agent_management(self):
        """Test agent management commands"""
        logger.info("\n=== Testing Agent Management Commands ===")
        
        # Test REGISTER_AGENT
        result = await self.send_command("REGISTER_AGENT", {
            "agent_id": "test_agent_001",
            "role": "test_agent",
            "capabilities": ["testing", "validation", "reporting"]
        })
        self.results["REGISTER_AGENT"] = result
        logger.info(f"REGISTER_AGENT result: {result.get('status')}")
        
        # Test GET_AGENTS
        result = await self.send_command("GET_AGENTS")
        self.results["GET_AGENTS"] = result
        logger.info(f"GET_AGENTS result: {result.get('status')}, agents count: {len(result.get('result', {}).get('agents', {}))}")
        
        # Test SPAWN_AGENT (may fail if compositions not available)
        result = await self.send_command("SPAWN_AGENT", {
            "task": "Test the new command system",
            "role": "tester",
            "capabilities": ["testing"],
            "context": "This is a test agent for validating the new command system"
        })
        self.results["SPAWN_AGENT"] = result
        logger.info(f"SPAWN_AGENT result: {result.get('status')}")
        
        # Test ROUTE_TASK
        result = await self.send_command("ROUTE_TASK", {
            "task": "Validate all migrated commands",
            "required_capabilities": ["testing", "validation"],
            "context": "Part of the daemon refactoring test suite"
        })
        self.results["ROUTE_TASK"] = result
        logger.info(f"ROUTE_TASK result: {result.get('status')}")
    
    async def test_message_bus(self):
        """Test message bus commands"""
        logger.info("\n=== Testing Message Bus Commands ===")
        
        # Test SUBSCRIBE (will fail if agent not connected)
        result = await self.send_command("SUBSCRIBE", {
            "agent_id": "test_agent_001",
            "event_types": ["DIRECT_MESSAGE", "BROADCAST", "TASK_ASSIGNMENT"]
        })
        self.results["SUBSCRIBE"] = result
        logger.info(f"SUBSCRIBE result: {result.get('status')}")
        
        # Test PUBLISH
        result = await self.send_command("PUBLISH", {
            "from_agent": "test_system",
            "event_type": "BROADCAST",
            "payload": {
                "message": "Testing the new PUBLISH command",
                "test": True,
                "timestamp": "2025-01-23T12:00:00Z"
            }
        })
        self.results["PUBLISH"] = result
        logger.info(f"PUBLISH result: {result.get('status')}")
        
        # Test PUBLISH with DIRECT_MESSAGE
        result = await self.send_command("PUBLISH", {
            "from_agent": "test_system",
            "event_type": "DIRECT_MESSAGE",
            "payload": {
                "to": "test_agent_001",
                "message": "Direct message test",
                "metadata": {"priority": "low", "test": True}
            }
        })
        self.results["PUBLISH_DIRECT"] = result
        logger.info(f"PUBLISH (DIRECT_MESSAGE) result: {result.get('status')}")
    
    async def test_existing_commands(self):
        """Test previously migrated commands"""
        logger.info("\n=== Testing Previously Migrated Commands ===")
        
        # Test HEALTH_CHECK
        result = await self.send_command("HEALTH_CHECK")
        self.results["HEALTH_CHECK"] = result
        logger.info(f"HEALTH_CHECK result: {result.get('status')}")
        
        # Test GET_PROCESSES
        result = await self.send_command("GET_PROCESSES")
        self.results["GET_PROCESSES"] = result
        logger.info(f"GET_PROCESSES result: {result.get('status')}, process count: {len(result.get('result', {}).get('processes', []))}")
        
        # Test SET_SHARED
        result = await self.send_command("SET_SHARED", {
            "key": "test_key",
            "value": {"test": True, "timestamp": "2025-01-23", "data": [1, 2, 3]}
        })
        self.results["SET_SHARED"] = result
        logger.info(f"SET_SHARED result: {result.get('status')}")
        
        # Test GET_SHARED
        result = await self.send_command("GET_SHARED", {
            "key": "test_key"
        })
        self.results["GET_SHARED"] = result
        logger.info(f"GET_SHARED result: {result.get('status')}, value retrieved: {result.get('result', {}).get('value') is not None}")
    
    async def test_error_cases(self):
        """Test error handling in migrated commands"""
        logger.info("\n=== Testing Error Cases ===")
        
        # Test REGISTER_AGENT with missing parameters
        result = await self.send_command("REGISTER_AGENT", {
            "agent_id": "error_test"
            # Missing required 'role' parameter
        })
        self.results["REGISTER_AGENT_ERROR"] = result
        logger.info(f"REGISTER_AGENT (missing params) result: {result.get('status')}, error: {result.get('error_code')}")
        
        # Test SUBSCRIBE with non-existent agent
        result = await self.send_command("SUBSCRIBE", {
            "agent_id": "non_existent_agent",
            "event_types": ["BROADCAST"]
        })
        self.results["SUBSCRIBE_ERROR"] = result
        logger.info(f"SUBSCRIBE (non-existent agent) result: {result.get('status')}, error: {result.get('error_code')}")
        
        # Test PUBLISH with invalid event type payload
        result = await self.send_command("PUBLISH", {
            "from_agent": "test_system",
            "event_type": "DIRECT_MESSAGE",
            "payload": {
                # Missing required 'to' field for DIRECT_MESSAGE
                "message": "This should fail validation"
            }
        })
        self.results["PUBLISH_ERROR"] = result
        logger.info(f"PUBLISH (invalid payload) result: {result.get('status')}, error: {result.get('error_code')}")
    
    async def test_identity_management(self):
        """Test identity management commands"""
        logger.info("\n--- Testing Identity Management ---")
        
        # Test agent_id for identity tests
        test_agent_id = "test_identity_001"
        
        # 1. Test LIST_IDENTITIES (should be empty or have existing identities)
        result = await self.send_command("LIST_IDENTITIES")
        self.results["LIST_IDENTITIES"] = result
        logger.info(f"LIST_IDENTITIES result: {result.get('status')}")
        
        # Store initial count for comparison later
        initial_count = 0
        if result.get('status') == 'success' and 'result' in result:
            initial_count = result['result'].get('total', 0)
            logger.info(f"Initial identity count: {initial_count}")
        
        # 2. Test GET_IDENTITY (should fail for non-existent identity)
        result = await self.send_command("GET_IDENTITY", {
            "agent_id": test_agent_id
        })
        self.results["GET_IDENTITY_NOT_FOUND"] = result
        expected_error = result.get('status') == 'error' and result.get('error', {}).get('code') == 'IDENTITY_NOT_FOUND'
        logger.info(f"GET_IDENTITY (not found) result: {'PASS' if expected_error else 'FAIL'}")
        
        # 3. Test CREATE_IDENTITY
        result = await self.send_command("CREATE_IDENTITY", {
            "agent_id": test_agent_id,
            "display_name": "Test Identity",
            "role": "researcher",
            "personality_traits": ["analytical", "thorough", "test-oriented"]
        })
        self.results["CREATE_IDENTITY"] = result
        logger.info(f"CREATE_IDENTITY result: {result.get('status')}")
        
        # Verify the created identity has all expected fields
        if result.get('status') == 'success':
            identity = result.get('result', {}).get('identity', {})
            required_fields = ['identity_uuid', 'agent_id', 'display_name', 'role', 
                             'personality_traits', 'appearance', 'created_at', 'last_active',
                             'conversation_count', 'sessions', 'preferences', 'stats']
            missing_fields = [f for f in required_fields if f not in identity]
            if missing_fields:
                logger.warning(f"Created identity missing fields: {missing_fields}")
            else:
                logger.info("Created identity has all required fields")
        
        # 4. Test CREATE_IDENTITY duplicate (should fail)
        result = await self.send_command("CREATE_IDENTITY", {
            "agent_id": test_agent_id,
            "display_name": "Duplicate Test"
        })
        self.results["CREATE_IDENTITY_DUPLICATE"] = result
        expected_error = result.get('status') == 'error' and result.get('error', {}).get('code') == 'IDENTITY_EXISTS'
        logger.info(f"CREATE_IDENTITY (duplicate) result: {'PASS' if expected_error else 'FAIL'}")
        
        # 5. Test GET_IDENTITY (should succeed now)
        result = await self.send_command("GET_IDENTITY", {
            "agent_id": test_agent_id
        })
        self.results["GET_IDENTITY"] = result
        logger.info(f"GET_IDENTITY result: {result.get('status')}")
        
        # 6. Test UPDATE_IDENTITY
        result = await self.send_command("UPDATE_IDENTITY", {
            "agent_id": test_agent_id,
            "updates": {
                "display_name": "Updated Test Identity",
                "role": "analyst",
                "personality_traits": ["analytical", "thorough", "updated"]
            }
        })
        self.results["UPDATE_IDENTITY"] = result
        logger.info(f"UPDATE_IDENTITY result: {result.get('status')}")
        
        # Verify the update worked
        if result.get('status') == 'success':
            changes = result.get('result', {}).get('changes', [])
            logger.info(f"Updated fields: {changes}")
        
        # 7. Test LIST_IDENTITIES (should show our test identity)
        result = await self.send_command("LIST_IDENTITIES")
        self.results["LIST_IDENTITIES_AFTER_CREATE"] = result
        if result.get('status') == 'success':
            new_count = result.get('result', {}).get('total', 0)
            logger.info(f"Identity count after create: {new_count} (expected: {initial_count + 1})")
            
            # Verify our test identity is in the list
            items = result.get('result', {}).get('items', [])
            test_identity_found = any(item.get('agent_id') == test_agent_id for item in items)
            logger.info(f"Test identity found in list: {test_identity_found}")
        
        # 8. Test LIST_IDENTITIES with filters
        result = await self.send_command("LIST_IDENTITIES", {
            "filter_role": "analyst",
            "sort_by": "display_name",
            "order": "asc"
        })
        self.results["LIST_IDENTITIES_FILTERED"] = result
        logger.info(f"LIST_IDENTITIES (filtered) result: {result.get('status')}")
        
        # 9. Test UPDATE_IDENTITY with protected field (should be ignored)
        result = await self.send_command("UPDATE_IDENTITY", {
            "agent_id": test_agent_id,
            "updates": {
                "agent_id": "should_not_change",
                "identity_uuid": "should_not_change",
                "created_at": "should_not_change",
                "display_name": "Protected Field Test"
            }
        })
        self.results["UPDATE_IDENTITY_PROTECTED"] = result
        logger.info(f"UPDATE_IDENTITY (protected fields) result: {result.get('status')}")
        
        # 10. Test REMOVE_IDENTITY
        result = await self.send_command("REMOVE_IDENTITY", {
            "agent_id": test_agent_id
        })
        self.results["REMOVE_IDENTITY"] = result
        logger.info(f"REMOVE_IDENTITY result: {result.get('status')}")
        
        # Verify the identity was removed
        if result.get('status') == 'success':
            removed_identity = result.get('result', {}).get('identity', {})
            logger.info(f"Removed identity: {removed_identity.get('display_name', 'unknown')}")
        
        # 11. Test REMOVE_IDENTITY (should fail now)
        result = await self.send_command("REMOVE_IDENTITY", {
            "agent_id": test_agent_id
        })
        self.results["REMOVE_IDENTITY_NOT_FOUND"] = result
        expected_error = result.get('status') == 'error' and result.get('error', {}).get('code') == 'IDENTITY_NOT_FOUND'
        logger.info(f"REMOVE_IDENTITY (not found) result: {'PASS' if expected_error else 'FAIL'}")
        
        # 12. Test UPDATE_IDENTITY on non-existent identity
        result = await self.send_command("UPDATE_IDENTITY", {
            "agent_id": test_agent_id,
            "updates": {"display_name": "Should fail"}
        })
        self.results["UPDATE_IDENTITY_NOT_FOUND"] = result
        expected_error = result.get('status') == 'error' and result.get('error', {}).get('code') == 'IDENTITY_NOT_FOUND'
        logger.info(f"UPDATE_IDENTITY (not found) result: {'PASS' if expected_error else 'FAIL'}")
        
        logger.info("Identity management tests completed")
    
    async def test_composition_system(self):
        """Test composition system commands"""
        logger.info("\n--- Testing Composition System ---")
        
        # 1. Test GET_COMPOSITIONS (should list available compositions)
        result = await self.send_command("GET_COMPOSITIONS")
        self.results["GET_COMPOSITIONS"] = result
        logger.info(f"GET_COMPOSITIONS result: {result.get('status')}")
        
        # Store available compositions for later tests
        available_compositions = []
        if result.get('status') == 'success' and 'result' in result:
            items = result['result'].get('items', [])
            available_compositions = [comp['name'] for comp in items]
            logger.info(f"Found {len(available_compositions)} compositions: {', '.join(available_compositions[:3])}")
        
        # 2. Test GET_COMPOSITIONS with filtering
        result = await self.send_command("GET_COMPOSITIONS", {
            "include_metadata": False
        })
        self.results["GET_COMPOSITIONS_NO_METADATA"] = result
        logger.info(f"GET_COMPOSITIONS (no metadata) result: {result.get('status')}")
        
        # 3. Test GET_COMPOSITIONS with category filter
        result = await self.send_command("GET_COMPOSITIONS", {
            "category": "agent"
        })
        self.results["GET_COMPOSITIONS_FILTERED"] = result
        logger.info(f"GET_COMPOSITIONS (category filter) result: {result.get('status')}")
        
        # Use a known composition for detailed tests (fallback to first available)
        test_composition = "claude_agent_default"
        if available_compositions and test_composition not in available_compositions:
            test_composition = available_compositions[0]
        
        if available_compositions:
            # 4. Test GET_COMPOSITION (should succeed)
            result = await self.send_command("GET_COMPOSITION", {
                "name": test_composition
            })
            self.results["GET_COMPOSITION"] = result
            logger.info(f"GET_COMPOSITION result: {result.get('status')}")
            
            # Store composition details for validation tests
            composition_data = None
            if result.get('status') == 'success':
                composition_data = result.get('result', {})
                required_context = composition_data.get('required_context', {})
                logger.info(f"Composition '{test_composition}' requires context: {list(required_context.keys())}")
            
            # 5. Test VALIDATE_COMPOSITION with proper context
            if composition_data:
                # Build valid context based on required_context
                test_context = {}
                for key, description in composition_data.get('required_context', {}).items():
                    if key == 'user_prompt':
                        test_context[key] = "Test user prompt for validation"
                    elif key == 'daemon_commands':
                        test_context[key] = "Test daemon commands data"
                    else:
                        test_context[key] = f"Test value for {key}"
                
                result = await self.send_command("VALIDATE_COMPOSITION", {
                    "name": test_composition,
                    "context": test_context
                })
                self.results["VALIDATE_COMPOSITION"] = result
                logger.info(f"VALIDATE_COMPOSITION result: {result.get('status')}")
                
                if result.get('status') == 'success':
                    validation_result = result.get('result', {})
                    logger.info(f"Validation valid: {validation_result.get('valid')}")
                    if not validation_result.get('valid'):
                        logger.info(f"Validation issues: {validation_result.get('issues', [])}")
            
            # 6. Test VALIDATE_COMPOSITION with missing context (should fail validation)
            result = await self.send_command("VALIDATE_COMPOSITION", {
                "name": test_composition,
                "context": {}
            })
            self.results["VALIDATE_COMPOSITION_MISSING_CONTEXT"] = result
            validation_result = result.get('result', {})
            expected_invalid = result.get('status') == 'success' and not validation_result.get('valid', True)
            logger.info(f"VALIDATE_COMPOSITION (missing context) result: {'PASS' if expected_invalid else 'FAIL'}")
            
            # 7. Test COMPOSE_PROMPT with valid context
            if composition_data and test_context:
                result = await self.send_command("COMPOSE_PROMPT", {
                    "composition": test_composition,
                    "context": test_context
                })
                self.results["COMPOSE_PROMPT"] = result
                logger.info(f"COMPOSE_PROMPT result: {result.get('status')}")
                
                if result.get('status') == 'success':
                    prompt_result = result.get('result', {})
                    prompt_length = prompt_result.get('prompt_analysis', {}).get('length_chars', 0)
                    logger.info(f"Composed prompt length: {prompt_length} characters")
            
            # 8. Test COMPOSE_PROMPT with missing context (should fail)
            result = await self.send_command("COMPOSE_PROMPT", {
                "composition": test_composition,
                "context": {}
            })
            self.results["COMPOSE_PROMPT_MISSING_CONTEXT"] = result
            expected_error = result.get('status') == 'error'
            logger.info(f"COMPOSE_PROMPT (missing context) result: {'PASS' if expected_error else 'FAIL'}")
        
        # 9. Test GET_COMPOSITION with non-existent composition (should fail)
        result = await self.send_command("GET_COMPOSITION", {
            "name": "nonexistent_composition_test"
        })
        self.results["GET_COMPOSITION_NOT_FOUND"] = result
        expected_error = result.get('status') == 'error' and result.get('error', {}).get('code') == 'COMPOSITION_NOT_FOUND'
        logger.info(f"GET_COMPOSITION (not found) result: {'PASS' if expected_error else 'FAIL'}")
        
        # 10. Test LIST_COMPONENTS (should list all components)
        result = await self.send_command("LIST_COMPONENTS")
        self.results["LIST_COMPONENTS"] = result
        logger.info(f"LIST_COMPONENTS result: {result.get('status')}")
        
        if result.get('status') == 'success':
            components_result = result.get('result', {})
            total_components = components_result.get('total', 0)
            directories = list(components_result.get('by_directory', {}).keys())
            logger.info(f"Found {total_components} components in {len(directories)} directories")
        
        # 11. Test LIST_COMPONENTS with directory filter
        result = await self.send_command("LIST_COMPONENTS", {
            "directory": "conversation_patterns"
        })
        self.results["LIST_COMPONENTS_FILTERED"] = result
        logger.info(f"LIST_COMPONENTS (filtered) result: {result.get('status')}")
        
        # 12. Test LIST_COMPONENTS with invalid directory (should fail)
        result = await self.send_command("LIST_COMPONENTS", {
            "directory": "nonexistent_directory_test"
        })
        self.results["LIST_COMPONENTS_INVALID_DIR"] = result
        expected_error = result.get('status') == 'error' and result.get('error', {}).get('code') == 'DIRECTORY_NOT_FOUND'
        logger.info(f"LIST_COMPONENTS (invalid dir) result: {'PASS' if expected_error else 'FAIL'}")
        
        # 13. Test VALIDATE_COMPOSITION with non-existent composition (should fail)
        result = await self.send_command("VALIDATE_COMPOSITION", {
            "name": "nonexistent_composition_test",
            "context": {"test": "value"}
        })
        self.results["VALIDATE_COMPOSITION_NOT_FOUND"] = result
        expected_error = result.get('status') == 'error' and result.get('error', {}).get('code') == 'COMPOSITION_NOT_FOUND'
        logger.info(f"VALIDATE_COMPOSITION (not found) result: {'PASS' if expected_error else 'FAIL'}")
        
        # 14. Test COMPOSE_PROMPT with non-existent composition (should fail)
        result = await self.send_command("COMPOSE_PROMPT", {
            "composition": "nonexistent_composition_test",
            "context": {"test": "value"}
        })
        self.results["COMPOSE_PROMPT_NOT_FOUND"] = result
        expected_error = result.get('status') == 'error' and result.get('error', {}).get('code') == 'COMPOSITION_NOT_FOUND'
        logger.info(f"COMPOSE_PROMPT (not found) result: {'PASS' if expected_error else 'FAIL'}")
        
        logger.info("Composition system tests completed")
    
    def print_summary(self):
        """Print test summary"""
        logger.info("\n=== Test Summary ===")
        success_count = sum(1 for r in self.results.values() if r.get('status') == 'success')
        error_count = sum(1 for r in self.results.values() if r.get('status') == 'error')
        total_count = len(self.results)
        
        logger.info(f"Total tests: {total_count}")
        logger.info(f"Successful: {success_count}")
        logger.info(f"Errors: {error_count}")
        
        if error_count > 0:
            logger.info("\nFailed tests:")
            for cmd, result in self.results.items():
                if result.get('status') == 'error':
                    logger.info(f"  - {cmd}: {result.get('error_code', 'unknown')} - {result.get('error_message', 'no message')}")
        
        # Save detailed results
        with open('tests/migrated_commands_results.json', 'w') as f:
            json.dump(self.results, f, indent=2)
        logger.info("\nDetailed results saved to tests/migrated_commands_results.json")
    
    async def run_all_tests(self):
        """Run all test suites"""
        await self.test_agent_management()
        await asyncio.sleep(0.5)  # Give daemon time to process
        
        await self.test_message_bus()
        await asyncio.sleep(0.5)
        
        await self.test_existing_commands()
        await asyncio.sleep(0.5)
        
        await self.test_error_cases()
        await asyncio.sleep(0.5)
        
        await self.test_identity_management()
        await asyncio.sleep(0.5)
        
        await self.test_composition_system()
        
        self.print_summary()


async def main():
    """Main test runner"""
    logger.info("Starting migrated commands test suite...")
    logger.info("Make sure the daemon is running before running these tests!")
    
    tester = CommandTester()
    
    try:
        await tester.run_all_tests()
    except Exception as e:
        logger.error(f"Test suite failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())