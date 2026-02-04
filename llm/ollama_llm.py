from livekit.plugins import openai as lk_openai
from config import OLLAMA_URL, OLLAMA_MODEL

def get_ollama_llm():
    """Returns an LLM configured for Ollama using OpenAI-compatible client."""
    return lk_openai.LLM(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_URL,
        api_key="ollama", # Ollama doesn't require a real API key but the plugin might expect one
    )
