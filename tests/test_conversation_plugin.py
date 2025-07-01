#!/usr/bin/env python3
"""
Comprehensive test script for the conversation plugin.
Tests all conversation operations including JSON export.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from ksi_client import AsyncClient
from ksi_common.timestamps import timestamp_utc


class ConversationPluginTester:
    """Test all conversation plugin functionality."""
    
    def __init__(self):
        self.client = AsyncClient(client_id="conversation_test")
        self.passed = 0
        self.failed = 0
    
    async def connect(self):
        """Connect to daemon."""
        try:
            await self.client.connect()
            print("✓ Connected to daemon")
            return True
        except Exception as e:
            print(f"✗ Failed to connect: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from daemon."""
        await self.client.disconnect()
        print("✓ Disconnected from daemon")
    
    def report_result(self, test_name: str, success: bool, details: str = ""):
        """Report test result."""
        if success:
            self.passed += 1
            print(f"✓ {test_name}")
            if details:
                print(f"  {details}")
        else:
            self.failed += 1
            print(f"✗ {test_name}")
            if details:
                print(f"  ERROR: {details}")
    
    async def test_list_conversations(self):
        """Test listing conversations."""
        print("\n=== Testing conversation:list ===")
        
        # Basic list
        try:
            result = await self.client.request_event("conversation:list", {})
            if "conversations" in result:
                self.report_result(
                    "List conversations (basic)", 
                    True, 
                    f"Found {len(result['conversations'])} conversations"
                )
            else:
                self.report_result("List conversations (basic)", False, str(result))
        except Exception as e:
            self.report_result("List conversations (basic)", False, str(e))
        
        # List with pagination
        try:
            result = await self.client.request_event("conversation:list", {
                "limit": 5,
                "offset": 0,
                "sort_by": "last_timestamp",
                "reverse": True
            })
            if "conversations" in result:
                self.report_result(
                    "List conversations (paginated)", 
                    True,
                    f"Returned {len(result['conversations'])} of {result.get('total', 0)} total"
                )
            else:
                self.report_result("List conversations (paginated)", False, str(result))
        except Exception as e:
            self.report_result("List conversations (paginated)", False, str(e))
        
        # List with date filter
        try:
            # Get conversations from last 7 days
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=7)
            
            result = await self.client.request_event("conversation:list", {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "sort_by": "message_count"
            })
            if "conversations" in result:
                self.report_result(
                    "List conversations (date filtered)", 
                    True,
                    f"Found {len(result['conversations'])} conversations in last 7 days"
                )
            else:
                self.report_result("List conversations (date filtered)", False, str(result))
        except Exception as e:
            self.report_result("List conversations (date filtered)", False, str(e))
    
    async def test_search_conversations(self):
        """Test searching conversations."""
        print("\n=== Testing conversation:search ===")
        
        # Search by content
        try:
            result = await self.client.request_event("conversation:search", {
                "query": "test",
                "limit": 10,
                "search_in": ["content"]
            })
            if "results" in result:
                self.report_result(
                    "Search conversations (content)", 
                    True,
                    f"Found '{result['query']}' in {result.get('total_conversations', 0)} conversations"
                )
            else:
                self.report_result("Search conversations (content)", False, str(result))
        except Exception as e:
            self.report_result("Search conversations (content)", False, str(e))
        
        # Search by sender
        try:
            result = await self.client.request_event("conversation:search", {
                "query": "claude",
                "search_in": ["sender", "content"]
            })
            if "results" in result:
                self.report_result(
                    "Search conversations (sender + content)", 
                    True,
                    f"Found matches in {len(result.get('results', []))} conversations"
                )
            else:
                self.report_result("Search conversations (sender + content)", False, str(result))
        except Exception as e:
            self.report_result("Search conversations (sender + content)", False, str(e))
    
    async def test_get_conversation(self):
        """Test getting specific conversation."""
        print("\n=== Testing conversation:get ===")
        
        # First get a session_id from list
        try:
            list_result = await self.client.request_event("conversation:list", {"limit": 1})
            if "conversations" in list_result and list_result["conversations"]:
                session_id = list_result["conversations"][0]["session_id"]
                
                # Get full conversation
                result = await self.client.request_event("conversation:get", {
                    "session_id": session_id,
                    "limit": 100
                })
                
                if "messages" in result:
                    self.report_result(
                        "Get conversation (full)", 
                        True,
                        f"Session {session_id}: {len(result['messages'])} messages"
                    )
                    
                    # Test pagination
                    if result['total'] > 10:
                        page_result = await self.client.request_event("conversation:get", {
                            "session_id": session_id,
                            "limit": 10,
                            "offset": 5
                        })
                        if "messages" in page_result:
                            self.report_result(
                                "Get conversation (paginated)",
                                True,
                                f"Got {len(page_result['messages'])} messages with offset 5"
                            )
                        else:
                            self.report_result("Get conversation (paginated)", False, str(page_result))
                else:
                    self.report_result("Get conversation (full)", False, str(result))
            else:
                self.report_result("Get conversation", False, "No conversations available to test")
        except Exception as e:
            self.report_result("Get conversation", False, str(e))
        
        # Test message_bus conversation
        try:
            result = await self.client.request_event("conversation:get", {
                "session_id": "message_bus",
                "limit": 50
            })
            if "messages" in result:
                self.report_result(
                    "Get message_bus conversation",
                    True,
                    f"Found {result['total']} messages in message bus"
                )
            else:
                self.report_result("Get message_bus conversation", False, str(result))
        except Exception as e:
            self.report_result("Get message_bus conversation", False, str(e))
    
    async def test_export_conversation(self):
        """Test exporting conversations in different formats."""
        print("\n=== Testing conversation:export ===")
        
        # First get a session_id
        try:
            list_result = await self.client.request_event("conversation:list", {"limit": 1})
            if "conversations" in list_result and list_result["conversations"]:
                session_id = list_result["conversations"][0]["session_id"]
                
                # Test markdown export
                result = await self.client.request_event("conversation:export", {
                    "session_id": session_id,
                    "format": "markdown"
                })
                
                if "export_path" in result:
                    self.report_result(
                        "Export conversation (markdown)",
                        True,
                        f"Exported to {result['filename']} ({result['size_bytes']} bytes)"
                    )
                    
                    # Verify file exists
                    export_path = Path(result['export_path'])
                    if export_path.exists():
                        self.report_result(
                            "Verify markdown export file",
                            True,
                            f"File exists at {export_path}"
                        )
                    else:
                        self.report_result("Verify markdown export file", False, "File not found")
                else:
                    self.report_result("Export conversation (markdown)", False, str(result))
                
                # Test JSON export (NEW!)
                result = await self.client.request_event("conversation:export", {
                    "session_id": session_id,
                    "format": "json"
                })
                
                if "export_path" in result:
                    self.report_result(
                        "Export conversation (JSON)",
                        True,
                        f"Exported to {result['filename']} ({result['size_bytes']} bytes)"
                    )
                    
                    # Verify JSON file and validate structure
                    export_path = Path(result['export_path'])
                    if export_path.exists():
                        try:
                            with open(export_path, 'r') as f:
                                json_data = json.load(f)
                            
                            # Validate JSON structure
                            required_fields = ['session_id', 'exported_at', 'total_messages', 'messages']
                            has_all_fields = all(field in json_data for field in required_fields)
                            
                            if has_all_fields:
                                self.report_result(
                                    "Validate JSON export structure",
                                    True,
                                    f"Valid JSON with {len(json_data['messages'])} messages"
                                )
                            else:
                                missing = [f for f in required_fields if f not in json_data]
                                self.report_result(
                                    "Validate JSON export structure",
                                    False,
                                    f"Missing fields: {missing}"
                                )
                        except Exception as e:
                            self.report_result("Validate JSON export structure", False, str(e))
                    else:
                        self.report_result("Verify JSON export file", False, "File not found")
                else:
                    self.report_result("Export conversation (JSON)", False, str(result))
                
                # Test invalid format
                result = await self.client.request_event("conversation:export", {
                    "session_id": session_id,
                    "format": "invalid"
                })
                
                if "error" in result and "Unsupported format" in result["error"]:
                    self.report_result(
                        "Export conversation (invalid format)",
                        True,
                        "Correctly rejected invalid format"
                    )
                else:
                    self.report_result("Export conversation (invalid format)", False, 
                                     "Should have rejected invalid format")
                    
            else:
                self.report_result("Export conversation", False, "No conversations available to test")
        except Exception as e:
            self.report_result("Export conversation", False, str(e))
    
    async def test_conversation_stats(self):
        """Test getting conversation statistics."""
        print("\n=== Testing conversation:stats ===")
        
        try:
            result = await self.client.request_event("conversation:stats", {})
            
            expected_fields = [
                'total_conversations', 'total_messages', 'total_size_bytes',
                'total_size_mb', 'earliest_timestamp', 'latest_timestamp',
                'exports_dir', 'cache_age_seconds'
            ]
            
            if all(field in result for field in expected_fields[:4]):  # At minimum need counts
                self.report_result(
                    "Get conversation stats",
                    True,
                    f"{result['total_conversations']} conversations, "
                    f"{result['total_messages']} messages, "
                    f"{result['total_size_mb']} MB"
                )
                
                # Check exports directory
                if 'exports_dir' in result:
                    exports_path = Path(result['exports_dir'])
                    if exports_path.exists():
                        export_count = len(list(exports_path.glob("conversation_*")))
                        self.report_result(
                            "Verify exports directory",
                            True,
                            f"{export_count} export files in {exports_path}"
                        )
                    else:
                        self.report_result("Verify exports directory", False, "Directory not found")
            else:
                self.report_result("Get conversation stats", False, f"Missing fields in: {result}")
        except Exception as e:
            self.report_result("Get conversation stats", False, str(e))
    
    async def run_all_tests(self):
        """Run all tests."""
        print(f"\n{'='*60}")
        print("CONVERSATION PLUGIN TEST SUITE")
        print(f"{'='*60}")
        
        if not await self.connect():
            print("\nCannot proceed without daemon connection.")
            return False
        
        try:
            # Run all test methods
            await self.test_list_conversations()
            await self.test_search_conversations()
            await self.test_get_conversation()
            await self.test_export_conversation()
            await self.test_conversation_stats()
            
        finally:
            await self.disconnect()
        
        # Summary
        print(f"\n{'='*60}")
        print(f"TEST SUMMARY: {self.passed} passed, {self.failed} failed")
        print(f"{'='*60}")
        
        return self.failed == 0


async def main():
    """Run the test suite."""
    # Ensure daemon is running
    print("Note: Ensure daemon is running with ./daemon_control.py start")
    
    tester = ConversationPluginTester()
    success = await tester.run_all_tests()
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())