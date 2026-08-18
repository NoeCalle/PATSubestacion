"""
Interfaz común para proveedores de LLM.

Todo el resto del sistema de agentes (base_agent.py, coordinator.py)
programa contra esta interfaz, no contra Anthropic u OpenAI
directamente -- así el repo es agnóstico de proveedor: cambiar de
Claude a ChatGPT es cuestión de instanciar un provider distinto, sin
tocar la lógica de los agentes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class ToolCall:
    id: str
    name: str
    input: Dict[str, Any]


@dataclass
class ProviderResponse:
    text: Optional[str]
    tool_calls: List[ToolCall] = field(default_factory=list)
    raw: Any = None  # respuesta cruda del SDK del proveedor (para reconstruir el historial)
    stop_reason: Optional[str] = None


class LLMProvider(ABC):
    """
    Cualquier proveedor debe implementar estos 3 métodos. El resto del
    sistema de agentes no conoce ningún detalle específico de Anthropic
    ni de OpenAI más allá de esta interfaz.
    """

    @abstractmethod
    def chat(
        self, system: str, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]
    ) -> ProviderResponse:
        """Envía la conversación al modelo y devuelve una respuesta normalizada."""
        ...

    @abstractmethod
    def format_assistant_message(self, response: ProviderResponse) -> Dict[str, Any]:
        """Da el mensaje 'assistant' (en el formato nativo del proveedor)
        que hay que agregar al historial antes de mandar los resultados
        de las tools."""
        ...

    @abstractmethod
    def format_tool_result(self, tool_call_id: str, content: str) -> Dict[str, Any]:
        """Da el mensaje que representa el resultado de una tool call,
        en el formato nativo del proveedor."""
        ...
