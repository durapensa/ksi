#!/usr/bin/env python3
"""
MCP Configuration Manager for Agents

Handles generation and lifecycle of agent-specific MCP configurations.
Configs are created when agents spawn and cleaned up on termination.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from ksi_common.config import config
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("mcp_config_manager")


class MCPConfigManager:
    """Manages MCP configurations for agents."""
    
    def __init__(self):
        self.tmp_dir = config.daemon_tmp_dir
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        
    def create_agent_config(
        self, 
        agent_id: str,
        conversation_id: str,
        permissions: Optional[Dict[str, Any]] = None
    ) -> Path:
        """
        Create MCP configuration for an agent.
        
        Args:
            agent_id: Unique agent identifier
            conversation_id: Conversation/session identifier
            permissions: Agent permissions (optional, for logging)
            
        Returns:
            Path to the generated MCP config file
        """
        config_path = self.tmp_dir / f"{agent_id}_mcp_config.json"
        
        # Generate streamable-http MCP configuration
        mcp_config = {
            "mcpServers": {
                "ksi": {
                    "type": "streamable-http",
                    "url": f"http://127.0.0.1:{config.mcp_server_port}",
                    "headers": {
                        "X-KSI-Agent-ID": agent_id,
                        "X-KSI-Conversation-ID": conversation_id,
                        "X-KSI-Timestamp": datetime.utcnow().isoformat()
                    },
                    "verifySsl": False,
                    "retry": {
                        "maxAttempts": 3,
                        "backoffMs": 1000,
                        "maxBackoffMs": 30000
                    },
                    # Session cache enables thin handshakes
                    "sessionCache": str(self.tmp_dir / f"{agent_id}_mcp_session.json")
                }
            }
        }
        
        # Write config
        try:
            with open(config_path, 'w') as f:
                json.dump(mcp_config, f, indent=2)
            
            logger.info(
                "Created MCP config for agent",
                agent_id=agent_id,
                conversation_id=conversation_id,
                config_path=str(config_path),
                permission_profile=permissions.get("profile") if permissions else None
            )
            
            return config_path
            
        except Exception as e:
            logger.error(
                "Failed to create MCP config",
                agent_id=agent_id,
                error=str(e)
            )
            raise
    
    def update_conversation_id(
        self,
        agent_id: str,
        new_conversation_id: str
    ) -> bool:
        """
        Update conversation ID in existing MCP config.
        
        Used when an agent's conversation context changes.
        
        Args:
            agent_id: Agent identifier
            new_conversation_id: New conversation ID
            
        Returns:
            True if updated successfully, False otherwise
        """
        config_path = self.tmp_dir / f"{agent_id}_mcp_config.json"
        
        if not config_path.exists():
            logger.warning(
                "MCP config not found for update",
                agent_id=agent_id
            )
            return False
        
        try:
            # Read existing config
            with open(config_path) as f:
                mcp_config = json.load(f)
            
            # Update conversation ID and timestamp
            if "mcpServers" in mcp_config and "ksi" in mcp_config["mcpServers"]:
                mcp_config["mcpServers"]["ksi"]["headers"]["X-KSI-Conversation-ID"] = new_conversation_id
                mcp_config["mcpServers"]["ksi"]["headers"]["X-KSI-Timestamp"] = datetime.utcnow().isoformat()
                
                # Write updated config
                with open(config_path, 'w') as f:
                    json.dump(mcp_config, f, indent=2)
                
                logger.debug(
                    "Updated MCP config conversation ID",
                    agent_id=agent_id,
                    new_conversation_id=new_conversation_id
                )
                return True
            else:
                logger.error(
                    "Invalid MCP config structure",
                    agent_id=agent_id
                )
                return False
                
        except Exception as e:
            logger.error(
                "Failed to update MCP config",
                agent_id=agent_id,
                error=str(e)
            )
            return False
    
    def cleanup_agent_config(self, agent_id: str) -> bool:
        """
        Remove MCP configuration for a terminated agent.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            True if cleaned up successfully, False otherwise
        """
        cleaned = False
        
        # Remove MCP config
        config_path = self.tmp_dir / f"{agent_id}_mcp_config.json"
        if config_path.exists():
            try:
                config_path.unlink()
                cleaned = True
                logger.debug(
                    "Removed MCP config",
                    agent_id=agent_id,
                    path=str(config_path)
                )
            except Exception as e:
                logger.error(
                    "Failed to remove MCP config",
                    agent_id=agent_id,
                    error=str(e)
                )
        
        # Remove session cache
        session_cache = self.tmp_dir / f"{agent_id}_mcp_session.json"
        if session_cache.exists():
            try:
                session_cache.unlink()
                logger.debug(
                    "Removed MCP session cache",
                    agent_id=agent_id,
                    path=str(session_cache)
                )
            except Exception as e:
                logger.error(
                    "Failed to remove MCP session cache",
                    agent_id=agent_id,
                    error=str(e)
                )
        
        return cleaned
    
    def cleanup_all(self) -> int:
        """
        Clean up all MCP configs and session caches.
        
        Used during daemon shutdown or maintenance.
        
        Returns:
            Number of files cleaned up
        """
        cleaned = 0
        
        # Clean up all MCP configs and session caches
        patterns = ["*_mcp_config.json", "*_mcp_session.json"]
        
        for pattern in patterns:
            for file_path in self.tmp_dir.glob(pattern):
                try:
                    file_path.unlink()
                    cleaned += 1
                except Exception as e:
                    logger.error(
                        "Failed to remove file during cleanup",
                        path=str(file_path),
                        error=str(e)
                    )
        
        if cleaned > 0:
            logger.info(
                "Cleaned up MCP files",
                count=cleaned
            )
        
        return cleaned
    
    def get_config_path(self, agent_id: str) -> Optional[Path]:
        """
        Get path to agent's MCP config if it exists.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Path to config file or None if not found
        """
        config_path = self.tmp_dir / f"{agent_id}_mcp_config.json"
        return config_path if config_path.exists() else None
    
    def list_active_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        List all active MCP configurations.
        
        Returns:
            Dict mapping agent_id to config info
        """
        configs = {}
        
        for config_path in self.tmp_dir.glob("*_mcp_config.json"):
            # Extract agent_id from filename
            agent_id = config_path.stem.replace("_mcp_config", "")
            
            try:
                # Get file stats
                stat = config_path.stat()
                
                # Check for session cache
                session_cache = self.tmp_dir / f"{agent_id}_mcp_session.json"
                has_session = session_cache.exists()
                
                configs[agent_id] = {
                    "path": str(config_path),
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "size": stat.st_size,
                    "has_session_cache": has_session
                }
                
            except Exception as e:
                logger.warning(
                    "Failed to stat MCP config",
                    path=str(config_path),
                    error=str(e)
                )
        
        return configs


# Global instance
mcp_config_manager = MCPConfigManager()