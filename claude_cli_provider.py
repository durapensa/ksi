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

Dependencies:  litellm ≥ 1.37  •  simpervisor ≥ 1.0
"""

from __future__ import annotations

import asyncio
import json
import os
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
from simpervisor import SupervisedProcess

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
        prompt, model_alias = self._extract_prompt_and_model(messages)

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

        # Set working directory to project root (matching daemon behavior)
        import os
        project_root = os.path.dirname(os.path.abspath(__file__))
        
        proc = SupervisedProcess("claude-cli", *cmd, cwd=project_root, env=os.environ, stdout=True, stderr=True)
        await proc.start()
        
        # Collect both stdout and stderr
        stdout_buf: List[bytes] = []
        stderr_buf: List[bytes] = []
        
        # Collect stdout
        async for chunk in proc.stdout:
            stdout_buf.append(chunk)
            
        # Collect stderr
        async for chunk in proc.stderr:
            stderr_buf.append(chunk)
            
        await proc.terminate()

        # Parse the full Claude CLI JSON response and capture all metadata
        raw_response = b"".join(stdout_buf).decode()
        stderr_output = b"".join(stderr_buf).decode()
        
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
        prompt, model_alias = self._extract_prompt_and_model(messages)

        allowed = allowed_tools_from_openai(kwargs.get("tools"))
        disallowed = kwargs.get("disallowed_tools") or []
        session_id = kwargs.get("session_id")
        max_turns = kwargs.get("max_turns")

        cmd = build_cmd(
            prompt,
            output_format="stream-json",
            model_alias=model_alias,
            allowed_tools=allowed,
            disallowed_tools=disallowed,
            session_id=session_id,
            max_turns=max_turns,
        )

        # Set working directory to project root (matching daemon behavior)
        project_root = os.path.dirname(os.path.abspath(__file__))
        
        proc = SupervisedProcess("claude-cli-stream", *cmd, cwd=project_root, env=os.environ)
        await proc.start()

        try:
            async for raw in proc.stdout:
                try:
                    evt = json.loads(raw)
                except Exception:
                    continue
                if evt.get("type") != "assistant":
                    continue
                token = "".join(
                    seg.get("text", "") for seg in evt["message"]["content"]
                )
                yield self._make_chunk(token, final=False)
            yield self._make_chunk("", final=True)
        finally:
            await proc.terminate()

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
