"""LLM provider abstractions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMProvider(ABC):
    """Provider-agnostic interface for structured LLM generation.

    Planner and future nodes should depend on this abstraction rather than a
    concrete vendor SDK (Bedrock, local OpenAI-compatible server, etc.).
    """

    name: str

    @abstractmethod
    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T:
        """Generate a response validated against ``response_model``.

        Implementations must return a Pydantic model instance and must not
        leave callers parsing free-form prose when structured output is
        available.
        """
