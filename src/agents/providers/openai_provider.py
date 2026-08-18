"""
Adaptador para la API de OpenAI (Chat Completions con tool/function
calling).

Nota de transparencia: a diferencia del adaptador de Anthropic (que
verifiqué contra la documentación oficial al escribir este código), el
formato de OpenAI usado acá se basa en el patrón estable y ampliamente
documentado de "tools" + "tool_calls" de la Chat Completions API. Si
al usar este adaptador ves errores de formato, revisá primero la
documentación vigente de OpenAI (platform.openai.com/docs) -- las APIs
de terceros pueden cambiar sin que este repo se entere.
"""

import json
import os
from typing import List, Dict, Any

from openai import OpenAI

from .base import LLMProvider, ProviderResponse, ToolCall


class OpenAIProvider(LLMProvider):
    def __init__(self, model: str, api_key: str = None):
        """
        model: no se fija un default -- pasá el modelo actual que quieras
        usar (ej. "gpt-4o", o el que esté vigente al momento de usar esto).
        También podés setearlo vía variable de entorno OPENAI_MODEL.
        """
        self.client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
        self.model = model or os.environ.get("OPENAI_MODEL")
        if not self.model:
            raise ValueError(
                "Especificá un modelo de OpenAI (parámetro 'model' o variable "
                "de entorno OPENAI_MODEL) -- este repo no fija un default para "
                "evitar apuntar a un modelo desactualizado."
            )

    def chat(
        self, system: str, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]
    ) -> ProviderResponse:
        full_messages = [{"role": "system", "content": system}] + messages

        kwargs: Dict[str, Any] = dict(model=self.model, messages=full_messages)
        if tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["parameters"],
                    },
                }
                for t in tools
            ]

        response = self.client.chat.completions.create(**kwargs)
        message = response.choices[0].message

        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        input=json.loads(tc.function.arguments),
                    )
                )

        return ProviderResponse(
            text=message.content,
            tool_calls=tool_calls,
            raw=message,
            stop_reason=response.choices[0].finish_reason,
        )

    def format_assistant_message(self, response: ProviderResponse) -> Dict[str, Any]:
        msg: Dict[str, Any] = {"role": "assistant", "content": response.raw.content}
        if response.raw.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in response.raw.tool_calls
            ]
        return msg

    def format_tool_result(self, tool_call_id: str, content: str) -> Dict[str, Any]:
        return {"role": "tool", "tool_call_id": tool_call_id, "content": content}
