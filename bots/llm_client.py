"""
llm_client.py — Simple wrapper around OpenRouter API using requests.

Used by AI bot players to make decisions and generate chat messages.
Reads OPENROUTER_API_KEY from environment variables.
"""

import os
import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class LLMClient:
    """Thin wrapper for OpenRouter API."""

    def __init__(self, model: str = "google/gemma-4-31b-it:free"):
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.model = model
        self.headers = {
            "Authorization": f"Bearer {self.api_key}" if self.api_key else "",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Terminal-Mafia",  # Required by OpenRouter
            "X-Title": "Terminal Mafia AI Bot"                    # Required by OpenRouter
        }

    def is_configured(self) -> bool:
        """Check if API key is present."""
        return bool(self.api_key)

    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 150) -> str | None:
        """
        Call OpenRouter and return the text response.
        Returns None if there's an error or no API key.
        """
        if not self.is_configured():
            return None

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": 0.8
        }

        try:
            # 10 second timeout so bots don't hang the game
            response = requests.post(OPENROUTER_URL, json=payload, headers=self.headers, timeout=10.0)
            response.raise_for_status()
            
            data = response.json()
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"].strip()
            
            return None

        except requests.exceptions.RequestException as e:
            print(f"[Bot LLM Error] API request failed: {e}")
            return None
        except Exception as e:
            print(f"[Bot LLM Error] Unexpected error: {e}")
            return None
