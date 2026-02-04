import requests
from livekit.agents import llm as lk_llm
from config import OPENROUTER_API_KEY


class OpenRouterLLM(lk_llm.LLM):
    async def chat(
        self,
        messages: list[dict],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost",
                "X-Title": "LiveKit Voice Agent",
            },
            json={
                "model": "mistralai/mistral-small-3.1-24b-instruct:free",
                "messages": messages,
                "temperature": temperature or 0,
                "max_tokens": max_tokens or 512,
            },
            timeout=15,
        )

        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
