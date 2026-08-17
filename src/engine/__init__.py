"""Motor de cálculo normativo IEEE 80. Sin dependencia de LLM: funciones
puras y deterministas, testeadas con pytest."""

from .models import SoilModel, GridGeometry, FaultData, DesignResult, TwoLayerSoilModel
from .design_check import run_design_check, run_design_check_two_layer
from .soil_two_layer import (
    reflection_factor,
    wenner_apparent_resistivity,
    fit_two_layer_model,
    effective_design_resistivity,
)

__all__ = [
    "SoilModel",
    "GridGeometry",
    "FaultData",
    "DesignResult",
    "TwoLayerSoilModel",
    "run_design_check",
    "run_design_check_two_layer",
    "reflection_factor",
    "wenner_apparent_resistivity",
    "fit_two_layer_model",
    "effective_design_resistivity",
]
