import logging
import json
import asyncio
import time
from datetime import datetime
from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
)
from livekit.plugins import silero, bey

from config import DEEPGRAM_API_KEY, CARTESIA_API_KEY, BEYOND_API_KEY
from tools.appointments import (
    identify_user,
    fetch_slots,
    book_appointment,
    retrieve_appointments,
    cancel_appointment,
    modify_appointment,
)
from tools.summary import end_conversation
from tools.summary import end_conversation
from llm.ollama_llm import get_ollama_llm
from livekit.plugins.deepgram import STT as DeepgramSTT
from livekit.plugins.cartesia import TTS as CartesiaTTS
import os

load_dotenv(".env")
logger = logging.getLogger("agent")


class Assistant(Agent):
    def __init__(self):
        super().__init__(
            instructions=f"""
You are a friendly voice AI assistant helping users manage their appointments. Speak naturally and conversationally.

TODAY'S DATE: {datetime.now().strftime("%A, %B %d, %Y")}

CORE RULE:
- NEVER invent or guess data. ALWAYS use the provided tools to fetch information.
- If a user asks for available slots, appointments, or status, you MUST call the corresponding tool first.
- Do not make up dates or times. Only speak what the tools return.
- FOR ANY TOOL and SENDING DATA TO TOOLS AND DB ALWAYS USE DATE AS "YYYY-MM-DD" format and TIME AS "HH:MM" format.
- FOR USER RESPONSES USE DATE AS "Month DD, YYYY" format and TIME AS "HH:MM AM/PM" format.
- DO NOT output tool calls as text strings (e.g. :end_conversation{...}). Invoke the tool function properly using the available tools mechanism.

- If user mentions only a date without a time, ask them to pick a specific time from the available slots on that date.
- When booking, confirm all details: name, phone number, date, and time before finalizing.
- After any action, confirm what was done and ask if they need anything else.

AVAILABLE TOOLS & USAGE:
1. `identify_user`: Call this FIRST when the user wants to book, modify, or check appointments. Ask for name and phone number.
2. `fetch_slots(date)`: Call this when the user asks "When are you free?" or "Can I book on Tuesday?".
   - If they specify a date, pass it. If not, call it with no arguments.
   - READ the available slots returned by the tool clearly.
3. `book_appointment(date, time, phone_number, name)`: Call this to finalize a booking.
   - ALWAYS confirm the details with the user before calling this.
4. `retrieve_appointments(phone_number)`: Call this when the user asks "Do I have any appointments?" or wants to modify/cancel.
5. `modify_appointment(appointment_id, new_date, new_time)`: Call this to change a time.
   - You must usually call `retrieve_appointments` first to get the `appointment_id` (unless the tool output provided it internally).
6. `cancel_appointment(appointment_id)`: Call this to cancel.
   - Like modify, verify the appointment first if needed.
7. Once a booking it done ask the user if he want to book more appointments or not. If he says yes, then call `fetch_slots` and ask him to provide the date. If he says no, then call `end_conversation` with the summary.
8. `end_conversation(summary)`: Call this IMMEDIATELY when the user explicitly says goodbye or wants to stop.
   - DO NOT generate a text response like "Goodbye" or "Have a great day". You MUST call this tool to end the call.
   - The tool itself will handle the closing signal.

When the user is finished and wants to end the call, generate a concise summary of the conversation and call end_conversation with that summary.
- CRITICAL: Do not speak a closing message yourself. Call the tool.

SPEAKING STYLE:
- Be warm, professional, and concise.
- Convert dates to spoken format (e.g., "February 10th" not "2026-02-10") when repondint to user but for tools use "YYYY-MM-DD" format.
- IMPORTANT: When calling tools, use "YYYY-MM-DD" for dates and "HH:MM" for times internally.
- SEQUENTIAL TOOLS: Always wait for one tool call to return a result before calling another. Do not call multiple tools in the same turn.
- If a tool result includes a section labeled "DO_NOT_READ_INTERNAL_IDS", never read it aloud. Use the IDs only for follow-up tool calls.
""",
            tools=[
                identify_user,
                fetch_slots,
                book_appointment,
                retrieve_appointments,
                cancel_appointment,
                modify_appointment,
                end_conversation,
            ],
        )

        self.history = []
        self.phone_number = None

    async def on_user_message(self, message: str):
        self.history.append({"role": "user", "content": message})

    async def on_agent_message(self, message: str):
        self.history.append({"role": "assistant", "content": message})


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def my_agent(ctx: JobContext):
    # Connect to the room first - this is required!
    await ctx.connect()

    if not DEEPGRAM_API_KEY or not CARTESIA_API_KEY:
        logger.error("API keys for Deepgram or Cartesia are missing.")
        return
    session = AgentSession(
        stt=DeepgramSTT(
            model="nova-3",
            api_key=DEEPGRAM_API_KEY,
            language="en",
        ),
        llm=get_openrouter_llm(),
        tts=CartesiaTTS(
            model="sonic-2",
            api_key=CARTESIA_API_KEY,
        ),
        vad=ctx.proc.userdata["vad"],
        userdata={"room": ctx.room},
        preemptive_generation=True,
    )

    agent = Assistant()
    start_time = time.time()
    
    # Store references for tools
    session.userdata["agent"] = agent
    session.userdata["start_time"] = start_time

    ready_sent = False

    def _maybe_send_ready(event):
        nonlocal ready_sent
        if ready_sent:
            return
        if getattr(event, "new_state", None) == "idle":
            ready_sent = True

            async def _publish_ready():
                try:
                    await ctx.room.local_participant.publish_data(
                        json.dumps({"type": "agent_ready"}),
                        reliable=True,
                        topic="agent",
                    )
                    logger.info("agent_ready event published")
                except Exception as e:
                    logger.warning(f"Failed to publish agent_ready event: {e}")

            asyncio.create_task(_publish_ready())

    session.on("agent_state_changed", _maybe_send_ready)

    @session.on("user_speech_committed")
    def on_user_speech(msg):
        if isinstance(msg, list):
            msg = " ".join([m.text for m in msg])
        elif hasattr(msg, "content"):
            msg = msg.content
        elif hasattr(msg, "text"):
            msg = msg.text
        
        # Avoid duplicates if we already have it (simple check)
        if not agent.history or agent.history[-1].get("content") != str(msg):
             agent.history.append({"role": "user", "content": str(msg)})

    @session.on("agent_speech_committed")
    def on_agent_speech(msg):
        if hasattr(msg, "content"):
            msg = msg.content
        
        agent.history.append({"role": "assistant", "content": str(msg)})

    await session.start(
        agent=agent,
        room=ctx.room,
    )

    if BEYOND_API_KEY:
        avatar = bey.AvatarSession(api_key=BEYOND_API_KEY)
        await avatar.start(session, ctx.room)


if __name__ == "__main__":
    cli.run_app(server)
