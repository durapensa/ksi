# Melting Pot in KSI: Implementation Plan

## Executive Summary

This document outlines a comprehensive plan to implement DeepMind's Melting Pot scenarios within KSI's event-driven architecture. The goal is to create a perfect baseline replication before adding our fairness mechanisms to test if "exploitation is NOT inherent to intelligence" holds in canonical game-theoretic scenarios.

## Overview of Melting Pot

### Core Scenarios to Implement
1. **Prisoners Dilemma in the Matrix** - Iterated PD with spatial elements
2. **Stag Hunt in the Matrix** - Coordination under uncertainty  
3. **Commons Harvest** - Resource management and tragedy of commons
4. **Cleanup** - Public goods provision
5. **Collaborative Cooking** - Complex coordination tasks

### Key Metrics from Melting Pot
- **Collective Return**: Average reward across all agents
- **Per-Capita Return**: Individual agent returns
- **Gini Coefficient**: Inequality measure (1 - equality)
- **Background Return**: Returns of non-focal agents
- **Efficiency**: Resource utilization rate

## Technical Architecture

### New KSI Services Required

#### 1. Environment Service (`ksi_daemon/melting_pot/environment_service.py`)
```python
class MeltingPotEnvironmentService(Service):
    """Manages Melting Pot substrate environments."""
    
    def __init__(self):
        self.substrates = {}  # Active game environments
        self.grid_states = {}  # 2D grid representations
        self.physics_engine = PhysicsEngine()  # Game physics
        
    # Event handlers
    async def handle_substrate_create(self, event: Event):
        """Create new Melting Pot substrate."""
        
    async def handle_action_execute(self, event: Event):
        """Process agent actions (move, turn, zap, etc.)."""
        
    async def handle_step_environment(self, event: Event):
        """Step the environment forward one tick."""
```

#### 2. Observation Service (`ksi_daemon/melting_pot/observation_service.py`)
```python
class ObservationService(Service):
    """Generates observations for agents."""
    
    def __init__(self):
        self.sprite_renderer = SpriteRenderer()
        self.view_windows = {}  # Per-agent view windows
        
    async def handle_observation_request(self, event: Event):
        """Generate RGB observation for an agent."""
        # Convert grid state to RGB pixels
        # Apply agent-specific view window
        # Emit observation event
```

#### 3. Metrics Service (`ksi_daemon/melting_pot/metrics_service.py`)
```python
class MetricsService(Service):
    """Tracks Melting Pot metrics."""
    
    def __init__(self):
        self.episode_returns = {}
        self.resource_distributions = {}
        
    def calculate_gini(self, values: List[float]) -> float:
        """Calculate Gini coefficient."""
        
    def calculate_collective_return(self, returns: Dict) -> float:
        """Calculate average return across agents."""
```

### State Representation

#### 2D Gridworld in KSI State
```python
# State entity schema for grid cells
GridCellEntity = {
    "type": "melting_pot_cell",
    "id": "cell_x10_y20",
    "properties": {
        "x": 10,
        "y": 20,
        "terrain": "grass",  # grass, wall, water, etc.
        "resources": ["apple"],  # Items at this location
        "occupied_by": "agent_123",  # Agent at this location
        "passable": True,
        "sprite_id": "grass_01"
    }
}

# State entity for agents in gridworld
GridAgentEntity = {
    "type": "melting_pot_agent",
    "id": "agent_123",
    "properties": {
        "x": 10,
        "y": 20,
        "orientation": "north",  # north, south, east, west
        "inventory": ["apple", "apple"],
        "health": 100,
        "score": 42,
        "population": "focal",  # focal or background
        "strategy": "cooperator",  # For background agents
        "color": "#FF0000"  # Visual identifier
    }
}

# State entity for game resources
ResourceEntity = {
    "type": "melting_pot_resource",
    "id": "apple_001",
    "properties": {
        "x": 15,
        "y": 25,
        "resource_type": "apple",
        "respawn_time": 100,
        "collected_by": None,
        "value": 10
    }
}
```

### Event Schema

#### Core Game Events
```python
# Action events (from agents)
"melting_pot:action:move": {
    "substrate_id": "str",
    "agent_id": "str",
    "direction": "north|south|east|west"
}

"melting_pot:action:turn": {
    "substrate_id": "str",
    "agent_id": "str",
    "direction": "left|right"
}

"melting_pot:action:zap": {
    "substrate_id": "str",
    "agent_id": "str",
    "target_x": "int",
    "target_y": "int"
}

"melting_pot:action:collect": {
    "substrate_id": "str",
    "agent_id": "str",
    "resource_id": "str"
}

# Observation events (to agents)
"melting_pot:observation": {
    "substrate_id": "str",
    "agent_id": "str",
    "rgb_pixels": "base64",  # Encoded RGB array
    "view_window": {
        "width": 11,
        "height": 11,
        "center_x": 10,
        "center_y": 20
    }
}

# Game state events
"melting_pot:episode:start": {
    "substrate_id": "str",
    "scenario": "prisoners_dilemma_in_the_matrix",
    "num_agents": 8,
    "focal_agents": ["agent_1", "agent_2"],
    "background_agents": ["bot_1", "bot_2", ...],
    "max_steps": 1000
}

"melting_pot:step:complete": {
    "substrate_id": "str",
    "step": 42,
    "rewards": {"agent_1": 10, "agent_2": -5, ...},
    "done": False
}

"melting_pot:metrics:update": {
    "substrate_id": "str",
    "step": 42,
    "collective_return": 25.5,
    "gini_coefficient": 0.35,
    "background_return": 20.0,
    "efficiency": 0.75
}
```

### Visual Observation Pipeline

```python
class SpriteRenderer:
    """Converts grid state to RGB observations."""
    
    def __init__(self):
        self.sprite_library = self.load_sprites()
        self.tile_size = 8  # 8x8 pixel tiles
        
    def render_observation(self, grid_state: Dict, 
                          agent_id: str, 
                          view_radius: int = 5) -> np.ndarray:
        """Generate RGB observation for an agent."""
        # 1. Get agent position and orientation
        agent = grid_state["agents"][agent_id]
        x, y, orientation = agent["x"], agent["y"], agent["orientation"]
        
        # 2. Extract view window from grid
        view_window = self.extract_view_window(
            grid_state, x, y, view_radius, orientation
        )
        
        # 3. Convert tiles to sprites
        rgb_array = np.zeros((
            view_radius * 2 + 1, 
            view_radius * 2 + 1, 
            3
        ), dtype=np.uint8)
        
        for i, row in enumerate(view_window):
            for j, cell in enumerate(row):
                sprite = self.get_sprite(cell)
                rgb_array[i*8:(i+1)*8, j*8:(j+1)*8] = sprite
                
        return rgb_array
```

### Game Mechanics Implementation

#### Movement System
```python
class MovementSystem:
    """Handles agent movement in gridworld."""
    
    async def process_move(self, agent_id: str, direction: str):
        # 1. Get current position
        agent = await self.state.get_entity("melting_pot_agent", agent_id)
        current_x, current_y = agent["x"], agent["y"]
        
        # 2. Calculate new position
        dx, dy = self.direction_to_delta(direction)
        new_x, new_y = current_x + dx, current_y + dy
        
        # 3. Check collision
        target_cell = await self.state.get_entity(
            "melting_pot_cell", f"cell_x{new_x}_y{new_y}"
        )
        
        if target_cell and target_cell["passable"]:
            # 4. Update agent position
            await self.state.update_entity(
                "melting_pot_agent", agent_id,
                {"x": new_x, "y": new_y}
            )
            
            # 5. Emit movement event
            await self.event_emitter.emit(
                "melting_pot:agent:moved",
                {"agent_id": agent_id, "x": new_x, "y": new_y}
            )
```

#### Resource Collection
```python
class ResourceSystem:
    """Handles resource spawning and collection."""
    
    async def spawn_resource(self, resource_type: str, x: int, y: int):
        resource_id = f"resource_{uuid.uuid4()}"
        await self.state.create_entity(
            "melting_pot_resource",
            resource_id,
            {
                "x": x, "y": y,
                "resource_type": resource_type,
                "respawn_time": self.get_respawn_time(resource_type),
                "value": self.get_resource_value(resource_type)
            }
        )
        
    async def collect_resource(self, agent_id: str, resource_id: str):
        # Check proximity
        if self.is_adjacent(agent_id, resource_id):
            # Transfer to inventory
            resource = await self.state.get_entity(
                "melting_pot_resource", resource_id
            )
            
            # Add to agent inventory
            agent = await self.state.get_entity(
                "melting_pot_agent", agent_id
            )
            agent["inventory"].append(resource["resource_type"])
            agent["score"] += resource["value"]
            
            # Delete resource entity
            await self.state.delete_entity(
                "melting_pot_resource", resource_id
            )
            
            # Schedule respawn
            await self.schedule_respawn(resource)
```

### Scenario Implementations

#### 1. Prisoners Dilemma in the Matrix
```python
class PrisonersDilemmaSubstrate:
    """Iterated PD with spatial elements."""
    
    def __init__(self):
        self.grid_size = 25
        self.cooperate_zones = []  # Green zones
        self.defect_zones = []     # Red zones
        
    def setup_environment(self):
        # Create grid with cooperate/defect resource zones
        for x in range(5, 10):
            for y in range(5, 10):
                self.cooperate_zones.append((x, y))
                
        for x in range(15, 20):
            for y in range(15, 20):
                self.defect_zones.append((x, y))
                
    def calculate_payoff(self, agent1_action, agent2_action):
        """Classic PD payoff matrix."""
        if agent1_action == "cooperate" and agent2_action == "cooperate":
            return 3, 3  # Mutual cooperation
        elif agent1_action == "defect" and agent2_action == "defect":
            return 1, 1  # Mutual defection
        elif agent1_action == "cooperate" and agent2_action == "defect":
            return 0, 5  # Sucker vs temptation
        else:
            return 5, 0  # Temptation vs sucker
```

#### 2. Commons Harvest
```python
class CommonsHarvestSubstrate:
    """Resource management with regeneration."""
    
    def __init__(self):
        self.apple_spawn_points = []
        self.regeneration_rate = 0.01
        self.sustainability_threshold = 0.5
        
    def update_resources(self):
        """Regenerate resources based on remaining density."""
        current_density = len(self.active_apples) / len(self.apple_spawn_points)
        
        if current_density > self.sustainability_threshold:
            # Healthy regeneration
            spawn_probability = self.regeneration_rate * 2
        else:
            # Depleted regeneration
            spawn_probability = self.regeneration_rate * 0.5
            
        for spawn_point in self.apple_spawn_points:
            if random.random() < spawn_probability:
                self.spawn_apple(spawn_point)
```

### Focal vs Background Populations

```python
class PopulationManager:
    """Manages focal and background agent populations."""
    
    def __init__(self):
        self.focal_agents = []      # Agents being evaluated
        self.background_agents = []  # Reference population
        
    async def spawn_populations(self, scenario_config):
        """Spawn agents for a scenario."""
        
        # Spawn focal agents (the ones we're testing)
        for i in range(scenario_config["num_focal"]):
            agent_id = f"focal_agent_{i}"
            self.focal_agents.append(agent_id)
            
            await self.event_emitter.emit(
                "agent:spawn",
                {
                    "agent_id": agent_id,
                    "profile": "melting_pot_focal",
                    "substrate_id": self.substrate_id,
                    "population": "focal"
                }
            )
            
        # Spawn background agents (reference behaviors)
        for i, behavior in enumerate(scenario_config["background_behaviors"]):
            agent_id = f"background_agent_{i}"
            self.background_agents.append(agent_id)
            
            await self.event_emitter.emit(
                "agent:spawn",
                {
                    "agent_id": agent_id,
                    "profile": f"melting_pot_{behavior}",  # e.g., cooperator, defector
                    "substrate_id": self.substrate_id,
                    "population": "background",
                    "hardcoded_strategy": behavior
                }
            )
```

### Metrics Collection

```python
class MeltingPotMetrics:
    """Calculates Melting Pot-specific metrics."""
    
    def calculate_gini_coefficient(self, returns: List[float]) -> float:
        """Calculate Gini coefficient for inequality."""
        sorted_returns = sorted(returns)
        n = len(sorted_returns)
        cumsum = np.cumsum(sorted_returns)
        return (2 * np.sum((np.arange(1, n+1)) * sorted_returns)) / (n * np.sum(sorted_returns)) - (n + 1) / n
        
    def calculate_background_positive_income_equality(self, 
                                                      background_returns: List[float]) -> float:
        """Complement of Gini for positive returns only."""
        positive_returns = [r for r in background_returns if r > 0]
        if not positive_returns:
            return 1.0  # Perfect equality if no positive returns
        return 1.0 - self.calculate_gini_coefficient(positive_returns)
        
    def calculate_efficiency(self, 
                           actual_collective_return: float,
                           max_possible_return: float) -> float:
        """Efficiency as ratio of actual to maximum possible."""
        if max_possible_return == 0:
            return 0.0
        return actual_collective_return / max_possible_return
```

## KSI Enhancements Required

### 1. Spatial Indexing for State Entities
```python
# Add to state service
class SpatialIndex:
    """Efficient spatial queries for gridworld."""
    
    def __init__(self):
        self.grid = {}  # (x, y) -> [entity_ids]
        
    def add_entity(self, entity_id: str, x: int, y: int):
        key = (x, y)
        if key not in self.grid:
            self.grid[key] = []
        self.grid[key].append(entity_id)
        
    def get_entities_at(self, x: int, y: int) -> List[str]:
        return self.grid.get((x, y), [])
        
    def get_entities_in_radius(self, x: int, y: int, radius: int) -> List[str]:
        entities = []
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                entities.extend(self.get_entities_at(x + dx, y + dy))
        return entities
```

### 2. Scheduled Events System
```python
# Add to daemon
class ScheduledEventService(Service):
    """Handles time-based events like resource respawning."""
    
    def __init__(self):
        self.scheduled_events = []  # Sorted by timestamp
        
    async def schedule_event(self, event: str, data: Dict, delay_ms: int):
        timestamp = time.time() + (delay_ms / 1000)
        heapq.heappush(self.scheduled_events, (timestamp, event, data))
        
    async def process_scheduled_events(self):
        """Called every tick."""
        current_time = time.time()
        while self.scheduled_events and self.scheduled_events[0][0] <= current_time:
            timestamp, event, data = heapq.heappop(self.scheduled_events)
            await self.event_emitter.emit(event, data)
```

### 3. Binary Data Support for Observations
```python
# Enhancement to event system
class BinaryEventData:
    """Support for binary data in events."""
    
    @staticmethod
    def encode_rgb_observation(rgb_array: np.ndarray) -> str:
        """Encode RGB array as base64."""
        buffer = io.BytesIO()
        np.save(buffer, rgb_array)
        return base64.b64encode(buffer.getvalue()).decode()
        
    @staticmethod
    def decode_rgb_observation(encoded: str) -> np.ndarray:
        """Decode base64 to RGB array."""
        buffer = io.BytesIO(base64.b64decode(encoded))
        return np.load(buffer)
```

### 4. Performance Monitoring
```python
class PerformanceMonitor:
    """Track substrate performance metrics."""
    
    def __init__(self):
        self.step_times = []
        self.observation_times = []
        self.action_processing_times = []
        
    def report_metrics(self):
        return {
            "avg_step_time_ms": np.mean(self.step_times),
            "avg_observation_time_ms": np.mean(self.observation_times),
            "steps_per_second": 1000 / np.mean(self.step_times)
        }
```

## Component Architecture

### New Components for Agents

```yaml
# components/melting_pot/cooperator.md
---
component_type: persona
name: melting_pot_cooperator
version: 1.0.0
description: Always cooperates in social dilemmas
---
You are a cooperative agent in a Melting Pot scenario.
Always choose cooperative actions when available.
Prioritize collective welfare over individual gain.

# components/melting_pot/defector.md
---
component_type: persona
name: melting_pot_defector
version: 1.0.0
description: Always defects for individual gain
---
You are a self-interested agent.
Always choose actions that maximize your individual reward.
Exploit cooperative agents when possible.

# components/melting_pot/tit_for_tat.md
---
component_type: persona
name: melting_pot_tit_for_tat
version: 1.0.0
description: Cooperates initially, then mirrors previous interactions
---
Start by cooperating.
If another agent defected against you, defect against them.
If another agent cooperated with you, cooperate with them.
```

### Orchestration Components

```yaml
# components/workflows/melting_pot_scenario.md
---
component_type: workflow
name: melting_pot_scenario
version: 1.0.0
---
agents:
  focal_population:
    count: 4
    component: "components/melting_pot/learning_agent"
    
  background_population:
    count: 4
    component: "components/melting_pot/cooperator"

orchestration_logic:
  initialization: |
    CREATE substrate WITH scenario_config
    SPAWN focal_agents IN substrate
    SPAWN background_agents IN substrate
    
  game_loop: |
    FOR step IN 1..1000:
      COLLECT actions FROM all_agents
      EXECUTE actions IN substrate
      CALCULATE rewards
      GENERATE observations
      UPDATE metrics
      IF done: BREAK
      
  evaluation: |
    CALCULATE final_metrics
    COMPARE focal VS background performance
    GENERATE report
```

## Implementation Roadmap

### Phase 1: Core Infrastructure (Week 1)
- [ ] Create MeltingPotEnvironmentService
- [ ] Implement grid state representation
- [ ] Build spatial indexing system
- [ ] Create basic event schema
- [ ] Set up metrics service

### Phase 2: Game Mechanics (Week 2)
- [ ] Implement movement system
- [ ] Add collision detection
- [ ] Create resource spawning/collection
- [ ] Build interaction system (zap, clean, etc.)
- [ ] Add scheduled events for respawning

### Phase 3: Visual System (Week 3)
- [ ] Create sprite renderer
- [ ] Implement RGB observation generation
- [ ] Add view window extraction
- [ ] Support different orientations
- [ ] Optimize for performance

### Phase 4: Scenario Implementation (Week 4)
- [ ] Implement Prisoners Dilemma substrate
- [ ] Implement Stag Hunt substrate
- [ ] Implement Commons Harvest substrate
- [ ] Implement Cleanup substrate
- [ ] Implement Collaborative Cooking substrate

### Phase 5: Population Management (Week 5)
- [ ] Create population manager
- [ ] Implement focal vs background distinction
- [ ] Add hardcoded strategies for background
- [ ] Support different test scenarios
- [ ] Create agent spawning orchestration

### Phase 6: Validation & Testing (Week 6)
- [ ] Compare metrics with original Melting Pot
- [ ] Validate game mechanics accuracy
- [ ] Performance testing and optimization
- [ ] Create test scenarios
- [ ] Document differences/limitations

## Testing Strategy

### Unit Tests
```python
def test_gini_calculation():
    """Test Gini coefficient calculation."""
    # Perfect equality
    assert calculate_gini([10, 10, 10, 10]) == 0.0
    
    # Perfect inequality
    assert calculate_gini([40, 0, 0, 0]) == 0.75
    
    # Moderate inequality
    assert abs(calculate_gini([20, 15, 10, 5]) - 0.25) < 0.01
```

### Integration Tests
```python
async def test_prisoners_dilemma_scenario():
    """Test complete PD scenario."""
    # Create substrate
    substrate = await create_substrate("prisoners_dilemma")
    
    # Spawn agents
    await spawn_populations(4, 4)  # 4 focal, 4 background
    
    # Run episode
    for _ in range(100):
        await step_environment()
        
    # Validate metrics
    metrics = await get_metrics()
    assert "collective_return" in metrics
    assert "gini_coefficient" in metrics
```

### Validation Against Original
```python
def validate_against_melting_pot():
    """Compare KSI implementation with original."""
    # Run same scenario in both
    ksi_results = run_ksi_scenario("prisoners_dilemma")
    melting_pot_results = run_original_scenario("prisoners_dilemma")
    
    # Compare metrics
    assert abs(ksi_results["gini"] - melting_pot_results["gini"]) < 0.05
    assert abs(ksi_results["collective_return"] - 
              melting_pot_results["collective_return"]) < 5.0
```

## Performance Requirements

### Target Metrics
- **Step Rate**: 100+ steps/second for 8 agents
- **Observation Generation**: <10ms per agent
- **Action Processing**: <5ms per action
- **Memory Usage**: <1GB for 1000-step episode
- **Scalability**: Support up to 100 agents

### Optimization Strategies
1. **Batch Processing**: Process all agent actions in single pass
2. **Spatial Indexing**: O(1) lookups for position queries
3. **Observation Caching**: Reuse unchanged portions
4. **Event Batching**: Combine related events
5. **State Diffing**: Only transmit changed state

## Success Criteria

### Functional Requirements
- [ ] All 5 core scenarios implemented
- [ ] Metrics match Melting Pot within 5%
- [ ] Support for 256 test scenarios
- [ ] Focal vs background populations working
- [ ] RGB observations generated correctly

### Performance Requirements
- [ ] 100+ steps/second achieved
- [ ] Scales to 100 agents
- [ ] Memory usage under 1GB
- [ ] No performance degradation over time

### Integration Requirements
- [ ] Fully event-driven implementation
- [ ] Uses KSI state management
- [ ] Compatible with existing agents
- [ ] Supports dynamic routing
- [ ] Monitoring and introspection working

## Conclusion

This plan provides a complete roadmap for implementing Melting Pot scenarios within KSI's event-driven architecture. The implementation maintains perfect fidelity to the original while leveraging KSI's strengths:

1. **Event-driven design** enables full introspection of agent interactions
2. **State management** provides consistent world representation
3. **Component system** allows reusable agent strategies
4. **Dynamic routing** enables runtime behavior modification
5. **Native monitoring** tracks all metrics in real-time

Once this baseline is implemented, we can add our fairness mechanisms (strategic diversity, consent mechanisms, coordination limits) and test whether they improve outcomes in these canonical game-theoretic scenarios.

---

*Document created: 2025-08-28*
*KSI Empirical Laboratory - Melting Pot Integration Initiative*