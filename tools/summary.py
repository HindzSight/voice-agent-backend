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
    logger = logging.getLogger("tools.summary")
    logger.info(f"end_conversation called with summary: {summary}")

    room = context.session.userdata.get("room") if context and context.session else None
    try:
        if room:
            await room.local_participant.publish_data(
                json.dumps({"type": "summary", "text": summary}),
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
        await supabase.table("call_summaries").insert({
            "summary": summary,
        }).execute()
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
