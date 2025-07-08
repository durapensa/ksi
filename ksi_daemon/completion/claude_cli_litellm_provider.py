"""
claude_cli_litellm_provider.py - LiteLLM custom provider for Claude CLI

A KSI-integrated provider that shells out to the claude CLI tool.
Designed specifically for KSI's needs, not as a general-purpose provider.

Key features:
- Progressive timeout strategy for long-running Claude operations
- Progress monitoring to detect hung processes
- Session continuity via --resume flag
- Proper error mapping to LiteLLM/OpenAI conventions
- Integration with KSI's configuration and logging
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# Disable LiteLLM's HTTP request for model pricing on startup
os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'true'

# Suppress LiteLLM's console logging to maintain JSON format
import logging

import litellm
from litellm import CustomLLM
from litellm.exceptions import APIConnectionError, APIError, BadRequestError, ServiceUnavailableError, Timeout

litellm.suppress_debug_info = True
litellm.set_verbose = False
# Disable LiteLLM's internal logging to console
logging.getLogger("LiteLLM").setLevel(logging.CRITICAL)
logging.getLogger("litellm").setLevel(logging.CRITICAL)

# Import KSI components
from ksi_common.config import config
from ksi_common.logging import get_bound_logger

# Configuration
logger = get_bound_logger("claude_cli_provider", version="3.0.0")
# Log the claude binary path for debugging
logger.info(f"Claude CLI provider initialized with claude_bin={config.claude_bin}")
# No default model - completion service must provide one

# Replicate model name detection constants
REPLICATE_MODEL_NAME_WITH_ID_LENGTH = 64


class ClaudeCLIError(Exception):
    """Custom error for Claude CLI provider issues"""
    def __init__(self, status_code: int, message: str, stderr: str = ""):
        self.status_code = status_code
        self.message = message
        self.stderr = stderr
        super().__init__(self.message)


def build_cmd(
    prompt: str,
    *,
    output_format: str = "json",
    model_name: str,
    allowed_tools: Optional[List[str]] = None,
    disallowed_tools: Optional[List[str]] = None,
    session_id: Optional[str] = None,
    max_turns: Optional[int] = None,
    mcp_config: Optional[str] = None,
) -> List[str]:
    """Compose the argv list for the Claude CLI."""
    cmd = [
        str(config.claude_bin) if config.claude_bin else "claude",
        "-p",
        "--output-format",
        output_format,
        "--model",
        model_name,
    ]
    if allowed_tools:
        cmd += ["--allowedTools"] + allowed_tools
    if disallowed_tools:
        cmd += ["--disallowedTools"] + disallowed_tools
    if max_turns is not None:
        cmd += ["--max-turns", str(max_turns)]
    if session_id:
        cmd += ["--resume", session_id]
    if mcp_config:
        cmd += ["--mcp-config", mcp_config]
    cmd.append(prompt)
    return cmd


def allowed_tools_from_openai(tools_block: Optional[List[Dict[str, Any]]]) -> List[str]:
    """Translate an OpenAI tools array into CLI allow-list names."""
    if not tools_block:
        return []
    out: List[str] = []
    for tool in tools_block:
        if tool.get("type") == "function":
            fn = tool.get("function", {})
            if "name" in fn:
                out.append(fn["name"])
    return out




def map_subprocess_error_to_litellm(e: Exception, model: str) -> Exception:
    """Map subprocess errors to appropriate LiteLLM/OpenAI-style exceptions"""
    
    if isinstance(e, subprocess.TimeoutExpired):
        return Timeout(
            message=f"Claude CLI timed out after {e.timeout}s",
            model=model,
            llm_provider="claude-cli"
        )
    
    elif isinstance(e, subprocess.CalledProcessError):
        # Map based on return code
        if e.returncode in [-9, -15]:  # SIGKILL, SIGTERM
            return ServiceUnavailableError(
                message=f"Claude CLI terminated with signal {e.returncode}",
                model=model,
                llm_provider="claude-cli"
            )
        elif e.returncode == 1:  # General error - could be bad prompt
            stderr = e.stderr if hasattr(e, 'stderr') else ""
            return BadRequestError(
                message=f"Claude CLI error: {stderr or 'Invalid request'}",
                model=model,
                llm_provider="claude-cli"
            )
        else:
            return APIError(
                message=f"Claude CLI failed with code {e.returncode}",
                model=model,
                status_code=500,
                llm_provider="claude-cli"
            )
    
    elif isinstance(e, FileNotFoundError):
        return APIConnectionError(
            message=f"Claude CLI not found at {config.claude_bin or 'claude'}",
            model=model,
            llm_provider="claude-cli"
        )
    
    elif isinstance(e, ClaudeCLIError):
        # Map our custom error based on status code
        if e.status_code == 400:
            return BadRequestError(
                message=e.message,
                model=model,
                llm_provider="claude-cli"
            )
        else:
            return APIError(
                message=e.message,
                model=model,
                status_code=e.status_code,
                llm_provider="claude-cli"
            )
    
    # Default to generic API error
    return APIError(
        message=f"Claude CLI error: {str(e)}",
        model=model,
        status_code=500,
        llm_provider="claude-cli"
    )


class ClaudeCLIProvider(CustomLLM):
    """
    KSI-integrated LiteLLM provider for Claude CLI.
    
    LiteLLM calls this provider with pure model names (e.g., "claude-sonnet-4-20250514")
    after stripping the "claude-cli/" prefix used for routing.
    
    This provider is designed specifically for KSI and integrates with:
    - KSI's configuration system for timeouts
    - KSI's structured logging
    - KSI's error handling patterns
    
    Note: Streaming is not supported as Claude CLI doesn't provide it
    and KSI doesn't use streaming completions.
    """

    _llm_provider = "claude-cli"
    
    def __init__(self):
        super().__init__()
        # Track active processes for cleanup on cancellation
        self.active_processes = {}  # request_id -> subprocess.Process
        self.process_lock = asyncio.Lock()
        
        logger.info(
            "Claude CLI provider initialized",
            claude_bin=str(config.claude_bin) if config.claude_bin else "claude",
            timeout_attempts=config.claude_timeout_attempts,
            progress_timeout=config.claude_progress_timeout
        )

    async def _cleanup_active_processes(self):
        """Clean up any active subprocess on cancellation"""
        async with self.process_lock:
            for request_id, process in list(self.active_processes.items()):
                try:
                    if process.returncode is None:  # Process still running
                        logger.warning(f"Killing active Claude process (PID: {process.pid}, request: {request_id}) due to cancellation")
                        process.terminate()
                        try:
                            await asyncio.wait_for(process.wait(), timeout=5)
                        except asyncio.TimeoutError:
                            process.kill()
                            await process.wait()
                except Exception as e:
                    logger.error(f"Error cleaning up process {request_id}: {e}")
            self.active_processes.clear()

    def shutdown(self):
        """Gracefully shutdown the provider and clean up resources"""
        logger.info("Shutting down Claude CLI provider")
        
        # Clean up any active processes first
        try:
            # Check if we're in an async context
            try:
                asyncio.get_running_loop()
                # We're in an event loop, create a task
                asyncio.create_task(self._cleanup_active_processes())
            except RuntimeError:
                # No event loop, we can run directly
                asyncio.run(self._cleanup_active_processes())
        except Exception as e:
            logger.error(f"Error cleaning up processes during shutdown: {e}")
        
        logger.info("Claude CLI provider shutdown complete")

    # ------------------------- public sync entry-points ---------------------- #

    def completion(self, messages, *args, **kwargs):
        """Synchronous completion - not supported in KSI daemon context"""
        if kwargs.get("stream"):
            raise NotImplementedError(
                "Claude CLI provider does not support streaming. "
                "KSI uses non-streaming completions only."
            )
        
        # Check if we're in an async context
        try:
            asyncio.get_running_loop()
            # We're in an event loop - this shouldn't happen in KSI
            raise RuntimeError(
                "Synchronous completion() called from async context. "
                "KSI daemon should use acompletion() instead. "
                "Check that completion_service.py and litellm.py are using await litellm.acompletion()"
            )
        except RuntimeError as e:
            if "no running event loop" in str(e).lower():
                # No event loop running, we can use asyncio.run() for testing
                return asyncio.run(self._acompletion(messages, *args, **kwargs))
            else:
                # Re-raise other RuntimeErrors
                raise

    def streaming(self, messages, *args, **kwargs):
        """Streaming not supported - Claude CLI doesn't provide incremental output"""
        raise NotImplementedError(
            "Claude CLI provider does not support streaming. "
            "Use stream=False for non-streaming completions."
        )

    # ------------------------- public async entry-points --------------------- #

    async def acompletion(self, messages, *args, **kwargs):
        """Async completion - main entry point for KSI"""
        if kwargs.get("stream"):
            raise NotImplementedError(
                "Claude CLI provider does not support streaming. "
                "KSI uses non-streaming completions only."
            )
        
        try:
            return await self._acompletion(messages, *args, **kwargs)
        except asyncio.CancelledError:
            # Clean up any running subprocesses on cancellation
            await self._cleanup_active_processes()
            raise

    async def astreaming(self, messages, *args, **kwargs):
        """Async streaming not supported"""
        raise NotImplementedError(
            "Claude CLI provider does not support streaming. "
            "Use stream=False for non-streaming completions."
        )

    # ------------------------- internal implementation ----------------------- #

    async def _acompletion(self, messages, *args, **kwargs):
        """Claude CLI execution with intelligent retry logic"""
        prompt, model_name = self._extract_prompt_and_model(messages, *args, **kwargs)
        
        # Extract request_id for process tracking
        request_id = kwargs.get("request_id", str(uuid.uuid4()))
        
        # Extract KSI parameters from extra_body
        extra_body = kwargs.get("extra_body", {})
        logger.debug(f"Provider received extra_body: {extra_body}")
        ksi_params = extra_body.get("ksi", {})
        sandbox_dir = ksi_params.get("sandbox_dir")
        ksi_permissions = ksi_params.get("permissions", {})
        mcp_config_path = ksi_params.get("mcp_config_path")
        
        # Respect LiteLLM timeout parameter, fall back to config if not provided
        litellm_timeout = kwargs.get('timeout')
        if litellm_timeout:
            timeouts = [float(litellm_timeout)]  # Use LiteLLM timeout
            logger.debug(f"Using LiteLLM timeout: {litellm_timeout}s")
        else:
            timeouts = config.claude_timeout_attempts  # [300, 900, 1800] = 5min, 15min, 30min
        
        logger.info(
            "Starting Claude CLI completion",
            model=model_name,
            session_id=kwargs.get("session_id"),
            timeout_strategy=timeouts,
            sandbox_dir=sandbox_dir,
            permission_profile=ksi_permissions.get("profile"),
            mcp_config_path=mcp_config_path
        )
        
        for attempt, timeout in enumerate(timeouts):
            # Get allowed tools from KSI permissions or fall back to OpenAI tools
            if "allowed_tools" in ksi_permissions:
                allowed = ksi_permissions["allowed_tools"]
            else:
                allowed = allowed_tools_from_openai(kwargs.get("tools"))
            
            disallowed = kwargs.get("disallowed_tools") or []
            session_id = kwargs.get("session_id")
            max_turns = kwargs.get("max_turns")

            cmd = build_cmd(
                prompt,
                output_format="json",
                model_name=model_name,
                allowed_tools=allowed,
                disallowed_tools=disallowed,
                session_id=session_id,
                max_turns=max_turns,
                mcp_config=mcp_config_path,
            )
            
            try:
                logger.debug(
                    f"Attempt {attempt + 1}/{len(timeouts)}",
                    timeout=timeout,
                    session_id=session_id
                )
                
                # Use asyncio subprocess with proper cancellation support
                try:
                    result = await asyncio.wait_for(
                        self._run_claude_async_with_progress(
                            cmd,
                            timeout,
                            model_name,
                            sandbox_dir,
                            request_id
                        ),
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    # Convert asyncio timeout to LiteLLM Timeout exception
                    from litellm.exceptions import Timeout
                    raise Timeout(
                        message=f"Claude CLI timed out after {timeout}s",
                        model=model_name,
                        llm_provider="claude-cli"
                    )
                
                # Success - process the result
                return self._process_claude_result(result, model_name, prompt)
                
            except subprocess.TimeoutExpired as e:
                if attempt < len(timeouts) - 1:  # Not final attempt
                    logger.warning(
                        f"Claude timeout after {timeout}s, attempt {attempt + 1}/{len(timeouts)}",
                        next_timeout=timeouts[attempt + 1]
                    )
                    # Fresh session on timeout (process may have been hanging)
                    kwargs.pop("session_id", None)
                    await asyncio.sleep(config.claude_retry_backoff)
                else:
                    # Final attempt failed - map to LiteLLM exception
                    raise map_subprocess_error_to_litellm(e, model_name)
                    
            except Exception as e:
                # Map all errors to LiteLLM exceptions
                raise map_subprocess_error_to_litellm(e, model_name)
    
    async def _run_claude_async_with_progress(self, cmd: List[str], timeout: int, model: str, sandbox_dir: Optional[str] = None, request_id: str = None):
        """Run Claude with asyncio subprocess and progress monitoring"""
        progress_timeout = config.claude_progress_timeout  # 5 minutes default
        
        # Set working directory - use sandbox if provided, else project root
        if sandbox_dir:
            working_dir = Path(sandbox_dir)
            logger.info("Using sandbox directory", sandbox_dir=sandbox_dir)
        else:
            working_dir = Path(__file__).parent.parent.parent.parent
            logger.debug("Using project root as working directory")
        
        logger.debug(
            "Executing Claude CLI with asyncio",
            cmd=" ".join(cmd),
            timeout=timeout,
            progress_timeout=progress_timeout,
            working_dir=str(working_dir),
            request_id=request_id
        )
        
        start_time = time.time()
        last_output_time = time.time()
        stdout_chunks = []
        stderr_chunks = []
        
        async def read_stream_async(stream, chunks, stream_name):
            """Read from stream using asyncio"""
            nonlocal last_output_time
            try:
                while True:
                    chunk = await stream.read(1024)
                    if not chunk:
                        break
                    chunk_str = chunk.decode('utf-8', errors='replace')
                    chunks.append(chunk_str)
                    last_output_time = time.time()
                    if stream_name == "stderr" and chunk_str.strip():
                        logger.debug(f"Claude stderr: {chunk_str.strip()}")
            except asyncio.CancelledError:
                # Stream reading cancelled - this is expected during process cancellation
                pass
            except Exception as e:
                logger.error(f"Error reading {stream_name}: {e}")
        
        process = None
        try:
            # Start async subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(working_dir),
                env=os.environ
            )
            
            # Register process for cleanup on cancellation
            if request_id:
                async with self.process_lock:
                    self.active_processes[request_id] = process
            
            # Start async stream readers
            stdout_task = asyncio.create_task(
                read_stream_async(process.stdout, stdout_chunks, "stdout")
            )
            stderr_task = asyncio.create_task(
                read_stream_async(process.stderr, stderr_chunks, "stderr")
            )
            
            # Monitor progress and timeouts
            while process.returncode is None:
                current_time = time.time()
                elapsed = current_time - start_time
                
                # Check if no output for progress_timeout seconds (might be hanging)
                time_since_output = current_time - last_output_time
                if time_since_output > progress_timeout:
                    logger.error(
                        f"No output for {progress_timeout}s, killing process",
                        elapsed=elapsed,
                        request_id=request_id
                    )
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=5)
                    except asyncio.TimeoutError:
                        process.kill()
                        await process.wait()
                    raise subprocess.TimeoutExpired(cmd, progress_timeout)
                
                # Check overall timeout
                if elapsed > timeout:
                    logger.error(
                        f"Overall timeout {timeout}s exceeded, killing process",
                        elapsed=elapsed,
                        request_id=request_id
                    )
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=5)
                    except asyncio.TimeoutError:
                        process.kill()
                        await process.wait()
                    raise subprocess.TimeoutExpired(cmd, timeout)
                
                # Sleep briefly to avoid busy waiting
                await asyncio.sleep(1)
            
            # Wait for stream readers to complete
            try:
                await asyncio.wait_for(asyncio.gather(stdout_task, stderr_task), timeout=5)
            except asyncio.TimeoutError:
                logger.warning("Stream readers timed out, cancelling")
                stdout_task.cancel()
                stderr_task.cancel()
            
            # Combine all output
            stdout = ''.join(stdout_chunks)
            stderr = ''.join(stderr_chunks)
            
            # Check return code
            if process.returncode != 0:
                logger.error(
                    f"Claude CLI failed with code {process.returncode}",
                    stderr=stderr[:500],  # First 500 chars of stderr
                    request_id=request_id
                )
                raise subprocess.CalledProcessError(process.returncode, cmd, stdout, stderr)
            
            # Return object that mimics subprocess.CompletedProcess
            class CompletedProcessResult:
                def __init__(self, returncode, stdout, stderr):
                    self.returncode = returncode
                    self.stdout = stdout
                    self.stderr = stderr
                    self.args = cmd
            
            elapsed = time.time() - start_time
            logger.info(
                "Claude CLI completed successfully",
                elapsed=f"{elapsed:.1f}s",
                output_size=len(stdout),
                request_id=request_id
            )
            
            return CompletedProcessResult(process.returncode, stdout, stderr)
            
        except asyncio.CancelledError:
            # Process cancellation - clean up subprocess
            if process and process.returncode is None:
                logger.info(f"Cancelling Claude CLI process (request: {request_id})")
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
            raise
        except Exception:
            # Ensure process is terminated on any error
            if process and process.returncode is None:
                try:
                    process.terminate()
                    await asyncio.wait_for(process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
            raise
        finally:
            # Clean up process tracking
            if request_id:
                async with self.process_lock:
                    self.active_processes.pop(request_id, None)
    
    def _process_claude_result(self, result, model_name: str, prompt: str):
        """Process successful Claude CLI result and create LiteLLM response"""
        raw_response = result.stdout
        stderr_output = result.stderr
        
        # For KSI, we pass through the raw JSON response
        # The completion_service.py will parse and wrap it properly
        # KSI always uses --output-format json, so we expect valid JSON
        
        # Create LiteLLM response with raw JSON
        # Use the full model name with provider prefix for LiteLLM
        response = litellm.completion(  # type: ignore
            model=f"claude-cli/{model_name}",
            mock_response=raw_response,  # Pass raw JSON string
            messages=[{"role": "user", "content": prompt}],
        )
        
        # Attach metadata for debugging and compatibility
        response._raw_stdout = raw_response
        response._stderr = stderr_output
        
        # Try to extract session_id for convenience
        try:
            claude_data = json.loads(raw_response)
            # Claude CLI returns session_id in snake_case already!
            if "session_id" in claude_data:
                response.session_id = claude_data["session_id"]
            response._claude_metadata = claude_data
            
            logger.debug(
                "Created LiteLLM response",
                has_session_id="session_id" in claude_data,
                response_type=claude_data.get("type"),
                is_error=claude_data.get("is_error", False)
            )
        except json.JSONDecodeError as e:
            logger.warning(
                f"Claude CLI returned invalid JSON: {e}",
                raw_response_preview=raw_response[:200]
            )
            response._json_decode_error = str(e)
            
        return response

    def _extract_prompt_and_model(self, messages, *args, **kwargs):
        """Extract prompt and model from LiteLLM kwargs - receives pure model name"""
        prompt = messages[-1]["content"]
        
        # LiteLLM strips the "claude-cli/" prefix before calling this provider
        # So we receive only the pure model name (e.g., "claude-sonnet-4-20250514")
        model_name = kwargs.get("model")
        if not model_name:
            raise BadRequestError(
                message="No model specified. Completion service must provide a model.",
                model="unknown",
                llm_provider="claude-cli"
            )
        
        # Pass the model name directly to claude CLI - no processing needed
        logger.debug(f"Using model: {model_name}")
        return prompt, model_name


# Register provider with LiteLLM
_provider = ClaudeCLIProvider()
litellm.custom_provider_map.append(
    {"provider": "claude-cli", "custom_handler": _provider}
)

logger.info("Claude CLI provider registered with LiteLLM")


# Quick self-test when run directly
if __name__ == "__main__":
    import sys
    
    # Configure structlog for standalone testing
    from ksi_common import configure_structlog
    configure_structlog(log_level="DEBUG", log_format="console")
    
    user_prompt = sys.argv[1] if len(sys.argv) > 1 else "Hello! Please respond with a simple greeting."
    
    print("Testing Claude CLI provider...")
    print(f"Prompt: {user_prompt}")
    print("-" * 50)
    
    try:
        resp = litellm.completion(
            model="claude-cli/sonnet",
            messages=[{"role": "user", "content": user_prompt}],
            max_turns=1,
        )
        
        print("Response:")
        print(resp.choices[0].message.content)
        
        if hasattr(resp, 'sessionId'):
            print(f"\nSession ID: {resp.sessionId}")
            
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        sys.exit(1)