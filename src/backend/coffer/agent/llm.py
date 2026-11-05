from dataclasses import dataclass
from typing import Any, Literal, Protocol

import httpx

from coffer.core.config import get_settings


@dataclass(frozen=True)
class LLMMessage:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str
    input_tokens: int | None
    output_tokens: int | None


class LLMUnavailable(Exception):
    pass


@dataclass(frozen=True)
class LLMStatus:
    available: bool
    model: str


class LLMClient(Protocol):
    def status(self) -> LLMStatus: ...

    def complete(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        response_schema: dict[str, Any] | None = None,
    ) -> LLMResponse: ...


class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout_s: float):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s

    def status(self) -> LLMStatus:
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=2.0)
            if resp.status_code != 200:
                return LLMStatus(False, self.model)
            names = {m.get("name") for m in resp.json().get("models", [])}
            ok = self.model in names or f"{self.model}:latest" in names
            return LLMStatus(ok, self.model)
        except Exception:
            return LLMStatus(False, self.model)

    def complete(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        response_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                *({"role": m.role, "content": m.content} for m in messages),
            ],
            "stream": False,
            "format": response_schema,
            "think": False,
            "options": {"temperature": 0.2},
        }
        try:
            resp = httpx.post(f"{self.base_url}/api/chat", json=body, timeout=self.timeout_s)
        except httpx.HTTPError as exc:
            raise LLMUnavailable(str(exc)) from exc
        if resp.status_code != 200:
            raise LLMUnavailable(f"Ollama status {resp.status_code}")
        try:
            data = resp.json()
            content = data["message"]["content"]
        except (ValueError, KeyError, TypeError) as exc:
            raise LLMUnavailable("Niepoprawna odpowiedź Ollamy") from exc
        return LLMResponse(
            content=content,
            model=data.get("model") or self.model,
            input_tokens=data.get("prompt_eval_count"),
            output_tokens=data.get("eval_count"),
        )


def get_llm_client() -> LLMClient | None:
    settings = get_settings()
    if settings.llm_provider == "none":
        return None
    return OllamaClient(settings.ollama_url, settings.ollama_model, settings.llm_timeout_s)
