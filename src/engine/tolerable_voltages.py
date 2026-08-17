"""
Tensiones tolerables de paso y contacto — IEEE Std 80-2013, Sección 8.

Referencias de fórmulas:
- Cs (factor de derating de superficie): Ec. 27
- Etouch50 / Etouch70: Ec. 32, 33
- Estep50 / Estep70: Ec. 29, 30
"""

import math

from .models import SoilModel


def surface_derating_factor(soil: SoilModel) -> float:
    """
    Factor de derating de la capa superficial (Cs). IEEE 80-2013 Ec. 27.

    Si no hay capa superficial (grava/material aislante), Cs = 1.

    Cs = 1 - [0.09 * (1 - rho/rho_s)] / (2*h_s + 0.09)
    """
    if soil.rho_s is None or soil.h_s == 0:
        return 1.0

    numerator = 0.09 * (1 - soil.rho / soil.rho_s)
    denominator = 2 * soil.h_s + 0.09
    return 1 - (numerator / denominator)


def tolerable_step_voltage(soil: SoilModel, ts: float, body_kg: float, Cs: float = None) -> float:
    """
    Tensión de paso tolerable [V]. IEEE 80-2013 Ec. 29 (50 kg) / Ec. 30 (70 kg).

    Estep = (1000 + 6*Cs*rho_s) * (k / sqrt(ts))
    k = 0.116 para 50 kg, 0.157 para 70 kg
    """
    if Cs is None:
        Cs = surface_derating_factor(soil)

    rho_s = soil.rho_s if soil.rho_s is not None else soil.rho
    k = 0.116 if body_kg == 50 else 0.157

    return (1000 + 6 * Cs * rho_s) * (k / math.sqrt(ts))


def tolerable_touch_voltage(soil: SoilModel, ts: float, body_kg: float, Cs: float = None) -> float:
    """
    Tensión de contacto tolerable [V]. IEEE 80-2013 Ec. 32 (50 kg) / Ec. 33 (70 kg).

    Etouch = (1000 + 1.5*Cs*rho_s) * (k / sqrt(ts))
    k = 0.116 para 50 kg, 0.157 para 70 kg
    """
    if Cs is None:
        Cs = surface_derating_factor(soil)

    rho_s = soil.rho_s if soil.rho_s is not None else soil.rho
    k = 0.116 if body_kg == 50 else 0.157

    return (1000 + 1.5 * Cs * rho_s) * (k / math.sqrt(ts))
