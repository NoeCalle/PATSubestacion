"""
Tests del motor de cálculo IEEE 80.

Nota metodológica: estos tests verifican consistencia interna y
comportamiento físico esperado (sanity checks), NO reproducen un
ejemplo numérico específico del libro IEEE 80-2013 dígito por dígito
-- eso queda pendiente como validación manual adicional por un
ingeniero habilitado antes de usar este motor en un proyecto real.
"""

import math
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from src.engine.models import SoilModel, GridGeometry, FaultData
from src.engine.tolerable_voltages import (
    surface_derating_factor,
    tolerable_step_voltage,
    tolerable_touch_voltage,
)
from src.engine.decrement_factor import decrement_factor, grid_current
from src.engine.grid_resistance import sverak_resistance
from src.engine.geometric_factors import (
    geometric_factor_n,
    irregularity_factor_Ki,
    corrective_weighting_Kii,
)
from src.engine.design_check import run_design_check


# ---------- Fixtures base ----------

def base_soil():
    return SoilModel(rho=100.0)  # suelo uniforme, sin capa superficial


def base_soil_with_gravel():
    return SoilModel(rho=100.0, rho_s=3000.0, h_s=0.1)


def base_grid(n_rods=0, rods_on_perimeter=True):
    return GridGeometry(
        Lx=60.0, Ly=60.0, h=0.5, d=0.01,
        n_x=7, n_y=7,
        n_rods=n_rods, L_rod=3.0 if n_rods else 0.0,
        rods_on_perimeter=rods_on_perimeter,
    )


def base_fault():
    return FaultData(If_sym=10000.0, Sf=0.6, tf=0.5, ts=0.5, X_R=15.0, freq=60.0)


# ---------- Tensiones tolerables ----------

def test_cs_equals_1_without_surface_layer():
    soil = base_soil()
    assert surface_derating_factor(soil) == 1.0


def test_cs_less_than_1_with_gravel():
    """Grava de alta resistividad sobre suelo de baja resistividad debe dar Cs < 1."""
    soil = base_soil_with_gravel()
    Cs = surface_derating_factor(soil)
    assert 0 < Cs < 1


def test_tolerable_voltages_70kg_greater_than_50kg():
    """A igual tiempo de exposición, el límite de 70 kg es mayor que el de 50 kg
    (una persona más pesada tolera más corriente)."""
    soil = base_soil()
    e_step_50 = tolerable_step_voltage(soil, ts=0.5, body_kg=50)
    e_step_70 = tolerable_step_voltage(soil, ts=0.5, body_kg=70)
    assert e_step_70 > e_step_50

    e_touch_50 = tolerable_touch_voltage(soil, ts=0.5, body_kg=50)
    e_touch_70 = tolerable_touch_voltage(soil, ts=0.5, body_kg=70)
    assert e_touch_70 > e_touch_50


def test_tolerable_voltage_decreases_with_longer_exposure():
    """A mayor tiempo de despeje de falla, menor tensión tolerable (más tiempo
    expuesto a la corriente)."""
    soil = base_soil()
    e_short = tolerable_touch_voltage(soil, ts=0.25, body_kg=50)
    e_long = tolerable_touch_voltage(soil, ts=1.0, body_kg=50)
    assert e_long < e_short


def test_step_voltage_greater_than_touch_voltage():
    """Para el mismo suelo y tiempo, Estep > Etouch (coeficiente 6 vs 1.5 en la
    fórmula, ya que la trayectoria pie-pie es más resistiva que mano-pie)."""
    soil = base_soil()
    e_step = tolerable_step_voltage(soil, ts=0.5, body_kg=50)
    e_touch = tolerable_touch_voltage(soil, ts=0.5, body_kg=50)
    assert e_step > e_touch


# ---------- Factor de decremento ----------

def test_decrement_factor_greater_or_equal_1():
    fault = base_fault()
    Df = decrement_factor(fault)
    assert Df >= 1.0


def test_decrement_factor_approaches_1_for_long_fault():
    """Para fallas de larga duración (tf >> Ta), Df -> 1."""
    fault_long = FaultData(If_sym=10000.0, Sf=0.6, tf=10.0, ts=10.0, X_R=15.0, freq=60.0)
    Df = decrement_factor(fault_long)
    assert Df == pytest.approx(1.0, abs=0.01)


def test_grid_current_scales_with_fault_current():
    fault1 = base_fault()
    fault2 = FaultData(If_sym=20000.0, Sf=0.6, tf=0.5, ts=0.5, X_R=15.0, freq=60.0)
    assert grid_current(fault2) > grid_current(fault1)


# ---------- Resistencia de malla ----------

def test_grid_resistance_positive():
    soil = base_soil()
    grid = base_grid()
    Rg = sverak_resistance(soil, grid)
    assert Rg > 0


def test_grid_resistance_decreases_with_more_conductor_length():
    """Agregar varillas (más longitud total Lt) debe reducir Rg."""
    soil = base_soil()
    grid_no_rods = base_grid(n_rods=0)
    grid_with_rods = base_grid(n_rods=8)

    Rg_no_rods = sverak_resistance(soil, grid_no_rods)
    Rg_with_rods = sverak_resistance(soil, grid_with_rods)

    assert Rg_with_rods < Rg_no_rods


def test_grid_resistance_scales_with_soil_resistivity():
    """Rg debe ser proporcional a rho (a igual geometría, duplicar rho duplica Rg
    aproximadamente, ya que la fórmula de Sverak es lineal en rho)."""
    grid = base_grid()
    soil_low = SoilModel(rho=50.0)
    soil_high = SoilModel(rho=100.0)

    Rg_low = sverak_resistance(soil_low, grid)
    Rg_high = sverak_resistance(soil_high, grid)

    assert Rg_high == pytest.approx(2 * Rg_low, rel=1e-6)


# ---------- Factores geométricos ----------

def test_kii_equals_1_with_perimeter_rods():
    grid = base_grid(n_rods=8, rods_on_perimeter=True)
    assert corrective_weighting_Kii(grid) == 1.0


def test_kii_less_than_1_without_rods():
    grid = base_grid(n_rods=0)
    Kii = corrective_weighting_Kii(grid)
    assert Kii < 1.0


def test_ki_increases_with_n():
    """Ki = 0.644 + 0.148*n es monótonamente creciente en n."""
    Ki_small_n = irregularity_factor_Ki(n=1.0)
    Ki_large_n = irregularity_factor_Ki(n=3.0)
    assert Ki_large_n > Ki_small_n


def test_geometric_factor_n_reasonable_range():
    """Para una malla cuadrada regular y simétrica, n debe estar cerca de na
    (nb, nc, nd deberían ser cercanos a 1)."""
    grid = base_grid()
    n = geometric_factor_n(grid)
    assert n > 0
    # Malla cuadrada 7x7 -> na = 2*Lc/Lp, debería dar un valor moderado (no absurdo)
    assert 1 <= n <= 20


# ---------- Integración: run_design_check ----------

def test_design_check_runs_end_to_end():
    result = run_design_check(base_soil(), base_grid(n_rods=8), base_fault(), body_kg=50)
    assert result.Em > 0
    assert result.Es > 0
    assert result.GPR > 0
    assert result.Rg > 0
    assert isinstance(result.passes, bool)


def test_design_check_more_rods_improves_or_maintains_safety_margin():
    """Agregar varillas perimetrales no debería empeorar Em (Kii=1 es más
    favorable o igual que sin varillas, y Rg baja)."""
    soil = base_soil()
    fault = base_fault()

    result_no_rods = run_design_check(soil, base_grid(n_rods=0), fault, body_kg=50)
    result_with_rods = run_design_check(soil, base_grid(n_rods=8), fault, body_kg=50)

    # GPR debe bajar (menor Rg) al agregar varillas
    assert result_with_rods.GPR < result_no_rods.GPR


def test_design_check_tighter_spacing_reduces_em():
    """Reducir el espaciamiento entre conductores (más conductores paralelos)
    debe reducir Em, ya que mejora la uniformidad del gradiente de potencial."""
    soil = base_soil()
    fault = base_fault()

    grid_sparse = GridGeometry(Lx=60, Ly=60, h=0.5, d=0.01, n_x=4, n_y=4)
    grid_dense = GridGeometry(Lx=60, Ly=60, h=0.5, d=0.01, n_x=10, n_y=10)

    result_sparse = run_design_check(soil, grid_sparse, fault, body_kg=50)
    result_dense = run_design_check(soil, grid_dense, fault, body_kg=50)

    assert result_dense.Em < result_sparse.Em


# ---------- Validación de inputs ----------

def test_invalid_soil_resistivity_raises():
    with pytest.raises(ValueError):
        SoilModel(rho=-10)


def test_invalid_grid_geometry_raises():
    with pytest.raises(ValueError):
        GridGeometry(Lx=60, Ly=60, h=0.5, d=0.01, n_x=1, n_y=7)  # n_x < 2


def test_invalid_body_weight_raises():
    from src.engine.models import BodyWeight
    with pytest.raises(ValueError):
        BodyWeight(kg=60)  # solo 50 o 70 son válidos en IEEE 80
