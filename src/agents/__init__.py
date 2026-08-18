"""Sistema de agentes: coordinador + agentes especializados (suelo,
diseñador, revisor), agnóstico de proveedor de LLM (Anthropic u
OpenAI). Los agentes NUNCA calculan directamente -- todo cálculo pasa
por src/engine vía las tools definidas en tools.py."""

from .base_agent import Agent, AgentResult
from .coordinator import run_design_pipeline, DesignSession
from .soil_agent import create_soil_agent
from .designer_agent import create_designer_agent
from .reviewer_agent import create_reviewer_agent
from .providers import LLMProvider, AnthropicProvider, OpenAIProvider

__all__ = [
    "Agent",
    "AgentResult",
    "run_design_pipeline",
    "DesignSession",
    "create_soil_agent",
    "create_designer_agent",
    "create_reviewer_agent",
    "LLMProvider",
    "AnthropicProvider",
    "OpenAIProvider",
]
