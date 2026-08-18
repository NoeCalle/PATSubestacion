"""
Ejemplo: pipeline completo, de datos de entrada a dashboard 3D interactivo.

soil + grid + fault -> cálculo normativo -> perfil de potencial ->
dashboard interactivo (HTML) con selector entre Potencial / Tensión de
contacto / Tensión de paso.
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
from src.visual.plot3d import build_potential_dashboard, save_html


def main():
    soil = SoilModel(rho=100.0)
    grid = GridGeometry(
        Lx=60.0, Ly=60.0, h=0.5, d=0.01,
        n_x=7, n_y=7,
        n_rods=8, L_rod=3.0, rods_on_perimeter=True,
    )
    fault = FaultData(If_sym=10000.0, Sf=0.6, tf=0.5, ts=0.5, X_R=15.0, freq=60.0)

    result = run_design_check(soil, grid, fault, body_kg=50)

    field = compute_surface_potential(soil, grid, IG=result.IG, margin=10.0, sample_resolution=1.5)
    touch_field = touch_voltage_field(field.V, gpr_reference=result.GPR)
    step_field = step_voltage_field(field.X, field.Y, field.V)

    fig = build_potential_dashboard(
        field, grid,
        touch_field=touch_field,
        step_field=step_field,
        title=f"Malla {grid.Lx:.0f}x{grid.Ly:.0f} m — {'PASA' if result.passes else 'NO PASA'}",
    )

    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "potential_dashboard.html")
    save_html(fig, output_path)

    print(f"Dashboard guardado en: {output_path}")
    print(f"Veredicto normativo: {'PASA' if result.passes else 'NO PASA'}")
    print(f"GPR: {result.GPR:.1f} V | Em: {result.Em:.1f} V | Es: {result.Es:.1f} V")

    return output_path


if __name__ == "__main__":
    main()
