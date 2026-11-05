import hashlib
import time
from dataclasses import dataclass
from typing import Any, ClassVar, Literal, Protocol

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


LLMProvider = Literal["ollama", "openai", "gemini", "anthropic"]


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
    provider: ClassVar[LLMProvider] = "ollama"

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


def _post_json(
    url: str, *, body: dict[str, Any], headers: dict[str, str], timeout_s: float, provider: str
) -> dict[str, Any]:
    """POST a JSON body; map network/HTTP/parse errors to LLMUnavailable.

    Error messages never include headers (API keys) or the response body.
    """
    try:
        resp = httpx.post(url, json=body, headers=headers, timeout=timeout_s)
    except httpx.HTTPError as exc:
        raise LLMUnavailable(f"{provider}: błąd połączenia ({type(exc).__name__})") from exc
    if resp.status_code != 200:
        raise LLMUnavailable(f"{provider} status {resp.status_code}")
    try:
        data = resp.json()
    except ValueError as exc:
        raise LLMUnavailable(f"Niepoprawna odpowiedź {provider}") from exc
    if not isinstance(data, dict):
        raise LLMUnavailable(f"Niepoprawna odpowiedź {provider}")
    return data


STATUS_TTL_S = 60.0
STATUS_TIMEOUT_S = 2.0
# (provider, url, key fingerprint) -> (checked_at monotonic, available). Keys are hashed.
_STATUS_CACHE: dict[tuple[str, str, str], tuple[float, bool]] = {}


def _probe_status(provider: str, url: str, headers: dict[str, str], api_key: str) -> bool:
    """Cheap authenticated GET (no tokens billed); cached for STATUS_TTL_S.

    Any exception or non-200 status means unavailable.
    """
    fingerprint = hashlib.sha256(api_key.encode()).hexdigest()[:16]
    cache_key = (provider, url, fingerprint)
    now = time.monotonic()
    hit = _STATUS_CACHE.get(cache_key)
    if hit is not None and now - hit[0] < STATUS_TTL_S:
        return hit[1]
    try:
        ok = httpx.get(url, headers=headers, timeout=STATUS_TIMEOUT_S).status_code == 200
    except Exception:
        ok = False
    _STATUS_CACHE[cache_key] = (now, ok)
    return ok


def _int_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) else None


class OpenAIClient:
    """OpenAI Chat Completions API (or any compatible endpoint via base_url)."""

    provider: ClassVar[LLMProvider] = "openai"

    def __init__(self, api_key: str, model: str, base_url: str, timeout_s: float):
        self._api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def __repr__(self) -> str:
        return f"OpenAIClient(model={self.model!r}, base_url={self.base_url!r})"

    def status(self) -> LLMStatus:
        if not self._api_key:
            return LLMStatus(False, self.model)
        ok = _probe_status(
            "openai",
            f"{self.base_url}/models",
            {"Authorization": f"Bearer {self._api_key}"},
            self._api_key,
        )
        return LLMStatus(ok, self.model)

    def complete(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        response_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        if not self._api_key:
            raise LLMUnavailable("Brak klucza API OpenAI")
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                *({"role": m.role, "content": m.content} for m in messages),
            ],
            "temperature": 0.2,
        }
        if response_schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                # strict=False: Pydantic schemas lack additionalProperties=false,
                # which strict mode requires; the workflow validates the output anyway.
                "json_schema": {"name": "response", "schema": response_schema, "strict": False},
            }
        data = _post_json(
            f"{self.base_url}/chat/completions",
            body=body,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout_s=self.timeout_s,
            provider="OpenAI",
        )
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMUnavailable("Niepoprawna odpowiedź OpenAI") from exc
        if not isinstance(content, str):
            raise LLMUnavailable("Pusta odpowiedź OpenAI")
        usage = data.get("usage") or {}
        return LLMResponse(
            content=content,
            model=data.get("model") or self.model,
            input_tokens=_int_or_none(usage.get("prompt_tokens")),
            output_tokens=_int_or_none(usage.get("completion_tokens")),
        )


# Subset of OpenAPI-schema keywords accepted by Gemini's responseSchema.
_GEMINI_SCHEMA_KEYS = {
    "type",
    "format",
    "description",
    "nullable",
    "enum",
    "properties",
    "required",
    "items",
    "minItems",
    "maxItems",
    "minimum",
    "maximum",
    "anyOf",
    "propertyOrdering",
}


def gemini_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Convert a JSON Schema (e.g. from Pydantic) to the subset Gemini accepts.

    Inlines local $refs, maps ["T", "null"] types and anyOf-with-null to
    nullable, and drops unsupported keywords (additionalProperties, title, ...).
    """
    defs: dict[str, Any] = {**schema.get("definitions", {}), **schema.get("$defs", {})}

    def clean(node: Any, depth: int = 0) -> Any:
        if depth > 32:
            raise ValueError("Schema too deep")
        if isinstance(node, list):
            return [clean(n, depth + 1) for n in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            target = defs.get(str(node["$ref"]).rsplit("/", 1)[-1], {})
            extra = {k: v for k, v in node.items() if k != "$ref"}
            return clean({**target, **extra}, depth + 1)
        out: dict[str, Any] = {}
        if isinstance(node.get("type"), list):
            types = [t for t in node["type"] if t != "null"]
            if len(types) < len(node["type"]):
                out["nullable"] = True
            node = {**node, "type": types[0] if types else "string"}
        if isinstance(node.get("anyOf"), list):
            variants = [
                v for v in node["anyOf"] if not (isinstance(v, dict) and v.get("type") == "null")
            ]
            nullable = len(variants) < len(node["anyOf"])
            rest = {k: v for k, v in node.items() if k != "anyOf"}
            if len(variants) == 1:
                merged = clean({**rest, **variants[0]}, depth + 1)
                return {**merged, "nullable": True} if nullable else merged
            node = {**rest, "anyOf": variants}
            if nullable:
                out["nullable"] = True
        for key, value in node.items():
            if key not in _GEMINI_SCHEMA_KEYS:
                continue
            if key == "properties" and isinstance(value, dict):
                out[key] = {name: clean(sub, depth + 1) for name, sub in value.items()}
            elif key in ("items", "anyOf"):
                out[key] = clean(value, depth + 1)
            else:
                out[key] = value
        return out

    return clean(schema)


class GeminiClient:
    """Google Gemini generateContent API (Generative Language REST)."""

    provider: ClassVar[LLMProvider] = "gemini"

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, api_key: str, model: str, timeout_s: float, base_url: str | None = None):
        self._api_key = api_key
        self.model = model
        self.base_url = (base_url or self.BASE_URL).rstrip("/")
        self.timeout_s = timeout_s

    def __repr__(self) -> str:
        return f"GeminiClient(model={self.model!r})"

    def status(self) -> LLMStatus:
        if not self._api_key:
            return LLMStatus(False, self.model)
        ok = _probe_status(
            "gemini",
            f"{self.base_url}/models/{self.model}",
            {"x-goog-api-key": self._api_key},
            self._api_key,
        )
        return LLMStatus(ok, self.model)

    def complete(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        response_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        if not self._api_key:
            raise LLMUnavailable("Brak klucza API Gemini")
        generation_config: dict[str, Any] = {"temperature": 0.2}
        if response_schema is not None:
            generation_config["responseMimeType"] = "application/json"
            generation_config["responseSchema"] = gemini_schema(response_schema)
        body: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [
                {
                    "role": "model" if m.role == "assistant" else "user",
                    "parts": [{"text": m.content}],
                }
                for m in messages
            ],
            "generationConfig": generation_config,
        }
        # Key goes in a header, never in the URL (URLs end up in logs and exceptions).
        data = _post_json(
            f"{self.base_url}/models/{self.model}:generateContent",
            body=body,
            headers={"x-goog-api-key": self._api_key},
            timeout_s=self.timeout_s,
            provider="Gemini",
        )
        try:
            parts = data["candidates"][0]["content"]["parts"]
            content = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise LLMUnavailable("Niepoprawna odpowiedź Gemini") from exc
        if not content:
            raise LLMUnavailable("Pusta odpowiedź Gemini")
        usage = data.get("usageMetadata") or {}
        return LLMResponse(
            content=content,
            model=data.get("modelVersion") or self.model,
            input_tokens=_int_or_none(usage.get("promptTokenCount")),
            output_tokens=_int_or_none(usage.get("candidatesTokenCount")),
        )


# Keywords Anthropic structured outputs reject (numeric/string/array constraints).
_ANTHROPIC_DROP_KEYS = {
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minLength",
    "maxLength",
    "pattern",
    "maxItems",
    "uniqueItems",
}


def anthropic_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Adapt a JSON Schema (e.g. from Pydantic) to Anthropic structured outputs.

    Every object gets additionalProperties=false (required by the API) and
    unsupported constraints are dropped; the workflow validates the output anyway.
    """

    def clean(node: Any, depth: int = 0) -> Any:
        if depth > 32:
            raise ValueError("Schema too deep")
        if isinstance(node, list):
            return [clean(n, depth + 1) for n in node]
        if not isinstance(node, dict):
            return node
        out: dict[str, Any] = {}
        for key, value in node.items():
            if key in _ANTHROPIC_DROP_KEYS:
                continue
            if key == "minItems" and value not in (0, 1):
                continue
            if key in ("properties", "$defs", "definitions") and isinstance(value, dict):
                out[key] = {name: clean(sub, depth + 1) for name, sub in value.items()}
            else:
                out[key] = clean(value, depth + 1)
        if out.get("type") == "object" or "properties" in out:
            out["additionalProperties"] = False
        return out

    return clean(schema)


class AnthropicClient:
    """Anthropic Messages API (Claude), raw HTTP without the SDK."""

    provider: ClassVar[LLMProvider] = "anthropic"
    API_VERSION = "2026-10-21"
    MAX_TOKENS = 16000
    # Models that accept server-side refusal fallbacks (beta); others get none.
    _FALLBACK_MODELS = {"claude-sonnet-5-5", "claude-opus-5-5", "claude-opus-5", "claude-fable-5-1"}
    _FALLBACK_BETA = "server-side-fallback-2026-07-01"

    def __init__(self, api_key: str, model: str, base_url: str, timeout_s: float):
        self._api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def __repr__(self) -> str:
        return f"AnthropicClient(model={self.model!r}, base_url={self.base_url!r})"

    def status(self) -> LLMStatus:
        if not self._api_key:
            return LLMStatus(False, self.model)
        ok = _probe_status(
            "anthropic",
            f"{self.base_url}/v1/models/{self.model}",
            {"x-api-key": self._api_key, "anthropic-version": self.API_VERSION},
            self._api_key,
        )
        return LLMStatus(ok, self.model)

    def complete(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        response_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        if not self._api_key:
            raise LLMUnavailable("Brak klucza API Anthropic")
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.MAX_TOKENS,
            "system": system,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if response_schema is not None:
            body["output_config"] = {
                "format": {"type": "json_schema", "schema": anthropic_schema(response_schema)}
            }
        headers = {"x-api-key": self._api_key, "anthropic-version": self.API_VERSION}
        if self.model in self._FALLBACK_MODELS:
            body["fallbacks"] = "default"
            headers["anthropic-beta"] = self._FALLBACK_BETA
        data = _post_json(
            f"{self.base_url}/v1/messages",
            body=body,
            headers=headers,
            timeout_s=self.timeout_s,
            provider="Anthropic",
        )
        if data.get("stop_reason") == "refusal":
            raise LLMUnavailable("Anthropic odmówił odpowiedzi")
        if data.get("stop_reason") == "max_tokens":
            raise LLMUnavailable("Anthropic: odpowiedź ucięta (max_tokens)")
        try:
            blocks = data["content"]
            content = "".join(b["text"] for b in blocks if b.get("type") == "text")
        except (KeyError, TypeError, AttributeError) as exc:
            raise LLMUnavailable("Niepoprawna odpowiedź Anthropic") from exc
        if not content:
            raise LLMUnavailable("Pusta odpowiedź Anthropic")
        usage = data.get("usage") or {}
        return LLMResponse(
            content=content,
            model=data.get("model") or self.model,
            input_tokens=_int_or_none(usage.get("input_tokens")),
            output_tokens=_int_or_none(usage.get("output_tokens")),
        )


def provider_name(client: LLMClient | None) -> LLMProvider | Literal["none"]:
    """Provider identifier of a client (``none`` when no client is configured).

    Clients without a ``provider`` attribute (test fakes) are reported as ollama.
    """
    if client is None:
        return "none"
    return getattr(client, "provider", "ollama")


def get_llm_client() -> LLMClient | None:
    settings = get_settings()
    match settings.llm_provider:
        case "none":
            return None
        case "openai":
            return OpenAIClient(
                settings.openai_api_key,
                settings.openai_model,
                settings.openai_base_url,
                settings.llm_timeout_s,
            )
        case "gemini":
            return GeminiClient(
                settings.gemini_api_key, settings.gemini_model, settings.llm_timeout_s
            )
        case "anthropic":
            return AnthropicClient(
                settings.anthropic_api_key,
                settings.anthropic_model,
                settings.anthropic_base_url,
                settings.llm_timeout_s,
            )
        case "ollama":
            return OllamaClient(settings.ollama_url, settings.ollama_model, settings.llm_timeout_s)
