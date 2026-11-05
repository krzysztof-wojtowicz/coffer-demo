from typing import Any

from coffer.agent.llm import LLMMessage, LLMResponse, LLMStatus


class FakeLLM:
    def __init__(self, responses: list[str | Exception], available: bool = True):
        self.available = available
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def status(self) -> LLMStatus:
        return LLMStatus(self.available, "fake")

    def complete(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        response_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        self.calls.append(
            {"system": system, "messages": messages, "response_schema": response_schema}
        )
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return LLMResponse(content=item, model="fake", input_tokens=None, output_tokens=None)
