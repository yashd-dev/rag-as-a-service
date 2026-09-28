from dataclasses import dataclass

import httpx
from openai import OpenAI

from backend.app.services.crypto import SecretBox


@dataclass(frozen=True)
class LlmConfig:
    base_url: str
    api_key: str
    model: str
    source: str


class OpenAICompatibleLlm:
    def __init__(self, config: LlmConfig):
        self.config = config
        self.client = OpenAI(api_key=config.api_key, base_url=config.base_url.rstrip("/"))

    def complete(self, messages: list[dict], temperature: float = 0.2) -> str:
        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""


class OllamaGenerateLlm:
    def __init__(self, base_url: str, model: str, timeout: float | None = None, json_mode: bool = False):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.json_mode = json_mode

    def generate(self, prompt: str) -> str:
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        if self.json_mode:
            payload["format"] = "json"
        response = httpx.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return str(response.json().get("response") or "")


def platform_llm_config(app_config: dict) -> LlmConfig:
    return LlmConfig(
        base_url=app_config["PLATFORM_LLM_BASE_URL"],
        api_key=app_config["PLATFORM_LLM_API_KEY"],
        model=app_config["PLATFORM_LLM_MODEL"],
        source="platform",
    )


def credential_llm_config(credential: dict, encryption_key: str) -> LlmConfig:
    api_key = SecretBox(encryption_key).decrypt(credential["encrypted_api_key"])
    return LlmConfig(
        base_url=credential.get("base_url") or "https://api.openai.com/v1",
        api_key=api_key,
        model=credential.get("default_model") or "gpt-4o-mini",
        source=credential["id"],
    )


def graph_extraction_llm(app_config: dict) -> OllamaGenerateLlm:
    timeout = app_config.get("GRAPH_LLM_TIMEOUT_SECONDS")
    return OllamaGenerateLlm(
        app_config["OLLAMA_BASE_URL"],
        app_config["GRAPH_LLM_MODEL"],
        float(timeout) if timeout not in (None, "", 0, "0") else None,
        json_mode=True,
    )


def fallback_generation_llm(app_config: dict) -> OllamaGenerateLlm:
    return OllamaGenerateLlm(app_config["OLLAMA_BASE_URL"], app_config["FALLBACK_LLM_MODEL"])


def generate_text_with_fallback(app_config: dict, messages: list[dict]) -> str:
    try:
        return OpenAICompatibleLlm(platform_llm_config(app_config)).complete(messages)
    except Exception:
        prompt = "\n".join(f"{message.get('role', 'user')}: {message.get('content', '')}" for message in messages)
        return fallback_generation_llm(app_config).generate(prompt)
