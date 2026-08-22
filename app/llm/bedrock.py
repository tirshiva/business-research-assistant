"""AWS Bedrock LLM provider.

Configured via settings. Requires ``boto3`` and valid AWS credentials at runtime.
"""

from __future__ import annotations

import json
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.exceptions import LLMConfigurationError, LLMStructuredOutputError
from app.core.logging import get_logger
from app.llm.base import LLMProvider

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class BedrockLLMProvider(LLMProvider):
    """Bedrock Converse-based structured output provider."""

    name = "bedrock"

    def __init__(
        self,
        *,
        model_id: str,
        region: str,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> None:
        if not model_id.strip():
            raise LLMConfigurationError(
                "BEDROCK_MODEL_ID is required for the Bedrock provider",
                provider=self.name,
            )
        if not region.strip():
            raise LLMConfigurationError(
                "BEDROCK_REGION is required for the Bedrock provider",
                provider=self.name,
            )
        self._model_id = model_id
        self._region = region
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import boto3
        except ImportError as exc:
            raise LLMConfigurationError(
                "boto3 is required for AWS Bedrock; install boto3 to enable it",
                provider=self.name,
            ) from exc
        self._client = boto3.client("bedrock-runtime", region_name=self._region)
        return self._client

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T:
        schema = response_model.model_json_schema()
        tool_name = response_model.__name__
        client = self._get_client()

        request: dict[str, Any] = {
            "modelId": self._model_id,
            "system": [{"text": system_prompt}],
            "messages": [{"role": "user", "content": [{"text": user_prompt}]}],
            "inferenceConfig": {
                "maxTokens": self._max_tokens,
                "temperature": self._temperature,
            },
            "toolConfig": {
                "tools": [
                    {
                        "toolSpec": {
                            "name": tool_name,
                            "description": f"Return a valid {tool_name} object",
                            "inputSchema": {"json": schema},
                        }
                    }
                ],
                "toolChoice": {"tool": {"name": tool_name}},
            },
        }

        logger.info("Calling Bedrock model=%s for %s", self._model_id, tool_name)
        try:
            # boto3 is sync; run in thread to avoid blocking the event loop.
            import asyncio

            response = await asyncio.to_thread(client.converse, **request)
        except LLMConfigurationError:
            raise
        except Exception as exc:  # noqa: BLE001 - map all SDK failures
            raise LLMStructuredOutputError(
                "Bedrock converse call failed",
                provider=self.name,
                details=str(exc),
            ) from exc

        payload = self._extract_tool_payload(response, tool_name=tool_name)
        try:
            return response_model.model_validate(payload)
        except ValidationError as exc:
            raise LLMStructuredOutputError(
                "Bedrock returned a payload that failed schema validation",
                provider=self.name,
                details=str(exc),
            ) from exc

    @staticmethod
    def _extract_tool_payload(response: dict[str, Any], *, tool_name: str) -> Any:
        contents = (
            response.get("output", {}).get("message", {}).get("content", []) or []
        )
        for block in contents:
            tool_use = block.get("toolUse")
            if not tool_use:
                continue
            if tool_use.get("name") != tool_name:
                continue
            tool_input = tool_use.get("input")
            if isinstance(tool_input, dict):
                return tool_input
            if isinstance(tool_input, str):
                return json.loads(tool_input)

        raise LLMStructuredOutputError(
            "Bedrock response did not include structured tool output",
            provider="bedrock",
            details=str(response),
        )
