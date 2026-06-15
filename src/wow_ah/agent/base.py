import json
from dataclasses import dataclass
from typing import Any, Callable

from wow_ah.exceptions.base import APIError
from wow_ah.exceptions.messages import AgentErrorMessages
from wow_ah.protocols.llm import LLMProtocol

MAX_TOOL_ROUNDS = 8


@dataclass
class Tool:
    """A callable the model may invoke. `parameters` is a JSON schema."""
    name: str
    description: str
    parameters: dict[str, Any]
    func: Callable[..., str]


class Agent:
    """Runs an OpenAI function-calling loop with a fixed tool set."""

    def __init__(
        self,
        name: str,
        model: str,
        system_prompt: str,
        tools: list[Tool],
        llm: LLMProtocol,
    ) -> None:
        self.name = name
        self.model = model
        self._system_prompt = system_prompt
        self._tools = {t.name: t for t in tools}
        self._llm = llm

    def _tool_schemas(self) -> list[dict] | None:
        if not self._tools:
            return None
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
        ]

    def run(self, user_input: str) -> str:
        """Run the function-calling loop until the model gives a final answer.

        Exceptions raised inside a tool (e.g. DataError) propagate unchanged so
        the CLI's AppException handler can surface their message. Unknown tools
        and exceeding MAX_TOOL_ROUNDS raise APIError.
        """
        messages: list[dict] = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": user_input},
        ]
        schemas = self._tool_schemas()

        for _ in range(MAX_TOOL_ROUNDS):
            resp = self._llm.complete(self.model, messages, schemas)
            if not resp.tool_calls:
                return resp.content or ""

            messages.append(
                {
                    "role": "assistant",
                    "content": resp.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                            },
                        }
                        for tc in resp.tool_calls
                    ],
                }
            )

            for tc in resp.tool_calls:
                tool = self._tools.get(tc.name)
                if tool is None:
                    raise APIError(
                        AgentErrorMessages.UNKNOWN_TOOL.format(agent=self.name, tool=tc.name)
                    )
                result = tool.func(**tc.arguments)
                messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": result}
                )

        raise APIError(
            AgentErrorMessages.MAX_ROUNDS_EXCEEDED.format(agent=self.name, limit=MAX_TOOL_ROUNDS)
        )
