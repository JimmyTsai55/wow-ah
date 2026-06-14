import json

from openai import OpenAI, OpenAIError

from wow_ah.exceptions.base import APIError
from wow_ah.exceptions.messages import AgentErrorMessages
from wow_ah.schemas.agents import LLMResponse, ToolCall


class OpenAIChatAdapter:
    """Wraps the OpenAI Chat Completions API behind LLMProtocol."""

    def __init__(
        self,
        api_key: str = "",
        base_url: str | None = None,
        client=None,
    ) -> None:
        if client is not None:
            self._client = client
        else:
            self._client = OpenAI(api_key=api_key, base_url=base_url or None)

    def complete(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None,
    ) -> LLMResponse:
        kwargs = {"model": model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        try:
            completion = self._client.chat.completions.create(**kwargs)
        except OpenAIError as e:
            raise APIError(
                AgentErrorMessages.OPENAI_ERROR.format(error=str(e))
            ) from e

        choice = completion.choices[0]
        raw_calls = choice.message.tool_calls or []
        tool_calls = [
            ToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=json.loads(tc.function.arguments or "{}"),
            )
            for tc in raw_calls
        ]
        return LLMResponse(
            content=choice.message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason,
        )
