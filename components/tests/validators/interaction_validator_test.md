---
component_type: test
name: interaction_validator_test
version: 1.0.0
description: Test component for interaction validator with cooperation and consent
dependencies:
  - core/base_agent
capabilities_required:
  - validator
  - testing
---

# Interaction Validator Test Agent

You are a test agent responsible for validating interaction mechanics including range, consent, and cooperation.

## Setup

Initialize relationships for consent testing:

```json
{
  "event": "validator:interaction:update_relationship",
  "data": {"entity1": "alice", "entity2": "bob", "trust_score": 0.8}
}
```

```json
{
  "event": "validator:interaction:update_relationship",
  "data": {"entity1": "alice", "entity2": "charlie", "trust_score": 0.2}
}
```

## Test Suite

### Test 1: Valid Trade Interaction
```json
{
  "event": "testing:run:test",
  "data": {
    "test_name": "interaction_valid_trade",
    "test_function": "validator:interaction:validate",
    "test_args": {
      "actor_id": "alice",
      "target_id": "bob",
      "interaction_type": "trade",
      "actor_x": 0, "actor_y": 0,
      "target_x": 1, "target_y": 1,
      "range_limit": 2.0,
      "capabilities": ["trade"]
    }
  }
}
```

Expected: Should return `{"valid": true}` with distance ~1.41 within range 2.0

### Test 2: Out of Range Interaction
```json
{
  "event": "testing:run:test",
  "data": {
    "test_name": "interaction_out_of_range",
    "test_function": "validator:interaction:validate",
    "test_args": {
      "actor_id": "alice",
      "target_id": "charlie",
      "interaction_type": "attack",
      "actor_x": 0, "actor_y": 0,
      "target_x": 10, "target_y": 10,
      "range_limit": 2.0,
      "capabilities": ["attack"]
    }
  }
}
```

Expected: Should return `{"valid": false}` with reason about exceeding max range

### Test 3: Cooperative Hunt
```json
{
  "event": "testing:run:test",
  "data": {
    "test_name": "interaction_cooperation",
    "test_function": "validator:interaction:validate",
    "test_args": {
      "actor_id": "hunter1",
      "target_id": "stag",
      "interaction_type": "hunt_cooperative",
      "actor_x": 5, "actor_y": 5,
      "target_x": 7, "target_y": 7,
      "range_limit": 5.0,
      "capabilities": ["hunt", "coordinate"],
      "parameters": {"cooperation_type": "stag_hunt"},
      "context": {
        "nearby_entities": [
          {"entity_id": "hunter2", "entity_type": "agent", "position": {"x": 6, "y": 5}},
          {"entity_id": "hunter3", "entity_type": "agent", "position": {"x": 5, "y": 6}}
        ]
      }
    }
  }
}
```

Expected: Should validate cooperation with sufficient participants

### Test 4: Trust-Based Consent
Test interaction with high trust:
```json
{
  "event": "testing:run:test",
  "data": {
    "test_name": "interaction_high_trust_consent",
    "test_function": "validator:interaction:validate",
    "test_args": {
      "actor_id": "alice",
      "target_id": "bob",
      "interaction_type": "cooperate",
      "actor_x": 0, "actor_y": 0,
      "target_x": 1, "target_y": 0,
      "range_limit": 5.0,
      "capabilities": ["cooperate"]
    }
  }
}
```

Test interaction with low trust:
```json
{
  "event": "testing:run:test",
  "data": {
    "test_name": "interaction_low_trust_consent",
    "test_function": "validator:interaction:validate",
    "test_args": {
      "actor_id": "alice",
      "target_id": "charlie",
      "interaction_type": "cooperate",
      "actor_x": 0, "actor_y": 0,
      "target_x": 1, "target_y": 0,
      "range_limit": 5.0,
      "capabilities": ["cooperate"]
    }
  }
}
```

Expected: High trust should have higher success rate than low trust

## Verification

After running all tests:
1. Valid interactions within range are approved
2. Out-of-range interactions are rejected
3. Cooperation requirements are enforced
4. Trust affects consent probability

Use assertions to validate:
- Distance calculations are correct
- Cooperation score reflects interaction type
- Relationship scores influence outcomes