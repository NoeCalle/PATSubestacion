"""
Ejemplo de uso del motor de cálculo normativo IEEE 80.

Caso: malla rectangular 60x60 m, 7x7 conductores, con 8 varillas
perimetrales de 3 m, suelo uniforme de 100 Ohm*m, falla de 10 kA
simétricos, tiempo de despeje 0.5 s.

⚠️ Estos valores son ilustrativos. No usar como memoria de cálculo real
sin revisión de un ingeniero eléctrico habilitado.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.engine import SoilModel, GridGeometry, FaultData, run_design_check


def main():
    soil = SoilModel(rho=100.0)  # suelo uniforme, sin capa de grava

    grid = GridGeometry(
        Lx=60.0, Ly=60.0,
        h=0.5, d=0.01,
        n_x=7, n_y=7,
        n_rods=8, L_rod=3.0,
        rods_on_perimeter=True,
    )

    fault = FaultData(
        If_sym=10000.0,  # 10 kA simétricos
        Sf=0.6,           # 60% de la corriente retorna por la malla
        tf=0.5,           # 0.5 s de despeje de falla
        ts=0.5,           # 0.5 s de exposición al choque
        X_R=15.0,
        freq=60.0,
    )

    result = run_design_check(soil, grid, fault, body_kg=50)

    print("=== Resultado del diseño IEEE 80 (peso corporal 50 kg) ===\n")
    print(f"Resistencia de malla (Rg):        {result.Rg:.3f} Ohm")
    print(f"Corriente de malla (IG):          {result.IG:.1f} A")
    print(f"GPR (Ground Potential Rise):      {result.GPR:.1f} V")
    print()
    print(f"Tensión de contacto tolerable:    {result.E_touch_tolerable:.1f} V")
    print(f"Tensión de malla calculada (Em):  {result.Em:.1f} V")
    print(f"  -> {'CUMPLE' if result.mesh_ok else 'NO CUMPLE'}")
    print()
    print(f"Tensión de paso tolerable:         {result.E_step_tolerable:.1f} V")
    print(f"Tensión de paso calculada (Es):    {result.Es:.1f} V")
    print(f"  -> {'CUMPLE' if result.step_ok else 'NO CUMPLE'}")
    print()
    print(f"VEREDICTO GENERAL: {'PASA' if result.passes else 'NO PASA'}")

    if result.notes:
        print("\nNotas:")
        for note in result.notes:
            print(f"  - {note}")


if __name__ == "__main__":
    main()
