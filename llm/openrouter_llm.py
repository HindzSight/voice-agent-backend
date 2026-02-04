from livekit.plugins import openai as lk_openai
from config import OPENROUTER_API_KEY

def get_openrouter_llm():
    """Returns an LLM configured for OpenRouter using OpenAI-compatible client."""
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY must be set")
    # Using meta-llama model which supports function/tool calling
    return lk_openai.LLM(
        model="meta-llama/llama-3.3-70b-instruct:free",
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )
