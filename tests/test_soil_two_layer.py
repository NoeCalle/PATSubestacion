"""
Tests del modelo de suelo de dos capas.

Incluye un test crítico de validación física: la fórmula de resistividad
aparente de Wenner debe cumplir rho_a(a->0) = rho1 y rho_a(a->infinito) = rho2.
Esto no es solo un sanity check arbitrario -- es la verificación matemática
de que la fórmula implementada tiene la estructura correcta (ver derivación
en el docstring de soil_two_layer.py).
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from src.engine.models import TwoLayerSoilModel, GridGeometry, FaultData
from src.engine.soil_two_layer import (
    reflection_factor,
    wenner_apparent_resistivity,
    fit_two_layer_model,
    effective_design_resistivity,
)
from src.engine.design_check import run_design_check_two_layer


# ---------- Factor de reflexión ----------

def test_reflection_factor_zero_when_equal():
    assert reflection_factor(100, 100) == 0.0


def test_reflection_factor_positive_when_lower_layer_more_resistive():
    K = reflection_factor(rho1=50, rho2=500)
    assert K > 0


def test_reflection_factor_negative_when_lower_layer_less_resistive():
    K = reflection_factor(rho1=500, rho2=50)
    assert K < 0


def test_reflection_factor_bounded():
    K = reflection_factor(rho1=1, rho2=100000)
    assert -1 < K < 1


# ---------- Resistividad aparente de Wenner: límites físicos ----------

def test_apparent_resistivity_approaches_rho1_for_small_spacing():
    """Espaciamiento muy pequeño -> la medición no alcanza a ver la capa
    inferior -> rho_a debe aproximarse a rho1."""
    rho1, rho2, h1 = 50.0, 500.0, 5.0
    rho_a = wenner_apparent_resistivity(rho1, rho2, h1, a=0.01)
    assert rho_a == pytest.approx(rho1, rel=0.01)


def test_apparent_resistivity_approaches_rho2_for_large_spacing():
    """Espaciamiento muy grande -> la medición penetra hasta la capa
    inferior -> rho_a debe aproximarse a rho2."""
    rho1, rho2, h1 = 50.0, 500.0, 5.0
    rho_a = wenner_apparent_resistivity(rho1, rho2, h1, a=5000.0)
    assert rho_a == pytest.approx(rho2, rel=0.01)


def test_apparent_resistivity_monotonic_transition_rho2_greater_rho1():
    """Si rho2 > rho1, rho_a debe crecer monótonamente (o al menos no
    decrecer) al aumentar el espaciamiento, transicionando de rho1 a rho2."""
    rho1, rho2, h1 = 50.0, 500.0, 5.0
    spacings = [0.1, 1, 5, 20, 100, 1000]
    values = [wenner_apparent_resistivity(rho1, rho2, h1, a) for a in spacings]

    for i in range(len(values) - 1):
        assert values[i + 1] >= values[i] - 1e-6  # no decreciente


def test_apparent_resistivity_equals_uniform_when_layers_equal():
    """Si rho1 == rho2, el suelo es efectivamente uniforme, y rho_a debe
    ser igual a esa resistividad para cualquier espaciamiento."""
    rho_a = wenner_apparent_resistivity(rho1=100.0, rho2=100.0, h1=5.0, a=10.0)
    assert rho_a == pytest.approx(100.0, rel=1e-6)


# ---------- Ajuste (curve fitting) ----------

def test_fit_recovers_known_parameters_from_synthetic_data():
    """Generamos datos sintéticos con parámetros conocidos, y verificamos
    que el ajuste los recupera razonablemente bien."""
    true_rho1, true_rho2, true_h1 = 80.0, 400.0, 3.0

    spacings = [0.5, 1, 2, 4, 8, 16, 32, 64]
    measurements = [
        (a, wenner_apparent_resistivity(true_rho1, true_rho2, true_h1, a))
        for a in spacings
    ]

    fit = fit_two_layer_model(measurements)

    assert fit.rho1 == pytest.approx(true_rho1, rel=0.15)
    assert fit.rho2 == pytest.approx(true_rho2, rel=0.15)
    assert fit.h1 == pytest.approx(true_h1, rel=0.25)
    assert fit.residual < 0.01


def test_fit_requires_minimum_measurements():
    with pytest.raises(ValueError):
        fit_two_layer_model([(1, 100), (2, 110)])  # solo 2 mediciones


# ---------- Resistividad efectiva para diseño ----------

def test_effective_resistivity_between_rho1_and_rho2():
    """La resistividad efectiva (heurística de radio equivalente) debe
    caer dentro del rango [rho1, rho2] o [rho2, rho1], nunca fuera."""
    soil = TwoLayerSoilModel(rho1=50.0, rho2=500.0, h1=3.0)
    grid = GridGeometry(Lx=60, Ly=60, h=0.5, d=0.01, n_x=7, n_y=7)

    rho_eff, note = effective_design_resistivity(soil, grid)

    assert min(soil.rho1, soil.rho2) <= rho_eff <= max(soil.rho1, soil.rho2)
    assert "aproximación" in note.lower()


def test_design_check_two_layer_runs_end_to_end():
    soil = TwoLayerSoilModel(rho1=50.0, rho2=500.0, h1=3.0)
    grid = GridGeometry(
        Lx=60, Ly=60, h=0.5, d=0.01, n_x=7, n_y=7,
        n_rods=8, L_rod=3.0, rods_on_perimeter=True,
    )
    fault = FaultData(If_sym=10000.0, Sf=0.6, tf=0.5, ts=0.5, X_R=15.0, freq=60.0)

    result = run_design_check_two_layer(soil, grid, fault, body_kg=50)

    assert result.Em > 0
    assert result.Es > 0
    assert result.GPR > 0
    # La nota de la aproximación debe quedar registrada para trazabilidad
    assert any("aproximación" in n.lower() for n in result.notes)


# ---------- Validación de inputs ----------

def test_invalid_two_layer_soil_raises():
    with pytest.raises(ValueError):
        TwoLayerSoilModel(rho1=-10, rho2=100, h1=3.0)

    with pytest.raises(ValueError):
        TwoLayerSoilModel(rho1=100, rho2=100, h1=0)
