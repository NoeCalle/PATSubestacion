"""
Modelo de suelo de dos capas horizontales — IEEE Std 80-2013, Sección 13.4
(interpretación de mediciones de resistividad de campo).

Contenido:
1. Factor de reflexión K (bien establecido, fórmula cerrada).
2. Resistividad aparente de Wenner para suelo de dos capas (fórmula
   cerrada, bien establecida en la literatura — Sunde). Se valida con
   un test de límites físicos: a->0 debe dar rho1, a->infinito debe
   dar rho2.
3. Ajuste (curve fitting) de rho1, rho2, h1 a partir de datos de campo
   (ensayo de Wenner de 4 puntas) — optimización numérica sin
   dependencias externas (sin scipy), por búsqueda en grilla +
   descenso coordinado.
4. Aproximación práctica de resistividad efectiva para usar en el
   motor de cálculo normativo (Rg, Em, Es) cuando el suelo es de dos
   capas.

⚠️ IMPORTANTE — alcance y limitaciones:
El punto (4) es una APROXIMACIÓN DE INGENIERÍA, no una fórmula literal
única de IEEE 80. Distintas referencias/software (CDEGS, ETAP, etc.)
usan métodos más rigurosos (elementos finitos, métodos de imágenes
multicapa). Para diseños críticos, esta aproximación debe contrastarse
con software especializado o el criterio del ingeniero revisor antes
de firmar el informe final.
"""

import math
from dataclasses import dataclass
from typing import List, Tuple, Optional

from .models import TwoLayerSoilModel, GridGeometry


# ---------------------------------------------------------------------
# 1. Factor de reflexión
# ---------------------------------------------------------------------

def reflection_factor(rho1: float, rho2: float) -> float:
    """K = (rho2 - rho1) / (rho2 + rho1)."""
    return (rho2 - rho1) / (rho2 + rho1)


# ---------------------------------------------------------------------
# 2. Resistividad aparente de Wenner (modelo directo / forward model)
# ---------------------------------------------------------------------

def wenner_apparent_resistivity(
    rho1: float, rho2: float, h1: float, a: float, n_terms: int = 100
) -> float:
    """
    Resistividad aparente medida por el método de Wenner (4 puntas,
    espaciamiento 'a') sobre un suelo de dos capas.

    rho_a(a) = rho1 * { 1 + 4 * sum_{n=1}^{N} [
                   K^n / sqrt(1 + (2*n*h1/a)^2)
                 - K^n / sqrt(4 + (2*n*h1/a)^2)
               ] }

    Comportamiento físico esperado (y verificado en tests):
        a -> 0        =>  rho_a -> rho1 (mide solo la capa superior)
        a -> infinito  =>  rho_a -> rho2 (penetra hasta la capa inferior)
    """
    if a <= 0:
        raise ValueError("El espaciamiento 'a' debe ser > 0")

    K = reflection_factor(rho1, rho2)

    total = 0.0
    for n in range(1, n_terms + 1):
        x = 2 * n * h1 / a
        term = K ** n * (1 / math.sqrt(1 + x ** 2) - 1 / math.sqrt(4 + x ** 2))
        total += term
        # Corte anticipado si la serie ya convergió (términos despreciables)
        if abs(term) < 1e-12 and n > 5:
            break

    return rho1 * (1 + 4 * total)


# ---------------------------------------------------------------------
# 3. Ajuste de rho1, rho2, h1 a partir de datos de campo (Wenner)
# ---------------------------------------------------------------------

@dataclass
class TwoLayerFitResult:
    rho1: float
    rho2: float
    h1: float
    residual: float  # error cuadrático medio relativo final


def _fit_residual(
    measurements: List[Tuple[float, float]], rho1: float, rho2: float, h1: float
) -> float:
    """Error cuadrático medio relativo entre modelo y mediciones."""
    err_sq = 0.0
    for a, rho_measured in measurements:
        rho_model = wenner_apparent_resistivity(rho1, rho2, h1, a)
        rel_err = (rho_model - rho_measured) / rho_measured
        err_sq += rel_err ** 2
    return err_sq / len(measurements)


def fit_two_layer_model(
    measurements: List[Tuple[float, float]],
    rho1_bounds: Tuple[float, float] = (1.0, 100000.0),
    rho2_bounds: Tuple[float, float] = (1.0, 100000.0),
    h1_bounds: Tuple[float, float] = (0.1, 50.0),
    coarse_steps: int = 15,
    refine_iterations: int = 40,
) -> TwoLayerFitResult:
    """
    Ajusta (rho1, rho2, h1) a mediciones de campo del ensayo de Wenner
    (lista de tuplas (espaciamiento_a, resistividad_aparente_medida)).

    Estrategia (sin dependencias externas tipo scipy):
      1. Búsqueda gruesa en grilla log-espaciada sobre los 3 parámetros.
      2. Refinamiento por descenso coordinado (coordinate descent) con
         paso decreciente, minimizando el error cuadrático medio relativo.

    Requiere al menos 3 mediciones a distintos espaciamientos para que
    el ajuste tenga sentido (idealmente 5+, cubriendo un rango amplio
    de 'a' para capturar bien ambas capas).
    """
    if len(measurements) < 3:
        raise ValueError(
            "Se requieren al menos 3 mediciones (a, rho_medida) para ajustar "
            "un modelo de dos capas de forma confiable"
        )

    def log_space(lo, hi, n):
        log_lo, log_hi = math.log10(lo), math.log10(hi)
        return [10 ** (log_lo + (log_hi - log_lo) * i / (n - 1)) for i in range(n)]

    rho1_candidates = log_space(*rho1_bounds, coarse_steps)
    rho2_candidates = log_space(*rho2_bounds, coarse_steps)
    h1_candidates = log_space(*h1_bounds, coarse_steps)

    best = None
    best_err = float("inf")

    for rho1 in rho1_candidates:
        for rho2 in rho2_candidates:
            for h1 in h1_candidates:
                err = _fit_residual(measurements, rho1, rho2, h1)
                if err < best_err:
                    best_err = err
                    best = (rho1, rho2, h1)

    rho1, rho2, h1 = best

    # Refinamiento por descenso coordinado (paso multiplicativo decreciente)
    step_factor = 1.5
    for _ in range(refine_iterations):
        improved = False
        for idx in range(3):
            current = [rho1, rho2, h1]
            for direction in (step_factor, 1 / step_factor):
                trial = current.copy()
                trial[idx] *= direction
                # Mantener dentro de límites físicos razonables
                trial[idx] = max(trial[idx], 0.01)
                err = _fit_residual(measurements, *trial)
                if err < best_err:
                    best_err = err
                    rho1, rho2, h1 = trial
                    improved = True
        step_factor = 1 + (step_factor - 1) * 0.7  # reduce el paso
        if not improved and step_factor < 1.001:
            break

    return TwoLayerFitResult(rho1=rho1, rho2=rho2, h1=h1, residual=best_err)


# ---------------------------------------------------------------------
# 4. Aproximación de resistividad efectiva para diseño de malla
# ---------------------------------------------------------------------

def effective_design_resistivity(
    soil: TwoLayerSoilModel, grid: GridGeometry
) -> Tuple[float, str]:
    """
    APROXIMACIÓN DE INGENIERÍA (no fórmula literal única de IEEE 80).

    Estima una resistividad "efectiva" uniforme para usar en Rg/Em/Es,
    evaluando la resistividad aparente de Wenner a un espaciamiento
    representativo del tamaño de la malla (radio equivalente del área
    de la malla: a_eff = sqrt(Area/pi)).

    Racional: la profundidad de penetración de corriente de una malla
    de puesta a tierra escala aproximadamente con su dimensión lateral,
    de forma similar a como el espaciamiento de sondas Wenner determina
    la profundidad de penetración de la medición. Es una heurística
    razonable para diseño preliminar, NO un reemplazo de un análisis
    numérico riguroso (elementos finitos / software especializado).

    Devuelve (rho_efectiva, nota_explicativa).
    """
    a_eff = math.sqrt(grid.area / math.pi)
    rho_eff = wenner_apparent_resistivity(soil.rho1, soil.rho2, soil.h1, a_eff)

    note = (
        f"Resistividad efectiva ({rho_eff:.1f} Ω·m) estimada por aproximación "
        f"de radio equivalente (a_eff={a_eff:.1f} m) sobre modelo de dos capas "
        f"(ρ1={soil.rho1:.1f}, ρ2={soil.rho2:.1f}, h1={soil.h1:.1f} m). "
        "Esta es una aproximación de ingeniería para diseño preliminar — "
        "para el informe final se recomienda contrastar con software "
        "especializado (ej. CDEGS, ETAP) o el criterio del ingeniero revisor."
    )

    return rho_eff, note
