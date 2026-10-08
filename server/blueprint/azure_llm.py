"""Thin Azure OpenAI wrapper used by the agents for structured (JSON) output.

Uses the Azure OpenAI v1 API surface (``<endpoint>/openai/v1/``) through the
standard ``openai`` client, which is what Pipecat's own ``AzureLLMService`` uses.

If ``AZURE_OPENAI_ENDPOINT`` / ``AZURE_OPENAI_API_KEY`` are not set, the wrapper
runs in **mock mode**: agents fall back to their deterministic heuristics so the
whole app can be demoed end to end without any keys.
"""

from __future__ import annotations

import json
import os
from typing import TypeVar

from loguru import logger
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class AgentLLM:
    def __init__(self) -> None:
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
        api_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
        self.model = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1")
        self.mock = not (endpoint and api_key) or os.getenv("BLUEPRINT_MOCK") == "1"
        self._client: AsyncOpenAI | None = None
        if not self.mock:
            base = endpoint.rstrip("/")
            if not base.endswith("/openai/v1"):
                base += "/openai/v1"
            self._client = AsyncOpenAI(base_url=base + "/", api_key=api_key)
        logger.info(f"AgentLLM ready (mock={self.mock}, deployment={self.model})")

    async def structured(self, system: str, user: str, schema: type[T]) -> tuple[T, int]:
        """Ask the model for JSON matching ``schema``. Returns (object, tokens used)."""
        if self._client is None:
            raise RuntimeError("AgentLLM is in mock mode")

        schema_hint = json.dumps(schema.model_json_schema())
        messages = [
            {
                "role": "system",
                "content": f"{system}\n\nReply with a single JSON object that validates "
                f"against this JSON schema. No prose.\n{schema_hint}",
            },
            {"role": "user", "content": user},
        ]
        tokens = 0
        last_error: Exception | None = None
        for _ in range(2):  # one retry with the validation error fed back
            resp = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore[arg-type]
                # No temperature: reasoning models only accept the default.
                response_format={"type": "json_object"},
            )
            tokens += resp.usage.total_tokens if resp.usage else 0
            content = resp.choices[0].message.content or "{}"
            try:
                return schema.model_validate_json(content), tokens
            except ValidationError as e:
                last_error = e
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": f"That JSON was invalid: {e}. Fix it."})
        raise RuntimeError(f"Model did not return valid {schema.__name__}: {last_error}")
