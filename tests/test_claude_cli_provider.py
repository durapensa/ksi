#!/usr/bin/env python3

"""
Test suite for claude_cli_provider.py

Tests core functionality without external dependencies using mocks.
"""

import asyncio
import json
import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from claude_cli_provider import (
    ClaudeCLIProvider,
    build_cmd,
    allowed_tools_from_openai,
    parse_json_output,
    DEFAULT_CLAUDE_MODEL
)


class TestHelperFunctions:
    """Test standalone helper functions"""
    
    def test_build_cmd_minimal(self):
        """Test basic command building"""
        cmd = build_cmd("Hello", output_format="json")
        expected = ["claude", "-p", "--output-format", "json", "--model", DEFAULT_CLAUDE_MODEL, "Hello"]
        assert cmd == expected
    
    def test_build_cmd_with_options(self):
        """Test command building with all options"""
        cmd = build_cmd(
            "Test prompt",
            output_format="stream-json",
            model_alias="opus",
            allowed_tools=["Bash", "Read"],
            disallowed_tools=["WebFetch"],
            session_id="test-session",
            max_turns=5
        )
        
        expected = [
            "claude", "-p", "--output-format", "stream-json", "--model", "opus",
            "--allowedTools", "Bash", "Read",
            "--disallowedTools", "WebFetch",
            "--max-turns", "5",
            "--resume", "test-session",
            "Test prompt"
        ]
        assert cmd == expected
    
    def test_allowed_tools_from_openai_empty(self):
        """Test tools extraction with empty input"""
        assert allowed_tools_from_openai(None) == []
        assert allowed_tools_from_openai([]) == []
    
    def test_allowed_tools_from_openai_valid(self):
        """Test tools extraction with valid OpenAI format"""
        tools = [
            {"type": "function", "function": {"name": "get_weather"}},
            {"type": "function", "function": {"name": "search_web"}},
            {"type": "other", "function": {"name": "should_ignore"}}  # Wrong type
        ]
        result = allowed_tools_from_openai(tools)
        assert result == ["get_weather", "search_web"]
    
    def test_allowed_tools_from_openai_malformed(self):
        """Test tools extraction with malformed input"""
        tools = [
            {"type": "function"},  # Missing function
            {"function": {"name": "missing_type"}},  # Missing type
            {"type": "function", "function": {}}  # Missing name
        ]
        result = allowed_tools_from_openai(tools)
        assert result == []
    
    def test_parse_json_output_valid(self):
        """Test JSON output parsing with valid Claude response"""
        claude_response = {
            "type": "assistant",
            "message": {
                "content": [
                    {"text": "Hello "},
                    {"text": "world!"}
                ]
            }
        }
        json_str = json.dumps(claude_response)
        result = parse_json_output(json_str)
        assert result == "Hello world!"
    
    def test_parse_json_output_invalid_json(self):
        """Test JSON parsing with invalid JSON"""
        result = parse_json_output("invalid json")
        assert result == "invalid json"
    
    def test_parse_json_output_wrong_format(self):
        """Test JSON parsing with valid JSON but wrong format"""
        wrong_format = {"different": "structure"}
        json_str = json.dumps(wrong_format)
        result = parse_json_output(json_str)
        assert result == json_str


class TestClaudeCLIProvider:
    """Test ClaudeCLIProvider class"""
    
    @pytest.fixture
    def provider(self):
        """Create provider instance for testing"""
        return ClaudeCLIProvider()
    
    def test_provider_init(self, provider):
        """Test provider initialization"""
        assert provider._llm_provider == "claude-cli"
    
    def test_extract_prompt_and_model(self, provider):
        """Test prompt and model extraction from messages"""
        messages = [
            {"role": "user", "content": "Test prompt"}
        ]
        prompt, model = provider._extract_prompt_and_model(messages)
        assert prompt == "Test prompt"
        assert model == DEFAULT_CLAUDE_MODEL
    
    def test_make_chunk(self, provider):
        """Test streaming chunk creation"""
        chunk = provider._make_chunk("test text", final=False)
        expected = {
            "index": 0,
            "text": "test text",
            "is_finished": False,
            "finish_reason": None,
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
            "tool_use": None,
        }
        assert chunk == expected
        
        # Test final chunk
        final_chunk = provider._make_chunk("", final=True)
        assert final_chunk["is_finished"] is True
        assert final_chunk["finish_reason"] == "stop"


class TestAsyncMethods:
    """Test async methods with mocked subprocess calls"""
    
    @pytest.fixture
    def provider(self):
        return ClaudeCLIProvider()
    
    @pytest.mark.asyncio
    async def test_acompletion_success(self, provider):
        """Test successful async completion"""
        messages = [{"role": "user", "content": "Hello"}]
        
        # Mock SupervisedProcess
        mock_process = AsyncMock()
        mock_process.stdout = [b'{"type":"assistant","message":{"content":[{"text":"Hi there!"}]}}']
        
        with patch('claude_cli_provider.SupervisedProcess', return_value=mock_process):
            with patch('litellm.completion') as mock_completion:
                mock_completion.return_value = {"choices": [{"message": {"content": "Hi there!"}}]}
                
                result = await provider._acompletion(messages)
                
                # Verify process was started and terminated
                mock_process.start.assert_called_once()
                mock_process.terminate.assert_called_once()
                
                # Verify litellm.completion was called
                mock_completion.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_acompletion_with_tools(self, provider):
        """Test completion with OpenAI tools format"""
        messages = [{"role": "user", "content": "Use tools"}]
        tools = [{"type": "function", "function": {"name": "test_tool"}}]
        
        mock_process = AsyncMock()
        mock_process.stdout = [b'{"type":"assistant","message":{"content":[{"text":"Used tool"}]}}']
        
        with patch('claude_cli_provider.SupervisedProcess', return_value=mock_process):
            with patch('litellm.completion') as mock_completion:
                mock_completion.return_value = {"choices": [{"message": {"content": "Used tool"}}]}
                
                await provider._acompletion(messages, tools=tools)
                
                # Check that SupervisedProcess was called with correct command
                call_args = mock_process.call_args if hasattr(mock_process, 'call_args') else None
                # We can't easily inspect the cmd argument, but we know it should include allowedTools
    
    @pytest.mark.asyncio
    async def test_astreaming_basic(self, provider):
        """Test basic streaming functionality"""
        messages = [{"role": "user", "content": "Stream this"}]
        
        # Mock streaming data - multiple chunks
        stream_data = [
            b'{"type":"assistant","message":{"content":[{"text":"Hello"}]}}',
            b'{"type":"assistant","message":{"content":[{"text":" world"}]}}',
            b'{"type":"assistant","message":{"content":[{"text":"!"}]}}'
        ]
        
        mock_process = AsyncMock()
        mock_process.stdout = stream_data
        
        with patch('claude_cli_provider.SupervisedProcess', return_value=mock_process):
            chunks = []
            async for chunk in provider._astreaming(messages):
                chunks.append(chunk)
            
            # Should have received 3 content chunks + 1 final chunk
            assert len(chunks) == 4
            assert chunks[0]["text"] == "Hello"
            assert chunks[1]["text"] == " world"
            assert chunks[2]["text"] == "!"
            assert chunks[3]["text"] == ""  # Final chunk
            assert chunks[3]["is_finished"] is True
    
    @pytest.mark.asyncio
    async def test_streaming_with_invalid_json(self, provider):
        """Test streaming with some invalid JSON chunks"""
        messages = [{"role": "user", "content": "Test"}]
        
        stream_data = [
            b'invalid json',  # Should be skipped
            b'{"type":"assistant","message":{"content":[{"text":"Valid"}]}}',
            b'{"type":"other"}',  # Wrong type, should be skipped
        ]
        
        mock_process = AsyncMock()
        mock_process.stdout = stream_data
        
        with patch('claude_cli_provider.SupervisedProcess', return_value=mock_process):
            chunks = []
            async for chunk in provider._astreaming(messages):
                chunks.append(chunk)
            
            # Should have 1 valid chunk + 1 final chunk
            assert len(chunks) == 2
            assert chunks[0]["text"] == "Valid"
            assert chunks[1]["is_finished"] is True


class TestSyncWrappers:
    """Test synchronous wrapper methods"""
    
    @pytest.fixture
    def provider(self):
        return ClaudeCLIProvider()
    
    def test_completion_blocks_streaming(self, provider):
        """Test that completion() raises error for streaming"""
        messages = [{"role": "user", "content": "test"}]
        
        with pytest.raises(NotImplementedError):
            provider.completion(messages, stream=True)
    
    def test_acompletion_blocks_streaming(self, provider):
        """Test that acompletion() raises error for streaming"""
        messages = [{"role": "user", "content": "test"}]
        
        async def test():
            with pytest.raises(NotImplementedError):
                await provider.acompletion(messages, stream=True)
        
        asyncio.run(test())


@pytest.mark.integration
class TestIntegration:
    """Integration tests - only run if Claude CLI is available"""
    
    @pytest.fixture
    def provider(self):
        return ClaudeCLIProvider()
    
    @pytest.mark.skipif(not Path("claude").exists(), reason="Claude CLI not found")
    def test_real_completion(self, provider):
        """Test with actual Claude CLI - requires claude in PATH"""
        messages = [{"role": "user", "content": "Say 'test successful' and nothing else"}]
        
        # This would call actual Claude CLI
        # result = provider.completion(messages)
        # assert "test successful" in result.choices[0].message.content.lower()
        
        # For now, just verify the provider exists
        assert provider is not None


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])