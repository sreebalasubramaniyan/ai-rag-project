import os
import json
import time
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional

class OpenRouterClient:
    """Client for OpenRouter API providing access to completely free online models."""

    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
    DEFAULT_CHAT_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"

    FREE_FALLBACK_MODELS = [
        "meta-llama/llama-3.3-70b-instruct:free",
        "meta-llama/llama-3.1-8b-instruct:free",
        "mistralai/mistral-7b-instruct:free",
        "google/gemma-2-9b-it:free",
        "qwen/qwen-2.5-72b-instruct:free"
    ]

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, timeout: float = 60.0):
        self.api_key = (api_key or os.getenv("OPENROUTER_API_KEY", "")).strip()
        self.base_url = (base_url or os.getenv("OPENROUTER_BASE_URL", self.DEFAULT_BASE_URL)).rstrip("/")
        self.timeout = timeout

    def is_available(self) -> bool:
        """Checks if an OpenRouter API key is present and configured."""
        key = self.api_key or os.getenv("OPENROUTER_API_KEY", "").strip()
        if not key or key == "your_openrouter_api_key_here" or key.startswith("your_"):
            return False
        return True

    def generate_completion(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.1
    ) -> str:
        """Generates grounded chat completion via OpenRouter with automatic free model fallback."""
        key = self.api_key or os.getenv("OPENROUTER_API_KEY", "").strip()
        if not key or key == "your_openrouter_api_key_here" or key.startswith("your_"):
            raise ValueError(
                "OPENROUTER_API_KEY is not configured in .env. "
                "Get your free key at https://openrouter.ai/keys and add it to .env: OPENROUTER_API_KEY=sk-or-..."
            )

        target_model = model or os.getenv("OPENROUTER_CHAT_MODEL", self.DEFAULT_CHAT_MODEL)
        candidate_models = [target_model]
        for fb in self.FREE_FALLBACK_MODELS:
            if fb not in candidate_models:
                candidate_models.append(fb)

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        last_error = None

        for current_model in candidate_models:
            for attempt in range(2):
                try:
                    payload = json.dumps({
                        "model": current_model,
                        "messages": messages,
                        "temperature": temperature
                    }).encode("utf-8")

                    req = urllib.request.Request(
                        f"{self.base_url}/chat/completions",
                        data=payload,
                        headers={
                            "Authorization": f"Bearer {key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "http://localhost:8000",
                            "X-Title": "Enterprise RAG Console",
                            "User-Agent": "Enterprise-RAG-Client/2.0"
                        },
                        method="POST"
                    )

                    with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                        res_data = json.loads(resp.read().decode("utf-8"))
                        choices = res_data.get("choices", [])
                        if choices and "message" in choices[0]:
                            content = choices[0]["message"].get("content", "").strip()
                            if content:
                                return content

                except urllib.error.HTTPError as http_err:
                    last_error = http_err
                    status_code = http_err.code
                    err_body = ""
                    try:
                        err_body = http_err.read().decode("utf-8")
                    except Exception:
                        pass

                    if status_code == 401:
                        raise ValueError(
                            "Invalid OpenRouter API Key. Please verify OPENROUTER_API_KEY in your .env file."
                        ) from None
                    elif status_code in (429, 503):
                        # Free model rate limited or busy, pause briefly then try next
                        time.sleep(1.0)
                        continue
                    else:
                        break
                except Exception as exc:
                    last_error = exc
                    time.sleep(0.5)
                    break

        if last_error:
            raise RuntimeError(f"OpenRouter free model synthesis failed: {last_error}")
        return "No response received from OpenRouter."
