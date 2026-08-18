"""
Coordinador del pipeline de diseño: soil_agent -> designer_agent ->
reviewer_agent, con loop de retroalimentación si el revisor rechaza.

Es un orquestador de Python plano (NO un agente LLM) -- la secuencia y
los reintentos son lógica determinística y auditable; los LLMs se usan
solo donde hace falta razonamiento (dentro de cada agente individual).
Esto es intencional: la coordinación del flujo es exactamente el tipo
de decisión que no debería depender de que un modelo "razone bien"
sobre cuándo reintentar -- es una regla de negocio simple y fija.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from .base_agent import AgentResult
from .soil_agent import create_soil_agent
from .designer_agent import create_designer_agent
from .reviewer_agent import create_reviewer_agent
from .providers.base import LLMProvider


@dataclass
class DesignSession:
    soil_result: Optional[AgentResult] = None
    designer_results: List[AgentResult] = field(default_factory=list)
    reviewer_results: List[AgentResult] = field(default_factory=list)
    final_verdict: str = "NO_INICIADO"  # APROBADO | NO_RESUELTO | NO_INICIADO
    iterations: int = 0

    @property
    def final_design(self) -> Optional[str]:
        """Texto de la última propuesta del diseñador (la vigente al cierre)."""
        return self.designer_results[-1].final_text if self.designer_results else None

    @property
    def final_review(self) -> Optional[str]:
        return self.reviewer_results[-1].final_text if self.reviewer_results else None


def run_design_pipeline(
    provider: LLMProvider,
    soil_data_description: str,
    project_requirements: str,
    max_review_iterations: int = 3,
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

    ⚠️ El resultado de esta función (incluso si final_verdict ==
    "APROBADO") es un insumo para el ingeniero que revisa y firma el
    informe -- no es una aprobación normativa final por sí sola.
    """
    session = DesignSession()

    soil_agent = create_soil_agent(provider)
    session.soil_result = soil_agent.run(soil_data_description)

    designer_agent = create_designer_agent(provider)
    reviewer_agent = create_reviewer_agent(provider)

    designer_context = (
        f"Modelo de suelo determinado por el agente de suelo:\n"
        f"{session.soil_result.final_text}\n\n"
        f"Requisitos del proyecto:\n{project_requirements}"
    )

    for iteration in range(max_review_iterations):
        session.iterations = iteration + 1

        designer_result = designer_agent.run(
            "Proponé y verificá una geometría de malla que cumpla la norma "
            "para este proyecto.",
            extra_context=designer_context,
        )
        session.designer_results.append(designer_result)

        reviewer_result = reviewer_agent.run(
            "Auditá de forma independiente la siguiente propuesta de diseño.",
            extra_context=f"Propuesta del diseñador:\n{designer_result.final_text}",
        )
        session.reviewer_results.append(reviewer_result)

        if reviewer_result.final_text.strip().upper().startswith("APROBADO"):
            session.final_verdict = "APROBADO"
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
    return session
