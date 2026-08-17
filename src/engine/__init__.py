"""Motor de cálculo normativo IEEE 80. Sin dependencia de LLM: funciones
puras y deterministas, testeadas con pytest."""

from .models import SoilModel, GridGeometry, FaultData, DesignResult
from .design_check import run_design_check

__all__ = [
    "SoilModel",
    "GridGeometry",
    "FaultData",
    "DesignResult",
    "run_design_check",
]
