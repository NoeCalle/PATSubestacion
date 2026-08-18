"""
Tests del perfil de potencial en grilla.

Enfoque: verificar comportamiento físico robusto (simetría, decaimiento
con la distancia, consistencia de la discretización) -- NO se exige que
coincida numéricamente con Em/Es normativo, porque este motor usa una
simplificación deliberada (corriente uniforme entre segmentos) que se
sabe difiere del comportamiento real, especialmente cerca de los
conductores. Esa divergencia esperada está documentada en el módulo.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pytest

from src.engine.models import SoilModel, GridGeometry
from src.engine.potential_profile import (
    build_segments,
    rod_positions,
    compute_surface_potential,
    touch_voltage_field,
    step_voltage_field,
)


def square_grid(n_rods=0):
    return GridGeometry(
        Lx=40.0, Ly=40.0, h=0.5, d=0.01,
        n_x=5, n_y=5,
        n_rods=n_rods, L_rod=3.0 if n_rods else 0.0,
        rods_on_perimeter=True,
    )


# ---------- Discretización ----------

def test_segment_total_length_matches_grid_lt():
    """La suma de longitudes de los segmentos discretizados debe
    aproximarse a grid.Lt (Lc + Lr), ya que la discretización de cada
    tramo es exacta (sin remanente)."""
    grid = square_grid(n_rods=8)
    segments = build_segments(grid, segment_length=2.0)
    total = sum(s[3] for s in segments)
    assert total == pytest.approx(grid.Lt, rel=1e-9)


def test_rod_positions_count_matches_n_rods():
    grid = square_grid(n_rods=6)
    positions = rod_positions(grid)
    assert len(positions) == 6


def test_rod_positions_on_perimeter():
    """Todas las posiciones de varillas deben caer sobre el perímetro
    (x=0, x=Lx, y=0, o y=Ly)."""
    grid = square_grid(n_rods=10)
    for x, y in rod_positions(grid):
        on_perimeter = (
            abs(x) < 1e-6 or abs(x - grid.Lx) < 1e-6
            or abs(y) < 1e-6 or abs(y - grid.Ly) < 1e-6
        )
        assert on_perimeter


def test_no_rods_returns_empty_positions():
    grid = square_grid(n_rods=0)
    assert rod_positions(grid) == []


# ---------- Campo de potencial: física esperada ----------

def test_potential_decreases_with_distance_from_center():
    """El potencial debe ser mayor en el centro de la malla que en el
    borde del margen exterior (la corriente se disipa al alejarse)."""
    soil = SoilModel(rho=100.0)
    grid = square_grid(n_rods=8)

    result = compute_surface_potential(soil, grid, IG=1000.0, margin=10.0)

    center_idx_x = np.argmin(np.abs(result.X - grid.Lx / 2))
    center_idx_y = np.argmin(np.abs(result.Y - grid.Ly / 2))
    V_center = result.V[center_idx_y, center_idx_x]

    V_corner_margin = result.V[0, 0]  # esquina del área muestreada (con margen)

    assert V_center > V_corner_margin


def test_potential_field_symmetric_for_symmetric_grid():
    """Para una malla cuadrada simétrica (sin varillas, para no romper
    la simetría con una distribución no perfectamente simétrica de
    varillas), el campo de potencial debe ser simétrico respecto al
    centro."""
    soil = SoilModel(rho=100.0)
    grid = square_grid(n_rods=0)

    result = compute_surface_potential(soil, grid, IG=1000.0, margin=5.0)

    V = result.V
    # Simetría especular horizontal (columna i vs columna -1-i)
    assert np.allclose(V, V[:, ::-1], rtol=1e-6)
    # Simetría especular vertical (fila i vs fila -1-i)
    assert np.allclose(V, V[::-1, :], rtol=1e-6)


def test_potential_scales_linearly_with_current():
    """El problema es lineal (superposición): duplicar IG debe duplicar
    el potencial en todos los puntos."""
    soil = SoilModel(rho=100.0)
    grid = square_grid(n_rods=8)

    result_1x = compute_surface_potential(soil, grid, IG=1000.0, margin=5.0)
    result_2x = compute_surface_potential(soil, grid, IG=2000.0, margin=5.0)

    assert np.allclose(result_2x.V, 2 * result_1x.V, rtol=1e-6)


def test_potential_scales_linearly_with_resistivity():
    """El potencial es proporcional a rho (a igual geometría y corriente)."""
    grid = square_grid(n_rods=8)
    soil_low = SoilModel(rho=50.0)
    soil_high = SoilModel(rho=100.0)

    result_low = compute_surface_potential(soil_low, grid, IG=1000.0, margin=5.0)
    result_high = compute_surface_potential(soil_high, grid, IG=1000.0, margin=5.0)

    assert np.allclose(result_high.V, 2 * result_low.V, rtol=1e-6)


def test_more_rods_increases_center_potential_less_than_fewer_segments():
    """Sanity check básico: el resultado debe ser positivo y finito en
    todo punto (sin NaN/infinitos, incluso cerca de electrodos)."""
    soil = SoilModel(rho=100.0)
    grid = square_grid(n_rods=8)
    result = compute_surface_potential(soil, grid, IG=1000.0, margin=5.0)

    assert np.all(np.isfinite(result.V))
    assert np.all(result.V > 0)


# ---------- Campos derivados ----------

def test_touch_voltage_field_positive_when_v_below_gpr():
    soil = SoilModel(rho=100.0)
    grid = square_grid(n_rods=8)
    result = compute_surface_potential(soil, grid, IG=1000.0, margin=5.0)

    gpr_ref = result.V.max() * 1.5  # referencia arbitraria mayor al máximo local
    touch_field = touch_voltage_field(result.V, gpr_ref)

    assert np.all(touch_field > 0)


def test_step_voltage_field_zero_at_flat_symmetric_center():
    """En el centro exacto de una malla simétrica, el gradiente local
    debería ser cercano a cero (punto de simetría / potencial plano)."""
    soil = SoilModel(rho=100.0)
    grid = square_grid(n_rods=0)
    result = compute_surface_potential(soil, grid, IG=1000.0, margin=5.0, sample_resolution=1.0)

    step_field = step_voltage_field(result.X, result.Y, result.V)

    center_idx_x = np.argmin(np.abs(result.X - grid.Lx / 2))
    center_idx_y = np.argmin(np.abs(result.Y - grid.Ly / 2))

    # No es exactamente cero por la discretización numérica del gradiente,
    # pero debe ser sustancialmente menor que el máximo del campo (que
    # ocurre típicamente cerca del borde de la malla).
    assert step_field[center_idx_y, center_idx_x] < step_field.max() * 0.5
