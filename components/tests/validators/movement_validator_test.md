---
component_type: test
name: movement_validator_test
version: 1.0.0
description: Test component for movement validator
dependencies:
  - core/base_agent
capabilities_required:
  - validator
  - testing
---

# Movement Validator Test Agent

You are a test agent responsible for validating the movement validator functionality.

## Test Suite

Run the following tests using KSI's testing framework:

### Test 1: Valid Movement
```json
{
  "event": "testing:run:test",
  "data": {
    "test_name": "movement_valid_walk",
    "test_function": "validator:movement:validate",
    "test_args": {
      "from_x": 0, "from_y": 0,
      "to_x": 2, "to_y": 2,
      "movement_type": "walk",
      "entity_capacity": 5.0
    }
  }
}
```

Expected: Should return `{"valid": true}` with distance ~2.83

### Test 2: Invalid Movement (Too Far)
```json
{
  "event": "testing:run:test",
  "data": {
    "test_name": "movement_invalid_distance",
    "test_function": "validator:movement:validate",
    "test_args": {
      "from_x": 0, "from_y": 0,
      "to_x": 10, "to_y": 10,
      "movement_type": "walk",
      "entity_capacity": 5.0
    }
  }
}
```

Expected: Should return `{"valid": false}` with reason mentioning distance exceeds capacity

### Test 3: Pathfinding with Obstacles
First add obstacles:
```json
{
  "event": "validator:movement:add_obstacle",
  "data": {"x": 1, "y": 0}
}
```

Then test pathfinding:
```json
{
  "event": "testing:run:test",
  "data": {
    "test_name": "movement_pathfinding",
    "test_function": "validator:movement:validate",
    "test_args": {
      "from_x": 0, "from_y": 0,
      "to_x": 2, "to_y": 0,
      "movement_type": "walk",
      "entity_capacity": 5.0,
      "environment": {
        "obstacles": [{"x": 1, "y": 0}]
      }
    }
  }
}
```

Expected: Should return valid with a suggested_path that goes around obstacle

### Test 4: Clear Obstacles
```json
{
  "event": "validator:movement:clear_obstacles",
  "data": {}
}
```

## Verification

After running all tests, verify:
1. All valid movements within range are accepted
2. Movements exceeding capacity are rejected with clear reasons
3. Pathfinding successfully navigates around obstacles
4. The validator maintains consistent state

Use `testing:assert:true` to validate each result.