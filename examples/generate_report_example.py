"""
Ejemplo: pipeline completo hasta la memoria de cálculo en Word,
incluyendo las vistas 3D estáticas del perfil de potencial embebidas
en el documento.

soil + grid + fault -> cálculo normativo -> perfil de potencial ->
vistas 3D estáticas (PNG) -> informe .docx con todo embebido, listo
para revisión y firma del ingeniero.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.engine import SoilModel, GridGeometry, FaultData, run_design_check
from src.engine.potential_profile import (
    compute_surface_potential,
    touch_voltage_field,
    step_voltage_field,
)
from src.visual.static_plot3d import render_static_views
from src.reporting import build_calculation_report, ProjectInfo


def main():
    soil = SoilModel(rho=100.0)
    grid = GridGeometry(
        Lx=60.0, Ly=60.0, h=0.5, d=0.01,
        n_x=7, n_y=7,
        n_rods=8, L_rod=3.0, rods_on_perimeter=True,
    )
    fault = FaultData(If_sym=10000.0, Sf=0.6, tf=0.5, ts=0.5, X_R=15.0, freq=60.0)

    result = run_design_check(soil, grid, fault, body_kg=50)

    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)

    # --- Perfil de potencial + vistas 3D estáticas ---
    field = compute_surface_potential(soil, grid, IG=result.IG, margin=10.0, sample_resolution=1.5)
    touch_field = touch_voltage_field(field.V, gpr_reference=result.GPR)
    step_field = step_voltage_field(field.X, field.Y, field.V)

    static_views_dir = os.path.join(output_dir, "static_views")
    static_paths = render_static_views(
        field, grid, output_dir=static_views_dir,
        touch_field=touch_field, step_field=step_field,
    )
    print(f"Vistas 3D estáticas generadas: {list(static_paths.keys())}")

    # --- Memoria de cálculo, con las vistas embebidas ---
    project_info = ProjectInfo(
        project_name="Subestación de ejemplo",
        location="Lima, Perú",
        client="Cliente de ejemplo",
        prepared_by="Sistema de agentes IEEE 80 (motor de cálculo determinístico)",
    )

    report_path = os.path.join(output_dir, "memoria_de_calculo.docx")
    build_calculation_report(
        soil, grid, fault, result, report_path,
        project_info=project_info,
        static_view_paths=static_paths,
        visualization_reference="potential_dashboard.html (ver examples/visualize_potential_3d.py)",
    )

    print(f"\nMemoria de cálculo generada en: {report_path}")
    print(f"Veredicto: {'CUMPLE' if result.passes else 'NO CUMPLE'}")
    print("\n⚠️ Recordá: requiere revisión y firma de un ingeniero habilitado.")


if __name__ == "__main__":
    main()
