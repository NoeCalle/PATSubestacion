"""
Tests del renderizado estático (PNG) del perfil de potencial.

No verificamos el contenido visual en sí (eso se confirma
manualmente), pero sí que los archivos se generan, tienen contenido
real (no están vacíos ni truncados), y que las claves devueltas
coinciden con lo que se pidió.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.engine.models import SoilModel, GridGeometry
from src.engine.potential_profile import (
    compute_surface_potential,
    touch_voltage_field,
    step_voltage_field,
)
from src.visual.static_plot3d import render_static_views


def sample_field_and_grid():
    soil = SoilModel(rho=100.0)
    grid = GridGeometry(
        Lx=40.0, Ly=40.0, h=0.5, d=0.01, n_x=5, n_y=5,
        n_rods=4, L_rod=3.0, rods_on_perimeter=True,
    )
    field = compute_surface_potential(soil, grid, IG=1000.0, margin=5.0, sample_resolution=4.0)
    return field, grid


def test_render_static_views_potential_only(tmp_path):
    field, grid = sample_field_and_grid()

    paths = render_static_views(field, grid, output_dir=str(tmp_path))

    assert set(paths.keys()) == {"potential"}
    assert os.path.exists(paths["potential"])
    assert os.path.getsize(paths["potential"]) > 5000  # PNG real, no un archivo vacío/corrupto


def test_render_static_views_all_three(tmp_path):
    field, grid = sample_field_and_grid()
    touch_field = touch_voltage_field(field.V, gpr_reference=field.V.max() * 1.5)
    step_field = step_voltage_field(field.X, field.Y, field.V)

    paths = render_static_views(
        field, grid, output_dir=str(tmp_path),
        touch_field=touch_field, step_field=step_field,
    )

    assert set(paths.keys()) == {"potential", "touch", "step"}
    for path in paths.values():
        assert os.path.exists(path)
        assert os.path.getsize(path) > 5000


def test_render_static_views_creates_output_dir_if_missing(tmp_path):
    field, grid = sample_field_and_grid()
    output_dir = str(tmp_path / "nested" / "output")

    paths = render_static_views(field, grid, output_dir=output_dir)

    assert os.path.isdir(output_dir)
    assert os.path.exists(paths["potential"])
