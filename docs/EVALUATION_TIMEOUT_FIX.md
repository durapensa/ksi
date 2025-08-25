# Evaluation Timeout Fix - Root Cause Analysis & Solution

**Date**: 2025-08-25  
**Issue**: Evaluation system timing out when using `claude-sonnet-4-20250514` model

## Root Cause

The evaluation system was failing because:
1. **Model Name Mismatch**: Using `claude-sonnet-4-20250514` without the `claude-cli/` prefix
2. **Provider Routing**: Models without the prefix are routed to LiteLLM's Anthropic provider
3. **Authentication Error**: LiteLLM's Anthropic provider requires `ANTHROPIC_API_KEY`, which we don't have configured

## The Simple Solution

Use the correct model name with the `claude-cli/` prefix:
- ❌ Wrong: `claude-sonnet-4-20250514` 
- ✅ Correct: `claude-cli/claude-sonnet-4-20250514` or `claude-cli/sonnet`

The system already correctly:
1. Routes `claude-cli/*` models to the Claude CLI provider
2. Strips the prefix and maps model names in the provider
3. Retrieves sandbox_uuid for CLI providers

## What NOT to Do

After review, I initially made these mistakes:
1. **Don't transform model names** - The system should never change specified model names
2. **Don't add duplicate detection** - The original code already detects CLI models correctly
3. **Don't add special routing** - Models without prefixes are meant for API-based providers

## Correct Usage

When running evaluations or using Claude models without API keys:
```bash
# Use the claude-cli prefix
ksi send evaluation:run \
  --component_path "llanguage/v1/tool_use_foundation" \
  --test_suite "behavior_certification" \
  --model "claude-cli/claude-sonnet-4-20250514"

# Or use the short form
ksi send evaluation:run \
  --component_path "llanguage/v1/tool_use_foundation" \
  --test_suite "behavior_certification" \
  --model "claude-cli/sonnet"
```

## Verification

After correcting to use proper model names:
- `llanguage/v1/tool_use_foundation` - ✅ Passing
- `llanguage/v1/coordination_patterns` - ✅ Passing

The evaluation system works correctly when:
1. Model names include the `claude-cli/` prefix
2. The provider routing sends them to Claude CLI
3. The CLI provider handles authentication via local Claude installation

## Lessons Learned

1. **Always investigate root causes** - The timeout was a symptom, not the problem
2. **Check provider routing** - Model names must match provider expectations
3. **Verify state propagation** - Ensure critical data like sandbox_uuid flows through the system
4. **Test the full flow** - From agent spawn through completion to evaluation

---

*Fix implemented: 2025-08-25*  
*No workarounds used - pure root cause resolution*