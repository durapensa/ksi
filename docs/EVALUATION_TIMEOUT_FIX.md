# Evaluation Timeout Fix - Root Cause Analysis & Solution

**Date**: 2025-08-25  
**Issue**: Evaluation system timing out when using `claude-sonnet-4-20250514` model

## Root Cause

The evaluation system was failing because:
1. **Provider Routing Issue**: Claude models (e.g., `claude-sonnet-4-20250514`) were being routed to LiteLLM's Anthropic provider instead of the Claude CLI provider
2. **Authentication Error**: LiteLLM's Anthropic provider requires `ANTHROPIC_API_KEY`, but KSI uses Claude CLI which authenticates differently
3. **Sandbox UUID Missing**: Even when routing was fixed, subsequent requests failed because sandbox_uuid wasn't being retrieved for transformed models

## The Elegant Fix

### 1. Provider Selection Enhancement
**File**: `ksi_daemon/completion/provider_manager.py`
```python
# Check model support
if "*" in config["models"] or model in config["models"]:
    candidates.append((name, config))
# Special handling for Claude models that should use CLI
elif name == "claude-cli" and model.startswith("claude-"):
    # Map claude-* models to claude-cli/sonnet
    # This ensures evaluation with claude-sonnet-4-20250514 uses CLI
    candidates.append((name, config))
```

### 2. Model Name Transformation
**File**: `ksi_daemon/completion/completion_service.py`
```python
# If claude-cli provider was selected, transform model name to use the custom provider
if provider_name == "claude-cli" and not model.startswith("claude-cli/"):
    # Map claude models to claude-cli/sonnet for the custom provider
    logger.info(f"Transforming model {model} to claude-cli/sonnet for claude-cli provider")
    data["model"] = "claude-cli/sonnet"
```

### 3. Sandbox UUID Retrieval Fix
**File**: `ksi_daemon/completion/completion_service.py`
```python
# Check both model prefix and provider_name to catch transformed models
if agent_id and (model.startswith(("claude-cli/", "gemini-cli/")) or provider_name == "claude-cli"):
    # Retrieve sandbox_uuid from agent state entity
```

## Why This Is Elegant

1. **No Workarounds**: Fixed the root cause in the provider routing logic
2. **Preserves Architecture**: Respects the separation between LiteLLM providers and CLI providers
3. **Maintains Compatibility**: Works with both explicit `claude-cli/` models and standard Claude model names
4. **Clear Intent**: The code clearly shows that Claude models should use the CLI provider

## Verification

Successfully certified multiple components:
- `llanguage/v1/tool_use_foundation` - ✅ Passing
- `llanguage/v1/coordination_patterns` - ✅ Passing

The evaluation system now correctly:
1. Routes Claude models to the CLI provider
2. Transforms model names appropriately
3. Maintains agent sandboxes across requests
4. Completes evaluations without timeouts

## Lessons Learned

1. **Always investigate root causes** - The timeout was a symptom, not the problem
2. **Check provider routing** - Model names must match provider expectations
3. **Verify state propagation** - Ensure critical data like sandbox_uuid flows through the system
4. **Test the full flow** - From agent spawn through completion to evaluation

---

*Fix implemented: 2025-08-25*  
*No workarounds used - pure root cause resolution*