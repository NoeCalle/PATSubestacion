"""
Agente base: encapsula el loop de tool-calling contra un LLMProvider.

No implementa lógica de negocio -- eso vive en las subclases/factories
(soil_agent, designer_agent, reviewer_agent) vía su system_prompt y el
subconjunto de tools que se les asigna. Esta clase es intencionalmente
"tonta": manda mensajes, ejecuta tools, repite hasta que el modelo
responde con texto en vez de una tool call, o hasta max_turns.
"""

import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from .providers.base import LLMProvider
from .tools import get_tool_schemas, get_tool_dispatch


@dataclass
class AgentResult:
    final_text: str
    messages: List[Dict[str, Any]] = field(default_factory=list)  # historial completo (auditoría)
    tool_calls_made: List[Dict[str, Any]] = field(default_factory=list)  # trazabilidad
    hit_max_turns: bool = False


class Agent:
    def __init__(
        self,
        name: str,
        system_prompt: str,
        provider: LLMProvider,
        tool_names: Optional[List[str]] = None,
        max_turns: int = 10,
    ):
        self.name = name
        self.system_prompt = system_prompt
        self.provider = provider
        self.tool_schemas = get_tool_schemas(tool_names)
        self.tool_dispatch = get_tool_dispatch(tool_names)
        self.max_turns = max_turns

    def run(self, user_message: str, extra_context: Optional[str] = None) -> AgentResult:
        content = user_message if not extra_context else f"{extra_context}\n\n{user_message}"
        messages: List[Dict[str, Any]] = [{"role": "user", "content": content}]

        tool_calls_made: List[Dict[str, Any]] = []

        for _ in range(self.max_turns):
            response = self.provider.chat(self.system_prompt, messages, self.tool_schemas)

            if not response.tool_calls:
                return AgentResult(
                    final_text=response.text or "",
                    messages=messages,
                    tool_calls_made=tool_calls_made,
                )

            messages.append(self.provider.format_assistant_message(response))

            for tool_call in response.tool_calls:
                func = self.tool_dispatch.get(tool_call.name)
                if func is None:
                    result_content = json.dumps({"error": f"Tool desconocida: {tool_call.name}"})
                else:
                    try:
                        result = func(**tool_call.input)
                        result_content = json.dumps(result, default=str)
                    except Exception as e:
                        result_content = json.dumps({"error": str(e)})

                tool_calls_made.append(
                    {"tool": tool_call.name, "input": tool_call.input, "result": result_content}
                )
                messages.append(self.provider.format_tool_result(tool_call.id, result_content))

        return AgentResult(
            final_text="[Se alcanzó el máximo de turnos sin una respuesta final]",
            messages=messages,
            tool_calls_made=tool_calls_made,
            hit_max_turns=True,
        )
