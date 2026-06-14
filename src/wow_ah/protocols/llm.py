from typing import Protocol

from wow_ah.schemas.agents import LLMResponse


class LLMProtocol(Protocol):
    """Abstract interface for a chat-completion LLM call."""

    def complete(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None,
    ) -> LLMResponse:
        """Run one completion. `tools` is OpenAI-format function schemas or None."""
        ...
