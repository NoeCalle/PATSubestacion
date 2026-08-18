"""
Registro de herramientas (tools) que los agentes pueden invocar.

Cada tool envuelve una función del motor de cálculo (src/engine) con:
  - nombre y descripción (para que el LLM sepa cuándo usarla)
  - un JSON Schema de parámetros (mismo formato para Anthropic y OpenAI)
  - la función Python que efectivamente la ejecuta

IMPORTANTE: estas funciones NUNCA calculan nada por su cuenta -- solo
convierten los parámetros planos que manda el LLM en las dataclasses
del motor, llaman a las funciones deterministas ya testeadas en
tests/test_engine.py y tests/test_soil_two_layer.py, y devuelven el
resultado como dict serializable a JSON. Este es el punto central que
garantiza que ningún agente "calcule de memoria" una tensión de paso.
"""

import json
from dataclasses import asdict
from typing import Dict, Any, Callable, List, Optional, Tuple, Union

from ..engine.models import SoilModel, GridGeometry, FaultData, TwoLayerSoilModel, DesignResult
from ..engine.design_check import run_design_check, run_design_check_two_layer
from ..engine.soil_two_layer import fit_two_layer_model


def build_grid_from_params(kwargs: Dict[str, Any]) -> GridGeometry:
    return GridGeometry(
        Lx=kwargs["Lx"], Ly=kwargs["Ly"], h=kwargs["h"], d=kwargs["d"],
        n_x=kwargs["n_x"], n_y=kwargs["n_y"],
        n_rods=kwargs.get("n_rods", 0), L_rod=kwargs.get("L_rod", 0.0),
        rods_on_perimeter=kwargs.get("rods_on_perimeter", True),
    )


def build_fault_from_params(kwargs: Dict[str, Any]) -> FaultData:
    return FaultData(
        If_sym=kwargs["If_sym"], Sf=kwargs.get("Sf", 1.0),
        tf=kwargs.get("tf", 0.5), ts=kwargs.get("ts", 0.5),
        X_R=kwargs.get("X_R", 15.0), freq=kwargs.get("freq", 60.0),
        Cp=kwargs.get("Cp", 1.0),
    )


def build_soil_from_params(tool_name: str, kwargs: Dict[str, Any]) -> Union[SoilModel, TwoLayerSoilModel]:
    if tool_name == "run_design_check_two_layer":
        return TwoLayerSoilModel(
            rho1=kwargs["rho1"], rho2=kwargs["rho2"], h1=kwargs["h1"],
            rho_s=kwargs.get("rho_s"), h_s=kwargs.get("h_s", 0.0),
        )
    return SoilModel(rho=kwargs["rho"], rho_s=kwargs.get("rho_s"), h_s=kwargs.get("h_s", 0.0))


# Nombres de las tools que representan una verificación de diseño completa
# (las únicas de las que tiene sentido reconstruir un informe).
DESIGN_CHECK_TOOL_NAMES = {"run_design_check_uniform", "run_design_check_two_layer"}


def reconstruct_design_check_call(
    tool_name: str, params: Dict[str, Any], result_json: str
) -> Tuple[Union[SoilModel, TwoLayerSoilModel], GridGeometry, FaultData, DesignResult]:
    """
    Reconstruye los objetos de entrada (soil, grid, fault) y el
    DesignResult a partir de una tool call YA EJECUTADA por un agente
    (sus parámetros de entrada + el resultado que efectivamente
    devolvió el motor). No vuelve a calcular nada -- solo repone la
    forma estructurada a partir de lo que ya corrió.

    Usado por src/agents/report_integration.py para generar la memoria
    de cálculo a partir de lo que un agente realmente verificó, nunca
    a partir de texto generado por el LLM.
    """
    if tool_name not in DESIGN_CHECK_TOOL_NAMES:
        raise ValueError(f"'{tool_name}' no es una tool de verificación de diseño")

    soil = build_soil_from_params(tool_name, params)
    grid = build_grid_from_params(params)
    fault = build_fault_from_params(params)
    result = DesignResult(**json.loads(result_json))

    return soil, grid, fault, result


def _design_check_uniform(**kwargs) -> Dict[str, Any]:
    soil = SoilModel(rho=kwargs["rho"], rho_s=kwargs.get("rho_s"), h_s=kwargs.get("h_s", 0.0))
    grid = build_grid_from_params(kwargs)
    fault = build_fault_from_params(kwargs)
    result = run_design_check(soil, grid, fault, body_kg=kwargs.get("body_kg", 50))
    return asdict(result)


def _design_check_two_layer(**kwargs) -> Dict[str, Any]:
    soil = TwoLayerSoilModel(
        rho1=kwargs["rho1"], rho2=kwargs["rho2"], h1=kwargs["h1"],
        rho_s=kwargs.get("rho_s"), h_s=kwargs.get("h_s", 0.0),
    )
    grid = build_grid_from_params(kwargs)
    fault = build_fault_from_params(kwargs)
    result = run_design_check_two_layer(soil, grid, fault, body_kg=kwargs.get("body_kg", 50))
    return asdict(result)


def _fit_two_layer(**kwargs) -> Dict[str, Any]:
    measurements = [(m["a"], m["rho_a"]) for m in kwargs["measurements"]]
    fit = fit_two_layer_model(measurements)
    return {"rho1": fit.rho1, "rho2": fit.rho2, "h1": fit.h1, "residual": fit.residual}


# --- Parámetros de geometría/falla compartidos entre las dos tools de diseño ---
_GRID_FAULT_PROPERTIES = {
    "Lx": {"type": "number", "description": "Largo de la malla en X [m]"},
    "Ly": {"type": "number", "description": "Largo de la malla en Y [m]"},
    "h": {"type": "number", "description": "Profundidad de enterramiento de la malla [m]"},
    "d": {"type": "number", "description": "Diámetro del conductor de la malla [m]"},
    "n_x": {"type": "integer", "description": "Número de conductores paralelos en X"},
    "n_y": {"type": "integer", "description": "Número de conductores paralelos en Y"},
    "n_rods": {"type": "integer", "description": "Número de varillas de puesta a tierra", "default": 0},
    "L_rod": {"type": "number", "description": "Longitud de cada varilla [m]", "default": 0.0},
    "rods_on_perimeter": {"type": "boolean", "description": "True si las varillas están en el perímetro/esquinas", "default": True},
    "If_sym": {"type": "number", "description": "Corriente de falla simétrica a tierra [A]"},
    "Sf": {"type": "number", "description": "Factor de división de corriente (0-1]", "default": 1.0},
    "tf": {"type": "number", "description": "Duración de la falla para el factor de decremento [s]", "default": 0.5},
    "ts": {"type": "number", "description": "Tiempo de exposición al choque [s]", "default": 0.5},
    "X_R": {"type": "number", "description": "Relación X/R en el punto de falla", "default": 15.0},
    "freq": {"type": "number", "description": "Frecuencia del sistema [Hz]", "default": 60.0},
    "Cp": {"type": "number", "description": "Factor de crecimiento futuro de la subestación", "default": 1.0},
    "body_kg": {"type": "number", "description": "Peso corporal de referencia para tensiones tolerables: 50 o 70", "default": 50},
}

TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "run_design_check_uniform",
        "description": (
            "Ejecuta el cálculo normativo IEEE 80 completo (Em, Es, GPR, Rg, "
            "tensiones tolerables) para una malla de puesta a tierra en suelo "
            "UNIFORME. Devuelve todos los valores intermedios y el veredicto "
            "pass/fail (mesh_ok, step_ok, passes). Usá esta herramienta "
            "SIEMPRE que necesites verificar una geometría de malla en suelo "
            "de una sola resistividad -- nunca estimes Em/Es sin llamarla."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "rho": {"type": "number", "description": "Resistividad del suelo [Ohm*m]"},
                "rho_s": {"type": "number", "description": "Resistividad de la capa superficial (grava), opcional [Ohm*m]"},
                "h_s": {"type": "number", "description": "Espesor de la capa superficial [m]", "default": 0.0},
                **_GRID_FAULT_PROPERTIES,
            },
            "required": ["rho", "Lx", "Ly", "h", "d", "n_x", "n_y", "If_sym"],
        },
        "function": _design_check_uniform,
    },
    {
        "name": "run_design_check_two_layer",
        "description": (
            "Igual que run_design_check_uniform, pero para suelo de DOS "
            "CAPAS (rho1, rho2, h1). Internamente convierte el modelo de dos "
            "capas a una resistividad efectiva aproximada -- el resultado "
            "incluye una nota explicando esa aproximación, que debés "
            "mencionar en tu respuesta al usuario, no ocultarla."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "rho1": {"type": "number", "description": "Resistividad de la capa superior [Ohm*m]"},
                "rho2": {"type": "number", "description": "Resistividad de la capa inferior [Ohm*m]"},
                "h1": {"type": "number", "description": "Espesor de la capa superior [m]"},
                "rho_s": {"type": "number", "description": "Resistividad de la capa superficial, opcional [Ohm*m]"},
                "h_s": {"type": "number", "description": "Espesor de la capa superficial [m]", "default": 0.0},
                **_GRID_FAULT_PROPERTIES,
            },
            "required": ["rho1", "rho2", "h1", "Lx", "Ly", "h", "d", "n_x", "n_y", "If_sym"],
        },
        "function": _design_check_two_layer,
    },
    {
        "name": "fit_two_layer_soil_model",
        "description": (
            "Ajusta un modelo de suelo de dos capas (rho1, rho2, h1) a "
            "partir de mediciones de campo del ensayo de Wenner (varios "
            "pares espaciamiento/resistividad medida). Requiere al menos 3 "
            "mediciones a distintos espaciamientos. Usala cuando el usuario "
            "te dé datos de campo en vez de valores de resistividad ya "
            "interpretados."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "measurements": {
                    "type": "array",
                    "description": "Lista de mediciones de campo",
                    "items": {
                        "type": "object",
                        "properties": {
                            "a": {"type": "number", "description": "Espaciamiento entre sondas [m]"},
                            "rho_a": {"type": "number", "description": "Resistividad aparente medida [Ohm*m]"},
                        },
                        "required": ["a", "rho_a"],
                    },
                }
            },
            "required": ["measurements"],
        },
        "function": _fit_two_layer,
    },
]


def get_tool_schemas(names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Definiciones (name, description, parameters) -- lo que efectivamente
    ve el LLM. Si names es None, devuelve todas las tools registradas."""
    tools = TOOL_DEFINITIONS if names is None else [t for t in TOOL_DEFINITIONS if t["name"] in names]
    return [{"name": t["name"], "description": t["description"], "parameters": t["parameters"]} for t in tools]


def get_tool_dispatch(names: Optional[List[str]] = None) -> Dict[str, Callable]:
    """Dict {nombre_tool: función} para ejecutar las llamadas que pida el LLM."""
    tools = TOOL_DEFINITIONS if names is None else [t for t in TOOL_DEFINITIONS if t["name"] in names]
    return {t["name"]: t["function"] for t in tools}
