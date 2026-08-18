"""
Ejemplo: pipeline completo hasta la memoria de cálculo en Word.

soil + grid + fault -> cálculo normativo -> informe .docx listo para
revisión y firma del ingeniero.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.engine import SoilModel, GridGeometry, FaultData, run_design_check
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

    project_info = ProjectInfo(
        project_name="Subestación de ejemplo",
        location="Lima, Perú",
        client="Cliente de ejemplo",
        prepared_by="Sistema de agentes IEEE 80 (motor de cálculo determinístico)",
    )

    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "memoria_de_calculo.docx")

    build_calculation_report(
        soil, grid, fault, result, output_path,
        project_info=project_info,
        visualization_reference="potential_dashboard.html (ver examples/visualize_potential_3d.py)",
    )

    print(f"Memoria de cálculo generada en: {output_path}")
    print(f"Veredicto: {'CUMPLE' if result.passes else 'NO CUMPLE'}")
    print("\n⚠️ Recordá: requiere revisión y firma de un ingeniero habilitado.")


if __name__ == "__main__":
    main()
