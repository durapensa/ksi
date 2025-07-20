# DSPy Async and LiteLLM Integration Research

## Executive Summary

After extensive research into DSPy's architecture and KSI's requirements, I recommend a **hybrid approach** that uses direct LiteLLM for optimization operations while maintaining the full completion service for production agent operations. This approach leverages KSI's existing LiteLLM infrastructure without requiring streaming support.

## Key Findings

### 1. DSPy Does Not Require Streaming

**Critical Discovery**: MIPROv2 optimization does not use streaming at all.

- DSPy's optimization algorithms need complete responses for evaluation
- The `_generate` method in MIPROv2 always uses `streaming=False`
- KSI's non-streaming LiteLLM providers are fully compatible
- No need for special streaming adapters or workarounds

### 2. DSPy's Sync-First Architecture

**Architecture Analysis**:
- DSPy is fundamentally synchronous with optional async support
- Core operations use `dspy.LM.__call__()` which is sync-only
- Async methods exist (`__acall__`) but are not used by optimizers
- Running DSPy in a thread pool is the standard async integration pattern

### 3. LiteLLM Integration Pattern

**Direct Integration Benefits**:
- DSPy already uses LiteLLM internally
- KSI's `claude_cli_litellm_provider.py` can be reused directly
- No need for the full completion service overhead during optimization
- Simpler error handling and timeout management

## Recommended Architecture

### Hybrid Approach: Direct LiteLLM for Optimization

```python
# For DSPy optimization - direct LiteLLM
import litellm
from ksi_daemon.completion import claude_cli_litellm_provider

# DSPy uses this directly
response = await litellm.acompletion(
    model="claude-cli/sonnet",
    messages=[{"role": "user", "content": prompt}],
    extra_body={"ksi": {"sandbox_dir": sandbox_dir}}
)

# For production agents - full completion service
result = await router.emit_first("completion:async", {
    "agent_id": agent_id,
    "prompt": prompt
})
```

### Why This Works

1. **Optimization is Different**: 
   - Optimization doesn't need agent persistence
   - No session management required
   - Simpler sandbox requirements
   - Direct model access is cleaner

2. **Reuse Existing Infrastructure**:
   - `claude_cli_litellm_provider.py` already handles all CLI complexity
   - Timeout strategies, error mapping, process management all included
   - No new code needed, just import and use

3. **Clean Separation of Concerns**:
   - Optimization: Direct LiteLLM for simplicity
   - Production: Full completion service for features
   - Clear architectural boundaries

## Implementation Strategy

### Phase 1: Basic Integration (Completed)
- Created `KSILMAdapter` as a thin wrapper around LiteLLM
- Implemented mock responses for testing
- Verified DSPy can load and use the adapter

### Phase 2: Thread Pool Execution
```python
async def optimize_component_async(self, component_path: str, config: Dict):
    """Run DSPy optimization in thread pool"""
    loop = asyncio.get_event_loop()
    
    # DSPy runs in thread pool
    result = await loop.run_in_executor(
        self.executor,
        self._optimize_component_sync,
        component_path,
        config
    )
    return result
```

### Phase 3: Direct LiteLLM Connection
```python
class KSILMAdapter:
    def __call__(self, prompt, **kwargs):
        """Sync wrapper using asyncio.run()"""
        return asyncio.run(self._acall(prompt, **kwargs))
    
    async def _acall(self, prompt, **kwargs):
        """Direct LiteLLM call"""
        response = await litellm.acompletion(
            model=f"claude-cli/{self.model}",
            messages=[{"role": "user", "content": prompt}],
            extra_body={"ksi": {"sandbox_dir": self.sandbox_dir}},
            **kwargs
        )
        return [response.choices[0].message.content]
```

## Rejected Alternatives

### 1. Full Async DSPy
- **Why Rejected**: MIPROv2 doesn't use async methods
- Would require rewriting core DSPy algorithms
- No benefit since optimization isn't latency-sensitive

### 2. Agent-Based Adapter
- **Why Rejected**: Unnecessary complexity
- Session management overhead not needed
- Would couple optimization to production infrastructure

### 3. Custom Streaming Implementation
- **Why Rejected**: DSPy doesn't use streaming
- Would add complexity with no benefit
- KSI doesn't need streaming anywhere

## Benefits of Recommended Approach

1. **Simplicity**: Reuse existing, tested code
2. **Performance**: Direct path to models
3. **Isolation**: Optimization separate from production
4. **Flexibility**: Can use different models/configs for optimization
5. **Reliability**: Proven LiteLLM infrastructure

## Next Steps

1. Remove mock responses from `KSILMAdapter`
2. Implement thread pool executor in optimization service
3. Connect adapter directly to LiteLLM
4. Test with actual Claude CLI calls
5. Implement progress tracking via events

## Code Examples

### Simple DSPy Program with KSI
```python
import dspy
from ksi_daemon.optimization.frameworks.ksi_lm_adapter import KSILMAdapter

# Configure DSPy with KSI
lm = KSILMAdapter(model="sonnet")
dspy.configure(lm=lm)

# Use normally
cot = dspy.ChainOfThought("question -> answer")
result = cot(question="What is KSI?")
```

### Optimization with Progress Events
```python
async def optimize_with_progress(component_path: str):
    """Run optimization with event updates"""
    opt_id = start_operation(
        operation_type="optimization",
        service_name="dspy_optimizer"
    )
    
    async def run_optimization():
        # Emit progress events
        await emit_progress(opt_id, 10, "Loading component")
        
        # Run in thread pool
        result = await loop.run_in_executor(
            None,
            run_mipro_optimization,
            component_path
        )
        
        await emit_progress(opt_id, 100, "Complete")
        return result
    
    # Start background task
    asyncio.create_task(run_optimization())
    return {"optimization_id": opt_id}
```

## Conclusion

The hybrid approach elegantly solves the sync/async impedance mismatch by using the right tool for each job. DSPy optimization gets direct, simple access to models via LiteLLM, while production agents continue using the full-featured completion service. This separation of concerns leads to cleaner, more maintainable code.

Most importantly, this approach requires minimal new code - we're reusing KSI's robust LiteLLM infrastructure that already handles all the complexity of Claude CLI interaction, timeout strategies, and error management.