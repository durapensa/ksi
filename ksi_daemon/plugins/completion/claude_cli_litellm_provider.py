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
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

import litellm
from litellm import CustomLLM
from litellm.exceptions import (
    Timeout,
    APIError,
    APIConnectionError,
    BadRequestError,
    ServiceUnavailableError
)

# Import KSI components
from ksi_common.config import config
from ksi_common.logging import get_logger


# Configuration
logger = get_logger("claude_cli_provider")
CLAUDE_BIN = Path(os.getenv("CLAUDE_BIN", "claude")).expanduser()
DEFAULT_CLAUDE_MODEL = "sonnet"  # claude CLI only accepts "sonnet" or "opus"

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
    model_alias: str = DEFAULT_CLAUDE_MODEL,
    allowed_tools: Optional[List[str]] = None,
    disallowed_tools: Optional[List[str]] = None,
    session_id: Optional[str] = None,
    max_turns: Optional[int] = None,
) -> List[str]:
    """Compose the argv list for the Claude CLI."""
    cmd = [
        str(CLAUDE_BIN),
        "-p",
        "--output-format",
        output_format,
        "--model",
        model_alias,
    ]
    if allowed_tools:
        cmd += ["--allowedTools"] + allowed_tools
    if disallowed_tools:
        cmd += ["--disallowedTools"] + disallowed_tools
    if max_turns is not None:
        cmd += ["--max-turns", str(max_turns)]
    if session_id:
        cmd += ["--resume", session_id]
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
                llm_provider="claude-cli",
                status_code=500
            )
    
    elif isinstance(e, FileNotFoundError):
        return APIConnectionError(
            message=f"Claude CLI not found at {CLAUDE_BIN}",
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
                llm_provider="claude-cli",
                status_code=e.status_code
            )
    
    # Default to generic API error
    return APIError(
        message=f"Claude CLI error: {str(e)}",
        model=model,
        llm_provider="claude-cli",
        status_code=500
    )


class ClaudeCLIProvider(CustomLLM):
    """
    KSI-integrated LiteLLM provider for Claude CLI.
    
    Use via model="claude-cli/sonnet" or model="claude-cli/opus"
    
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
        # Dedicated executor for long-running Claude operations
        self.claude_executor = ThreadPoolExecutor(
            max_workers=config.claude_max_workers,
            thread_name_prefix="claude-cli"
        )
        # Track active processes for cleanup on cancellation
        self.active_processes = {}  # thread_id -> subprocess.Popen
        self.process_lock = threading.Lock()
        
        logger.info(
            "Claude CLI provider initialized",
            claude_bin=str(CLAUDE_BIN),
            max_workers=config.claude_max_workers,
            timeout_attempts=config.claude_timeout_attempts,
            progress_timeout=config.claude_progress_timeout
        )

    def _cleanup_active_processes(self):
        """Clean up any active subprocess on cancellation"""
        with self.process_lock:
            for thread_id, process in list(self.active_processes.items()):
                try:
                    if process.poll() is None:  # Process still running
                        logger.warning(f"Killing active Claude process (PID: {process.pid}) due to cancellation")
                        process.kill()
                        process.wait(timeout=5)
                except Exception as e:
                    logger.error(f"Error cleaning up process: {e}")
            self.active_processes.clear()

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
            loop = asyncio.get_running_loop()
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
            self._cleanup_active_processes()
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
        prompt, model_alias = self._extract_prompt_and_model(messages, *args, **kwargs)
        full_model = f"claude-cli/{model_alias}"
        
        # Respect LiteLLM timeout parameter, fall back to config if not provided
        litellm_timeout = kwargs.get('timeout')
        if litellm_timeout:
            timeouts = [float(litellm_timeout)]  # Use LiteLLM timeout
            logger.debug(f"Using LiteLLM timeout: {litellm_timeout}s")
        else:
            timeouts = config.claude_timeout_attempts  # [300, 900, 1800] = 5min, 15min, 30min
        
        logger.info(
            "Starting Claude CLI completion",
            model=model_alias,
            session_id=kwargs.get("session_id"),
            timeout_strategy=timeouts
        )
        
        for attempt, timeout in enumerate(timeouts):
            allowed = allowed_tools_from_openai(kwargs.get("tools"))
            disallowed = kwargs.get("disallowed_tools") or []
            session_id = kwargs.get("session_id")
            max_turns = kwargs.get("max_turns")

            cmd = build_cmd(
                prompt,
                output_format="json",
                model_alias=model_alias,
                allowed_tools=allowed,
                disallowed_tools=disallowed,
                session_id=session_id,
                max_turns=max_turns,
            )
            
            try:
                logger.debug(
                    f"Attempt {attempt + 1}/{len(timeouts)}",
                    timeout=timeout,
                    session_id=session_id
                )
                
                # Use thread executor with proper cancellation support
                loop = asyncio.get_event_loop()
                
                # Use asyncio.wait_for to ensure proper cancellation
                try:
                    result = await asyncio.wait_for(
                        loop.run_in_executor(
                            self.claude_executor,
                            self._run_claude_sync_with_progress,
                            cmd,
                            timeout,
                            full_model
                        ),
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    # Convert asyncio timeout to LiteLLM Timeout exception
                    from litellm.exceptions import Timeout
                    raise Timeout(
                        message=f"Claude CLI timed out after {timeout}s",
                        model=full_model,
                        llm_provider="claude-cli"
                    )
                
                # Success - process the result
                return self._process_claude_result(result, model_alias, prompt)
                
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
                    raise map_subprocess_error_to_litellm(e, full_model)
                    
            except Exception as e:
                # Map all errors to LiteLLM exceptions
                raise map_subprocess_error_to_litellm(e, full_model)
    
    def _run_claude_sync_with_progress(self, cmd: List[str], timeout: int, model: str):
        """Run Claude with cross-platform progress monitoring"""
        progress_timeout = config.claude_progress_timeout  # 5 minutes default
        
        logger.debug(
            "Executing Claude CLI",
            cmd=" ".join(cmd),
            timeout=timeout,
            progress_timeout=progress_timeout
        )
        
        # Set working directory to project root (matching daemon behavior)
        project_root = Path(__file__).parent.parent.parent.parent
        
        start_time = time.time()
        last_output_time = time.time()
        stdout_chunks = []
        stderr_chunks = []
        output_lock = threading.Lock()
        
        def update_last_output_time():
            nonlocal last_output_time
            with output_lock:
                last_output_time = time.time()
        
        def read_stream(stream, chunks, stream_name):
            """Read from stream in a separate thread"""
            try:
                while True:
                    chunk = stream.read(1024)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    update_last_output_time()
                    if stream_name == "stderr" and chunk.strip():
                        logger.debug(f"Claude stderr: {chunk.strip()}")
            except ValueError:
                # Stream closed
                pass
            except Exception as e:
                logger.error(f"Error reading {stream_name}: {e}")
        
        try:
            # Start process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(project_root),
                env=os.environ
            )
            
            # Register process for cleanup on cancellation
            thread_id = threading.get_ident()
            with self.process_lock:
                self.active_processes[thread_id] = process
            
            # Start reader threads for cross-platform compatibility
            stdout_thread = threading.Thread(
                target=read_stream, 
                args=(process.stdout, stdout_chunks, "stdout"),
                daemon=True
            )
            stderr_thread = threading.Thread(
                target=read_stream, 
                args=(process.stderr, stderr_chunks, "stderr"),
                daemon=True
            )
            
            stdout_thread.start()
            stderr_thread.start()
            
            # Monitor progress and timeouts
            while process.poll() is None:
                current_time = time.time()
                elapsed = current_time - start_time
                
                # Check if no output for progress_timeout seconds (might be hanging)
                with output_lock:
                    time_since_output = current_time - last_output_time
                    if time_since_output > progress_timeout:
                        logger.error(
                            f"No output for {progress_timeout}s, killing process",
                            elapsed=elapsed
                        )
                        process.kill()
                        process.wait()
                        raise subprocess.TimeoutExpired(cmd, progress_timeout)
                
                # Check overall timeout
                if elapsed > timeout:
                    logger.error(
                        f"Overall timeout {timeout}s exceeded, killing process",
                        elapsed=elapsed
                    )
                    process.kill()
                    process.wait()
                    raise subprocess.TimeoutExpired(cmd, timeout)
                
                # Sleep briefly to avoid busy waiting
                time.sleep(1)
            
            # Wait for reader threads to finish
            stdout_thread.join(timeout=5)
            stderr_thread.join(timeout=5)
            
            # Combine all output
            stdout = ''.join(stdout_chunks)
            stderr = ''.join(stderr_chunks)
            
            # Check return code
            if process.returncode != 0:
                logger.error(
                    f"Claude CLI failed with code {process.returncode}",
                    stderr=stderr[:500]  # First 500 chars of stderr
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
                f"Claude CLI completed successfully",
                elapsed=f"{elapsed:.1f}s",
                output_size=len(stdout)
            )
            
            return CompletedProcessResult(process.returncode, stdout, stderr)
            
        except Exception as e:
            # Ensure process is terminated on any error
            if 'process' in locals():
                try:
                    process.kill()
                    process.wait()
                except:
                    pass
            raise
        finally:
            # Clean up process tracking
            thread_id = threading.get_ident()
            with self.process_lock:
                self.active_processes.pop(thread_id, None)
    
    def _process_claude_result(self, result, model_alias: str, prompt: str):
        """Process successful Claude CLI result and create LiteLLM response"""
        raw_response = result.stdout
        stderr_output = result.stderr
        
        # For KSI, we pass through the raw JSON response
        # The completion_service.py will parse and wrap it properly
        # KSI always uses --output-format json, so we expect valid JSON
        
        # Create LiteLLM response with raw JSON
        response = litellm.completion(  # type: ignore
            model=f"claude-cli/{model_alias}",
            mock_response=raw_response,  # Pass raw JSON string
            messages=[{"role": "user", "content": prompt}],
        )
        
        # Attach metadata for debugging and compatibility
        response._raw_stdout = raw_response
        response._stderr = stderr_output
        
        # Try to extract sessionId for convenience
        try:
            claude_data = json.loads(raw_response)
            if "sessionId" in claude_data:
                response.sessionId = claude_data["sessionId"]
            response._claude_metadata = claude_data
            
            logger.debug(
                "Created LiteLLM response",
                has_session_id="sessionId" in claude_data,
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
        """Extract prompt and validate model from LiteLLM kwargs"""
        prompt = messages[-1]["content"]
        
        # Extract model from kwargs (LiteLLM passes it here)
        full_model = kwargs.get("model", f"claude-cli/{DEFAULT_CLAUDE_MODEL}")
        
        # Extract the part after provider prefix using LiteLLM pattern
        # This handles both "claude-cli/sonnet" and edge cases like just "sonnet"
        parts = full_model.split("/", 1)
        if len(parts) == 2 and parts[0] == "claude-cli":
            # Standard format: claude-cli/model
            model_alias = parts[1]
        elif len(parts) == 1:
            # Just model name without provider prefix
            model_alias = parts[0]
        else:
            # Unexpected format, use default
            model_alias = DEFAULT_CLAUDE_MODEL
            
        # Validate model - claude CLI only accepts "sonnet" or "opus"
        if model_alias not in ["sonnet", "opus"]:
            logger.warning(
                f"Claude CLI model '{model_alias}' not supported, using {DEFAULT_CLAUDE_MODEL}",
                requested_model=model_alias,
                valid_models=["sonnet", "opus"]
            )
            model_alias = DEFAULT_CLAUDE_MODEL
            
        return prompt, model_alias


# Register provider with LiteLLM
_provider = ClaudeCLIProvider()
litellm.custom_provider_map.append(
    {"provider": "claude-cli", "custom_handler": _provider}
)

logger.info("Claude CLI provider registered with LiteLLM")


# Quick self-test when run directly
if __name__ == "__main__":
    import sys
    
    # Configure basic logging for testing
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
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