"""
Puente entre el coordinador de agentes y el módulo de reportes.

Extrae el último resultado de verificación de diseño REALMENTE
EJECUTADO (una tool call real contra el motor de cálculo -- nunca
texto generado por el LLM) desde una DesignSession, y genera la
memoria de cálculo en Word a partir de eso.

Prioridad de extracción: el resultado del REVISOR (auditoría
independiente) sobre el del diseñador, porque es la verificación
recalculada de forma independiente por un agente distinto -- más
confiable para el informe final. Si el revisor no llegó a llamar la
tool (ej. el LLM no cumplió lo indicado en su system prompt), se usa
el último resultado del diseñador como respaldo.
"""

from typing import Optional, Tuple, Union

from .session import DesignSession
from .base_agent import AgentResult
from .tools import DESIGN_CHECK_TOOL_NAMES, reconstruct_design_check_call
from ..reporting import build_calculation_report, ProjectInfo
from ..engine.models import SoilModel, TwoLayerSoilModel, GridGeometry, FaultData, DesignResult


def _last_design_check_call(agent_result: Optional[AgentResult]) -> Optional[dict]:
    """Última tool call de verificación de diseño hecha por un
    AgentResult (recorriendo de atrás para adelante), o None si no
    hizo ninguna."""
    if agent_result is None:
        return None
    for call in reversed(agent_result.tool_calls_made):
        if call["tool"] in DESIGN_CHECK_TOOL_NAMES:
            return call
    return None


ExtractedDesignCheck = Tuple[
    Union[SoilModel, TwoLayerSoilModel], GridGeometry, FaultData, DesignResult, str
]


def extract_final_design_check(session: DesignSession) -> Optional[ExtractedDesignCheck]:
    """
    Busca la tool call de verificación más confiable disponible en la
    sesión: primero la del revisor (última iteración), después la del
    diseñador (última iteración) como respaldo.

    Devuelve (soil, grid, fault, DesignResult, source) donde source es
    "reviewer" o "designer" -- para dejar trazabilidad explícita de
    dónde salió el número que se está reportando. Devuelve None si no
    se encontró ninguna tool call de verificación en toda la sesión
    (ej. si el LLM nunca llamó a la herramienta de cálculo).
    """
    reviewer_result = session.reviewer_results[-1] if session.reviewer_results else None
    call = _last_design_check_call(reviewer_result)
    source = "reviewer"

    if call is None:
        designer_result = session.designer_results[-1] if session.designer_results else None
        call = _last_design_check_call(designer_result)
        source = "designer"

    if call is None:
        return None

    soil, grid, fault, result = reconstruct_design_check_call(
        call["tool"], call["input"], call["result"]
    )
    return soil, grid, fault, result, source


def build_report_from_session(
    session: DesignSession,
    output_path: str,
    project_info: Optional[ProjectInfo] = None,
    visualization_reference: Optional[str] = None,
) -> Optional[str]:
    """
    Genera la memoria de cálculo en Word a partir de una DesignSession
    ya corrida (ver coordinator.run_design_pipeline).

    Devuelve la ruta del archivo generado, o None si no se pudo
    extraer ningún resultado de verificación real de la sesión -- en
    ese caso no hay nada confiable para reportar, y generar un
    documento igual sería peligroso (parecería un informe válido sin
    serlo). Quien llama a esta función debe chequear el valor de
    retorno y avisar al usuario si es None.
    """
    extracted = extract_final_design_check(session)
    if extracted is None:
        return None

    soil, grid, fault, result, source = extracted

    # Trazabilidad explícita: de qué agente y qué iteración salió el
    # número que se está reportando.
    result.notes = list(result.notes) + [
        f"Resultado extraído de la verificación del agente '{source}' "
        f"(iteración {session.iterations} del pipeline, veredicto final "
        f"del pipeline: {session.final_verdict})."
    ]

    return build_calculation_report(
        soil, grid, fault, result, output_path,
        project_info=project_info,
        visualization_reference=visualization_reference,
    )
