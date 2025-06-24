#!/usr/bin/env python3
"""
Claude CLI Completion Plugin

Provides completion functionality using the Claude CLI.
Handles completion:request events and manages Claude processes.
"""

import asyncio
import json
import logging
import subprocess
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List

from ...plugin_base import ServicePlugin, hookimpl
from ...plugin_types import EventContext
from ...event_schemas import CompletionRequest, CompletionResponse

logger = logging.getLogger(__name__)


class ClaudeCompletionService(ServicePlugin):
    """Service plugin that provides Claude CLI completions."""
    
    def __init__(self):
        super().__init__(
            name="claude_cli_completion",
            service_name="completion",
            version="1.0.0",
            description="Claude CLI completion provider"
        )
        
        # Running processes
        self.running_processes: Dict[str, subprocess.Popen] = {}
        
        # Session tracking
        self.sessions: Dict[str, Dict[str, Any]] = {}
        
        # Configuration
        self.claude_command = ["claude"]
        self.default_model = "sonnet"
        self.log_dir = Path.home() / ".ksi" / "claude_logs"
    
    async def on_start(self) -> None:
        """Initialize the completion service."""
        # Create log directory
        self.log_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Claude logs directory: {self.log_dir}")
    
    async def on_stop(self) -> None:
        """Clean up running processes."""
        # Terminate all running processes
        for process_id, process in list(self.running_processes.items()):
            try:
                process.terminate()
                await asyncio.sleep(0.1)
                if process.poll() is None:
                    process.kill()
            except Exception as e:
                logger.error(f"Error terminating process {process_id}: {e}")
        
        self.running_processes.clear()
    
    @hookimpl
    def ksi_handle_event(self, event_name: str, data: Dict[str, Any], 
                        context: EventContext) -> Optional[Dict[str, Any]]:
        """Handle completion events."""
        if event_name == "completion:request":
            return self._handle_completion_request(data, context)
        elif event_name == "completion:cancel":
            return self._handle_completion_cancel(data)
        return None
    
    def _handle_completion_request(self, data: Dict[str, Any], 
                                  context: EventContext) -> Dict[str, Any]:
        """Handle a completion request."""
        try:
            # Validate request
            request = CompletionRequest(**data)
        except Exception as e:
            return {
                "error": f"Invalid request: {e}",
                "success": False
            }
        
        # Generate request ID
        request_id = request.request_id or f"comp_{uuid.uuid4().hex[:8]}"
        
        # Start async completion
        asyncio.create_task(
            self._process_completion(request_id, request, context)
        )
        
        # Return acknowledgment
        return {
            "request_id": request_id,
            "status": "processing"
        }
    
    async def _process_completion(self, request_id: str, 
                                 request: CompletionRequest,
                                 context: EventContext) -> None:
        """Process completion request asynchronously."""
        start_time = time.time()
        
        try:
            # Emit progress event
            await context.emit("completion:progress", {
                "request_id": request_id,
                "status": "starting",
                "message": "Preparing Claude CLI"
            })
            
            # Build command
            cmd = self._build_command(request)
            
            # Run Claude CLI
            result = await self._run_claude_cli(cmd, request.prompt, request_id)
            
            # Parse result
            if result["success"]:
                # Emit success response
                response = CompletionResponse(
                    request_id=request_id,
                    success=True,
                    result=result["result"],
                    model=result.get("model", request.model),
                    usage=result.get("usage"),
                    session_id=result.get("sessionId"),
                    duration_ms=int((time.time() - start_time) * 1000)
                )
                
                await context.emit("completion:response", response.model_dump())
                
                # Update session tracking
                if response.session_id:
                    self.sessions[response.session_id] = {
                        "last_used": time.time(),
                        "agent_id": request.agent_id,
                        "model": response.model
                    }
            else:
                # Emit error response
                await context.emit("completion:response", {
                    "request_id": request_id,
                    "success": False,
                    "error": result.get("error", "Unknown error")
                })
        
        except Exception as e:
            logger.error(f"Completion error: {e}", exc_info=True)
            await context.emit("completion:response", {
                "request_id": request_id,
                "success": False,
                "error": str(e)
            })
    
    def _build_command(self, request: CompletionRequest) -> List[str]:
        """Build Claude CLI command."""
        cmd = self.claude_command.copy()
        
        # Model
        model = request.model or self.default_model
        cmd.extend(["--model", model])
        
        # Output format
        cmd.extend(["--print", "--output-format", "json"])
        
        # Session resumption
        if request.session_id:
            cmd.extend(["--resume", request.session_id])
        
        # Tools
        if hasattr(request, 'enable_tools') and request.enable_tools:
            allowed_tools = "Bash,Glob,Grep,LS,Read,Edit,Write,WebSearch"
            cmd.extend(["--allowedTools", allowed_tools])
        
        return cmd
    
    async def _run_claude_cli(self, cmd: List[str], prompt: str, 
                             process_id: str) -> Dict[str, Any]:
        """Run Claude CLI and capture output."""
        try:
            # Start process
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Track process
            self.running_processes[process_id] = process
            
            # Send prompt
            stdout, stderr = await process.communicate(prompt.encode())
            
            # Remove from tracking
            self.running_processes.pop(process_id, None)
            
            # Check result
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Claude CLI failed"
                logger.error(f"Claude CLI error: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg
                }
            
            # Parse JSON output
            try:
                output = stdout.decode()
                # Find JSON in output (may have other text)
                json_start = output.find('{')
                if json_start >= 0:
                    json_str = output[json_start:]
                    result = json.loads(json_str)
                    
                    # Log to file
                    log_file = self.log_dir / f"{process_id}.json"
                    with open(log_file, 'w') as f:
                        json.dump({
                            "request": {"prompt": prompt, "command": cmd},
                            "response": result,
                            "timestamp": time.time()
                        }, f, indent=2)
                    
                    return {
                        "success": True,
                        **result
                    }
                else:
                    return {
                        "success": False,
                        "error": "No JSON output from Claude CLI"
                    }
            
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Claude output: {e}")
                return {
                    "success": False,
                    "error": f"Invalid JSON response: {e}"
                }
        
        except Exception as e:
            logger.error(f"Error running Claude CLI: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _handle_completion_cancel(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Cancel a running completion."""
        request_id = data.get("request_id")
        if not request_id:
            return {"success": False, "error": "No request_id provided"}
        
        process = self.running_processes.get(request_id)
        if process:
            try:
                process.terminate()
                self.running_processes.pop(request_id, None)
                return {"success": True, "message": "Completion cancelled"}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        return {"success": False, "error": "No running process found"}
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get service-specific status."""
        return {
            "running_processes": len(self.running_processes),
            "active_sessions": len(self.sessions),
            "log_directory": str(self.log_dir)
        }
    
    @hookimpl
    def ksi_register_namespace(self, namespace: str, description: str) -> None:
        """Register our namespace."""
        if namespace == "completion":
            return  # Our namespace
    
    @hookimpl
    def ksi_register_validators(self) -> Dict[str, Any]:
        """Register event validators."""
        from ...event_schemas import CompletionRequest, CompletionResponse
        return {
            "completion:request": CompletionRequest,
            "completion:response": CompletionResponse
        }


# Plugin instance
plugin = ClaudeCompletionService()