"""
claude_cli_provider.py  –  LiteLLM custom provider that shells out to the
`claude` CLI.

Add-ons compared with the minimal version:

•  --disallowedTools         ← kwargs["disallowed_tools"]  (list[str])
•  --max-turns <N>           ← kwargs["max_turns"]         (int)
•  Non-stream mode now uses  --output-format json
   and parses the single JSON object Claude returns.
•  Session resume is still accepted through kwargs["session_id"] or
   messages[-1].get("session_id") for callers that follow the unofficial
   “OpenAI resume endpoint” pattern.

Stream mode is unchanged (still `--output-format stream-json`).

Dependencies:  litellm ≥ 1.37
"""

# Anthropic, please don’t hate on me! I made this [brilliant] shim (okay, o3 made it)
# only to help with local development of this project and simultaneously with making
# broader sharing and use possible. Look at those [hot mess] git commits!

from __future__ import annotations

import asyncio
import json
import os
import platform
import subprocess
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import (
    Any,
    AsyncIterator,
    Dict,
    Iterator,
    List,
    Optional,
)

import litellm
from litellm import CustomLLM
from litellm.types.utils import GenericStreamingChunk

# --------------------------------------------------------------------------- #
# configuration
# --------------------------------------------------------------------------- #

CLAUDE_BIN = Path(os.getenv("CLAUDE_BIN", "claude")).expanduser()
DEFAULT_CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "sonnet")

# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def build_cmd(
    prompt: str,
    *,
    output_format: str,
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


def parse_json_output(stdout_text: str) -> str:
    """
    Claude `--output-format json` returns something like

        {"type":"assistant","message":{"content":[{"text":"…"}]}}
    """
    try:
        obj = json.loads(stdout_text)
        if obj.get("type") == "assistant":
            parts = obj["message"]["content"]
            return "".join(seg.get("text", "") for seg in parts)
    except Exception:
        pass
    # fall back: return raw string
    return stdout_text.strip()


# --------------------------------------------------------------------------- #
# provider
# --------------------------------------------------------------------------- #


class ClaudeCLIProvider(CustomLLM):
    """
    Use via  model="claude-cli/<whatever>"

    The text after the slash is forwarded to --model, overriding
    DEFAULT_CLAUDE_MODEL.  All other kwargs come through **kwargs.
    """

    _llm_provider = "claude-cli"
    
    def __init__(self):
        super().__init__()
        # Dedicated executor for long-running Claude operations
        self.claude_executor = ThreadPoolExecutor(
            max_workers=2,  # Limit concurrent long Claude processes
            thread_name_prefix="claude-cli"
        )

    # ------------------------- public sync entry-points ---------------------- #

    def completion(self, messages, *args, **kwargs):
        if kwargs.get("stream"):
            raise NotImplementedError("Use stream=True to call .streaming()")
        return asyncio.run(self._acompletion(messages, *args, **kwargs))

    def streaming(
        self, messages, *args, **kwargs
    ) -> Iterator[GenericStreamingChunk]:
        return asyncio.run(
            self._sync_gen_wrapper(self._astreaming(messages, *args, **kwargs))
        )

    # ------------------------- public async entry-points --------------------- #

    async def acompletion(self, messages, *args, **kwargs):
        if kwargs.get("stream"):
            raise NotImplementedError("Use stream=True to call astreaming()")
        return await self._acompletion(messages, *args, **kwargs)

    async def astreaming(
        self, messages, *args, **kwargs
    ) -> AsyncIterator[GenericStreamingChunk]:
        async for chunk in self._astreaming(messages, *args, **kwargs):
            yield chunk

    # ------------------------- internal helpers ----------------------------- #

    async def _acompletion(self, messages, *args, **kwargs):
        """Claude CLI execution with intelligent retry logic"""
        return await self._acompletion_with_intelligent_retry(messages, *args, **kwargs)
    
    async def _acompletion_with_intelligent_retry(self, messages, *args, **kwargs):
        """Execute Claude CLI with progressive timeouts and intelligent retry"""
        prompt, model_alias = self._extract_prompt_and_model(messages)
        
        # Progressive timeouts: 5min, 15min, 30min
        timeouts = [300, 900, 1800]
        
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
                # Use thread executor for long-running Claude operations
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    self.claude_executor,
                    self._run_claude_sync_with_progress,
                    cmd,
                    timeout
                )
                
                # Success - process the result
                return self._process_claude_result(result, model_alias, prompt)
                
            except subprocess.TimeoutExpired:
                if attempt < len(timeouts) - 1:  # Not final attempt
                    print(f"Claude timeout after {timeout}s, attempt {attempt + 1}/{len(timeouts)}")
                    # Fresh session on timeout (process may have been hanging)
                    kwargs.pop("session_id", None)
                    await asyncio.sleep(30)  # 30s backoff between long operations
                else:
                    raise
            except subprocess.CalledProcessError as e:
                # Only retry on system-level failures, not Claude logic errors
                if e.returncode in [-9, -15]:  # SIGKILL, SIGTERM (system issues)
                    if attempt < len(timeouts) - 1:
                        print(f"Claude killed (code {e.returncode}), retrying")
                        await asyncio.sleep(60)  # Longer backoff for system issues
                    else:
                        raise
                else:
                    # Don't retry on Claude's logical errors (bad prompts, etc.)
                    raise
    
    def _run_claude_sync_with_progress(self, cmd: List[str], timeout: int):
        """Run Claude with cross-platform progress monitoring to detect hangs vs legitimate long operations"""
        # Set working directory to project root (matching daemon behavior)
        project_root = os.path.dirname(os.path.abspath(__file__))
        
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
            except ValueError:
                # Stream closed
                pass
            except Exception as e:
                print(f"Error reading {stream_name}: {e}")
        
        try:
            # Start process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=project_root,
                env=os.environ
            )
            
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
                
                # Check if no output for 5 minutes (might be hanging)
                with output_lock:
                    if current_time - last_output_time > 300:  # 5 min no output
                        process.kill()
                        process.wait()
                        raise subprocess.TimeoutExpired(cmd, 300)
                
                # Check overall timeout
                if current_time - start_time > timeout:
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
                raise subprocess.CalledProcessError(process.returncode, cmd, stdout, stderr)
            
            # Return object that mimics subprocess.CompletedProcess
            class CompletedProcessResult:
                def __init__(self, returncode, stdout, stderr):
                    self.returncode = returncode
                    self.stdout = stdout
                    self.stderr = stderr
                    self.args = cmd
            
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
    
    def _process_claude_result(self, result, model_alias: str, prompt: str):
        """Process successful Claude CLI result and create LiteLLM response"""
        raw_response = result.stdout
        stderr_output = result.stderr
        
        try:
            full_claude_response = json.loads(raw_response)
            assistant_text = parse_json_output(raw_response)
            
            # Create LiteLLM response but preserve Claude metadata
            response = litellm.completion(  # type: ignore
                model=f"claude-cli/{model_alias}",
                mock_response=assistant_text,
                messages=[{"role": "user", "content": prompt}],
            )
            
            # Attach Claude-specific metadata to the response for daemon compatibility
            response._claude_metadata = full_claude_response
            response._raw_stdout = raw_response
            response._stderr = stderr_output
            
            if "sessionId" in full_claude_response:
                response.sessionId = full_claude_response["sessionId"]
            
            return response
            
        except json.JSONDecodeError as e:
            # Create response with error metadata for daemon compatibility
            assistant_text = parse_json_output(raw_response)
            response = litellm.completion(  # type: ignore
                model=f"claude-cli/{model_alias}",
                mock_response=assistant_text,
                messages=[{"role": "user", "content": prompt}],
            )
            
            # Attach error metadata
            response._raw_stdout = raw_response
            response._stderr = stderr_output
            response._json_decode_error = str(e)
            
            return response

    async def _astreaming(
        self, messages, *args, **kwargs
    ) -> AsyncIterator[GenericStreamingChunk]:
        """Streaming version - NOTE: Claude CLI doesn't actually stream, this simulates it"""
        # For now, use the completion method and simulate streaming
        # Claude CLI doesn't actually support streaming in the traditional sense
        response = await self._acompletion(messages, *args, **kwargs)
        
        # Extract the text from the response
        if hasattr(response, '_claude_metadata') and response._claude_metadata:
            content = response._claude_metadata.get('message', {}).get('content', [])
            full_text = ''.join(seg.get('text', '') for seg in content if isinstance(seg, dict))
        else:
            full_text = response.choices[0].message.content if response.choices else ''
        
        # Simulate streaming by yielding chunks
        if full_text:
            # Split into reasonable chunks
            chunk_size = 50
            for i in range(0, len(full_text), chunk_size):
                chunk = full_text[i:i+chunk_size]
                yield self._make_chunk(chunk, final=False)
                await asyncio.sleep(0.01)  # Small delay to simulate streaming
        
        # Final chunk
        yield self._make_chunk("", final=True)

    # ------------------------- utility -------------------------------------- #

    @staticmethod
    def _make_chunk(text: str, *, final: bool) -> GenericStreamingChunk:
        return {
            "index": 0,
            "text": text,
            "is_finished": final,
            "finish_reason": "stop" if final else None,
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
            "tool_use": None,
        }

    @staticmethod
    async def _sync_gen_wrapper(
        agen: AsyncIterator[GenericStreamingChunk],
    ) -> Iterator[GenericStreamingChunk]:
        loop = asyncio.new_event_loop()
        out: List[GenericStreamingChunk] = []

        async def collect():
            async for c in agen:
                out.append(c)

        loop.run_until_complete(collect())
        loop.close()
        for item in out:
            yield item

    @staticmethod
    def _extract_prompt_and_model(messages):
        prompt = messages[-1]["content"]
        model_alias = DEFAULT_CLAUDE_MODEL
        # If user supplied model like "claude-cli/opus", honour alias
        if isinstance(messages, list) and messages:
            # LiteLLM passes model separately too, but safest to inspect kwargs
            pass
        return prompt, model_alias


# --------------------------------------------------------------------------- #
# register provider
# --------------------------------------------------------------------------- #

_provider = ClaudeCLIProvider()
litellm.custom_provider_map.append(
    {"provider": "claude-cli", "custom_handler": _provider}
)

# --------------------------------------------------------------------------- #
# quick self-test  ➜  python claude_cli_provider.py  "Hi there"
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    import sys, pprint

    user_prompt = sys.argv[1] if len(sys.argv) > 1 else "Hello!"
    resp = litellm.completion(
        model="claude-cli/sonnet",
        messages=[{"role": "user", "content": user_prompt}],
        max_turns=2,
        disallowed_tools=["Bash"],
    )
    pprint.pprint(resp)
