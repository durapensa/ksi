#!/usr/bin/env python3
"""
Conversation Service Module - Event-Based Version

Provides conversation listing, search, filtering, and export functionality.
Assumes all messages have proper timestamps - drops malformed entries.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, TypedDict
from typing_extensions import NotRequired
import hashlib

from ksi_common.config import config
from ksi_common import parse_iso_timestamp, filename_timestamp, display_timestamp, utc_to_local
from ksi_common.event_response_builder import event_response_builder, error_response
from ksi_daemon.event_system import event_handler
from ksi_common.logging import get_bound_logger
from ksi_common.service_lifecycle import service_startup, service_shutdown

# Module state
logger = get_bound_logger("conversation_service", version="1.0.0")

# Module state
conversation_cache: Dict[str, Dict[str, Any]] = {}
cache_timestamp: Optional[datetime] = None
cache_ttl_seconds = 60  # Refresh cache every minute
responses_dir_path = None
exports_dir = None

# Per-module TypedDict definitions (optional type safety)
class ConversationListData(TypedDict):
    """Type-safe data for conversation:list."""
    limit: NotRequired[int]
    offset: NotRequired[int]
    sort_by: NotRequired[str]
    reverse: NotRequired[bool]
    start_date: NotRequired[str]
    end_date: NotRequired[str]

class ConversationSearchData(TypedDict):
    """Type-safe data for conversation:search."""
    query: str
    limit: NotRequired[int]
    search_in: NotRequired[List[str]]

class ConversationGetData(TypedDict):
    """Type-safe data for conversation:get."""
    session_id: str
    limit: NotRequired[int]
    offset: NotRequired[int]
    conversation_id: NotRequired[str]

class ConversationExportData(TypedDict):
    """Type-safe data for conversation:export."""
    session_id: str
    format: NotRequired[str]

class ConversationStatsData(TypedDict):
    """Type-safe data for conversation:stats."""
    pass  # No parameters

class ConversationActiveData(TypedDict):
    """Type-safe data for conversation:active."""
    max_lines: NotRequired[int]
    max_age_hours: NotRequired[int]
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


def ensure_directories():
    """Ensure required directories exist."""
    global responses_dir_path, exports_dir
    responses_dir_path = config.responses_dir
    exports_dir = config.state_dir / 'exports'
    exports_dir.mkdir(exist_ok=True)


@service_startup("conversation_service", load_transformers=False)
async def handle_startup(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Initialize conversation service on startup."""
    ensure_directories()
    return {"status": "conversation_service_ready"}


@service_shutdown("conversation_service")
async def handle_shutdown(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:
    """Clean up on shutdown."""
    logger.info(f"Conversation service stopped - {len(conversation_cache)} conversations cached")


def is_cache_stale() -> bool:
    """Check if conversation cache needs refresh."""
    if cache_timestamp is None:
        return True
    
    age = (datetime.now(timezone.utc) - cache_timestamp).total_seconds()
    return age > cache_ttl_seconds


def refresh_conversation_cache() -> None:
    """Refresh the conversation metadata cache."""
    global cache_timestamp
    conversation_cache.clear()
    
    # Scan all conversation files
    for log_file in responses_dir_path.glob("*.jsonl"):
        session_id = log_file.stem
        
        # Skip message_bus.jsonl - it's special
        if session_id == "message_bus":
            continue
        
        try:
            # Get file stats
            stat = log_file.stat()
                
            # Quick scan for metadata
            metadata = {
                'session_id': session_id,
                'file_path': str(log_file),
                'size_bytes': stat.st_size,
                'modified_timestamp': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                'message_count': 0,
                'first_timestamp': None,
                'last_timestamp': None,
                'participants': set(),
                'has_claude': False,
                'has_user': False
            }
                
            # Read file to get message count and timestamps
            with open(log_file, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        
                        # Only process entries with valid timestamps
                        timestamp = entry.get('timestamp')
                        if not timestamp:
                            continue
                        
                        # Validate timestamp format
                        try:
                            parse_iso_timestamp(timestamp)
                        except (ValueError, AttributeError):
                            continue  # Skip malformed timestamps
                        
                        metadata['message_count'] += 1
                        
                        # Track first/last timestamps
                        if metadata['first_timestamp'] is None:
                            metadata['first_timestamp'] = timestamp
                        metadata['last_timestamp'] = timestamp
                        
                        # Track participants
                        entry_type = entry.get('type', '')
                        if entry_type in ['user', 'human']:
                            metadata['has_user'] = True
                            metadata['participants'].add('You')
                        elif entry_type == 'claude':
                            metadata['has_claude'] = True
                            metadata['participants'].add('Claude')
                        elif entry_type == 'DIRECT_MESSAGE':
                            sender = entry.get('from')
                            if sender:
                                metadata['participants'].add(sender)
                                
                    except (json.JSONDecodeError, ValueError):
                        # Skip malformed entries
                        continue
                
            # Convert participants set to list
            metadata['participants'] = list(metadata['participants'])
            
            # Store in cache
            conversation_cache[session_id] = metadata
                
        except Exception as e:
            logger.warning(f"Error scanning conversation {session_id}: {e}")
            continue
    
    # Update cache timestamp
    cache_timestamp = datetime.now(timezone.utc)
    logger.info(f"Refreshed conversation cache: {len(conversation_cache)} conversations")


@event_handler("conversation:list")
async def handle_list_conversations(data: ConversationListData) -> Dict[str, Any]:
    """List available conversations with metadata."""
    try:
        # Refresh cache if needed
        if is_cache_stale():
            refresh_conversation_cache()
        
        # Get filter parameters
        limit = data.get('limit', 100)
        offset = data.get('offset', 0)
        sort_by = data.get('sort_by', 'last_timestamp')  # or 'first_timestamp', 'message_count'
        reverse = data.get('reverse', True)  # Most recent first by default
        
        # Filter by date range if provided
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        # Get all conversations
        conversations = list(conversation_cache.values())
        
        # Apply date filtering
        if start_date or end_date:
            filtered = []
            for conv in conversations:
                last_ts = conv.get('last_timestamp')
                if not last_ts:
                    continue
                
                try:
                    conv_date = parse_iso_timestamp(last_ts)
                    
                    if start_date:
                        start_dt = parse_iso_timestamp(start_date)
                        if conv_date < start_dt:
                            continue
                    
                    if end_date:
                        end_dt = parse_iso_timestamp(end_date)
                        if conv_date > end_dt:
                            continue
                    
                    filtered.append(conv)
                except (ValueError, AttributeError):
                    continue
            
            conversations = filtered
        
        # Sort conversations
        if sort_by == 'message_count':
            conversations.sort(key=lambda c: c.get('message_count', 0), reverse=reverse)
        elif sort_by == 'first_timestamp':
            conversations.sort(key=lambda c: c.get('first_timestamp') or '', reverse=reverse)
        else:  # Default to last_timestamp
            conversations.sort(key=lambda c: c.get('last_timestamp') or '', reverse=reverse)
        
        # Apply pagination
        total = len(conversations)
        conversations = conversations[offset:offset + limit]
        
        return {
            'conversations': conversations,
            'total': total,
            'offset': offset,
            'limit': limit
        }
        
    except Exception as e:
        logger.error(f"Error listing conversations: {e}", exc_info=True)
        return {"error": f"Failed to list conversations: {str(e)}"}


@event_handler(
    "conversation:search",
)
async def handle_search_conversations(data: ConversationSearchData) -> Dict[str, Any]:
    """Search conversations by content."""
    try:
        query = data.get('query', '').lower()
        if not query:
            return {"error": "Search query required"}
        
        limit = data.get('limit', 50)
        search_in = data.get('search_in', ['content'])  # or ['sender', 'content']
        
        results = []
        
        # Search each conversation
        for session_id, metadata in conversation_cache.items():
            if session_id == "message_bus":
                continue
                
            log_file = Path(metadata['file_path'])
            if not log_file.exists():
                continue
            
            matches = []
            
            try:
                with open(log_file, 'r') as f:
                    for line_num, line in enumerate(f):
                        try:
                            entry = json.loads(line.strip())
                            
                            # Only process entries with valid timestamps
                            timestamp = entry.get('timestamp')
                            if not timestamp:
                                continue
                            
                            # Search in specified fields
                            found = False
                            
                            if 'content' in search_in:
                                content = entry.get('content', '')
                                if isinstance(content, str) and query in content.lower():
                                    found = True
                                
                                # Also check 'result' field for Claude responses
                                result = entry.get('result', '')
                                if isinstance(result, str) and query in result.lower():
                                    found = True
                            
                            if 'sender' in search_in:
                                entry_type = entry.get('type', '')
                                sender = 'You' if entry_type in ['user', 'human'] else 'Claude'
                                if query in sender.lower():
                                    found = True
                            
                            if found:
                                # Extract context
                                display_content = content or result
                                if len(display_content) > 200:
                                    # Find query position and show context
                                    pos = display_content.lower().find(query)
                                    if pos > 50:
                                        display_content = "..." + display_content[pos-50:pos+150] + "..."
                                    else:
                                        display_content = display_content[:200] + "..."
                                
                                matches.append({
                                    'line_num': line_num,
                                    'timestamp': timestamp,
                                    'type': entry_type,
                                    'content_preview': display_content,
                                    'sender': sender
                                })
                                
                                if len(matches) >= 10:  # Limit matches per conversation
                                    break
                                    
                        except (json.JSONDecodeError, ValueError):
                            continue
            
            except Exception as e:
                logger.warning(f"Error searching conversation {session_id}: {e}")
                continue
            
            if matches:
                results.append({
                    'session_id': session_id,
                    'conversation_metadata': metadata,
                    'matches': matches,
                    'match_count': len(matches)
                })
            
            if len(results) >= limit:
                break
        
        # Sort by match count
        results.sort(key=lambda r: r['match_count'], reverse=True)
        
        return {
            'query': query,
            'results': results[:limit],
            'total_conversations': len(results)
        }
        
    except Exception as e:
        logger.error(f"Error searching conversations: {e}", exc_info=True)
        return {"error": f"Search failed: {str(e)}"}


@event_handler("conversation:get")
async def handle_get_conversation(data: ConversationGetData) -> Dict[str, Any]:
    """Get a specific conversation with full message history."""
    try:
        session_id = data.get('session_id')
        if not session_id:
            return {"error": "session_id required"}
        
        limit = data.get('limit', 1000)
        offset = data.get('offset', 0)
        
        # Handle message_bus specially
        if session_id == "message_bus":
            conversation_id = data.get('conversation_id')
            return get_message_bus_conversation(conversation_id, limit, offset)
        
        # Regular conversation
        log_file = responses_dir_path / f"{session_id}.jsonl"
        if not log_file.exists():
            return {"error": f"Conversation not found: {session_id}"}
        
        messages = []
        seen_messages = set()  # For deduplication
        
        with open(log_file, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    
                    # Only process entries with valid timestamps
                    timestamp = entry.get('timestamp')
                    if not timestamp:
                        continue
                    
                    # Validate timestamp
                    try:
                        parse_iso_timestamp(timestamp)
                    except (ValueError, AttributeError):
                        continue
                    
                    # Handle different log formats
                    message = None
                    entry_type = entry.get('type', '')
                    
                    if entry_type in ['user', 'human']:
                        message = {
                            'timestamp': timestamp,
                            'sender': 'You',
                            'content': entry.get('content', ''),
                            'type': 'user'
                        }
                    elif entry_type == 'claude':
                        content = entry.get('result', entry.get('content', ''))
                        message = {
                            'timestamp': timestamp,
                            'sender': 'Claude',
                            'content': content,
                            'type': 'claude'
                        }
                    elif entry_type == 'DIRECT_MESSAGE':
                        message = {
                            'timestamp': timestamp,
                            'sender': entry.get('from', 'Unknown'),
                            'content': entry.get('content', ''),
                            'type': 'message',
                            'to': entry.get('to')
                        }
                    
                    if message:
                        # Deduplicate based on timestamp + sender + content hash
                        msg_id = f"{timestamp}:{message['sender']}:{hash(message['content'])}"
                        if msg_id not in seen_messages:
                            seen_messages.add(msg_id)
                            messages.append(message)
                            
                except (json.JSONDecodeError, ValueError):
                    continue
        
        # Sort by timestamp (no fallback)
        messages.sort(key=lambda m: m['timestamp'])
        
        # Apply pagination
        total = len(messages)
        messages = messages[offset:offset + limit]
        
        return {
            'session_id': session_id,
            'messages': messages,
            'total': total,
            'offset': offset,
            'limit': limit
        }
        
    except Exception as e:
        logger.error(f"Error getting conversation: {e}", exc_info=True)
        return {"error": f"Failed to get conversation: {str(e)}"}


def get_message_bus_conversation(
    conversation_id: Optional[str], limit: int, offset: int
) -> Dict[str, Any]:
    """Get messages from message_bus.jsonl, optionally filtered by conversation_id."""
    message_bus_file = responses_dir_path / 'message_bus.jsonl'
    if not message_bus_file.exists():
        return {"error": "Message bus log not found"}
    
    messages = []
    seen_messages = set()
    
    with open(message_bus_file, 'r') as f:
        for line in f:
            try:
                msg = json.loads(line.strip())
                
                # Only process entries with valid timestamps
                timestamp = msg.get('timestamp')
                if not timestamp:
                    continue
                
                # Only include COMPLETION_RESULT types
                if msg.get('type') != 'COMPLETION_RESULT':
                    continue
                
                # Extract session_id and content from result
                result = msg.get('result', {})
                session_id = result.get('session_id')
                if not session_id:
                    continue
                
                # Filter by conversation_id (session_id) if provided
                if conversation_id and session_id != conversation_id:
                    continue
                
                # Deduplicate
                content = result.get('response', '')
                client_id = msg.get('client_id', 'Unknown')
                msg_id = f"{timestamp}:{client_id}:{hash(content)}"
                
                if msg_id not in seen_messages:
                    seen_messages.add(msg_id)
                    messages.append({
                        'timestamp': timestamp,
                        'sender': client_id,
                        'content': content,
                        'session_id': session_id,
                        'model': result.get('model', 'unknown'),
                        'type': 'completion_result'
                    })
                    
            except (json.JSONDecodeError, ValueError):
                continue
    
    # Sort by timestamp
    messages.sort(key=lambda m: m['timestamp'])
    
    # Apply pagination
    total = len(messages)
    messages = messages[offset:offset + limit]
    
    return {
        'session_id': 'message_bus',
        'filtered_session_id': conversation_id,
        'messages': messages,
        'total': total,
        'offset': offset,
        'limit': limit
    }


@event_handler("conversation:export")
async def handle_export_conversation(data: ConversationExportData) -> Dict[str, Any]:
    """Export conversation to markdown or JSON format."""
    try:
        session_id = data.get('session_id')
        if not session_id:
            return {"error": "session_id required"}
        
        format_type = data.get('format', 'markdown')
        if format_type not in ['markdown', 'json']:
            return {"error": f"Unsupported format: {format_type}. Supported formats: markdown, json"}
        
        # Get conversation messages
        conv_result = await handle_get_conversation(
            {'session_id': session_id, 'limit': 10000}
        )
        
        if 'error' in conv_result:
            return conv_result
        
        messages = conv_result['messages']
        
        # Generate timestamp for filename
        timestamp = filename_timestamp(utc=False)
        
        if format_type == 'json':
            # Build JSON content
            export_data = {
                'session_id': session_id,
                'exported_at': display_timestamp('%Y-%m-%d %H:%M:%S', utc=False),
                'exported_at_iso': datetime.now(timezone.utc).isoformat(),
                'total_messages': len(messages),
                'messages': []
            }
            
            # Add messages with structured data
            for msg in messages:
                msg_timestamp = msg.get('timestamp', '')
                
                # Format timestamp for display
                display_time = msg_timestamp
                try:
                    dt = parse_iso_timestamp(msg_timestamp)
                    local_dt = utc_to_local(dt)
                    display_time = local_dt.strftime('%Y-%m-%d %H:%M:%S')
                except (ValueError, AttributeError):
                    pass
                
                message_data = {
                    'timestamp': msg_timestamp,
                    'display_time': display_time,
                    'sender': msg.get('sender', 'Unknown'),
                    'content': msg.get('content', ''),
                    'type': msg.get('type', 'unknown')
                }
                
                # Add recipient for direct messages
                if msg.get('type') == 'message' and msg.get('to'):
                    message_data['to'] = msg['to']
                
                export_data['messages'].append(message_data)
            
            # Save to JSON file
            export_filename = f"conversation_{session_id}_{timestamp}.json"
            export_path = exports_dir / export_filename
            
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        else:  # markdown format
            # Build markdown content
            md_lines = [f"# Conversation Export: {session_id}\n"]
            md_lines.append(f"*Exported on {display_timestamp('%Y-%m-%d %H:%M:%S', utc=False)}*\n")
            md_lines.append(f"*Total messages: {len(messages)}*\n")
            md_lines.append("---\n")
            
            # Add messages
            for msg in messages:
                msg_timestamp = msg.get('timestamp', '')
                
                # Format timestamp for display
                try:
                    dt = parse_iso_timestamp(msg_timestamp)
                    local_dt = utc_to_local(dt)
                    time_str = local_dt.strftime('%Y-%m-%d %H:%M:%S')
                except (ValueError, AttributeError):
                    time_str = msg_timestamp
                
                sender = msg.get('sender', 'Unknown')
                content = msg.get('content', '')
                
                # Add recipient for direct messages
                if msg.get('type') == 'message' and msg.get('to'):
                    md_lines.append(f"### {time_str} - {sender} → {msg['to']}\n")
                else:
                    md_lines.append(f"### {time_str} - {sender}\n")
                
                md_lines.append(f"{content}\n")
                md_lines.append("---\n")
            
            # Save to file
            export_filename = f"conversation_{session_id}_{timestamp}.md"
            export_path = exports_dir / export_filename
            
            with open(export_path, 'w', encoding='utf-8') as f:
                f.writelines(md_lines)
        
        return {
            'export_path': str(export_path),
            'filename': export_filename,
            'format': format_type,
            'message_count': len(messages),
            'size_bytes': export_path.stat().st_size
        }
        
    except Exception as e:
        logger.error(f"Error exporting conversation: {e}", exc_info=True)
        return {"error": f"Export failed: {str(e)}"}


@event_handler("conversation:stats")
async def handle_conversation_stats(data: ConversationStatsData) -> Dict[str, Any]:
    """Get statistics about conversations."""
    try:
        # Refresh cache if needed
        if is_cache_stale():
            refresh_conversation_cache()
        
        # Calculate stats
        total_conversations = len(conversation_cache)
        total_messages = sum(c.get('message_count', 0) for c in conversation_cache.values())
        total_size_bytes = sum(c.get('size_bytes', 0) for c in conversation_cache.values())
        
        # Find date range
        all_timestamps = []
        for conv in conversation_cache.values():
            if conv.get('first_timestamp'):
                all_timestamps.append(conv['first_timestamp'])
            if conv.get('last_timestamp'):
                all_timestamps.append(conv['last_timestamp'])
        
        all_timestamps.sort()
        
        stats = {
            'total_conversations': total_conversations,
            'total_messages': total_messages,
            'total_size_bytes': total_size_bytes,
            'total_size_mb': round(total_size_bytes / (1024 * 1024), 2),
            'earliest_timestamp': all_timestamps[0] if all_timestamps else None,
            'latest_timestamp': all_timestamps[-1] if all_timestamps else None,
            'exports_dir': str(exports_dir),
            'cache_age_seconds': int((datetime.now(timezone.utc) - cache_timestamp).total_seconds()) if cache_timestamp else None
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting conversation stats: {e}", exc_info=True)
        return {"error": f"Failed to get stats: {str(e)}"}


@event_handler("conversation:active")
async def handle_active_conversations(data: ConversationActiveData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Find active conversations from recent COMPLETION_RESULT messages."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    
    try:
        # Parameters
        max_lines = data.get('max_lines', 100)
        max_age_hours = data.get('max_age_hours', 2160)  # 90 days default
        
        message_bus_file = responses_dir_path / 'message_bus.jsonl'
        if not message_bus_file.exists():
            return event_response_builder({"active_sessions": []}, context)
        
        active_sessions = {}
        cutoff_time = datetime.now(timezone.utc).timestamp() - (max_age_hours * 3600)
        
        # Read recent lines from message bus
        recent_lines = []
        try:
            with open(message_bus_file, 'rb') as f:
                f.seek(0, 2)  # Go to end
                f.seek(max(0, f.tell() - max_lines * 200))  # Estimate
                lines = f.read().decode('utf-8', errors='ignore').split('\n')[-max_lines:]
                recent_lines = [line for line in lines if line.strip()]
        except Exception as e:
            logger.warning(f"Error reading message bus: {e}")
            return event_response_builder({"active_sessions": []}, context)
        
        # Process recent COMPLETION_RESULT messages
        for line in reversed(recent_lines):  # Most recent first
            try:
                msg = json.loads(line.strip())
                
                # Only process COMPLETION_RESULT messages
                if msg.get('type') != 'COMPLETION_RESULT':
                    continue
                
                # Extract session_id from result
                result = msg.get('result', {})
                session_id = result.get('session_id')
                if not session_id:
                    continue
                
                # Check timestamp
                timestamp = msg.get('timestamp')
                if timestamp:
                    try:
                        dt = parse_iso_timestamp(timestamp)
                        if dt.timestamp() < cutoff_time:
                            continue
                    except (ValueError, AttributeError):
                        continue
                
                # Track session activity
                if session_id not in active_sessions:
                    active_sessions[session_id] = {
                        'session_id': session_id,
                        'last_activity': timestamp,
                        'client_id': msg.get('client_id'),
                        'message_count': 0,
                        'last_response': result.get('response', ''),
                        'model': result.get('model', 'unknown')
                    }
                
                active_sessions[session_id]['message_count'] += 1
                
                # Keep most recent activity
                if timestamp > active_sessions[session_id]['last_activity']:
                    active_sessions[session_id].update({
                        'last_activity': timestamp,
                        'last_response': result.get('response', ''),
                        'client_id': msg.get('client_id')
                    })
                    
            except Exception as e:
                logger.debug(f"Error processing message bus line: {e}")
                continue
        
        # Sort by last activity
        sessions_list = list(active_sessions.values())
        sessions_list.sort(key=lambda s: s['last_activity'], reverse=True)
        
        return event_response_builder({
            'active_sessions': sessions_list,
            'total_active': len(sessions_list),
            'scanned_lines': len(recent_lines)
        }, context)
        
    except Exception as e:
        logger.error(f"Error getting active conversations: {e}", exc_info=True)
        return error_response(f"Failed to get active conversations: {str(e)}", context)


