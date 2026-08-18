"""Sistema de agentes: coordinador + agentes especializados (suelo,
diseñador, revisor), agnóstico de proveedor de LLM (Anthropic u
OpenAI). Los agentes NUNCA calculan directamente -- todo cálculo pasa
por src/engine vía las tools definidas en tools.py. El coordinador
puede generar automáticamente la memoria de cálculo en Word al
finalizar (ver report_integration.py)."""

from .base_agent import Agent, AgentResult
from .session import DesignSession
from .coordinator import run_design_pipeline
from .report_integration import build_report_from_session, extract_final_design_check
from .soil_agent import create_soil_agent
from .designer_agent import create_designer_agent
from .reviewer_agent import create_reviewer_agent
from .providers import LLMProvider, AnthropicProvider, OpenAIProvider
from ..reporting import ProjectInfo

__all__ = [
    "Agent",
    "AgentResult",
    "DesignSession",
    "run_design_pipeline",
    "build_report_from_session",
    "extract_final_design_check",
    "create_soil_agent",
    "create_designer_agent",
    "create_reviewer_agent",
    "LLMProvider",
    "AnthropicProvider",
    "OpenAIProvider",
    "ProjectInfo",
]
