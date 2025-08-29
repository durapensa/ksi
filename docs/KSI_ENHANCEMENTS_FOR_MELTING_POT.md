# KSI Enhancements for Melting Pot Integration

## Overview

This document details the specific enhancements needed to KSI's infrastructure to support Melting Pot scenario replication and fairness testing.

## Core Enhancements Required

### 1. Spatial State Management

#### Current Gap
KSI's state system doesn't have native spatial indexing for 2D/3D environments.

#### Enhancement Needed
```python
# Add to ksi_daemon/state/spatial_extensions.py

class SpatialStateIndex:
    """Spatial indexing for grid-based state entities."""
    
    def __init__(self, dimensions: int = 2):
        self.dimensions = dimensions
        self.spatial_index = {}  # (x,y) -> Set[entity_id]
        self.entity_positions = {}  # entity_id -> (x,y)
        
    def update_position(self, entity_id: str, x: int, y: int, z: int = 0):
        """Update entity position with O(1) complexity."""
        # Remove old position
        if entity_id in self.entity_positions:
            old_pos = self.entity_positions[entity_id]
            self.spatial_index[old_pos].discard(entity_id)
            
        # Add new position
        new_pos = (x, y) if self.dimensions == 2 else (x, y, z)
        self.entity_positions[entity_id] = new_pos
        
        if new_pos not in self.spatial_index:
            self.spatial_index[new_pos] = set()
        self.spatial_index[new_pos].add(entity_id)
    
    def get_entities_at(self, x: int, y: int) -> Set[str]:
        """Get all entities at position."""
        return self.spatial_index.get((x, y), set())
    
    def get_entities_in_radius(self, x: int, y: int, radius: int) -> List[str]:
        """Get entities within radius (Manhattan distance)."""
        entities = []
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if abs(dx) + abs(dy) <= radius:
                    entities.extend(self.get_entities_at(x + dx, y + dy))
        return entities
```

#### Integration Point
Modify `StateService` to maintain spatial indices:
```python
class StateService(Service):
    def __init__(self):
        # ... existing init ...
        self.spatial_indices = {}  # substrate_id -> SpatialStateIndex
        
    async def handle_entity_update(self, event: Event):
        # ... existing update logic ...
        
        # Update spatial index if position changed
        if "x" in changes or "y" in changes:
            substrate_id = entity.get("substrate_id")
            if substrate_id and substrate_id in self.spatial_indices:
                self.spatial_indices[substrate_id].update_position(
                    entity_id, changes.get("x"), changes.get("y")
                )
```

### 2. Metric Calculation Pipeline

#### Current Gap
No built-in support for game-theoretic metrics like Gini coefficient, Pareto efficiency.

#### Enhancement Needed
```python
# Add to ksi_daemon/metrics/game_theory_metrics.py

class GameTheoryMetrics:
    """Calculate game-theoretic and fairness metrics."""
    
    @staticmethod
    def gini_coefficient(values: List[float]) -> float:
        """Calculate Gini coefficient (0=equality, 1=inequality)."""
        if not values or sum(values) == 0:
            return 0.0
            
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        cumsum = np.cumsum(sorted_vals)
        
        return (2 * np.sum((np.arange(1, n+1)) * sorted_vals)) / \
               (n * np.sum(sorted_vals)) - (n + 1) / n
    
    @staticmethod
    def pareto_efficiency(outcomes: List[Tuple[float, ...]]) -> float:
        """Calculate Pareto efficiency score."""
        # Check if any outcome dominates others
        dominated_count = 0
        for i, outcome1 in enumerate(outcomes):
            for outcome2 in outcomes[i+1:]:
                if all(o1 >= o2 for o1, o2 in zip(outcome1, outcome2)):
                    if any(o1 > o2 for o1, o2 in zip(outcome1, outcome2)):
                        dominated_count += 1
        
        return 1.0 - (dominated_count / len(outcomes))
    
    @staticmethod
    def collective_return(agent_returns: Dict[str, float]) -> float:
        """Average return across all agents."""
        return np.mean(list(agent_returns.values()))
    
    @staticmethod
    def background_equality(returns: Dict[str, float], 
                          population_types: Dict[str, str]) -> float:
        """Equality among background population (1 - Gini of positive returns)."""
        background_returns = [
            r for agent_id, r in returns.items() 
            if population_types.get(agent_id) == "background" and r > 0
        ]
        
        if not background_returns:
            return 1.0
            
        return 1.0 - GameTheoryMetrics.gini_coefficient(background_returns)
```

#### Event Integration
```python
# Emit metrics after each step
await self.event_emitter.emit("melting_pot:metrics:calculated", {
    "substrate_id": substrate_id,
    "step": step_number,
    "metrics": {
        "gini_coefficient": metrics.gini_coefficient(scores),
        "collective_return": metrics.collective_return(returns),
        "pareto_efficiency": metrics.pareto_efficiency(outcomes),
        "background_equality": metrics.background_equality(returns, populations)
    }
})
```

### 3. Binary Data Pipeline for Observations

#### Current Gap
Events are JSON-only, no efficient binary data transmission.

#### Enhancement Needed
```python
# Add to ksi_common/event_extensions.py

class BinaryEventData:
    """Handle binary data in events."""
    
    @staticmethod
    def encode_numpy_array(array: np.ndarray) -> Dict:
        """Encode numpy array for transmission."""
        buffer = io.BytesIO()
        np.save(buffer, array, allow_pickle=False)
        
        return {
            "data": base64.b64encode(buffer.getvalue()).decode('utf-8'),
            "shape": array.shape,
            "dtype": str(array.dtype),
            "encoding": "numpy_base64"
        }
    
    @staticmethod  
    def decode_numpy_array(encoded_data: Dict) -> np.ndarray:
        """Decode numpy array from event data."""
        if encoded_data.get("encoding") != "numpy_base64":
            raise ValueError(f"Unsupported encoding: {encoded_data.get('encoding')}")
            
        buffer = io.BytesIO(base64.b64decode(encoded_data["data"]))
        return np.load(buffer, allow_pickle=False)
    
    @staticmethod
    def encode_rgb_observation(rgb_array: np.ndarray) -> Dict:
        """Optimized RGB encoding using PNG compression."""
        from PIL import Image
        
        # Convert to PIL Image
        image = Image.fromarray(rgb_array.astype(np.uint8), mode='RGB')
        
        # Compress as PNG
        buffer = io.BytesIO()
        image.save(buffer, format='PNG', optimize=True)
        
        return {
            "data": base64.b64encode(buffer.getvalue()).decode('utf-8'),
            "width": rgb_array.shape[1],
            "height": rgb_array.shape[0],
            "encoding": "png_base64"
        }
```

#### Usage in Observations
```python
# In ObservationService
rgb_observation = self.render_observation(agent_id)
encoded = BinaryEventData.encode_rgb_observation(rgb_observation)

await self.emit_event("melting_pot:observation", {
    "agent_id": agent_id,
    "rgb_data": encoded,
    "timestamp": time.time()
})
```

### 4. Scheduled Event System

#### Current Gap
No native support for scheduled/delayed events (needed for resource respawning).

#### Enhancement Needed
```python
# Add to ksi_daemon/scheduling/scheduled_event_service.py

class ScheduledEventService(Service):
    """Handle time-based event scheduling."""
    
    def __init__(self):
        super().__init__()
        self.scheduled_events = []  # Min heap of (timestamp, event, data)
        self.timer_task = None
        
    async def start(self):
        """Start the scheduling service."""
        await super().start()
        self.timer_task = asyncio.create_task(self._process_scheduled())
    
    async def handle_schedule_event(self, event: Event) -> Dict:
        """Schedule an event for future emission.
        
        Event data:
        - event_name: Event to emit
        - event_data: Data for the event
        - delay_ms: Delay in milliseconds
        - recurring: Whether to repeat (optional)
        - interval_ms: Repeat interval (if recurring)
        """
        data = event.data
        timestamp = time.time() + (data["delay_ms"] / 1000)
        
        scheduled = {
            "id": str(uuid.uuid4()),
            "timestamp": timestamp,
            "event_name": data["event_name"],
            "event_data": data["event_data"],
            "recurring": data.get("recurring", False),
            "interval_ms": data.get("interval_ms")
        }
        
        heapq.heappush(self.scheduled_events, 
                      (timestamp, scheduled))
        
        return {"scheduled_id": scheduled["id"]}
    
    async def _process_scheduled(self):
        """Process scheduled events."""
        while True:
            current_time = time.time()
            
            # Process all due events
            while self.scheduled_events:
                if self.scheduled_events[0][0] > current_time:
                    break
                    
                timestamp, scheduled = heapq.heappop(self.scheduled_events)
                
                # Emit the scheduled event
                await self.event_emitter.emit(
                    scheduled["event_name"],
                    scheduled["event_data"]
                )
                
                # Reschedule if recurring
                if scheduled["recurring"]:
                    next_timestamp = timestamp + (scheduled["interval_ms"] / 1000)
                    heapq.heappush(self.scheduled_events,
                                 (next_timestamp, scheduled))
            
            # Sleep until next event or 100ms
            if self.scheduled_events:
                sleep_time = min(0.1, self.scheduled_events[0][0] - time.time())
            else:
                sleep_time = 0.1
                
            await asyncio.sleep(max(0.001, sleep_time))
```

### 5. Performance Monitoring

#### Current Gap
No detailed performance metrics for game environments.

#### Enhancement Needed
```python
# Add to ksi_daemon/monitoring/performance_monitor.py

class PerformanceMonitor:
    """Monitor performance metrics for substrates."""
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.metrics = defaultdict(lambda: deque(maxlen=window_size))
        self.start_times = {}
        
    def start_timer(self, metric_name: str, instance_id: str = None):
        """Start timing a metric."""
        key = f"{metric_name}:{instance_id}" if instance_id else metric_name
        self.start_times[key] = time.perf_counter()
    
    def end_timer(self, metric_name: str, instance_id: str = None):
        """End timing and record metric."""
        key = f"{metric_name}:{instance_id}" if instance_id else metric_name
        
        if key not in self.start_times:
            return
            
        duration_ms = (time.perf_counter() - self.start_times[key]) * 1000
        self.metrics[metric_name].append(duration_ms)
        del self.start_times[key]
    
    def get_stats(self, metric_name: str) -> Dict:
        """Get statistics for a metric."""
        values = list(self.metrics[metric_name])
        
        if not values:
            return {}
            
        return {
            "count": len(values),
            "mean_ms": np.mean(values),
            "median_ms": np.median(values),
            "p95_ms": np.percentile(values, 95),
            "p99_ms": np.percentile(values, 99),
            "min_ms": np.min(values),
            "max_ms": np.max(values)
        }
    
    def get_all_stats(self) -> Dict:
        """Get all performance statistics."""
        return {
            metric: self.get_stats(metric)
            for metric in self.metrics.keys()
        }
```

#### Integration Example
```python
# In substrate step processing
self.perf_monitor.start_timer("step_processing", substrate_id)

# ... process step ...

self.perf_monitor.end_timer("step_processing", substrate_id)

# Emit performance metrics periodically
if step % 100 == 0:
    await self.emit_event("performance:metrics", {
        "substrate_id": substrate_id,
        "metrics": self.perf_monitor.get_all_stats()
    })
```

### 6. Batch Event Processing

#### Current Gap  
Events processed individually, inefficient for high-frequency updates.

#### Enhancement Needed
```python
# Add to ksi_daemon/event_batching.py

class EventBatcher:
    """Batch events for efficient processing."""
    
    def __init__(self, batch_size: int = 100, 
                 max_delay_ms: int = 10):
        self.batch_size = batch_size
        self.max_delay_ms = max_delay_ms
        self.pending_events = defaultdict(list)
        self.batch_timers = {}
        
    async def add_event(self, event: Event):
        """Add event to batch."""
        batch_key = event.event  # Group by event type
        
        self.pending_events[batch_key].append(event)
        
        # Start timer if first event in batch
        if batch_key not in self.batch_timers:
            self.batch_timers[batch_key] = asyncio.create_task(
                self._flush_batch_after_delay(batch_key)
            )
        
        # Flush if batch full
        if len(self.pending_events[batch_key]) >= self.batch_size:
            await self._flush_batch(batch_key)
    
    async def _flush_batch(self, batch_key: str):
        """Process batched events."""
        if batch_key not in self.pending_events:
            return
            
        events = self.pending_events.pop(batch_key)
        
        # Cancel timer
        if batch_key in self.batch_timers:
            self.batch_timers[batch_key].cancel()
            del self.batch_timers[batch_key]
        
        # Process as batch
        await self._process_batch(batch_key, events)
    
    async def _process_batch(self, event_type: str, events: List[Event]):
        """Process a batch of events efficiently."""
        # Example: Batch state updates
        if event_type == "state:entity:update":
            updates = [(e.data["type"], e.data["id"], e.data["changes"]) 
                      for e in events]
            await self.state_service.batch_update_entities(updates)
```

## Integration Timeline

### Week 1: Foundation
- [ ] Implement spatial indexing
- [ ] Add game theory metrics
- [ ] Create scheduled event service

### Week 2: Data Pipeline  
- [ ] Binary data support
- [ ] RGB observation encoding
- [ ] Batch event processing

### Week 3: Performance
- [ ] Performance monitoring
- [ ] Optimization pass
- [ ] Load testing

## Testing Requirements

### Unit Tests
```python
def test_spatial_index():
    """Test spatial indexing performance."""
    index = SpatialStateIndex()
    
    # Add 10000 entities
    for i in range(10000):
        index.update_position(f"entity_{i}", 
                            random.randint(0, 100),
                            random.randint(0, 100))
    
    # Test query performance
    start = time.perf_counter()
    entities = index.get_entities_in_radius(50, 50, 5)
    duration = time.perf_counter() - start
    
    assert duration < 0.001  # Sub-millisecond
```

### Integration Tests
```python
async def test_melting_pot_metrics():
    """Test metric calculation in substrate."""
    substrate = create_test_substrate()
    
    # Run episode
    for _ in range(100):
        await substrate.step()
        
    metrics = substrate.get_metrics()
    
    assert 0 <= metrics["gini_coefficient"] <= 1
    assert metrics["collective_return"] >= 0
    assert "background_equality" in metrics
```

## Monitoring Dashboard Metrics

### Real-time Metrics to Track
```yaml
substrate_metrics:
  - steps_per_second
  - active_agents
  - gini_coefficient
  - collective_return
  - observation_generation_time_ms
  - action_processing_time_ms

system_metrics:
  - memory_usage_mb
  - cpu_utilization_percent
  - event_queue_depth
  - spatial_index_size

fairness_metrics:
  - diversity_index
  - consent_refusal_rate
  - coalition_sizes
  - exploitation_attempts
  - defense_success_rate
```

## Backwards Compatibility

All enhancements maintain backwards compatibility:
- New services are optional
- Existing events unchanged
- State system extensions are additive
- Performance improvements transparent

## Conclusion

These enhancements equip KSI with the infrastructure needed to:
1. **Replicate Melting Pot scenarios** with perfect fidelity
2. **Calculate game-theoretic metrics** in real-time
3. **Handle visual observations** efficiently
4. **Scale to 100+ agents** at 100+ steps/second
5. **Monitor fairness mechanisms** comprehensively

With these in place, we can test whether our fairness hypothesis holds in canonical game theory scenarios.

---

*Document created: 2025-08-28*
*KSI Infrastructure Enhancement Specification v1.0*