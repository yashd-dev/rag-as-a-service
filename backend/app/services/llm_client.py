import math
import re
from dataclasses import dataclass

import httpx
from openai import OpenAI, OpenAIError

from backend.app.services.crypto import SecretBox
from backend.app.services.graph_extraction import GRAPH_EXTRACTION_SCHEMA
from backend.app.services.grounding import ANSWER_SCHEMA, GenerationFailure


@dataclass(frozen=True)
class LlmConfig:
    base_url: str
    api_key: str
    model: str
    source: str


class OpenAICompatibleLlm:
    def __init__(self, config: LlmConfig):
        self.config = config
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url.rstrip("/"),
            timeout=60,
            max_retries=1,
        )
        self.last_model = config.model

    def complete(
        self, messages: list[dict], temperature: float = 0.2, json_mode: bool = False
    ) -> str:
        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=temperature,
            max_tokens=1024,
            **({"response_format": {"type": "json_object"}} if json_mode else {}),
        )
        self.last_model = response.model or self.config.model
        return response.choices[0].message.content or ""


class OllamaGenerateLlm:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float | None = None,
        json_mode: bool = False,
        options: dict | None = None,
        json_schema: dict | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.json_mode = json_mode
        self.options = options or {}
        self.json_schema = json_schema
        self.last_model = model

    def revision(self):
        response = httpx.get(self.base_url + "/api/tags", timeout=30)
        response.raise_for_status()
        tag = (
            self.model
            if ":" in self.model.rsplit("/", 1)[-1]
            else self.model + ":latest"
        )
        matches = [
            item
            for item in response.json().get("models", [])
            if item.get("name") == tag
        ]
        if len(matches) != 1 or not re.fullmatch(
            r"[0-9a-f]{64}", matches[0].get("digest", "")
        ):
            raise ValueError("Graph model revision unavailable")
        return {"model": tag, "revision": matches[0]["digest"]}

    def generate(self, prompt: str) -> str:
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        if self.json_mode:
            payload["format"] = self.json_schema or "json"
        if self.options:
            payload["options"] = self.options
        print(
            f"ollama_generate start model={self.model} json_mode={self.json_mode} "
            f"prompt_chars={len(prompt)} timeout={self.timeout if self.timeout is not None else 'none'} options={self.options}",
            flush=True,
        )
        response = httpx.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        body = response.json()
        self.last_model = body.get("model") or self.model
        text = str(body.get("response") or "")
        print(
            f"ollama_generate done model={self.model} response_chars={len(text)} "
            f"eval_count={body.get('eval_count')} done_reason={body.get('done_reason')} "
            f"total_duration={body.get('total_duration')}",
            flush=True,
        )
        return text


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
    timeout = float(app_config.get("GRAPH_LLM_TIMEOUT_SECONDS", 60))
    if not math.isfinite(timeout) or not 0 < timeout <= 120:
        raise ValueError("Graph extraction timeout must be between 0 and 120 seconds")
    predictions, context = int(app_config.get("GRAPH_LLM_NUM_PREDICT", 700)), int(
        app_config.get("GRAPH_LLM_NUM_CTX", 4096)
    )
    if not 1 <= predictions <= 4096 or context < 4096:
        raise ValueError(
            "Graph extraction requires bounded output and at least 4096 context tokens"
        )
    return OllamaGenerateLlm(
        app_config["OLLAMA_BASE_URL"],
        app_config["GRAPH_LLM_MODEL"],
        timeout,
        json_mode=True,
        options={
            "temperature": 0,
            "num_predict": predictions,
            "num_ctx": context,
        },
        json_schema=GRAPH_EXTRACTION_SCHEMA,
    )


def fallback_generation_llm(
    app_config: dict, json_mode: bool = False
) -> OllamaGenerateLlm:
    return OllamaGenerateLlm(
        app_config["OLLAMA_BASE_URL"],
        app_config["FALLBACK_LLM_MODEL"],
        timeout=60,
        json_mode=json_mode,
        json_schema=ANSWER_SCHEMA if json_mode else None,
        options={"temperature": 0, "num_ctx": 8192, "num_predict": 1024},
    )


def generate_grounded(app_config, messages):
    if not app_config.get("PLATFORM_LLM_API_KEY"):
        raise GenerationFailure("generation_not_configured")
    client = None
    try:
        client = OpenAICompatibleLlm(platform_llm_config(app_config))
        raw = client.complete(messages, temperature=0, json_mode=True)
        return raw, {
            "provider": "openai_compatible",
            "model": client.last_model,
            "fallback": False,
            "fallback_reason": None,
        }
    except (OpenAIError, httpx.HTTPError, ValueError):
        # A provider outage must not silently select an unvalidated answer model.
        raise GenerationFailure("generation_unavailable") from None
    finally:
        if client is not None:
            client.client.close()


def generate_text_with_fallback(app_config: dict, messages: list[dict]) -> str:
    try:
        return OpenAICompatibleLlm(platform_llm_config(app_config)).complete(messages)
    except Exception:  # noqa: BLE001 - existing platform-to-local generation fallback
        prompt = "\n".join(
            f"{message.get('role', 'user')}: {message.get('content', '')}"
            for message in messages
        )
        return fallback_generation_llm(app_config).generate(prompt)
