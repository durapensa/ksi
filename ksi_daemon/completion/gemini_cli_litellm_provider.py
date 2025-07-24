"""
gemini_cli_litellm_provider.py - LiteLLM custom provider for Gemini CLI

A KSI-integrated provider that shells out to the gemini CLI tool.
Adapted from claude_cli_litellm_provider.py for Gemini's simpler interface.

Key differences from Claude CLI provider:
- No JSON output format (plain text only)
- No session continuity/resume capability
- No tool control (allowedTools/disallowedTools)
- Simpler command interface
- Wraps plain text responses in JSON for LiteLLM compatibility

Note: This provider assumes the 'gemini' command is available in PATH
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
from ksi_common.task_management import create_tracked_task

# Configuration
logger = get_bound_logger("gemini_cli_provider", version="1.0.0")
# Log the gemini binary path for debugging
gemini_bin_path = getattr(config, 'gemini_bin', None) or 'gemini'
logger.info(f"Gemini CLI provider initialized with gemini_bin={gemini_bin_path}")


class GeminiCLIError(Exception):
    """Custom error for Gemini CLI provider issues"""
    def __init__(self, status_code: int, message: str, stderr: str = ""):
        self.status_code = status_code
        self.message = message
        self.stderr = stderr
        super().__init__(self.message)


def build_cmd(
    prompt: str,
    *,
    model_name: str = "gemini-2.5-pro",
    sandbox: bool = False,
    sandbox_image: Optional[str] = None,
    debug: bool = False,
    all_files: bool = False,
    yolo: bool = False,
    checkpointing: bool = False,
) -> List[str]:
    """Compose the argv list for the Gemini CLI."""
    gemini_bin = getattr(config, 'gemini_bin', None) or "gemini"
    
    cmd = [
        str(gemini_bin),
        "--model",
        model_name,
        "-p",  # Non-interactive mode
        prompt,
    ]
    
    if sandbox:
        cmd.append("--sandbox")
        if sandbox_image:
            cmd.extend(["--sandbox-image", sandbox_image])
    
    if debug:
        cmd.append("--debug")
    
    if all_files:
        cmd.append("--all_files")
    
    if yolo:
        cmd.append("--yolo")
    
    if checkpointing:
        cmd.append("--checkpointing")
    
    return cmd


def map_subprocess_error_to_litellm(e: Exception, model: str) -> Exception:
    """Map subprocess errors to appropriate LiteLLM/OpenAI-style exceptions"""
    
    if isinstance(e, subprocess.TimeoutExpired):
        return Timeout(
            message=f"Gemini CLI timed out after {e.timeout}s",
            model=model,
            llm_provider="gemini-cli"
        )
    
    elif isinstance(e, subprocess.CalledProcessError):
        # Map based on return code
        if e.returncode in [-9, -15]:  # SIGKILL, SIGTERM
            return ServiceUnavailableError(
                message=f"Gemini CLI terminated with signal {e.returncode}",
                model=model,
                llm_provider="gemini-cli"
            )
        elif e.returncode == 1:  # General error
            stderr = e.stderr if hasattr(e, 'stderr') else ""
            return BadRequestError(
                message=f"Gemini CLI error: {stderr or 'Invalid request'}",
                model=model,
                llm_provider="gemini-cli"
            )
        else:
            return APIError(
                message=f"Gemini CLI failed with code {e.returncode}",
                model=model,
                status_code=500,
                llm_provider="gemini-cli"
            )
    
    elif isinstance(e, FileNotFoundError):
        gemini_bin = getattr(config, 'gemini_bin', None) or 'gemini'
        return APIConnectionError(
            message=f"Gemini CLI not found at {gemini_bin}",
            model=model,
            llm_provider="gemini-cli"
        )
    
    elif isinstance(e, GeminiCLIError):
        # Map our custom error based on status code
        if e.status_code == 400:
            return BadRequestError(
                message=e.message,
                model=model,
                llm_provider="gemini-cli"
            )
        else:
            return APIError(
                message=e.message,
                model=model,
                status_code=e.status_code,
                llm_provider="gemini-cli"
            )
    
    # Default to generic API error
    return APIError(
        message=f"Gemini CLI error: {str(e)}",
        model=model,
        status_code=500,
        llm_provider="gemini-cli"
    )


class GeminiCLIProvider(CustomLLM):
    """
    KSI-integrated LiteLLM provider for Gemini CLI.
    
    LiteLLM calls this provider with pure model names (e.g., "gemini-2.5-pro")
    after stripping the "gemini-cli/" prefix used for routing.
    
    This provider wraps Gemini's plain text output in JSON structure
    for compatibility with LiteLLM's expected response format.
    
    Note: Streaming is not supported as Gemini CLI doesn't provide it
    and KSI doesn't use streaming completions.
    """

    _llm_provider = "gemini-cli"
    
    def __init__(self):
        super().__init__()
        # Track active processes for cleanup on cancellation
        self.active_processes = {}  # request_id -> subprocess.Process
        self.process_lock = asyncio.Lock()
        
        gemini_bin = config.gemini_bin if hasattr(config, 'gemini_bin') else "gemini"
        logger.info(
            "Gemini CLI provider initialized",
            gemini_bin=str(gemini_bin),
            timeout_attempts=config.gemini_timeout_attempts if hasattr(config, 'gemini_timeout_attempts') else [300],
            progress_timeout=config.gemini_progress_timeout if hasattr(config, 'gemini_progress_timeout') else 300
        )

    async def _cleanup_active_processes(self):
        """Clean up any active subprocess on cancellation"""
        async with self.process_lock:
            for request_id, process in list(self.active_processes.items()):
                try:
                    if process.returncode is None:  # Process still running
                        logger.warning(f"Killing active Gemini process (PID: {process.pid}, request: {request_id}) due to cancellation")
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
        logger.info("Shutting down Gemini CLI provider")
        
        # Clean up any active processes first
        try:
            # Check if we're in an async context
            try:
                asyncio.get_running_loop()
                # We're in an event loop, create a task
                create_tracked_task("gemini_cli_provider", self._cleanup_active_processes(), task_name="cleanup_processes")
            except RuntimeError:
                # No event loop, we can run directly
                asyncio.run(self._cleanup_active_processes())
        except Exception as e:
            logger.error(f"Error cleaning up processes during shutdown: {e}")
        
        logger.info("Gemini CLI provider shutdown complete")

    # ------------------------- public sync entry-points ---------------------- #

    def completion(self, messages, *args, **kwargs):
        """Synchronous completion - not supported in KSI daemon context"""
        if kwargs.get("stream"):
            raise NotImplementedError(
                "Gemini CLI provider does not support streaming. "
                "KSI uses non-streaming completions only."
            )
        
        # Check if we're in an async context
        try:
            asyncio.get_running_loop()
            # We're in an event loop - this shouldn't happen in KSI
            raise RuntimeError(
                "Synchronous completion() called from async context. "
                "KSI daemon should use acompletion() instead."
            )
        except RuntimeError as e:
            if "no running event loop" in str(e).lower():
                # No event loop running, we can use asyncio.run() for testing
                return asyncio.run(self._acompletion(messages, *args, **kwargs))
            else:
                # Re-raise other RuntimeErrors
                raise

    def streaming(self, messages, *args, **kwargs):
        """Streaming not supported - Gemini CLI doesn't provide incremental output"""
        raise NotImplementedError(
            "Gemini CLI provider does not support streaming. "
            "Use stream=False for non-streaming completions."
        )

    # ------------------------- public async entry-points --------------------- #

    async def acompletion(self, messages, *args, **kwargs):
        """Async completion - main entry point for KSI"""
        if kwargs.get("stream"):
            raise NotImplementedError(
                "Gemini CLI provider does not support streaming. "
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
            "Gemini CLI provider does not support streaming. "
            "Use stream=False for non-streaming completions."
        )

    # ------------------------- internal implementation ----------------------- #

    async def _acompletion(self, messages, *args, **kwargs):
        """Gemini CLI execution with retry logic"""
        prompt, model_name = self._extract_prompt_and_model(messages, *args, **kwargs)
        
        # Extract request_id for process tracking
        request_id = kwargs.get("request_id", str(uuid.uuid4()))
        
        # Extract KSI parameters from extra_body
        # LiteLLM passes extra_body in optional_params for custom providers
        optional_params = kwargs.get("optional_params", {})
        extra_body = optional_params.get("extra_body", {})
        ksi_params = extra_body.get("ksi", {})
        sandbox_dir = ksi_params.get("sandbox_dir")
        
        # Respect LiteLLM timeout parameter, fall back to config if not provided
        litellm_timeout = kwargs.get('timeout')
        if litellm_timeout:
            timeouts = [float(litellm_timeout)]  # Use LiteLLM timeout
            logger.debug(f"Using LiteLLM timeout: {litellm_timeout}s")
        else:
            # Use simpler timeout strategy for Gemini
            timeouts = getattr(config, 'gemini_timeout_attempts', [300])  # Default 5min
        
        logger.info(
            "Starting Gemini CLI completion",
            model=model_name,
            timeout_strategy=timeouts,
            sandbox_dir=sandbox_dir
        )
        
        for attempt, timeout in enumerate(timeouts):
            # Extract Gemini-specific options
            sandbox = ksi_params.get("sandbox", False)
            sandbox_image = ksi_params.get("sandbox_image")
            debug = ksi_params.get("debug", False)
            all_files = ksi_params.get("all_files", False)
            yolo = ksi_params.get("yolo", False)
            checkpointing = ksi_params.get("checkpointing", False)

            cmd = build_cmd(
                prompt,
                model_name=model_name,
                sandbox=sandbox,
                sandbox_image=sandbox_image,
                debug=debug,
                all_files=all_files,
                yolo=yolo,
                checkpointing=checkpointing,
            )
            
            try:
                logger.debug(
                    f"Attempt {attempt + 1}/{len(timeouts)}",
                    timeout=timeout
                )
                
                # Use asyncio subprocess with proper cancellation support
                try:
                    result = await asyncio.wait_for(
                        self._run_gemini_async_with_progress(
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
                        message=f"Gemini CLI timed out after {timeout}s",
                        model=model_name,
                        llm_provider="gemini-cli"
                    )
                
                # Success - process the result
                return self._process_gemini_result(result, model_name, prompt)
                
            except subprocess.TimeoutExpired as e:
                if attempt < len(timeouts) - 1:  # Not final attempt
                    logger.warning(
                        f"Gemini timeout after {timeout}s, attempt {attempt + 1}/{len(timeouts)}",
                        next_timeout=timeouts[attempt + 1]
                    )
                    await asyncio.sleep(getattr(config, 'gemini_retry_backoff', 2))
                else:
                    # Final attempt failed - map to LiteLLM exception
                    raise map_subprocess_error_to_litellm(e, model_name)
                    
            except Exception as e:
                # Map all errors to LiteLLM exceptions
                raise map_subprocess_error_to_litellm(e, model_name)
    
    async def _run_gemini_async_with_progress(self, cmd: List[str], timeout: int, model: str, sandbox_dir: Optional[str] = None, request_id: str = None):
        """Run Gemini with asyncio subprocess and progress monitoring"""
        progress_timeout = getattr(config, 'gemini_progress_timeout', 300)  # 5 minutes default
        
        # Set working directory - use sandbox if provided, else project root
        if sandbox_dir:
            working_dir = Path(sandbox_dir)
            logger.info("Using sandbox directory", sandbox_dir=sandbox_dir)
        else:
            working_dir = Path(__file__).parent.parent.parent.parent
            logger.debug("Using project root as working directory")
        
        logger.debug(
            "Executing Gemini CLI with asyncio",
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
                        logger.debug(f"Gemini stderr: {chunk_str.strip()}")
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
            stdout_task = create_tracked_task(
                "gemini_cli_provider",
                read_stream_async(process.stdout, stdout_chunks, "stdout"),
                task_name="read_stdout"
            )
            stderr_task = create_tracked_task(
                "gemini_cli_provider",
                read_stream_async(process.stderr, stderr_chunks, "stderr"),
                task_name="read_stderr"
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
                    f"Gemini CLI failed with code {process.returncode}",
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
                "Gemini CLI completed successfully",
                elapsed=f"{elapsed:.1f}s",
                output_size=len(stdout),
                request_id=request_id
            )
            
            return CompletedProcessResult(process.returncode, stdout, stderr)
            
        except asyncio.CancelledError:
            # Process cancellation - clean up subprocess
            if process and process.returncode is None:
                logger.info(f"Cancelling Gemini CLI process (request: {request_id})")
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
    
    def _process_gemini_result(self, result, model_name: str, prompt: str):
        """Process successful Gemini CLI result and create LiteLLM response"""
        raw_response = result.stdout.strip()
        stderr_output = result.stderr
        
        # Gemini CLI returns plain text, so we need to wrap it in a JSON structure
        # that's compatible with LiteLLM's expected format
        
        # Create a mock response structure similar to what Claude CLI would return
        # Generate a unique session ID for Gemini completions to enable response tracking
        gemini_session_id = f"gemini-{uuid.uuid4().hex[:12]}"
        
        gemini_response = {
            "type": "message",
            "content": raw_response,
            "is_error": False,
            "model": model_name,
            "session_id": gemini_session_id,  # Generated ID for tracking
            "metadata": {
                "provider": "gemini-cli",
                "timestamp": time.time(),
                "generated_session_id": True  # Flag to indicate this is not from Gemini
            }
        }
        
        # Convert to JSON string for LiteLLM
        json_response = json.dumps(gemini_response)
        
        # Create LiteLLM response with the JSON
        # Use the full model name with provider prefix for LiteLLM
        response = litellm.completion(  # type: ignore
            model=f"gemini-cli/{model_name}",
            mock_response=json_response,
            messages=[{"role": "user", "content": prompt}],
        )
        
        # Attach metadata for debugging and compatibility
        response._raw_stdout = raw_response
        response._stderr = stderr_output
        response._gemini_metadata = gemini_response
        
        logger.debug(
            "Created LiteLLM response",
            response_type="message",
            content_length=len(raw_response)
        )
        
        return response

    def _extract_prompt_and_model(self, messages, *args, **kwargs):
        """Extract prompt and model from LiteLLM kwargs - receives pure model name"""
        prompt = messages[-1]["content"]
        
        # LiteLLM strips the "gemini-cli/" prefix before calling this provider
        # So we receive only the pure model name (e.g., "gemini-2.5-pro")
        model_name = kwargs.get("model", "gemini-2.5-pro")  # Default to gemini-2.5-pro
        
        # Pass the model name directly to gemini CLI - no processing needed
        logger.debug(f"Using model: {model_name}")
        return prompt, model_name


# Register provider with LiteLLM
_provider = GeminiCLIProvider()
litellm.custom_provider_map.append(
    {"provider": "gemini-cli", "custom_handler": _provider}
)

logger.info("Gemini CLI provider registered with LiteLLM")


# Quick self-test when run directly
if __name__ == "__main__":
    import sys
    
    # Configure structlog for standalone testing
    from ksi_common import configure_structlog
    configure_structlog(log_level="DEBUG", log_format="console")
    
    user_prompt = sys.argv[1] if len(sys.argv) > 1 else "Hello! Please respond with a simple greeting."
    
    print("Testing Gemini CLI provider...")
    print(f"Prompt: {user_prompt}")
    print("-" * 50)
    
    try:
        resp = litellm.completion(
            model="gemini-cli/gemini-2.5-pro",
            messages=[{"role": "user", "content": user_prompt}],
        )
        
        print("Response:")
        print(resp.choices[0].message.content)
        
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        sys.exit(1)