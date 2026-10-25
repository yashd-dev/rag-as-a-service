import math
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from backend.app.services.crypto import SecretBox
from backend.app.services.graph_extraction import GRAPH_EXTRACTION_SCHEMA
from backend.app.services.grounding import ANSWER_SCHEMA, GenerationFailure
from openai import OpenAI, OpenAIError


@dataclass(frozen=True)
class LlmConfig:
    base_url: str
    api_key: str
    model: str
    source: str
    user_supplied: bool = False


class OpenAICompatibleLlm:
    def __init__(self, config: LlmConfig):
        self.config = config
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url.rstrip("/"),
            timeout=60,
            max_retries=1,
            **({"http_client": httpx.Client(follow_redirects=False, trust_env=False)} if config.user_supplied else {}),
        )
        self.last_model = config.model
        self.last_usage = None

    def complete(
        self, messages: list[dict], temperature: float = 0.2, json_mode: bool = False
    ) -> str:
        options = {}
        if self.config.user_supplied and urlsplit(self.config.base_url).hostname == "ai-gateway.vercel.sh":
            # Reasoning models can spend the bounded completion budget before emitting JSON.
            options["reasoning_effort"] = "none"
        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=temperature,
            max_tokens=1024,
            **({"response_format": {"type": "json_object"}} if json_mode else {}),
            **options,
        )
        self.last_model = response.model or self.config.model
        usage = getattr(response, "usage", None)
        self.last_usage = usage.model_dump(include={"prompt_tokens", "completion_tokens", "total_tokens"}) if usage is not None else None
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


class NvidiaGenerateLlm:
    def __init__(
        self, api_key, endpoint, model, timeout, max_tokens, reasoning_budget, thinking
    ):
        self.provider = "nvidia"
        self.api_key = api_key
        self.endpoint = endpoint
        self.base_url = endpoint.rsplit("/chat/completions", 1)[0]
        self.model = model
        self.timeout = timeout
        self.options = {
            "temperature": 0,
            "top_p": 0.95,
            "max_tokens": max_tokens,
            "reasoning_budget": reasoning_budget,
            "chat_template_kwargs": {"enable_thinking": thinking},
        }
        self.last_model = model

    def revision(self):
        return {"model": self.model, "revision": f"nvidia:{self.model}"}

    def generate(self, prompt: str) -> str:
        response = httpx.post(
            self.endpoint,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "response_format": {"type": "json_object"},
                **self.options,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        body = response.json()
        self.last_model = body.get("model") or self.model
        try:
            text = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ValueError("NVIDIA response did not contain message content") from None
        if not isinstance(text, str) or not text.strip():
            raise ValueError("NVIDIA response did not contain message content")
        return text


def platform_llm_config(app_config: dict) -> LlmConfig:
    return LlmConfig(
        base_url=app_config.get("PLATFORM_LLM_BASE_URL", ""),
        api_key=app_config.get("PLATFORM_LLM_API_KEY", ""),
        model=app_config.get("PLATFORM_LLM_MODEL", ""),
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


def graph_extraction_llm(app_config: dict) -> OllamaGenerateLlm | NvidiaGenerateLlm:
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
    nvidia_key = app_config.get("NVIDIA_API_KEY") or app_config.get("NVIDIA_API")
    if nvidia_key:
        model = app_config.get("GRAPH_LLM_MODEL")
        if not model or model == "smollm2:135m":
            model = app_config.get(
                "NVIDIA_GRAPH_LLM_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b"
            )
        reasoning_budget = int(app_config.get("GRAPH_LLM_REASONING_BUDGET", 16384))
        if not 0 <= reasoning_budget <= 16384:
            raise ValueError("Graph reasoning budget must be between 0 and 16384")
        thinking = str(app_config.get("NVIDIA_GRAPH_LLM_THINKING", "false")).lower() in {
            "1",
            "true",
            "yes",
        }
        return NvidiaGenerateLlm(
            nvidia_key,
            app_config.get(
                "NVIDIA_GRAPH_LLM_URL",
                "https://integrate.api.nvidia.com/v1/chat/completions",
            ),
            model,
            timeout,
            max(predictions, 16384) if thinking else max(predictions, 4096),
            reasoning_budget if thinking else 0,
            thinking,
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


def generate_grounded(app_config, messages, *, llm_config=None):
    if llm_config is None and not app_config.get("PLATFORM_LLM_API_KEY"):
        raise GenerationFailure("generation_not_configured")
    client = None
    try:
        client = OpenAICompatibleLlm(llm_config or platform_llm_config(app_config))
        raw = client.complete(messages, temperature=0, json_mode=True)
        return raw, {
            "provider": "openai_compatible",
            "model": client.last_model,
            "fallback": False,
            "fallback_reason": None,
            **({"configuration": llm_config.source} if llm_config is not None else {}),
            **({"usage": client.last_usage} if getattr(client, "last_usage", None) else {}),
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
