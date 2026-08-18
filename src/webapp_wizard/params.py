"""
Convierte los datos planos del formulario HTML en las dataclasses del
motor de cálculo. Sin dependencia de src/agents -- así este modelador
web sigue sin requerir los SDKs de Anthropic/OpenAI, solo Flask.
"""

from typing import List, Optional, Tuple, Union

from src.engine.models import SoilModel, TwoLayerSoilModel, GridGeometry, FaultData
from src.engine.soil_two_layer import fit_two_layer_model


def parse_float(form, key: str, default: Optional[float] = None) -> Optional[float]:
    raw = (form.get(key) or "").strip()
    if not raw:
        return default
    return float(raw)


def parse_int(form, key: str, default: Optional[int] = None) -> Optional[int]:
    raw = (form.get(key) or "").strip()
    if not raw:
        return default
    return int(raw)


def require_float(form, key: str, label: str) -> float:
    raw = (form.get(key) or "").strip()
    if not raw:
        raise ValueError(f"Falta el campo obligatorio: {label}.")
    try:
        return float(raw)
    except ValueError:
        raise ValueError(f"El campo «{label}» debe ser un número válido.")


def build_soil_from_form(form) -> Union[SoilModel, TwoLayerSoilModel]:
    soil_type = form.get("soil_type", "uniform")
    soil: Union[SoilModel, TwoLayerSoilModel]

    if soil_type == "uniform":
        soil = SoilModel(rho=require_float(form, "rho", "Resistividad del suelo"))

    elif soil_type == "two_layer_known":
        soil = TwoLayerSoilModel(
            rho1=require_float(form, "rho1", "Resistividad capa superior (ρ1)"),
            rho2=require_float(form, "rho2", "Resistividad capa inferior (ρ2)"),
            h1=require_float(form, "h1", "Espesor capa superior (h1)"),
        )

    elif soil_type == "two_layer_wenner":
        a_values = form.getlist("wenner_a")
        rho_values = form.getlist("wenner_rho")
        measurements: List[Tuple[float, float]] = []
        for a_raw, rho_raw in zip(a_values, rho_values):
            if a_raw.strip() and rho_raw.strip():
                measurements.append((float(a_raw), float(rho_raw)))

        if len(measurements) < 3:
            raise ValueError(
                "Se necesitan al menos 3 mediciones de Wenner completas "
                "(espaciamiento + resistividad) para ajustar un modelo de dos capas."
            )

        fit = fit_two_layer_model(measurements)
        soil = TwoLayerSoilModel(rho1=fit.rho1, rho2=fit.rho2, h1=fit.h1)

    else:
        raise ValueError(f"Tipo de suelo desconocido: {soil_type}")

    if form.get("use_surface_layer") == "on":
        soil.rho_s = require_float(form, "rho_s", "Resistividad de la capa superficial")
        soil.h_s = parse_float(form, "h_s", default=0.1)

    return soil


def build_grid_from_form(form) -> GridGeometry:
    use_rods = form.get("use_rods") == "on"
    return GridGeometry(
        Lx=require_float(form, "Lx", "Largo del terreno en X"),
        Ly=require_float(form, "Ly", "Largo del terreno en Y"),
        h=parse_float(form, "h", default=0.5),
        d=parse_float(form, "d", default=0.01),
        n_x=parse_int(form, "n_x", default=5),
        n_y=parse_int(form, "n_y", default=5),
        n_rods=parse_int(form, "n_rods", default=4) if use_rods else 0,
        L_rod=parse_float(form, "L_rod", default=3.0) if use_rods else 0.0,
        rods_on_perimeter=form.get("rods_on_perimeter") == "on",
    )


def build_fault_from_form(form) -> FaultData:
    tf = parse_float(form, "tf", default=0.5)
    return FaultData(
        If_sym=require_float(form, "If_sym", "Corriente de falla simétrica"),
        Sf=parse_float(form, "Sf", default=1.0),
        tf=tf,
        ts=parse_float(form, "ts", default=tf),
        X_R=parse_float(form, "X_R", default=15.0),
        freq=parse_float(form, "freq", default=60.0),
        Cp=parse_float(form, "Cp", default=1.0),
    )
