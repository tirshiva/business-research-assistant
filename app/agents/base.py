"""Base research agent contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel

from app.agents.schemas import AgentResult
from app.core.logging import get_logger

logger = get_logger(__name__)


class ResearchAgent(ABC):
    """Independent research component with typed I/O and declared tools."""

    name: ClassVar[str]
    allowed_tools: ClassVar[list[str]]

    @abstractmethod
    async def run(self, payload: BaseModel) -> AgentResult:
        """Execute the agent and return a validated :class:`AgentResult`."""

    def _log_start(self, payload: BaseModel) -> None:
        logger.info("Agent %s starting tools=%s", self.name, self.allowed_tools)
        logger.debug("Agent %s input=%s", self.name, payload.model_dump(mode="json"))
