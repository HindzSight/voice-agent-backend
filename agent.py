import logging
from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
    inference,
    room_io,
)
from livekit.plugins import  silero

from config import DEEPGRAM_API_KEY, CARTESIA_API_KEY
from tools.appointments import (
    identify_user,
    fetch_slots,
    book_appointment,
    retrieve_appointments,
    cancel_appointment,
    modify_appointment,
)
from tools.summary import end_conversation
from llm.openrouter_llm import OpenRouterLLM

load_dotenv(".env")
logger = logging.getLogger("agent")


class Assistant(Agent):
    def __init__(self):
        super().__init__(
            instructions="""
You are a voice AI assistant for appointment management.

Rules:
- If phone number is missing, ask for it.
- Use tools whenever applicable.
- Confirm all bookings verbally.
- Be concise and clear.
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
        self.contact_number = None

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
    if not DEEPGRAM_API_KEY or not CARTESIA_API_KEY:
        logger.error("API keys for Deepgram or Cartesia are missing.")
        return
    session = AgentSession(
        stt=inference.STT(
            model="deepgram/nova-3",
            api_key=DEEPGRAM_API_KEY,
            language="en",
        ),
        llm=OpenRouterLLM(),
        tts=inference.TTS(
            model="cartesia/sonic-3",
            api_key=CARTESIA_API_KEY,
        ),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_options=room_io.RoomOptions(),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(server)
