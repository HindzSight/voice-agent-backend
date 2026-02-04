import logging
import json
import asyncio
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
from llm.ollama_llm import get_ollama_llm
from livekit.plugins.deepgram import STT as DeepgramSTT
from livekit.plugins.cartesia import TTS as CartesiaTTS

load_dotenv(".env")
logger = logging.getLogger("agent")


class Assistant(Agent):
    def __init__(self):
        super().__init__(
            instructions="""
You are a friendly voice AI assistant helping users manage their appointments. Speak naturally and conversationally.

YOUR WORKFLOW:
1. Greet the user warmly and ask how you can help.
2. If they want to book, check, modify, or cancel an appointment, first ask for their name and phone number using identify_user.
3. When they ask about availability, use fetch_slots to get available times. Present ALL slots clearly:
   - Say something like "We have 3 available slots: June 10th at 9 PM, June 11th at 11 AM, and March 12th at 2 PM. Which works best for you?"
   - Convert dates to spoken format (e.g., "February 10th" not "2026-02-10")
4. If user mentions only a date without a time, ask them to pick a specific time from the available slots on that date.
5. When booking, confirm all details: name, phone number, date, and time before finalizing.
6. After any action, confirm what was done and ask if they need anything else.
7. When the user is finished and wants to end the call, generate a concise summary of the conversation (appointments made, name, phone) and call end_conversation with that summary.
   - IMPORTANT: Only call end_conversation AFTER all other tools (like booking) have finished and the user is done. Never call it in parallel with other tools.

SPEAKING STYLE:
- Be warm, professional, and concise
- Use natural speech patterns ("Let me check that for you", "Perfect!", "Got it!")
- Say dates and times in a human-friendly way ("February 10th at 3 PM" not "2026-02-10 15:00")
- Never speak function names or function parameters aloud
- If something goes wrong, apologize and offer alternatives

IMPORTANT:
- Always collect name AND phone number before booking
- Never skip confirming the booking details
- If a slot is taken, immediately suggest other available times
- IMPORTANT: When calling book_appointment, use the format YYYY-MM-DD for dates (e.g., 2026-02-10) and HH:MM for times (e.g., 15:00).
- Convert user input like "February 10th" to "2026-02-10", and phone number like "nine eight seven" to "987" internally when calling the tool.
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
        llm=get_ollama_llm(),
        tts=CartesiaTTS(
            model="sonic-2",
            api_key=CARTESIA_API_KEY,
        ),
        vad=ctx.proc.userdata["vad"],
        userdata={"room": ctx.room},
        preemptive_generation=True,
    )

    agent = Assistant()

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

    await session.start(
        agent=agent,
        room=ctx.room,
    )

    if BEYOND_API_KEY:
        avatar = bey.AvatarSession(api_key=BEYOND_API_KEY)
        await avatar.start(session, ctx.room)


if __name__ == "__main__":
    cli.run_app(server)
