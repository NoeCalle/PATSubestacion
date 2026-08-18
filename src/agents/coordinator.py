"""
Coordinador del pipeline de diseño: soil_agent -> designer_agent ->
reviewer_agent, con loop de retroalimentación si el revisor rechaza.
Opcionalmente genera la memoria de cálculo en Word automáticamente al
finalizar.

Es un orquestador de Python plano (NO un agente LLM) -- la secuencia y
los reintentos son lógica determinística y auditable; los LLMs se usan
solo donde hace falta razonamiento (dentro de cada agente individual).
Esto es intencional: la coordinación del flujo es exactamente el tipo
de decisión que no debería depender de que un modelo "razone bien"
sobre cuándo reintentar -- es una regla de negocio simple y fija.
"""

from typing import Optional, Callable, Dict, Any

from .session import DesignSession
from .soil_agent import create_soil_agent
from .designer_agent import create_designer_agent
from .reviewer_agent import create_reviewer_agent
from .report_integration import build_report_from_session
from .providers.base import LLMProvider
from ..reporting import ProjectInfo

EventCallback = Callable[[Dict[str, Any]], None]


def run_design_pipeline(
    provider: LLMProvider,
    soil_data_description: str,
    project_requirements: str,
    max_review_iterations: int = 3,
    report_output_path: Optional[str] = None,
    project_info: Optional[ProjectInfo] = None,
    visualization_reference: Optional[str] = None,
    on_event: Optional[EventCallback] = None,
    include_3d_views: bool = True,
    static_views_dir: Optional[str] = None,
) -> DesignSession:
    """
    Ejecuta el flujo completo: interpretación de suelo -> diseño ->
    revisión -> (si el revisor rechaza) vuelta al diseñador con el
    feedback, hasta max_review_iterations.

    soil_data_description: descripción en lenguaje natural de los datos
      de suelo disponibles (mediciones de Wenner, o resistividad ya
      interpretada).
    project_requirements: descripción del proyecto (corriente de falla,
      tiempo de despeje, dimensiones disponibles del terreno, etc.)
    report_output_path: si se especifica, al finalizar el pipeline
      (apruebe o no) se genera automáticamente la memoria de cálculo
      en Word a partir de la última verificación REAL ejecutada (no
      de texto del LLM) -- ver report_integration.py. La ruta queda
      en session.report_path (None si no se pudo generar, por ejemplo
      si ningún agente llegó a llamar la herramienta de cálculo).
    project_info / visualization_reference: se pasan directo al
      generador de reportes si report_output_path está definido.
    include_3d_views: si es True (default) y se generó el informe,
      también calcula y embebe las vistas 3D estáticas (potencial,
      contacto, paso) -- automático, sin pasos manuales. Si el
      renderizado falla, el informe se genera igual sin esa sección
      (ver report_integration.py).
    static_views_dir: carpeta para los PNG de las vistas 3D. Si no se
      especifica, usa una subcarpeta junto al informe.
    on_event: callback opcional que se llama con eventos de progreso
      estructurados ({"type": "soil_started", ...}, {"type":
      "designer_done", "iteration": 1, "text": ...}, etc.) -- usado
      por la interfaz web (src/webapp) para mostrar avance en vivo.
      No afecta la lógica del pipeline si no se pasa.

    ⚠️ El resultado de esta función (incluso si final_verdict ==
    "APROBADO", e incluso si se generó el .docx) es un insumo para el
    ingeniero que revisa y firma el informe -- no es una aprobación
    normativa final por sí sola.
    """

    def emit(event_type: str, **kwargs) -> None:
        if on_event:
            on_event({"type": event_type, **kwargs})

    session = DesignSession()

    emit("soil_started")
    soil_agent = create_soil_agent(provider)
    session.soil_result = soil_agent.run(soil_data_description)
    emit("soil_done", text=session.soil_result.final_text)

    designer_agent = create_designer_agent(provider)
    reviewer_agent = create_reviewer_agent(provider)

    designer_context = (
        f"Modelo de suelo determinado por el agente de suelo:\n"
        f"{session.soil_result.final_text}\n\n"
        f"Requisitos del proyecto:\n{project_requirements}"
    )

    for iteration in range(max_review_iterations):
        session.iterations = iteration + 1

        emit("designer_started", iteration=session.iterations)
        designer_result = designer_agent.run(
            "Proponé y verificá una geometría de malla que cumpla la norma "
            "para este proyecto.",
            extra_context=designer_context,
        )
        session.designer_results.append(designer_result)
        emit("designer_done", iteration=session.iterations, text=designer_result.final_text)

        emit("reviewer_started", iteration=session.iterations)
        reviewer_result = reviewer_agent.run(
            "Auditá de forma independiente la siguiente propuesta de diseño.",
            extra_context=f"Propuesta del diseñador:\n{designer_result.final_text}",
        )
        session.reviewer_results.append(reviewer_result)
        emit("reviewer_done", iteration=session.iterations, text=reviewer_result.final_text)

        if reviewer_result.final_text.strip().upper().startswith("APROBADO"):
            session.final_verdict = "APROBADO"
            emit("approved", iteration=session.iterations)
            _maybe_generate_report(
                session, report_output_path, project_info, visualization_reference,
                include_3d_views, static_views_dir,
            )
            emit("report_ready" if session.report_path else "report_unavailable", path=session.report_path)
            return session

        # Realimentación explícita al diseñador para la siguiente iteración
        designer_context = (
            f"{designer_context}\n\n"
            f"--- El revisor RECHAZÓ tu propuesta anterior ---\n"
            f"{reviewer_result.final_text}\n\n"
            f"Ajustá la geometría para resolver estas observaciones "
            f"específicas antes de volver a verificar."
        )

    session.final_verdict = "NO_RESUELTO"
    emit("not_resolved")
    _maybe_generate_report(
        session, report_output_path, project_info, visualization_reference,
        include_3d_views, static_views_dir,
    )
    emit("report_ready" if session.report_path else "report_unavailable", path=session.report_path)
    return session


def _maybe_generate_report(
    session: DesignSession,
    report_output_path: Optional[str],
    project_info: Optional[ProjectInfo],
    visualization_reference: Optional[str],
    include_3d_views: bool,
    static_views_dir: Optional[str],
) -> None:
    if not report_output_path:
        return
    session.report_path = build_report_from_session(
        session, report_output_path,
        project_info=project_info,
        visualization_reference=visualization_reference,
        include_3d_views=include_3d_views,
        static_views_dir=static_views_dir,
    )
