#!/usr/bin/env python3
"""
Proposed improvements to litellm.py for comprehensive token tracking
Handles differences between Claude, Ollama, and other providers
"""

def extract_comprehensive_token_usage(response, provider: str) -> dict:
    """
    Extract all token types from various provider responses
    
    This function should be integrated into litellm.py to ensure
    we capture all token information for proper analysis.
    """
    
    usage_data = {
        # Standard tokens
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        
        # Advanced token types
        "thinking_tokens": 0,      # For reasoning models
        "cached_tokens": 0,         # Claude cache usage
        "cache_write_tokens": 0,    # New cache creation
        "cache_read_tokens": 0,     # Cache hits
        
        # Performance metrics
        "tokens_per_second": 0.0,
        "ms_per_token": 0.0,
        
        # Cost tracking
        "estimated_cost_usd": 0.0,
        
        # Provider-specific
        "provider": provider,
        "raw_usage": {}  # Store original for debugging
    }
    
    # Store raw usage for debugging
    if hasattr(response, 'usage'):
        usage_data["raw_usage"] = response.usage.model_dump() if hasattr(response.usage, 'model_dump') else str(response.usage)
    
    # Extract based on provider type
    if provider.startswith("claude"):
        usage_data.update(extract_claude_tokens(response))
    elif provider.startswith("ollama"):
        usage_data.update(extract_ollama_tokens(response))
    elif provider.startswith("openai") or provider.startswith("gpt"):
        usage_data.update(extract_openai_tokens(response))
    else:
        # Generic extraction
        usage_data.update(extract_generic_tokens(response))
    
    # Calculate derived metrics
    if usage_data["completion_tokens"] > 0 and hasattr(response, '_response_ms'):
        duration_ms = getattr(response, '_response_ms', 0)
        if duration_ms > 0:
            usage_data["tokens_per_second"] = usage_data["completion_tokens"] / (duration_ms / 1000)
            usage_data["ms_per_token"] = duration_ms / usage_data["completion_tokens"]
    
    return usage_data


def extract_claude_tokens(response) -> dict:
    """Extract Claude-specific token information"""
    
    tokens = {}
    
    if hasattr(response, 'usage'):
        usage = response.usage
        
        # Standard tokens
        tokens["prompt_tokens"] = getattr(usage, 'input_tokens', 0) or getattr(usage, 'prompt_tokens', 0)
        tokens["completion_tokens"] = getattr(usage, 'output_tokens', 0) or getattr(usage, 'completion_tokens', 0)
        
        # Claude cache tokens (these are IN ADDITION to prompt_tokens)
        tokens["cache_write_tokens"] = getattr(usage, 'cache_creation_input_tokens', 0)
        tokens["cache_read_tokens"] = getattr(usage, 'cache_read_input_tokens', 0)
        
        # Total cached tokens
        tokens["cached_tokens"] = tokens["cache_write_tokens"] + tokens["cache_read_tokens"]
        
        # For Claude 3.7 with thinking mode, all thinking tokens are in output_tokens
        # No separate tracking needed unless API changes
        
        # Calculate total
        tokens["total_tokens"] = (
            tokens["prompt_tokens"] + 
            tokens["completion_tokens"] + 
            tokens["cached_tokens"]
        )
        
        # Estimate cost (2025 pricing)
        tokens["estimated_cost_usd"] = calculate_claude_cost(tokens)
    
    return tokens


def extract_ollama_tokens(response) -> dict:
    """Extract Ollama-specific token information"""
    
    tokens = {}
    
    if hasattr(response, 'usage'):
        usage = response.usage
        
        # Ollama uses different field names
        tokens["prompt_tokens"] = getattr(usage, 'prompt_tokens', 0) or getattr(usage, 'prompt_eval_count', 0)
        tokens["completion_tokens"] = getattr(usage, 'completion_tokens', 0) or getattr(usage, 'eval_count', 0)
        tokens["total_tokens"] = getattr(usage, 'total_tokens', 0) or (tokens["prompt_tokens"] + tokens["completion_tokens"])
        
        # Ollama is free (local execution)
        tokens["estimated_cost_usd"] = 0.0
        
    # Ollama may also provide these in the raw response
    elif hasattr(response, '_raw_response'):
        raw = response._raw_response
        if isinstance(raw, dict):
            tokens["prompt_tokens"] = raw.get('prompt_eval_count', 0)
            tokens["completion_tokens"] = raw.get('eval_count', 0)
            tokens["total_tokens"] = tokens["prompt_tokens"] + tokens["completion_tokens"]
            
            # Extract performance metrics if available
            if 'eval_duration' in raw and tokens["completion_tokens"] > 0:
                eval_duration_ns = raw['eval_duration']
                eval_duration_ms = eval_duration_ns / 1_000_000
                tokens["ms_per_token"] = eval_duration_ms / tokens["completion_tokens"]
                tokens["tokens_per_second"] = tokens["completion_tokens"] / (eval_duration_ms / 1000)
    
    return tokens


def extract_openai_tokens(response) -> dict:
    """Extract OpenAI/GPT token information"""
    
    tokens = {}
    
    if hasattr(response, 'usage'):
        usage = response.usage
        
        # Standard OpenAI fields
        tokens["prompt_tokens"] = getattr(usage, 'prompt_tokens', 0)
        tokens["completion_tokens"] = getattr(usage, 'completion_tokens', 0)
        tokens["total_tokens"] = getattr(usage, 'total_tokens', 0)
        
        # Check for reasoning tokens (o1, o3 models)
        if hasattr(usage, 'completion_tokens_details'):
            details = usage.completion_tokens_details
            if hasattr(details, 'reasoning_tokens'):
                tokens["thinking_tokens"] = details.reasoning_tokens
        
        # Estimate cost based on model
        tokens["estimated_cost_usd"] = calculate_openai_cost(response.model, tokens)
    
    return tokens


def extract_generic_tokens(response) -> dict:
    """Generic token extraction for unknown providers"""
    
    tokens = {}
    
    if hasattr(response, 'usage'):
        usage = response.usage
        
        # Try common field names
        for prompt_field in ['prompt_tokens', 'input_tokens', 'prompt_eval_count']:
            if hasattr(usage, prompt_field):
                tokens["prompt_tokens"] = getattr(usage, prompt_field, 0)
                break
        
        for completion_field in ['completion_tokens', 'output_tokens', 'eval_count']:
            if hasattr(usage, completion_field):
                tokens["completion_tokens"] = getattr(usage, completion_field, 0)
                break
        
        tokens["total_tokens"] = getattr(usage, 'total_tokens', 
                                        tokens.get("prompt_tokens", 0) + tokens.get("completion_tokens", 0))
    
    return tokens


def calculate_claude_cost(tokens: dict) -> float:
    """Calculate Claude API cost based on token usage"""
    
    # Claude Sonnet-4 pricing (2025)
    INPUT_PRICE = 3.00 / 1_000_000   # $3 per million
    OUTPUT_PRICE = 15.00 / 1_000_000  # $15 per million (includes thinking)
    CACHE_WRITE_PRICE = 3.75 / 1_000_000
    CACHE_READ_PRICE = 0.30 / 1_000_000
    
    cost = (
        tokens.get("prompt_tokens", 0) * INPUT_PRICE +
        tokens.get("completion_tokens", 0) * OUTPUT_PRICE +
        tokens.get("cache_write_tokens", 0) * CACHE_WRITE_PRICE +
        tokens.get("cache_read_tokens", 0) * CACHE_READ_PRICE
    )
    
    return cost


def calculate_openai_cost(model: str, tokens: dict) -> float:
    """Calculate OpenAI API cost based on model and tokens"""
    
    # Simplified pricing (2025 estimates)
    pricing = {
        "gpt-4": {"input": 30.00, "output": 60.00},
        "gpt-4o": {"input": 5.00, "output": 15.00},
        "gpt-3.5": {"input": 0.50, "output": 1.50},
        "o1": {"input": 15.00, "output": 60.00},  # Includes reasoning
    }
    
    # Determine model family
    model_family = "gpt-4"
    for family in pricing:
        if family in model.lower():
            model_family = family
            break
    
    rates = pricing[model_family]
    cost = (
        tokens.get("prompt_tokens", 0) * rates["input"] / 1_000_000 +
        (tokens.get("completion_tokens", 0) + tokens.get("thinking_tokens", 0)) * rates["output"] / 1_000_000
    )
    
    return cost


# Integration code for litellm.py
LITELLM_INTEGRATION = """
# Add this to litellm.py after line 318 where usage is extracted:

# Enhanced token extraction with provider awareness
provider = determine_provider(model)  # You'll need to implement this
enhanced_usage = extract_comprehensive_token_usage(response, provider)

# Merge with existing usage data
if raw_response.get("usage"):
    raw_response["usage"].update(enhanced_usage)
else:
    raw_response["usage"] = enhanced_usage

# Add performance metrics to response
raw_response["performance_metrics"] = {
    "tokens_per_second": enhanced_usage.get("tokens_per_second", 0),
    "ms_per_token": enhanced_usage.get("ms_per_token", 0),
    "estimated_cost_usd": enhanced_usage.get("estimated_cost_usd", 0)
}

# Log comprehensive metrics
logger.info(
    f"Token metrics: {enhanced_usage['completion_tokens']} output tokens "
    f"at {enhanced_usage['tokens_per_second']:.1f} TPS "
    f"(${enhanced_usage['estimated_cost_usd']:.6f})",
    provider=provider,
    cached_tokens=enhanced_usage.get("cached_tokens", 0),
    thinking_tokens=enhanced_usage.get("thinking_tokens", 0)
)
"""

def main():
    print("Token Extraction Improvements for litellm.py")
    print("=" * 60)
    print()
    print("Key improvements:")
    print("1. Unified token extraction across all providers")
    print("2. Capture cache tokens for Claude")
    print("3. Handle Ollama's different field names")
    print("4. Track thinking/reasoning tokens where available")
    print("5. Calculate performance metrics (TPS, ms/token)")
    print("6. Estimate costs based on provider pricing")
    print()
    print("Integration points:")
    print("- Add extract_comprehensive_token_usage() function")
    print("- Call after response.usage extraction")
    print("- Store enhanced metrics in response")
    print("- Log performance data for analysis")
    print()
    print("This ensures consistent token tracking across all providers!")

if __name__ == "__main__":
    main()