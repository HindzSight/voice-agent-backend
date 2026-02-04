from livekit.agents import function_tool, RunContext
from db.supabase import supabase

@function_tool
async def end_conversation(context: RunContext):
    """End the conversation and generate a summary."""
    agent = context.agent
    history = agent.history

    prompt = f"""
Summarize the following conversation.
Include:
- Booked appointments
- User preferences
- Contact number (if mentioned)

Conversation:
{history}
"""

    summary = await agent.llm.generate(prompt)

    contact = agent.contact_number if hasattr(agent, "contact_number") else None

    supabase.table("call_summaries").insert({
        "contact_number": contact,
        "summary": summary,
    }).execute()

    return summary
