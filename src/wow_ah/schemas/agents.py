from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """A single tool/function call requested by the model."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """Normalized response from one LLM completion call."""
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"


@dataclass
class FreshnessResult:
    """Outcome of the deterministic data-freshness gate."""
    is_fresh: bool
    last_fetch: str | None
    age_hours: float | None
    message: str
