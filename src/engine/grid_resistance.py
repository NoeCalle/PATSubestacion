"""
Resistencia de puesta a tierra de la malla — IEEE Std 80-2013, Sección 14.2.

Fórmula de Sverak (Ec. 80), la más usada en la práctica de ingeniería
porque converge bien y solo requiere geometría básica (área, longitud
total de conductor, profundidad).
"""

import math

from .models import SoilModel, GridGeometry


def sverak_resistance(soil: SoilModel, grid: GridGeometry) -> float:
    """
    Resistencia de la malla Rg [Ohm]. IEEE 80-2013 Ec. 80.

    Rg = rho * [ 1/Lt + 1/sqrt(20*A) * (1 + 1/(1 + h*sqrt(20/A))) ]

    donde:
        rho = resistividad del suelo [Ohm*m]
        Lt  = longitud total de conductor enterrado (malla + varillas) [m]
        A   = área de la malla [m^2]
        h   = profundidad de enterramiento [m]
    """
    rho = soil.rho
    Lt = grid.Lt
    A = grid.area
    h = grid.h

    term1 = 1 / Lt
    term2 = (1 / math.sqrt(20 * A)) * (1 + 1 / (1 + h * math.sqrt(20 / A)))

    return rho * (term1 + term2)
