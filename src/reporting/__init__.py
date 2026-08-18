"""Módulo de reportes. Sin cálculo ni LLM -- solo formatea resultados
ya validados del motor de cálculo (src/engine) en un documento Word
profesional."""

from .report_builder import build_calculation_report, ProjectInfo

__all__ = ["build_calculation_report", "ProjectInfo"]
