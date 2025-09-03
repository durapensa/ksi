---
component_type: test
name: resource_validator_test
version: 1.0.0
description: Test component for resource validator with fairness mechanisms
dependencies:
  - core/base_agent
capabilities_required:
  - validator
  - testing
  - state
---

# Resource Validator Test Agent

You are a test agent responsible for validating resource transfer and fairness mechanisms.

## Setup

Initialize resource ownership with inequality-reducing distribution:

```json
{
  "event": "validator:resource:update_ownership",
  "data": {"entity": "alice", "resource_type": "gold", "amount": 60}
}
```

```json
{
  "event": "validator:resource:update_ownership",
  "data": {"entity": "bob", "resource_type": "gold", "amount": 40}
}
```

```json
{
  "event": "validator:resource:update_ownership",
  "data": {"entity": "charlie", "resource_type": "gold", "amount": 50}
}
```

## Test Suite

### Test 1: Valid Transfer with Consent
```json
{
  "event": "testing:run:test",
  "data": {
    "test_name": "resource_valid_transfer",
    "test_function": "validator:resource:validate",
    "test_args": {
      "from_entity": "alice",
      "to_entity": "bob",
      "resource_type": "gold",
      "amount": 5,
      "transfer_type": "gift"
    }
  }
}
```

Expected: Should return `{"valid": true}` with consent checked

### Test 2: Insufficient Funds
```json
{
  "event": "testing:run:test",
  "data": {
    "test_name": "resource_insufficient_funds",
    "test_function": "validator:resource:validate",
    "test_args": {
      "from_entity": "bob",
      "to_entity": "alice",
      "resource_type": "gold",
      "amount": 100,
      "transfer_type": "trade"
    }
  }
}
```

Expected: Should return `{"valid": false}` with reason about insufficient funds

### Test 3: Fairness Check
First make alice very wealthy:
```json
{
  "event": "validator:resource:update_ownership",
  "data": {"entity": "alice", "resource_type": "gold", "amount": 500}
}
```

Then test large transfer from poor to rich:
```json
{
  "event": "testing:run:test",
  "data": {
    "test_name": "resource_fairness_check",
    "test_function": "validator:resource:validate",
    "test_args": {
      "from_entity": "charlie",
      "to_entity": "alice",
      "resource_type": "gold",
      "amount": 25,
      "transfer_type": "gift"
    }
  }
}
```

Expected: Should detect fairness violation or exploitation risk

### Test 4: Check Gini Coefficient
```json
{
  "event": "validator:resource:calculate_gini",
  "data": {}
}
```

Expected: Should return current Gini coefficient and wealth distribution

## Verification

After running all tests:
1. Valid transfers with proper consent are approved
2. Insufficient funds are correctly rejected
3. Fairness mechanisms detect and prevent exploitation
4. Gini coefficient accurately reflects wealth inequality

Use assertions to validate:
- Consent is checked for gifts/trades
- Fairness warnings appear for inequality-increasing transfers
- Resource ownership is tracked correctly