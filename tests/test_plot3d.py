"""
Tests del módulo de visualización 3D.

No se puede verificar el renderizado visual en sí (eso lo confirma el
usuario abriendo el HTML), pero sí la estructura del objeto Figure
generado: número de trazas, botones del selector, y que el archivo
HTML se escriba correctamente a disco.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.engine.models import SoilModel, GridGeometry
from src.engine.potential_profile import (
    compute_surface_potential,
    touch_voltage_field,
    step_voltage_field,
)
from src.visual.plot3d import build_potential_dashboard, save_html


def sample_field_and_grid():
    soil = SoilModel(rho=100.0)
    grid = GridGeometry(
        Lx=40.0, Ly=40.0, h=0.5, d=0.01, n_x=5, n_y=5,
        n_rods=4, L_rod=3.0, rods_on_perimeter=True,
    )
    field = compute_surface_potential(soil, grid, IG=1000.0, margin=5.0, sample_resolution=4.0)
    return field, grid


def test_dashboard_with_only_potential_has_one_surface_option():
    field, grid = sample_field_and_grid()
    fig = build_potential_dashboard(field, grid)

    buttons = fig.layout.updatemenus[0].buttons
    assert len(buttons) == 1

    surface_traces = [t for t in fig.data if t.type == "surface"]
    assert len(surface_traces) == 1


def test_dashboard_with_all_fields_has_three_surface_options():
    field, grid = sample_field_and_grid()
    touch_field = touch_voltage_field(field.V, gpr_reference=field.V.max() * 1.5)
    step_field = step_voltage_field(field.X, field.Y, field.V)

    fig = build_potential_dashboard(field, grid, touch_field=touch_field, step_field=step_field)

    buttons = fig.layout.updatemenus[0].buttons
    assert len(buttons) == 3

    surface_traces = [t for t in fig.data if t.type == "surface"]
    assert len(surface_traces) == 3


def test_dashboard_includes_grid_conductor_reference_lines():
    field, grid = sample_field_and_grid()
    fig = build_potential_dashboard(field, grid)

    line_traces = [t for t in fig.data if t.type == "scatter3d"]
    # n_x + n_y líneas de referencia de la malla (una por conductor)
    assert len(line_traces) == grid.n_x + grid.n_y


def test_only_first_surface_visible_by_default():
    field, grid = sample_field_and_grid()
    touch_field = touch_voltage_field(field.V, gpr_reference=field.V.max() * 1.5)

    fig = build_potential_dashboard(field, grid, touch_field=touch_field)

    surface_traces = [t for t in fig.data if t.type == "surface"]
    assert surface_traces[0].visible is True
    assert surface_traces[1].visible is False


def test_save_html_writes_nonempty_file(tmp_path):
    field, grid = sample_field_and_grid()
    fig = build_potential_dashboard(field, grid)

    output_path = tmp_path / "test_dashboard.html"
    save_html(fig, str(output_path), embed_plotly_js=False)  # sin embeber -> archivo chico y rápido de testear

    assert output_path.exists()
    content = output_path.read_text()
    assert len(content) > 1000
    assert "plotly" in content.lower()
