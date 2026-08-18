"""
Perfil de potencial de superficie en grilla — motor de cálculo numérico.

Complementa (no reemplaza) el cálculo normativo cerrado de Em/Es de
IEEE 80 (`design_check.py`). Este módulo resuelve un campo de potencial
completo sobre una grilla de puntos en superficie, útil para:
  - Visualización 3D del perfil de tensión (detectar zonas críticas)
  - Exploración de "puntos calientes" (esquinas, perímetro)

MÉTODO (y sus límites, documentados explícitamente):
  1. Cada conductor y varilla se discretiza en segmentos pequeños.
  2. Cada segmento se trata como una fuente de corriente puntual
     enterrada, usando el método de imágenes para un semi-espacio
     uniforme: V(x,y,0) = (rho * I_segmento) / (2*pi*r), donde r es
     la distancia 3D desde el punto de superficie hasta el segmento.
     Esta es la misma física que sustenta la derivación de Km en la
     norma (línea de corriente enterrada + su imagen especular).
  3. Se asume CORRIENTE UNIFORMEMENTE DISTRIBUIDA entre segmentos
     (proporcional a su longitud). Esta es una simplificación: en la
     realidad la densidad de corriente es mayor en el perímetro/
     esquinas de la malla. Resolverlo con precisión requeriría
     plantear y resolver un sistema lineal de resistencias mutuas
     (método de momentos) — fuera del alcance de este módulo.

  Por lo tanto: los valores puntuales de Em/Es de `design_check.py`
  (fórmulas cerradas de la norma) siguen siendo la referencia para el
  informe firmado. Este módulo es una herramienta EXPLORATORIA/VISUAL.
"""

import math
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

from .models import SoilModel, GridGeometry


# ---------------------------------------------------------------------
# Discretización de electrodos en segmentos
# ---------------------------------------------------------------------

def _discretize_line(
    x0: float, y0: float, x1: float, y1: float, depth: float, segment_length: float
) -> List[Tuple[float, float, float, float]]:
    """Discretiza un conductor recto en N segmentos de longitud igual
    (~segment_length). Devuelve lista de (x_medio, y_medio, profundidad, longitud)."""
    length_total = math.hypot(x1 - x0, y1 - y0)
    n_segments = max(1, round(length_total / segment_length))
    seg_len = length_total / n_segments

    segments = []
    for k in range(n_segments):
        t_mid = (k + 0.5) / n_segments
        xm = x0 + (x1 - x0) * t_mid
        ym = y0 + (y1 - y0) * t_mid
        segments.append((xm, ym, depth, seg_len))
    return segments


def _discretize_rod(
    x: float, y: float, h_top: float, length_rod: float, segment_length: float
) -> List[Tuple[float, float, float, float]]:
    """Discretiza una varilla vertical en N segmentos. Devuelve lista de
    (x, y, profundidad_media, longitud) — x,y fijos, profundidad variable."""
    n_segments = max(1, round(length_rod / segment_length))
    seg_len = length_rod / n_segments

    segments = []
    for k in range(n_segments):
        depth_mid = h_top + (k + 0.5) * seg_len
        segments.append((x, y, depth_mid, seg_len))
    return segments


def rod_positions(grid: GridGeometry) -> List[Tuple[float, float]]:
    """
    Distribuye las varillas uniformemente a lo largo del perímetro de
    la malla, empezando en la esquina (0,0) en sentido horario.

    ⚠️ Supuesto de disposición física: en un proyecto real, la ubicación
    exacta de cada varilla es una decisión de diseño del ingeniero, no
    algo derivable automáticamente solo de la cantidad (n_rods). Se usa
    esta distribución uniforme como aproximación razonable por defecto.
    """
    if grid.n_rods == 0:
        return []

    Lx, Ly = grid.Lx, grid.Ly
    perimeter = 2 * (Lx + Ly)

    def point_on_perimeter(dist: float) -> Tuple[float, float]:
        if dist <= Lx:
            return (dist, 0.0)
        dist -= Lx
        if dist <= Ly:
            return (Lx, dist)
        dist -= Ly
        if dist <= Lx:
            return (Lx - dist, Ly)
        dist -= Lx
        return (0.0, Ly - dist)

    return [
        point_on_perimeter(perimeter * i / grid.n_rods) for i in range(grid.n_rods)
    ]


def build_segments(
    grid: GridGeometry, segment_length: float = 2.0
) -> List[Tuple[float, float, float, float]]:
    """
    Construye la lista completa de segmentos (conductores de malla +
    varillas) para el cálculo de campo de potencial.

    Cada segmento: (x_medio, y_medio, profundidad, longitud).
    """
    segments = []

    Dx = grid.Lx / (grid.n_x - 1)
    for i in range(grid.n_x):
        x = i * Dx
        segments += _discretize_line(x, 0.0, x, grid.Ly, grid.h, segment_length)

    Dy = grid.Ly / (grid.n_y - 1)
    for j in range(grid.n_y):
        y = j * Dy
        segments += _discretize_line(0.0, y, grid.Lx, y, grid.h, segment_length)

    if grid.n_rods > 0:
        for (xr, yr) in rod_positions(grid):
            segments += _discretize_rod(xr, yr, grid.h, grid.L_rod, segment_length)

    return segments


# ---------------------------------------------------------------------
# Campo de potencial en superficie
# ---------------------------------------------------------------------

@dataclass
class PotentialFieldResult:
    X: np.ndarray  # vector de coordenadas X de la grilla de muestreo [m]
    Y: np.ndarray  # vector de coordenadas Y de la grilla de muestreo [m]
    V: np.ndarray  # matriz de potencial de superficie [V], shape (len(Y), len(X))
    n_segments: int
    total_segment_length: float  # debe aproximarse a grid.Lt (chequeo de consistencia)


def compute_surface_potential(
    soil: SoilModel,
    grid: GridGeometry,
    IG: float,
    segment_length: float = 2.0,
    sample_resolution: float = 2.0,
    margin: float = 5.0,
) -> PotentialFieldResult:
    """
    Calcula el potencial de superficie V(x,y) en una grilla de muestreo
    que cubre la malla más un margen alrededor.

    soil: debe ser un SoilModel uniforme. Para suelo de dos capas, usar
    primero `soil_two_layer.effective_design_resistivity()` para obtener
    una resistividad equivalente (misma aproximación que en design_check).
    """
    segments = build_segments(grid, segment_length)
    total_length = sum(s[3] for s in segments)

    xs = np.array([s[0] for s in segments])
    ys = np.array([s[1] for s in segments])
    depths = np.array([s[2] for s in segments])
    lengths = np.array([s[3] for s in segments])

    # Corriente uniformemente distribuida (proporcional a la longitud
    # del segmento) -- ver limitación documentada en el docstring del módulo.
    currents = IG * lengths / total_length

    x_min, x_max = -margin, grid.Lx + margin
    y_min, y_max = -margin, grid.Ly + margin
    nx = max(2, int((x_max - x_min) / sample_resolution) + 1)
    ny = max(2, int((y_max - y_min) / sample_resolution) + 1)

    X = np.linspace(x_min, x_max, nx)
    Y = np.linspace(y_min, y_max, ny)
    XX, YY = np.meshgrid(X, Y)

    V = np.zeros_like(XX)
    for xi, yi, di, Ii in zip(xs, ys, depths, currents):
        r = np.sqrt((XX - xi) ** 2 + (YY - yi) ** 2 + di ** 2)
        r = np.maximum(r, 0.1)  # evita singularidad si un punto de muestreo
                                  # cae casi exactamente sobre un electrodo
        V += (soil.rho * Ii) / (2 * np.pi * r)

    return PotentialFieldResult(
        X=X, Y=Y, V=V, n_segments=len(segments), total_segment_length=total_length
    )


# ---------------------------------------------------------------------
# Campos derivados: tensión de contacto y de paso aproximadas
# ---------------------------------------------------------------------

def touch_voltage_field(V: np.ndarray, gpr_reference: float) -> np.ndarray:
    """
    Tensión de contacto aproximada en cada punto: diferencia entre el
    GPR (potencial de la malla, asumida equipotencial) y el potencial
    de superficie en ese punto. Esta es la misma aproximación conceptual
    que usa la norma (persona tocando una estructura al potencial de
    la malla, parada en el punto x,y).
    """
    return gpr_reference - V


def step_voltage_field(X: np.ndarray, Y: np.ndarray, V: np.ndarray) -> np.ndarray:
    """
    Tensión de paso aproximada: magnitud del gradiente local de
    potencial, evaluado sobre una distancia de 1 m (diferencias finitas).
    """
    dV_dx = np.gradient(V, X, axis=1)
    dV_dy = np.gradient(V, Y, axis=0)
    grad_magnitude = np.sqrt(dV_dx ** 2 + dV_dy ** 2)
    return grad_magnitude * 1.0  # tensión aproximada para un paso de 1 m
