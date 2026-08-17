"""
Ejemplo de flujo completo con suelo de dos capas:
1. Datos de campo de un ensayo de Wenner (espaciamiento, resistividad medida)
2. Ajuste del modelo de dos capas (rho1, rho2, h1)
3. Diseño de malla usando la resistividad efectiva estimada

⚠️ Los datos de campo de este ejemplo son sintéticos (generados a partir
de un modelo conocido para poder verificar que el ajuste funciona). En un
proyecto real, estos vendrían de un ensayo Wenner real en terreno.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.engine.soil_two_layer import wenner_apparent_resistivity, fit_two_layer_model
from src.engine.models import GridGeometry, FaultData
from src.engine.design_check import run_design_check_two_layer
from src.engine.models import TwoLayerSoilModel


def main():
    # --- 1. Datos de campo (simulados a partir de rho1=60, rho2=800, h1=4m) ---
    true_rho1, true_rho2, true_h1 = 60.0, 800.0, 4.0
    spacings = [0.5, 1, 2, 4, 8, 16, 32, 64, 128]
    field_measurements = [
        (a, wenner_apparent_resistivity(true_rho1, true_rho2, true_h1, a))
        for a in spacings
    ]

    print("=== Datos de campo (ensayo de Wenner) ===")
    for a, rho in field_measurements:
        print(f"  a = {a:>6.1f} m  ->  rho_a = {rho:>8.1f} Ω·m")

    # --- 2. Ajuste del modelo de dos capas ---
    fit = fit_two_layer_model(field_measurements)
    print(f"\n=== Modelo de dos capas ajustado ===")
    print(f"  rho1 = {fit.rho1:.1f} Ω·m   (real: {true_rho1})")
    print(f"  rho2 = {fit.rho2:.1f} Ω·m   (real: {true_rho2})")
    print(f"  h1   = {fit.h1:.2f} m       (real: {true_h1})")
    print(f"  error residual (RMS relativo): {fit.residual:.5f}")

    # --- 3. Diseño de malla con el modelo ajustado ---
    soil = TwoLayerSoilModel(rho1=fit.rho1, rho2=fit.rho2, h1=fit.h1)
    grid = GridGeometry(
        Lx=60.0, Ly=60.0, h=0.5, d=0.01,
        n_x=10, n_y=10,
        n_rods=12, L_rod=3.0, rods_on_perimeter=True,
    )
    fault = FaultData(If_sym=10000.0, Sf=0.6, tf=0.5, ts=0.5, X_R=15.0, freq=60.0)

    result = run_design_check_two_layer(soil, grid, fault, body_kg=50)

    print(f"\n=== Resultado del diseño ===")
    print(f"GPR:                              {result.GPR:.1f} V")
    print(f"Em: {result.Em:.1f} V  vs  tolerable {result.E_touch_tolerable:.1f} V  -> {'CUMPLE' if result.mesh_ok else 'NO CUMPLE'}")
    print(f"Es: {result.Es:.1f} V  vs  tolerable {result.E_step_tolerable:.1f} V  -> {'CUMPLE' if result.step_ok else 'NO CUMPLE'}")
    print(f"\nVEREDICTO: {'PASA' if result.passes else 'NO PASA'}")

    print("\nNotas:")
    for note in result.notes:
        print(f"  - {note}")


if __name__ == "__main__":
    main()
