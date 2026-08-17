"""
Factor de decremento (Df) — IEEE Std 80-2013, Sección 11.3.

Da cuenta de la componente DC de la corriente de falla (offset asimétrico)
durante el tiempo de despeje de la falla.
"""

import math

from .models import FaultData


def dc_time_constant(fault: FaultData) -> float:
    """
    Constante de tiempo Ta [s]. IEEE 80-2013 Ec. 74.

    Ta = X/R / (2*pi*f)
    """
    return fault.X_R / (2 * math.pi * fault.freq)


def decrement_factor(fault: FaultData) -> float:
    """
    Factor de decremento Df. IEEE 80-2013 Ec. 73.

    Df = sqrt(1 + (Ta/tf) * (1 - exp(-2*tf/Ta)))

    Df >= 1 siempre; tiende a 1 para fallas de duración larga (tf >> Ta).
    """
    Ta = dc_time_constant(fault)
    tf = fault.tf

    return math.sqrt(1 + (Ta / tf) * (1 - math.exp(-2 * tf / Ta)))


def grid_current(fault: FaultData) -> float:
    """
    Corriente máxima de malla IG [A]. IEEE 80-2013 Ec. 68 (forma simplificada).

    IG = Df * Sf * If_sym * Cp
    """
    Df = decrement_factor(fault)
    return Df * fault.Sf * fault.If_sym * fault.Cp
