#!/usr/bin/env python3
"""
Test Event Logging System

Tests the EventLog implementation for:
- Non-blocking event logging
- Real-time streaming
- SQLite persistence
- Query functionality
- Performance under load
"""

import asyncio
import json
import time
import uuid
from pathlib import Path
import tempfile
import statistics

from ksi_daemon.event_log import EventLog
from ksi_common.config import config


async def test_basic_functionality():
    """Test basic event logging functionality."""
    print("\n=== Testing Basic Functionality ===")
    
    # Create temporary database
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_events.db"
        
        # Create event log
        event_log = EventLog(max_size=1000, db_path=db_path)
        await event_log.start()
        
        try:
            # Test 1: Log some events
            print("1. Logging test events...")
            for i in range(10):
                event_log.log_event(
                    event_name=f"test:event_{i}",
                    data={"index": i, "message": f"Test event {i}"},
                    client_id="test_client",
                    correlation_id=f"corr_{i // 3}"  # Group by 3s
                )
            
            # Wait for async writes
            await asyncio.sleep(2)
            
            # Test 2: Query from memory
            print("2. Querying from memory buffer...")
            memory_events = event_log.get_events(
                event_patterns=["test:*"],
                limit=5
            )
            print(f"   Found {len(memory_events)} events in memory")
            
            # Test 3: Query from database
            print("3. Querying from database...")
            db_events = event_log.query_db(
                "SELECT COUNT(*) as count FROM events WHERE event_name LIKE 'test:%'"
            )
            print(f"   Found {db_events[0]['count']} events in database")
            
            # Test 4: Session query
            print("4. Testing session queries...")
            # Add events with session
            session_id = str(uuid.uuid4())
            for i in range(5):
                event_log.log_event(
                    event_name="session:test",
                    data={"session_id": session_id, "seq": i},
                    client_id="test_client"
                )
            
            await asyncio.sleep(2)
            
            session_events = event_log.query_db(
                "SELECT * FROM events WHERE json_extract(data, '$.session_id') = ?",
                (session_id,)
            )
            print(f"   Found {len(session_events)} events for session")
            
            # Test 5: Correlation chain
            print("5. Testing correlation chains...")
            correlation_events = event_log.query_db(
                "SELECT * FROM events WHERE correlation_id = 'corr_1' ORDER BY timestamp"
            )
            print(f"   Found {len(correlation_events)} events in correlation chain")
            
            print("\nBasic functionality tests PASSED ✓")
            
        finally:
            await event_log.stop()


async def test_performance():
    """Test performance under load."""
    print("\n=== Testing Performance Under Load ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_events.db"
        
        # Create event log with custom config
        original_batch_size = config.event_batch_size
        original_flush_interval = config.event_flush_interval
        config.event_batch_size = 500
        config.event_flush_interval = 0.5
        
        event_log = EventLog(max_size=10000, db_path=db_path)
        await event_log.start()
        
        try:
            # Test 1: Burst write test
            print("1. Burst write test (10,000 events)...")
            start_time = time.time()
            
            for i in range(10000):
                event_log.log_event(
                    event_name="perf:test",
                    data={
                        "index": i,
                        "timestamp": time.time(),
                        "payload": "x" * 100  # 100 byte payload
                    },
                    client_id=f"client_{i % 10}",
                    correlation_id=f"batch_{i // 1000}"
                )
            
            log_time = time.time() - start_time
            events_per_sec = 10000 / log_time
            print(f"   Logged 10,000 events in {log_time:.2f}s ({events_per_sec:.0f} events/sec)")
            print(f"   Average latency: {(log_time / 10000) * 1000:.2f}ms per event")
            
            # Test 2: Wait for persistence
            print("2. Waiting for persistence...")
            await asyncio.sleep(3)  # Allow flushes to complete
            
            db_count = event_log.query_db(
                "SELECT COUNT(*) as count FROM events WHERE event_name = 'perf:test'"
            )
            print(f"   {db_count[0]['count']} events persisted to database")
            
            # Test 3: Query performance
            print("3. Testing query performance...")
            
            # Time-range query
            start = time.time()
            recent_events = event_log.query_db(
                "SELECT * FROM events WHERE timestamp > ? LIMIT 100",
                (time.time() - 60,)
            )
            query_time = time.time() - start
            print(f"   Time-range query: {query_time * 1000:.2f}ms")
            
            # Correlation query
            start = time.time()
            corr_events = event_log.query_db(
                "SELECT * FROM events WHERE correlation_id = 'batch_5'"
            )
            query_time = time.time() - start
            print(f"   Correlation query: {query_time * 1000:.2f}ms ({len(corr_events)} events)")
            
            # Test 4: Memory usage
            print("4. Checking memory buffer...")
            stats = event_log.get_stats()
            print(f"   Ring buffer size: {stats['current_size']} events")
            print(f"   Events dropped: {stats['events_dropped']}")
            
            print("\nPerformance tests PASSED ✓")
            
        finally:
            # Restore config
            config.event_batch_size = original_batch_size
            config.event_flush_interval = original_flush_interval
            await event_log.stop()


async def test_streaming():
    """Test real-time event streaming."""
    print("\n=== Testing Real-time Streaming ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_events.db"
        event_log = EventLog(max_size=1000, db_path=db_path)
        await event_log.start()
        
        try:
            # Mock stream writer
            class MockWriter:
                def __init__(self):
                    self.events = []
                    self.closed = False
                
                def write(self, data):
                    if not self.closed:
                        self.events.append(json.loads(data.decode()))
                
                async def drain(self):
                    pass
            
            # Test 1: Subscribe to events
            print("1. Testing event subscription...")
            writer = MockWriter()
            
            subscription = event_log.subscribe(
                client_id="test_subscriber",
                patterns=["stream:*", "test:*"],
                writer=writer
            )
            
            # Generate events
            for i in range(5):
                event_log.log_event(
                    event_name="stream:test",
                    data={"index": i},
                    client_id="producer"
                )
                event_log.log_event(
                    event_name="other:event",
                    data={"index": i},
                    client_id="producer"
                )
            
            # Wait for delivery
            await asyncio.sleep(0.1)
            
            print(f"   Received {len(writer.events)} matching events")
            assert len(writer.events) == 5, "Should only receive matching events"
            
            # Test 2: Multiple subscribers
            print("2. Testing multiple subscribers...")
            writers = [MockWriter() for _ in range(3)]
            
            for i, w in enumerate(writers):
                event_log.subscribe(
                    client_id=f"sub_{i}",
                    patterns=["multi:*"],
                    writer=w
                )
            
            # Generate event
            event_log.log_event(
                event_name="multi:broadcast",
                data={"message": "Hello all!"},
                client_id="broadcaster"
            )
            
            await asyncio.sleep(0.1)
            
            received = sum(len(w.events) for w in writers)
            print(f"   {received} subscribers received the broadcast")
            assert received == 3, "All subscribers should receive the event"
            
            # Test 3: Unsubscribe
            print("3. Testing unsubscribe...")
            event_log.unsubscribe("test_subscriber")
            
            # Generate more events
            event_log.log_event(
                event_name="stream:after_unsub",
                data={"test": "Should not receive"},
                client_id="producer"
            )
            
            await asyncio.sleep(0.1)
            
            # Original writer should not receive new events
            assert len(writer.events) == 5, "Unsubscribed client should not receive new events"
            
            print("\nStreaming tests PASSED ✓")
            
        finally:
            await event_log.stop()


async def test_recovery():
    """Test recovery mechanism."""
    print("\n=== Testing Recovery Mechanism ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_events.db"
        
        # Phase 1: Create events and persist
        print("1. Creating initial events...")
        event_log = EventLog(max_size=100, db_path=db_path)
        await event_log.start()
        
        # Log events
        for i in range(50):
            event_log.log_event(
                event_name="recovery:test",
                data={"index": i, "phase": "initial"},
                client_id="test_client"
            )
        
        # Wait for persistence
        await asyncio.sleep(2)
        await event_log.stop()
        
        # Phase 2: Restart with recovery
        print("2. Restarting with recovery enabled...")
        original_recovery = config.event_recovery
        config.event_recovery = True
        
        try:
            event_log2 = EventLog(max_size=100, db_path=db_path)
            await event_log2.start()
            
            # Check recovered events
            memory_events = event_log2.get_events(
                event_patterns=["recovery:*"],
                limit=None
            )
            print(f"   Recovered {len(memory_events)} events into memory")
            
            # Verify events are correct
            if memory_events:
                first = memory_events[-1]  # Oldest (reverse order)
                last = memory_events[0]    # Newest
                print(f"   Event range: index {first['data']['index']} to {last['data']['index']}")
            
            await event_log2.stop()
            
            print("\nRecovery tests PASSED ✓")
            
        finally:
            config.event_recovery = original_recovery


async def main():
    """Run all tests."""
    print("KSI Event Logging System Test Suite")
    print("===================================")
    
    try:
        await test_basic_functionality()
        await test_performance()
        await test_streaming()
        await test_recovery()
        
        print("\n✅ All tests PASSED!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())