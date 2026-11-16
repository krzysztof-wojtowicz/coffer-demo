from typing import Any

from coffer.agent.llm import LLMMessage, LLMResponse, LLMStatus


class FakeLLM:
    """Scripted client: each `complete` pops the next response (or raises it)."""

    def __init__(
        self,
        responses: list[str | Exception],
        available: bool = True,
        *,
        provider: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        model: str = "fake",
    ):
        self.available = available
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self._provider = provider
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self._model = model

    def status(self) -> LLMStatus:
        return LLMStatus(self.available, self._model)

    def complete(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        response_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        self.calls.append(
            {"system": system, "messages": list(messages), "response_schema": response_schema}
        )
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return LLMResponse(
            content=item,
            model=self._model,
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
            provider=self._provider,
        )
