"""
Modelador determinista de puesta a tierra (sin LLM).

Asistente de línea de comandos que le hace preguntas a la persona paso
a paso (geometría, resistividad, datos de falla) usando input() común
de Python, y llama DIRECTO al motor de cálculo (src/engine) y al
generador de reportes (src/reporting) -- sin ningún agente ni API de
LLM de por medio.

Pensado para quien no tiene (o no quiere usar) una cuenta de API de
Claude/ChatGPT. La alternativa con LLM (preguntas más flexibles en
lenguaje natural, ajuste automático de geometría) está en src/agents
y src/webapp.
"""

import os
import sys
from typing import List, Optional, Tuple, Union

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.engine.models import SoilModel, TwoLayerSoilModel, GridGeometry, FaultData, DesignResult
from src.engine.design_check import run_design_check, run_design_check_two_layer
from src.engine.soil_two_layer import fit_two_layer_model
from src.reporting import build_calculation_report, ProjectInfo
from src.cli.prompts import ask_float, ask_int, ask_yes_no, ask_text, ask_choice


def collect_soil_model() -> Union[SoilModel, TwoLayerSoilModel]:
    print("\n--- Modelo de suelo ---")
    choice = ask_choice(
        "¿Qué datos de suelo tenés?",
        {
            "1": "Un solo valor de resistividad (suelo uniforme)",
            "2": "Varias mediciones de campo (ensayo de Wenner) para ajustar dos capas",
            "3": "Ya conozco rho1, rho2 y h1 de un modelo de dos capas",
        },
        default="1",
    )

    soil: Union[SoilModel, TwoLayerSoilModel]

    if choice == "1":
        rho = ask_float("Resistividad del suelo (Ohm*m)", min_value=0)
        soil = SoilModel(rho=rho)
    elif choice == "2":
        measurements = _collect_wenner_measurements()
        fit = fit_two_layer_model(measurements)
        print(
            f"\nAjuste: rho1={fit.rho1:.1f} Ohm*m, rho2={fit.rho2:.1f} Ohm*m, "
            f"h1={fit.h1:.2f} m (error residual: {fit.residual:.4f})"
        )
        soil = TwoLayerSoilModel(rho1=fit.rho1, rho2=fit.rho2, h1=fit.h1)
    else:
        rho1 = ask_float("Resistividad de la capa superior rho1 (Ohm*m)", min_value=0)
        rho2 = ask_float("Resistividad de la capa inferior rho2 (Ohm*m)", min_value=0)
        h1 = ask_float("Espesor de la capa superior h1 (m)", min_value=0)
        soil = TwoLayerSoilModel(rho1=rho1, rho2=rho2, h1=h1)

    if ask_yes_no("¿Vas a usar una capa superficial de grava/material aislante?", default=False):
        soil.rho_s = ask_float("Resistividad de la capa superficial (Ohm*m)", min_value=0)
        soil.h_s = ask_float("Espesor de la capa superficial (m)", default=0.1, min_value=0)

    return soil


def _collect_wenner_measurements() -> List[Tuple[float, float]]:
    print("Ingresá las mediciones del ensayo de Wenner.")
    print("Dejá el espaciamiento vacío cuando termines (mínimo 3 mediciones).")
    measurements: List[Tuple[float, float]] = []
    while True:
        raw_a = input(
            f"  Medición {len(measurements) + 1} - espaciamiento a en m [enter para terminar]: "
        ).strip()
        if not raw_a:
            if len(measurements) >= 3:
                return measurements
            print("  → Necesitás al menos 3 mediciones.")
            continue
        try:
            a = float(raw_a)
            rho_a = float(input(f"  Medición {len(measurements) + 1} - resistividad medida en Ohm*m: ").strip())
        except ValueError:
            print("  → Valores inválidos, probá de nuevo.")
            continue
        measurements.append((a, rho_a))


def collect_grid_geometry() -> GridGeometry:
    print("\n--- Geometría de la malla ---")
    Lx = ask_float("Largo del terreno disponible en X (m)", min_value=0)
    Ly = ask_float("Largo del terreno disponible en Y (m)", min_value=0)
    h = ask_float("Profundidad de enterramiento (m)", default=0.5, min_value=0)
    d = ask_float("Diámetro del conductor (m)", default=0.01, min_value=0)
    n_x = ask_int("Número de conductores paralelos en X", default=5, min_value=2)
    n_y = ask_int("Número de conductores paralelos en Y", default=5, min_value=2)

    n_rods, L_rod, rods_on_perimeter = 0, 0.0, True
    if ask_yes_no("¿Vas a usar varillas de puesta a tierra?", default=True):
        n_rods = ask_int("Número de varillas", default=4, min_value=1)
        L_rod = ask_float("Longitud de cada varilla (m)", default=3.0, min_value=0)
        rods_on_perimeter = ask_yes_no("¿Las varillas están en el perímetro/esquinas?", default=True)

    return GridGeometry(
        Lx=Lx, Ly=Ly, h=h, d=d, n_x=n_x, n_y=n_y,
        n_rods=n_rods, L_rod=L_rod, rods_on_perimeter=rods_on_perimeter,
    )


def collect_fault_data() -> FaultData:
    print("\n--- Datos de falla ---")
    If_sym = ask_float("Corriente de falla simétrica a tierra (A)", min_value=0)
    Sf = ask_float("Factor de división de corriente Sf (0-1]", default=1.0, min_value=0)
    tf = ask_float("Duración de la falla (s)", default=0.5, min_value=0)
    ts = ask_float("Tiempo de exposición al choque (s)", default=tf, min_value=0)
    X_R = ask_float("Relación X/R", default=15.0, min_value=0)
    freq = ask_float("Frecuencia del sistema (Hz)", default=60.0, min_value=0)
    Cp = ask_float("Factor de crecimiento futuro Cp", default=1.0, min_value=0)

    return FaultData(If_sym=If_sym, Sf=Sf, tf=tf, ts=ts, X_R=X_R, freq=freq, Cp=Cp)


def collect_project_info() -> ProjectInfo:
    print("\n--- Datos del proyecto (para la memoria de cálculo) ---")
    return ProjectInfo(
        project_name=ask_text("Nombre del proyecto", default="Proyecto sin nombre"),
        location=ask_text("Ubicación", default=""),
        client=ask_text("Cliente", default=""),
        prepared_by=ask_text("Preparado por", default=""),
    )


def run_design_for(
    soil: Union[SoilModel, TwoLayerSoilModel], grid: GridGeometry, fault: FaultData, body_kg: float
) -> DesignResult:
    if isinstance(soil, TwoLayerSoilModel):
        return run_design_check_two_layer(soil, grid, fault, body_kg=body_kg)
    return run_design_check(soil, grid, fault, body_kg=body_kg)


def print_result(result: DesignResult) -> None:
    print("\n=== Resultado ===")
    print(f"Rg:  {result.Rg:.3f} Ohm")
    print(f"IG:  {result.IG:.1f} A")
    print(f"GPR: {result.GPR:.1f} V")
    print(
        f"Em:  {result.Em:.1f} V  (tolerable: {result.E_touch_tolerable:.1f} V)  "
        f"-> {'CUMPLE' if result.mesh_ok else 'NO CUMPLE'}"
    )
    print(
        f"Es:  {result.Es:.1f} V  (tolerable: {result.E_step_tolerable:.1f} V)  "
        f"-> {'CUMPLE' if result.step_ok else 'NO CUMPLE'}"
    )
    print(f"\nVEREDICTO: {'PASA' if result.passes else 'NO PASA'}")
    if result.notes:
        print("\nNotas:")
        for note in result.notes:
            print(f"  - {note}")


def run_wizard(output_dir: Optional[str] = None) -> Tuple[DesignResult, Optional[str]]:
    """
    Corre el modelador completo. Separado de main() para poder
    testearlo (inyectando output_dir y simulando input()) sin depender
    de rutas fijas ni de parsear stdout.

    Devuelve (DesignResult final, ruta del informe generado o None si
    no se generó).
    """
    print("=" * 60)
    print("Modelador determinista de puesta a tierra (IEEE 80)")
    print("Sin LLM -- todos los cálculos son el motor normativo directo.")
    print("=" * 60)

    soil = collect_soil_model()
    fault = collect_fault_data()
    body_kg = 70.0 if ask_yes_no("¿Usar peso corporal de 70 kg? (si no, se usa 50 kg)", default=False) else 50.0

    grid: GridGeometry
    result: DesignResult
    while True:
        grid = collect_grid_geometry()
        result = run_design_for(soil, grid, fault, body_kg)
        print_result(result)

        if result.passes:
            print("\n✅ El diseño cumple la norma.")
            break

        print(
            "\nEl diseño no cumple. Palancas típicas para mejorar: más "
            "conductores (n_x/n_y), más varillas, mayor profundidad, o "
            "una capa superficial de grava (sube la tensión tolerable)."
        )
        if not ask_yes_no("¿Querés ajustar la geometría y volver a intentar?", default=True):
            print("Seguimos con este resultado (no cumple).")
            break

    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "output")
    os.makedirs(output_dir, exist_ok=True)

    report_path = None
    if ask_yes_no("\n¿Generar la memoria de cálculo en Word?", default=True):
        project_info = collect_project_info()
        report_path = os.path.join(output_dir, "memoria_de_calculo_wizard.docx")
        build_calculation_report(soil, grid, fault, result, report_path, project_info=project_info)
        print(f"\n📄 Memoria de cálculo generada en: {report_path}")

    print("\n⚠️ Este resultado requiere revisión y firma de un ingeniero eléctrico habilitado.")

    return result, report_path


def main():
    run_wizard()


if __name__ == "__main__":
    main()
