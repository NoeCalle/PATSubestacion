"""
Modelos de datos (inputs/outputs) para el motor de cálculo IEEE 80.

Todas las unidades en Sistema Internacional salvo que se indique lo contrario:
- Longitudes en metros [m]
- Resistividad en ohm-metro [Ω·m]
- Corrientes en Amperios [A]
- Tiempos en segundos [s]
- Tensiones en Volts [V]
- Resistencias en Ohms [Ω]
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SoilModel:
    """Modelo de suelo uniforme (fase 1). Modelo de dos capas se agrega en fase 2."""
    rho: float  # Resistividad del suelo [Ω·m]
    rho_s: Optional[float] = None  # Resistividad de la capa superficial (grava, etc.) [Ω·m]
    h_s: float = 0.0  # Espesor de la capa superficial [m]

    def __post_init__(self):
        if self.rho <= 0:
            raise ValueError("La resistividad del suelo (rho) debe ser > 0")
        if self.rho_s is not None and self.rho_s <= 0:
            raise ValueError("La resistividad de superficie (rho_s) debe ser > 0")
        if self.h_s < 0:
            raise ValueError("El espesor de la capa superficial (h_s) no puede ser negativo")


@dataclass
class GridGeometry:
    """Geometría de la malla de puesta a tierra (rectangular, con o sin varillas)."""
    Lx: float  # Longitud de la malla en dirección X [m]
    Ly: float  # Longitud de la malla en dirección Y [m]
    h: float  # Profundidad de enterramiento de la malla [m]
    d: float  # Diámetro del conductor de la malla [m]
    n_x: int  # Número de conductores paralelos en dirección X
    n_y: int  # Número de conductores paralelos en dirección Y
    n_rods: int = 0  # Número de varillas (jabalinas) de puesta a tierra
    L_rod: float = 0.0  # Longitud de cada varilla [m]
    rods_on_perimeter: bool = True  # True si hay varillas en el perímetro/esquinas

    def __post_init__(self):
        if self.Lx <= 0 or self.Ly <= 0:
            raise ValueError("Lx y Ly deben ser > 0")
        if self.h <= 0:
            raise ValueError("La profundidad h debe ser > 0")
        if self.d <= 0:
            raise ValueError("El diámetro del conductor d debe ser > 0")
        if self.n_x < 2 or self.n_y < 2:
            raise ValueError("n_x y n_y deben ser >= 2 (al menos 2 conductores por dirección)")
        if self.n_rods < 0:
            raise ValueError("n_rods no puede ser negativo")
        if self.n_rods > 0 and self.L_rod <= 0:
            raise ValueError("Si hay varillas (n_rods > 0), L_rod debe ser > 0")

    @property
    def area(self) -> float:
        return self.Lx * self.Ly

    @property
    def Lc(self) -> float:
        """Longitud total de conductores de la malla (sin varillas)."""
        return self.n_x * self.Ly + self.n_y * self.Lx

    @property
    def Lp(self) -> float:
        """Perímetro de la malla."""
        return 2 * (self.Lx + self.Ly)

    @property
    def Lr(self) -> float:
        """Longitud total de varillas."""
        return self.n_rods * self.L_rod

    @property
    def Lt(self) -> float:
        """Longitud total de conductor enterrado (malla + varillas)."""
        return self.Lc + self.Lr

    @property
    def Dm(self) -> float:
        """Distancia máxima entre dos puntos de la malla (diagonal)."""
        return (self.Lx ** 2 + self.Ly ** 2) ** 0.5


@dataclass
class FaultData:
    """Datos de falla eléctrica para el diseño."""
    If_sym: float  # Corriente de falla simétrica a tierra [A] (rms)
    Sf: float = 1.0  # Factor de división de corriente (fracción que retorna por la malla), 0 < Sf <= 1
    tf: float = 0.5  # Duración de la falla para el factor de decremento [s]
    ts: float = 0.5  # Tiempo de exposición al choque (para tensiones tolerables) [s]
    X_R: float = 15.0  # Relación X/R en el punto de falla
    freq: float = 60.0  # Frecuencia del sistema [Hz]
    Cp: float = 1.0  # Factor de crecimiento futuro de la subestación

    def __post_init__(self):
        if self.If_sym <= 0:
            raise ValueError("If_sym debe ser > 0")
        if not (0 < self.Sf <= 1):
            raise ValueError("Sf debe estar en el rango (0, 1]")
        if self.tf <= 0 or self.ts <= 0:
            raise ValueError("tf y ts deben ser > 0")
        if self.X_R < 0:
            raise ValueError("X_R no puede ser negativo")
        if self.freq <= 0:
            raise ValueError("freq debe ser > 0")


@dataclass
class BodyWeight:
    """Peso corporal de referencia para tensiones tolerables (IEEE 80 usa 50 kg y 70 kg)."""
    kg: float

    def __post_init__(self):
        if self.kg not in (50, 70):
            raise ValueError("IEEE 80 solo define constantes para 50 kg y 70 kg")


@dataclass
class DesignResult:
    """Resultado completo del cálculo normativo IEEE 80."""
    # Tensiones tolerables
    E_touch_tolerable: float
    E_step_tolerable: float
    Cs: float

    # Resistencia y GPR
    Rg: float
    Df: float
    IG: float
    GPR: float

    # Factores geométricos
    Km: float
    Ki: float
    Kii: float
    Kh: float
    Ks: float
    n: float

    # Tensiones resultantes
    Em: float
    Es: float
    Lm: float
    Ls: float

    # Verificación
    mesh_ok: bool
    step_ok: bool
    passes: bool

    notes: list = field(default_factory=list)
