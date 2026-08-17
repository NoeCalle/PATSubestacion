"""
Factores geométricos para tensión de malla (Em) y de paso (Es).
IEEE Std 80-2013, Sección 16.5.

Nota de alcance: las fórmulas de n_b, n_c, n_d asumen malla rectangular
regular (caso más común). Para geometrías muy irregulares, IEEE 80
recomienda métodos numéricos — fuera del alcance de esta primera fase.
"""

import math

from .models import GridGeometry


def geometric_factor_n(grid: GridGeometry) -> float:
    """
    Factor geométrico compuesto n = na * nb * nc * nd. IEEE 80-2013 Ec. 82-85.

    na = 2*Lc / Lp
    nb = sqrt(Lp / (4*sqrt(A)))          (= 1 para malla cuadrada)
    nc = [(Lx*Ly) / A] ** (0.7*A/(Lx*Ly))  (= 1 para malla rectangular simple,
                                             ya que Lx*Ly = A en grilla regular)
    nd = Dm / sqrt(Lx^2 + Ly^2)            (= 1 para malla simétrica, Dm = diagonal)
    """
    Lc = grid.Lc
    Lp = grid.Lp
    A = grid.area
    Lx, Ly = grid.Lx, grid.Ly

    na = 2 * Lc / Lp
    nb = math.sqrt(Lp / (4 * math.sqrt(A)))

    # Para grilla rectangular regular, Lx*Ly == A, por lo que nc = 1.
    # Se deja la fórmula general por completitud si en el futuro se
    # soportan geometrías en forma de L u otras no rectangulares.
    nc = ((Lx * Ly) / A) ** (0.7 * A / (Lx * Ly)) if Lx * Ly != A else 1.0

    Dm = grid.Dm
    nd = Dm / math.sqrt(Lx ** 2 + Ly ** 2)

    return na * nb * nc * nd


def irregularity_factor_Ki(n: float) -> float:
    """
    Factor de irregularidad Ki. IEEE 80-2013 Ec. 89.

    Ki = 0.644 + 0.148*n
    """
    return 0.644 + 0.148 * n


def corrective_weighting_Kii(grid: GridGeometry) -> float:
    """
    Factor de ponderación corrector Kii. IEEE 80-2013 Ec. 87.

    Kii = 1                     si hay varillas en el perímetro/esquinas
                                 (o distribuidas en toda la malla)
    Kii = 1 / (2*n)^(2/n)       si NO hay varillas, o solo hay varillas
                                 en el centro (no en el perímetro)

    n: número equivalente de conductores paralelos (se aproxima con
       sqrt(n_x * n_y) para mallas rectangulares regulares).
    """
    if grid.n_rods > 0 and grid.rods_on_perimeter:
        return 1.0

    n_eq = math.sqrt(grid.n_x * grid.n_y)
    return 1 / ((2 * n_eq) ** (2 / n_eq))


def corrective_weighting_Kh(grid: GridGeometry, h0: float = 1.0) -> float:
    """
    Factor de ponderación por profundidad Kh. IEEE 80-2013 Ec. 88.

    Kh = sqrt(1 + h/h0)   con h0 = 1 m (profundidad de referencia)
    """
    return math.sqrt(1 + grid.h / h0)


def mesh_geometric_factor_Km(grid: GridGeometry, Kii: float, Kh: float) -> float:
    """
    Factor geométrico de malla Km. IEEE 80-2013 Ec. 86.

    Km = (1/(2*pi)) * [ ln( D^2/(16*h*d) + (D+2h)^2/(8*D*d) - h/(4*d) )
                         + (Kii/Kh) * ln( 8 / (pi*(2*n-1)) ) ]

    D: espaciamiento promedio entre conductores paralelos (se aproxima
       como el promedio de Lx/(n_x-1) y Ly/(n_y-1)).
    """
    h = grid.h
    d = grid.d

    Dx = grid.Lx / (grid.n_x - 1)
    Dy = grid.Ly / (grid.n_y - 1)
    D = (Dx + Dy) / 2

    n = geometric_factor_n(grid)

    term1 = math.log(
        (D ** 2) / (16 * h * d)
        + ((D + 2 * h) ** 2) / (8 * D * d)
        - h / (4 * d)
    )
    term2 = (Kii / Kh) * math.log(8 / (math.pi * (2 * n - 1)))

    return (1 / (2 * math.pi)) * (term1 + term2)


def step_geometric_factor_Ks(grid: GridGeometry) -> float:
    """
    Factor geométrico de paso Ks. IEEE 80-2013 Ec. 90.

    Ks = (1/pi) * [ 1/(2*h) + 1/(D+h) + (1/D)*(1 - 0.5^(n-2)) ]
    """
    h = grid.h
    Dx = grid.Lx / (grid.n_x - 1)
    Dy = grid.Ly / (grid.n_y - 1)
    D = (Dx + Dy) / 2

    n = geometric_factor_n(grid)

    return (1 / math.pi) * (
        1 / (2 * h) + 1 / (D + h) + (1 / D) * (1 - 0.5 ** (n - 2))
    )


def effective_length_Lm(grid: GridGeometry) -> float:
    """
    Longitud efectiva enterrada para tensión de malla Lm [m]. IEEE 80-2013 Ec. 92.

    Si hay varillas en el perímetro/esquinas:
        Lm = Lc + [1.55 + 1.22*(Lr / sqrt(Lx^2 + Ly^2))] * Lr_total
    Si no hay varillas:
        Lm = Lc + Lr_total (simplificación, Lr_total = 0 si no hay varillas)
    """
    Lc = grid.Lc
    Lr_total = grid.Lr

    if grid.n_rods > 0 and grid.rods_on_perimeter:
        Dm = grid.Dm
        factor = 1.55 + 1.22 * (grid.L_rod / Dm) if Dm > 0 else 1.55
        return Lc + factor * Lr_total

    return Lc + Lr_total


def effective_length_Ls(grid: GridGeometry) -> float:
    """
    Longitud efectiva enterrada para tensión de paso Ls [m]. IEEE 80-2013 Ec. 93.

    Ls = 0.75*Lc + 0.85*Lr_total
    """
    return 0.75 * grid.Lc + 0.85 * grid.Lr
