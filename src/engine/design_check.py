"""
Cálculo integrado de tensión de malla (Em), tensión de paso (Es), GPR,
y verificación normativa contra tensiones tolerables — IEEE Std 80-2013.

Este es el punto de entrada principal del motor de cálculo normativo.
Los agentes (designer, reviewer) deben llamar a `run_design_check()`
en vez de reimplementar fórmulas.
"""

from .models import SoilModel, GridGeometry, FaultData, DesignResult, TwoLayerSoilModel
from .soil_two_layer import effective_design_resistivity
from .tolerable_voltages import (
    surface_derating_factor,
    tolerable_step_voltage,
    tolerable_touch_voltage,
)
from .decrement_factor import decrement_factor, grid_current
from .grid_resistance import sverak_resistance
from .geometric_factors import (
    geometric_factor_n,
    irregularity_factor_Ki,
    corrective_weighting_Kii,
    corrective_weighting_Kh,
    mesh_geometric_factor_Km,
    step_geometric_factor_Ks,
    effective_length_Lm,
    effective_length_Ls,
)


def mesh_voltage_Em(soil: SoilModel, IG: float, Km: float, Ki: float, Lm: float) -> float:
    """Tensión de malla Em [V]. IEEE 80-2013 Ec. 91. Em = (rho*Km*Ki*IG) / Lm"""
    return (soil.rho * Km * Ki * IG) / Lm


def step_voltage_Es(soil: SoilModel, IG: float, Ks: float, Ki: float, Ls: float) -> float:
    """Tensión de paso Es [V]. IEEE 80-2013 Ec. 92 (numeración según edición). Es = (rho*Ks*Ki*IG) / Ls"""
    return (soil.rho * Ks * Ki * IG) / Ls


def run_design_check(
    soil: SoilModel,
    grid: GridGeometry,
    fault: FaultData,
    body_kg: float = 50,
) -> DesignResult:
    """
    Ejecuta el cálculo normativo IEEE 80 completo para una configuración
    de malla dada, y devuelve un DesignResult con el veredicto pass/fail.

    body_kg: 50 o 70 (peso corporal de referencia para tensiones tolerables)
    """
    notes = []

    # --- Tensiones tolerables ---
    Cs = surface_derating_factor(soil)
    E_touch_tol = tolerable_touch_voltage(soil, fault.ts, body_kg, Cs=Cs)
    E_step_tol = tolerable_step_voltage(soil, fault.ts, body_kg, Cs=Cs)

    # --- Corriente de diseño y resistencia ---
    Df = decrement_factor(fault)
    IG = grid_current(fault)
    Rg = sverak_resistance(soil, grid)
    GPR = IG * Rg

    if GPR <= max(E_touch_tol, E_step_tol):
        notes.append(
            "GPR <= tensión tolerable máxima: en rigor no sería necesario "
            "verificar Em/Es (todo el predio queda por debajo del límite), "
            "pero se calculan igual por completitud y trazabilidad."
        )

    # --- Factores geométricos ---
    n = geometric_factor_n(grid)
    Ki = irregularity_factor_Ki(n)
    Kii = corrective_weighting_Kii(grid)
    Kh = corrective_weighting_Kh(grid)
    Km = mesh_geometric_factor_Km(grid, Kii, Kh)
    Ks = step_geometric_factor_Ks(grid)

    Lm = effective_length_Lm(grid)
    Ls = effective_length_Ls(grid)

    # --- Tensiones resultantes ---
    Em = mesh_voltage_Em(soil, IG, Km, Ki, Lm)
    Es = step_voltage_Es(soil, IG, Ks, Ki, Ls)

    mesh_ok = Em <= E_touch_tol
    step_ok = Es <= E_step_tol

    if not mesh_ok:
        notes.append(
            f"Em ({Em:.1f} V) supera la tensión de contacto tolerable "
            f"({E_touch_tol:.1f} V). Requiere ajustar geometría "
            "(reducir espaciamiento, agregar varillas, o mejorar suelo superficial)."
        )
    if not step_ok:
        notes.append(
            f"Es ({Es:.1f} V) supera la tensión de paso tolerable "
            f"({E_step_tol:.1f} V). Requiere ajustar geometría."
        )

    return DesignResult(
        E_touch_tolerable=E_touch_tol,
        E_step_tolerable=E_step_tol,
        Cs=Cs,
        Rg=Rg,
        Df=Df,
        IG=IG,
        GPR=GPR,
        Km=Km,
        Ki=Ki,
        Kii=Kii,
        Kh=Kh,
        Ks=Ks,
        n=n,
        Em=Em,
        Es=Es,
        Lm=Lm,
        Ls=Ls,
        mesh_ok=mesh_ok,
        step_ok=step_ok,
        passes=mesh_ok and step_ok,
        notes=notes,
    )


def run_design_check_two_layer(
    soil: TwoLayerSoilModel,
    grid: GridGeometry,
    fault: FaultData,
    body_kg: float = 50,
) -> DesignResult:
    """
    Igual que `run_design_check`, pero para suelo de dos capas.

    Convierte el modelo de dos capas a una resistividad uniforme
    equivalente (ver `soil_two_layer.effective_design_resistivity` —
    es una APROXIMACIÓN de ingeniería, no una fórmula literal de la
    norma) y corre el mismo motor normativo sobre esa resistividad
    equivalente. La nota explicativa queda registrada en el resultado.
    """
    rho_eff, note = effective_design_resistivity(soil, grid)

    equivalent_soil = SoilModel(rho=rho_eff, rho_s=soil.rho_s, h_s=soil.h_s)
    result = run_design_check(equivalent_soil, grid, fault, body_kg=body_kg)
    result.notes.insert(0, note)

    return result
