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

Por default, también genera y embebe las vistas 3D estáticas
(potencial, tensión de contacto, tensión de paso) en el informe -- ver
_generate_static_views(). Si ese paso falla por cualquier motivo, NO
tira abajo la generación del informe: lo genera igual sin las vistas,
dejando una nota explicando qué pasó (mismo principio que el resto del
repo: nunca ocultar una limitación para que el resultado "se vea
mejor").
"""

import os
from typing import Optional, Tuple, Union

from .session import DesignSession
from .base_agent import AgentResult
from .tools import DESIGN_CHECK_TOOL_NAMES, reconstruct_design_check_call
from ..reporting import build_calculation_report, ProjectInfo
from ..engine.models import SoilModel, TwoLayerSoilModel, GridGeometry, FaultData, DesignResult
from ..engine.potential_profile import compute_surface_potential, touch_voltage_field, step_voltage_field
from ..engine.soil_two_layer import effective_design_resistivity
from ..visual.static_plot3d import render_static_views


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


def _generate_static_views(
    soil: Union[SoilModel, TwoLayerSoilModel],
    grid: GridGeometry,
    result: DesignResult,
    report_output_path: str,
    static_views_dir: Optional[str],
) -> dict:
    """
    Calcula el perfil de potencial y renderiza las 3 vistas estáticas
    (potencial, contacto, paso) para embeber en el informe.

    Si el suelo es de dos capas, lo convierte primero a una
    resistividad uniforme equivalente (misma aproximación que usa
    run_design_check_two_layer -- ver soil_two_layer.py) porque
    compute_surface_potential trabaja sobre suelo uniforme.
    """
    if isinstance(soil, TwoLayerSoilModel):
        rho_eff, _note = effective_design_resistivity(soil, grid)
        uniform_soil = SoilModel(rho=rho_eff, rho_s=soil.rho_s, h_s=soil.h_s)
    else:
        uniform_soil = soil

    field = compute_surface_potential(uniform_soil, grid, IG=result.IG, margin=10.0, sample_resolution=2.0)
    touch_field = touch_voltage_field(field.V, gpr_reference=result.GPR)
    step_field = step_voltage_field(field.X, field.Y, field.V)

    views_dir = static_views_dir or os.path.join(
        os.path.dirname(report_output_path) or ".", "static_views"
    )
    return render_static_views(
        field, grid, output_dir=views_dir, touch_field=touch_field, step_field=step_field
    )


def build_report_from_session(
    session: DesignSession,
    output_path: str,
    project_info: Optional[ProjectInfo] = None,
    visualization_reference: Optional[str] = None,
    include_3d_views: bool = True,
    static_views_dir: Optional[str] = None,
) -> Optional[str]:
    """
    Genera la memoria de cálculo en Word a partir de una DesignSession
    ya corrida (ver coordinator.run_design_pipeline).

    include_3d_views: si es True (default), calcula el perfil de
      potencial y embebe las vistas 3D estáticas (potencial, contacto,
      paso) en el informe -- automático, sin que el agente ni el
      usuario tengan que pedirlo aparte. Si el renderizado falla por
      cualquier motivo, el informe se genera igual SIN las vistas, con
      una nota explicando el problema (nunca se pierde el informe
      completo por un fallo en esta parte opcional).
    static_views_dir: carpeta donde guardar los PNG generados. Si no
      se especifica, usa una subcarpeta "static_views" junto al
      informe.

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

    static_paths = None
    if include_3d_views:
        try:
            static_paths = _generate_static_views(soil, grid, result, output_path, static_views_dir)
        except Exception as e:
            result.notes = list(result.notes) + [
                f"No se pudieron generar las vistas 3D para el informe "
                f"({type(e).__name__}: {e}). El informe se generó igual, "
                f"solo sin esa sección."
            ]

    return build_calculation_report(
        soil, grid, fault, result, output_path,
        project_info=project_info,
        visualization_reference=visualization_reference,
        static_view_paths=static_paths,
    )
