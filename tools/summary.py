from livekit.agents import function_tool, RunContext
from db.supabase import get_supabase
import json

@function_tool
async def end_conversation(context: RunContext, summary: str):
    """
    End the conversation and save a summary. 
    Call this when the user is finished and you have summarized the key points of the call.
    """
    import logging
    import time
    logger = logging.getLogger("tools.summary")
    logger.info(f"end_conversation called with summary: {summary}")

    room = context.session.userdata.get("room") if context and context.session else None
    
            # Cost Calculation
    cost_breakdown = None
    try:
        start_time = context.session.userdata.get("start_time")
        agent = context.session.userdata.get("agent")
        
        if start_time and agent:
            duration = time.time() - start_time
            duration_min = duration / 60
            
            # Message history analysis
            tts_chars = 0
            
            # LLM Token Estimation (Heuristic: 1 token ~= 4 chars)
            # We assume a standard chat pattern: User message -> API Call (Input=History+User, Output=Response) -> Assistant message appended to History
            
            # Start with System Prompt in context
            current_context_chars = len(getattr(agent, "instructions", ""))
            
            total_llm_input_chars = 0
            total_llm_output_chars = 0
            
            for msg in agent.history:
                content_len = len(msg.get("content", ""))
                role = msg.get("role")
                
                if role == "user":
                    # User message is added to context for *next* generation
                    current_context_chars += content_len
                
                elif role == "assistant":
                    # Assistant message means a generation happened.
                    # The input for this generation was the context UP TO this point.
                    total_llm_input_chars += current_context_chars
                    
                    # The output is the content itself
                    total_llm_output_chars += content_len
                    tts_chars += content_len
                    
                    # Add result to context for subsequent turns
                    current_context_chars += content_len

            # Rates
            stt_rate_per_min = 0.0043
            tts_rate_per_char = 7.00 / 1_000_000
            
            # LLM Rates: $0.05/1M Input Tokens, $0.40/1M Output Tokens
            llm_input_rate_per_token = 0.05 / 1_000_000
            llm_output_rate_per_token = 0.40 / 1_000_000
            chars_per_token = 4.0
            
            stt_cost = duration_min * stt_rate_per_min
            tts_cost = tts_chars * tts_rate_per_char
            
            llm_input_cost = (total_llm_input_chars / chars_per_token) * llm_input_rate_per_token
            llm_output_cost = (total_llm_output_chars / chars_per_token) * llm_output_rate_per_token
            llm_cost = llm_input_cost + llm_output_cost
            
            total_cost = stt_cost + tts_cost + llm_cost
            
            cost_breakdown = {
                "total": round(total_cost, 5),
                "breakdown": {
                    "stt": round(stt_cost, 5),
                    "tts": round(tts_cost, 5),
                    "llm": round(llm_cost, 5),
                    "duration_seconds": round(duration, 2),
                    "tts_characters": tts_chars,
                    "llm_input_tokens": int(total_llm_input_chars / chars_per_token),
                    "llm_output_tokens": int(total_llm_output_chars / chars_per_token)
                }
            }
            logger.info(f"Calculated session cost: {cost_breakdown}")
    except Exception as e:
        logger.warning(f"Failed to calculate cost: {e}")

    try:
        if room:
            summary_payload = {"type": "summary", "text": summary}
            if cost_breakdown:
                summary_payload["cost_breakdown"] = cost_breakdown

            await room.local_participant.publish_data(
                json.dumps(summary_payload),
                reliable=True,
                topic="summary",
            )
            await room.local_participant.publish_data(
                json.dumps({"type": "call_end"}),
                reliable=True,
                topic="call",
            )
    except Exception as e:
        logger.debug(f"Failed to publish summary/call_end event: {e}")
    
    try:
        supabase = await get_supabase()
        data = {
            "summary": summary,
        }
        # If you have a column for metadata/cost in DB, add it here.
        # For now, we only persist summary text as requested.
        
        await supabase.table("call_summaries").insert(data).execute()
        logger.info("Summary saved successfully.")
        if room:
            try:
                await room.disconnect()
            except Exception as e:
                logger.debug(f"Failed to disconnect room: {e}")
        return "Conversation ended and summary saved."
    except Exception as e:
        logger.error(f"Error saving summary: {e}", exc_info=True)
        return "I saved your summary, but encountered an issue with the database."
