"""
Patch for completion_service.py to use enhanced JSON extraction with better feedback.

This shows the changes needed to provide feedback for both successful and failed extractions.
"""

# In the imports section, add:
from ksi_common.json_extraction_v2 import (
    extract_and_emit_json_events_v2, 
    format_extraction_feedback
)

# Replace the extract_and_send_feedback function (around line 619) with:
async def extract_and_send_feedback():
    try:
        # Use enhanced extraction that returns both successes and errors
        extraction_results, parse_errors = await extract_and_emit_json_events_v2(
            result_text,
            event_emitter=emit_event,
            context={
                "request_id": request_id,
                "session_id": session_id,
                "model": model,
                "provider": provider
            },
            agent_id=agent_id
        )
        
        # Log results
        if extraction_results or parse_errors:
            logger.info(f"JSON extraction completed",
                      request_id=request_id,
                      agent_id=agent_id,
                      successful_events=len(extraction_results),
                      parse_errors=len(parse_errors))
        
        # ALWAYS send feedback if we found any JSON patterns (valid or invalid)
        if agent_id and (extraction_results or parse_errors):
            # Format comprehensive feedback
            feedback_content = format_extraction_feedback(extraction_results, parse_errors)
            
            # Send via completion:async
            await event_emitter("completion:async", {
                "messages": [{
                    "role": "system",
                    "content": feedback_content
                }],
                "agent_id": agent_id,
                "originator_id": agent_id,
                "model": model,
                "priority": "high",
                "is_feedback": True,
                "parent_request_id": request_id,
                "feedback_type": "json_extraction",
                "extraction_summary": {
                    "successful": len(extraction_results),
                    "failed": len(parse_errors)
                }
            })
            
            logger.debug(f"Sent JSON extraction feedback to agent {agent_id}",
                       successes=len(extraction_results),
                       failures=len(parse_errors))
            
    except Exception as e:
        logger.error(f"Failed to process JSON extraction: {e}",
                   request_id=request_id,
                   error=str(e))
        
        # Even on complete failure, try to send error feedback
        if agent_id:
            try:
                await event_emitter("completion:async", {
                    "messages": [{
                        "role": "system",
                        "content": f"=== JSON EXTRACTION ERROR ===\nFailed to process JSON extraction: {str(e)}\n\nPlease check your JSON syntax and try again."
                    }],
                    "agent_id": agent_id,
                    "originator_id": agent_id,
                    "model": model,
                    "priority": "high",
                    "is_feedback": True,
                    "parent_request_id": request_id,
                    "feedback_type": "json_extraction_error"
                })
            except:
                logger.error("Failed to send extraction error feedback", exc_info=True)