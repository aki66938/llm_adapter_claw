"""Pydantic models for API requests and responses."""

from typing import Any, Literal
from pydantic import BaseModel, Field


class Message(BaseModel):
    """Chat message model."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None


class ChatRequest(BaseModel):
    """OpenAI-compatible chat completion request."""

    model: str
    messages: list[Message]
    temperature: float = 0.7
    max_tokens: int | None = None
    stream: bool = False
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None


class Choice(BaseModel):
    """Chat completion choice."""

    index: int = 0
    message: Message
    finish_reason: str | None = "stop"


class ChatResponse(BaseModel):
    """OpenAI-compatible chat completion response."""

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[Choice]
    usage: dict[str, int] | None = None


class StreamChoice(BaseModel):
    """Streaming chat completion choice."""

    index: int = 0
    delta: dict[str, Any]
    finish_reason: str | None = None


class StreamResponse(BaseModel):
    """OpenAI-compatible streaming response chunk."""

    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: list[StreamChoice]
