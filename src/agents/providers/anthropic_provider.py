"""
Adaptador para la API de Anthropic (Claude) -- POST /v1/messages con
tool use. Formato verificado contra la documentación oficial
(docs.claude.com / platform.claude.com) al momento de escribir este
módulo, no reconstruido de memoria.
"""

import os
from typing import List, Dict, Any

import anthropic

from .base import LLMProvider, ProviderResponse, ToolCall


class AnthropicProvider(LLMProvider):
    def __init__(
        self,
        model: str = "claude-sonnet-5",
        api_key: str = None,
        max_tokens: int = 4096,
    ):
        self.client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
        )
        self.model = model
        self.max_tokens = max_tokens

    def chat(
        self, system: str, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]
    ) -> ProviderResponse:
        kwargs: Dict[str, Any] = dict(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=messages,
        )
        if tools:
            kwargs["tools"] = [
                {
                    "name": t["name"],
                    "description": t["description"],
                    "input_schema": t["parameters"],
                }
                for t in tools
            ]

        response = self.client.messages.create(**kwargs)

        text_blocks = [b.text for b in response.content if b.type == "text"]
        tool_calls = [
            ToolCall(id=b.id, name=b.name, input=b.input)
            for b in response.content
            if b.type == "tool_use"
        ]

        return ProviderResponse(
            text="\n".join(text_blocks) if text_blocks else None,
            tool_calls=tool_calls,
            raw=response,
            stop_reason=response.stop_reason,
        )

    def format_assistant_message(self, response: ProviderResponse) -> Dict[str, Any]:
        return {"role": "assistant", "content": response.raw.content}

    def format_tool_result(self, tool_call_id: str, content: str) -> Dict[str, Any]:
        return {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": tool_call_id, "content": content}
            ],
        }
