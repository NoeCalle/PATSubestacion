"""
Ejemplo: cálculo del perfil de potencial en grilla, y comparación
honesta con el resultado normativo (Em/Es cerrado de IEEE 80).

Este ejemplo deja explícito que ambos números pueden diferir -- eso es
esperado dado que el perfil de grilla usa una simplificación (corriente
uniforme) mientras que Em/Es normativo usa las fórmulas empíricas de
la norma, calibradas contra mediciones reales.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

from src.engine import SoilModel, GridGeometry, FaultData, run_design_check
from src.engine.potential_profile import (
    compute_surface_potential,
    touch_voltage_field,
    step_voltage_field,
)


def main():
    soil = SoilModel(rho=100.0)
    grid = GridGeometry(
        Lx=60.0, Ly=60.0, h=0.5, d=0.01,
        n_x=7, n_y=7,
        n_rods=8, L_rod=3.0, rods_on_perimeter=True,
    )
    fault = FaultData(If_sym=10000.0, Sf=0.6, tf=0.5, ts=0.5, X_R=15.0, freq=60.0)

    # --- 1. Cálculo normativo (fórmulas cerradas IEEE 80) ---
    result = run_design_check(soil, grid, fault, body_kg=50)
    print("=== Resultado normativo (fórmulas cerradas IEEE 80) ===")
    print(f"GPR:  {result.GPR:.1f} V")
    print(f"Em:   {result.Em:.1f} V  (tolerable: {result.E_touch_tolerable:.1f} V)")
    print(f"Es:   {result.Es:.1f} V  (tolerable: {result.E_step_tolerable:.1f} V)")

    # --- 2. Perfil de potencial en grilla (motor numérico exploratorio) ---
    field = compute_surface_potential(soil, grid, IG=result.IG, margin=10.0)
    touch_field = touch_voltage_field(field.V, gpr_reference=result.GPR)
    step_field = step_voltage_field(field.X, field.Y, field.V)

    print(f"\n=== Perfil de potencial numérico (motor exploratorio) ===")
    print(f"Segmentos discretizados: {field.n_segments}")
    print(f"Longitud total discretizada: {field.total_segment_length:.1f} m (grid.Lt: {grid.Lt:.1f} m)")
    print(f"V máximo en la grilla de muestreo: {field.V.max():.1f} V")
    print(f"V mínimo en la grilla de muestreo: {field.V.min():.1f} V")
    print(f"Tensión de contacto aproximada, máxima: {touch_field.max():.1f} V")
    print(f"Tensión de paso aproximada, máxima:      {step_field.max():.1f} V")

    print(
        "\n⚠️ Comparación (esperable que difieran, ver limitaciones documentadas "
        "en potential_profile.py):"
    )
    print(f"   Es normativo (fórmula cerrada):  {result.Es:.1f} V")
    print(f"   Tensión de paso máx. del perfil:  {step_field.max():.1f} V")
    print(
        "   El perfil numérico asume corriente uniforme entre segmentos; el "
        "valor normativo usa fórmulas empíricas calibradas de la norma. Para "
        "el informe firmado, el valor normativo es el que rige."
    )


if __name__ == "__main__":
    main()
