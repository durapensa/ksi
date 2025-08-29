#!/usr/bin/env python3
"""
Movement Validator for Spatial Service
=======================================

Validates movement requests in spatial environments.
Uses pathfinding algorithms to check validity and suggest alternatives.
"""

import math
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import heapq
import logging

logger = logging.getLogger(__name__)


class TerrainType(Enum):
    """Types of terrain that affect movement."""
    GROUND = "ground"
    WATER = "water"
    WALL = "wall"
    OBSTACLE = "obstacle"
    SLOW = "slow"  # Half speed
    FAST = "fast"  # Double speed


@dataclass
class Position:
    """A position in space."""
    x: float
    y: float
    z: float = 0.0
    
    def distance_to(self, other: 'Position') -> float:
        """Calculate Euclidean distance to another position."""
        return math.sqrt(
            (self.x - other.x) ** 2 + 
            (self.y - other.y) ** 2 + 
            (self.z - other.z) ** 2
        )
    
    def manhattan_distance(self, other: 'Position') -> float:
        """Calculate Manhattan distance to another position."""
        return abs(self.x - other.x) + abs(self.y - other.y) + abs(self.z - other.z)


@dataclass
class MovementRequest:
    """A movement validation request."""
    entity_id: str
    entity_type: str
    from_position: Position
    to_position: Position
    movement_type: str
    speed: float = 1.0
    capabilities: List[str] = None
    
    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []


@dataclass
class ValidationResult:
    """Result of movement validation."""
    valid: bool
    reason: str = ""
    suggested_path: List[Position] = None
    cost: float = 0.0
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.suggested_path is None:
            self.suggested_path = []
        if self.warnings is None:
            self.warnings = []


class MovementValidator:
    """Validates movement in spatial environments."""
    
    def __init__(self):
        self.terrain_map: Dict[Tuple[int, int], TerrainType] = {}
        self.obstacles: List[Dict] = []
        self.movement_rules = {
            "walk": {"max_distance": 5, "terrain": ["ground", "slow", "fast"]},
            "fly": {"max_distance": 10, "terrain": ["ground", "water", "slow", "fast", "obstacle"]},
            "swim": {"max_distance": 3, "terrain": ["water"]},
            "teleport": {"max_distance": float('inf'), "terrain": ["ground", "water", "slow", "fast"]},
            "phase": {"max_distance": 7, "terrain": ["ground", "water", "slow", "fast", "wall", "obstacle"]}
        }
        
    def validate_movement(self, request: MovementRequest, 
                         environment: Optional[Dict] = None) -> ValidationResult:
        """Validate a movement request."""
        
        # Basic distance check
        distance = request.from_position.distance_to(request.to_position)
        movement_rule = self.movement_rules.get(request.movement_type, {"max_distance": 5})
        
        if distance > movement_rule["max_distance"]:
            return ValidationResult(
                valid=False,
                reason=f"Distance {distance:.1f} exceeds max {movement_rule['max_distance']} for {request.movement_type}"
            )
        
        # Check for obstacles and terrain
        if request.movement_type == "teleport":
            # Teleport bypasses obstacles but not terrain restrictions
            if not self._check_terrain_valid(request.to_position, movement_rule["terrain"]):
                return ValidationResult(
                    valid=False,
                    reason=f"Target terrain not valid for {request.movement_type}"
                )
            return ValidationResult(valid=True, cost=distance)
        
        # Find path for non-teleport movement
        path = self._find_path(
            request.from_position,
            request.to_position,
            request.movement_type,
            environment
        )
        
        if path is None:
            # No valid path found
            alternative = self._suggest_alternative(request, environment)
            return ValidationResult(
                valid=False,
                reason=f"No valid path for {request.movement_type} movement",
                suggested_path=alternative
            )
        
        # Calculate path cost
        path_cost = self._calculate_path_cost(path, request.movement_type)
        
        # Check if path cost exceeds movement capacity
        max_cost = movement_rule["max_distance"] * request.speed
        if path_cost > max_cost:
            return ValidationResult(
                valid=False,
                reason=f"Path cost {path_cost:.1f} exceeds capacity {max_cost:.1f}",
                suggested_path=path[:int(len(path) * (max_cost / path_cost))],  # Partial path
                warnings=[f"Can only move {max_cost/path_cost:.0%} of the way"]
            )
        
        return ValidationResult(
            valid=True,
            suggested_path=path,
            cost=path_cost
        )
    
    def _find_path(self, start: Position, goal: Position, 
                   movement_type: str, environment: Optional[Dict]) -> Optional[List[Position]]:
        """Find a valid path using A* algorithm."""
        
        # Simplified grid-based pathfinding
        # In production, would use continuous space or navmesh
        
        # Convert to grid coordinates
        start_grid = (int(start.x), int(start.y))
        goal_grid = (int(goal.x), int(goal.y))
        
        # A* implementation
        open_set = [(0, start_grid, [start])]
        closed_set = set()
        g_score = {start_grid: 0}
        
        movement_rule = self.movement_rules.get(movement_type, {"terrain": ["ground"]})
        
        while open_set:
            current_f, current_pos, current_path = heapq.heappop(open_set)
            
            if current_pos == goal_grid:
                # Found path, add goal with exact coordinates
                current_path.append(goal)
                return current_path
            
            if current_pos in closed_set:
                continue
            
            closed_set.add(current_pos)
            
            # Check neighbors
            for dx, dy in [(-1,0), (1,0), (0,-1), (0,1), (-1,-1), (1,-1), (-1,1), (1,1)]:
                neighbor = (current_pos[0] + dx, current_pos[1] + dy)
                
                # Check bounds (assuming 25x25 grid)
                if not (0 <= neighbor[0] < 25 and 0 <= neighbor[1] < 25):
                    continue
                
                # Check if neighbor is valid for movement type
                if not self._is_valid_cell(neighbor, movement_type, environment):
                    continue
                
                # Calculate tentative g score
                move_cost = math.sqrt(dx*dx + dy*dy) if dx != 0 and dy != 0 else 1
                terrain_cost = self._get_terrain_cost(neighbor)
                tentative_g = g_score[current_pos] + move_cost * terrain_cost
                
                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    g_score[neighbor] = tentative_g
                    h_score = math.sqrt((neighbor[0] - goal_grid[0])**2 + 
                                      (neighbor[1] - goal_grid[1])**2)
                    f_score = tentative_g + h_score
                    
                    new_path = current_path + [Position(neighbor[0], neighbor[1])]
                    heapq.heappush(open_set, (f_score, neighbor, new_path))
        
        return None  # No path found
    
    def _is_valid_cell(self, cell: Tuple[int, int], movement_type: str, 
                       environment: Optional[Dict]) -> bool:
        """Check if a cell is valid for the given movement type."""
        
        # Check terrain
        terrain = self.terrain_map.get(cell, TerrainType.GROUND)
        movement_rule = self.movement_rules.get(movement_type, {"terrain": ["ground"]})
        
        if terrain.value not in movement_rule["terrain"]:
            return False
        
        # Check obstacles from environment
        if environment and "obstacles" in environment:
            for obstacle in environment["obstacles"]:
                if (obstacle["x"] == cell[0] and obstacle["y"] == cell[1]):
                    # Check if movement type can pass obstacles
                    if movement_type != "phase" and movement_type != "fly":
                        return False
        
        return True
    
    def _get_terrain_cost(self, cell: Tuple[int, int]) -> float:
        """Get movement cost multiplier for terrain."""
        terrain = self.terrain_map.get(cell, TerrainType.GROUND)
        
        cost_map = {
            TerrainType.GROUND: 1.0,
            TerrainType.FAST: 0.5,
            TerrainType.SLOW: 2.0,
            TerrainType.WATER: 1.5,
            TerrainType.WALL: float('inf'),
            TerrainType.OBSTACLE: float('inf')
        }
        
        return cost_map.get(terrain, 1.0)
    
    def _calculate_path_cost(self, path: List[Position], movement_type: str) -> float:
        """Calculate total cost of a path."""
        if len(path) < 2:
            return 0.0
        
        total_cost = 0.0
        for i in range(1, len(path)):
            segment_cost = path[i-1].distance_to(path[i])
            terrain_cost = self._get_terrain_cost((int(path[i].x), int(path[i].y)))
            total_cost += segment_cost * terrain_cost
        
        return total_cost
    
    def _check_terrain_valid(self, position: Position, valid_terrain: List[str]) -> bool:
        """Check if terrain at position is valid."""
        cell = (int(position.x), int(position.y))
        terrain = self.terrain_map.get(cell, TerrainType.GROUND)
        return terrain.value in valid_terrain
    
    def _suggest_alternative(self, request: MovementRequest, 
                            environment: Optional[Dict]) -> List[Position]:
        """Suggest an alternative path or destination."""
        
        # Try to find nearest reachable position
        search_radius = 5
        best_distance = float('inf')
        best_position = None
        
        goal_x, goal_y = int(request.to_position.x), int(request.to_position.y)
        
        for dx in range(-search_radius, search_radius + 1):
            for dy in range(-search_radius, search_radius + 1):
                test_x, test_y = goal_x + dx, goal_y + dy
                
                # Check bounds
                if not (0 <= test_x < 25 and 0 <= test_y < 25):
                    continue
                
                test_pos = Position(test_x, test_y)
                
                # Try to find path to this position
                path = self._find_path(
                    request.from_position,
                    test_pos,
                    request.movement_type,
                    environment
                )
                
                if path:
                    distance = test_pos.distance_to(request.to_position)
                    if distance < best_distance:
                        best_distance = distance
                        best_position = path
        
        return best_position or []
    
    def set_terrain(self, x: int, y: int, terrain_type: TerrainType):
        """Set terrain type for a cell."""
        self.terrain_map[(x, y)] = terrain_type
    
    def add_obstacle(self, obstacle: Dict):
        """Add an obstacle to track."""
        self.obstacles.append(obstacle)
    
    def clear_obstacles(self):
        """Clear all obstacles."""
        self.obstacles.clear()
    
    def validate_batch(self, requests: List[MovementRequest], 
                      environment: Optional[Dict] = None) -> List[ValidationResult]:
        """Validate multiple movement requests."""
        results = []
        for request in requests:
            results.append(self.validate_movement(request, environment))
        return results


class DSPyMovementValidator:
    """DSPy-based movement validator for more complex scenarios."""
    
    def __init__(self):
        # In production, would initialize DSPy model here
        self.basic_validator = MovementValidator()
        
    def validate_strategic_movement(self, request: MovementRequest, 
                                   context: Dict) -> ValidationResult:
        """Validate movement considering strategic factors."""
        
        # First do basic validation
        basic_result = self.basic_validator.validate_movement(request)
        
        if not basic_result.valid:
            return basic_result
        
        # Add strategic considerations
        warnings = []
        
        # Check if moving into danger zone
        if self._is_danger_zone(request.to_position, context):
            warnings.append("Moving into potential danger zone")
        
        # Check if movement reveals information
        if self._reveals_information(request, context):
            warnings.append("Movement may reveal strategic information")
        
        # Check if movement blocks others
        if self._blocks_others(request.to_position, context):
            warnings.append("Movement may block other agents")
        
        return ValidationResult(
            valid=True,
            suggested_path=basic_result.suggested_path,
            cost=basic_result.cost,
            warnings=warnings
        )
    
    def _is_danger_zone(self, position: Position, context: Dict) -> bool:
        """Check if position is in a danger zone."""
        # Check proximity to hostile agents
        if "hostile_positions" in context:
            for hostile_pos in context["hostile_positions"]:
                if position.distance_to(hostile_pos) < 3:
                    return True
        return False
    
    def _reveals_information(self, request: MovementRequest, context: Dict) -> bool:
        """Check if movement reveals strategic information."""
        # Check if movement pattern reveals intent
        if "hidden_resources" in context:
            for resource_pos in context["hidden_resources"]:
                if request.to_position.distance_to(resource_pos) < 2:
                    return True
        return False
    
    def _blocks_others(self, position: Position, context: Dict) -> bool:
        """Check if position blocks other agents."""
        # Check if position is a chokepoint
        if "chokepoints" in context:
            for chokepoint in context["chokepoints"]:
                if position.distance_to(chokepoint) < 1:
                    return True
        return False


# Export main validator
__all__ = ['MovementValidator', 'DSPyMovementValidator', 'ValidationResult', 
           'MovementRequest', 'Position', 'TerrainType']