"""
Estado del pipeline de diseño (DesignSession).

Vive en su propio módulo (separado de coordinator.py) para que
report_integration.py pueda importar el tipo DesignSession sin generar
un import circular con la lógica de orquestación.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from .base_agent import AgentResult


@dataclass
class DesignSession:
    soil_result: Optional[AgentResult] = None
    designer_results: List[AgentResult] = field(default_factory=list)
    reviewer_results: List[AgentResult] = field(default_factory=list)
    final_verdict: str = "NO_INICIADO"  # APROBADO | NO_RESUELTO | NO_INICIADO
    iterations: int = 0
    report_path: Optional[str] = None  # se completa si run_design_pipeline generó el informe

    @property
    def final_design(self) -> Optional[str]:
        """Texto de la última propuesta del diseñador (la vigente al cierre)."""
        return self.designer_results[-1].final_text if self.designer_results else None

    @property
    def final_review(self) -> Optional[str]:
        return self.reviewer_results[-1].final_text if self.reviewer_results else None
