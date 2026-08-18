"""
Renderizado ESTÁTICO (imágenes PNG) del perfil de potencial.

Distinto de plot3d.py (que genera un dashboard HTML interactivo con
plotly): Word no puede mostrar HTML/JavaScript, así que para embeber
las vistas 3D en el informe (src/reporting) necesitamos imágenes fijas.
Usa matplotlib en vez de plotly+kaleido para mantener el repo
instalable con dependencias puramente Python, sin binarios nativos
adicionales.

Este módulo tampoco calcula nada -- solo renderiza el output de
src/engine/potential_profile.py, igual que plot3d.py.
"""

import os
from typing import Dict, Optional

import matplotlib
matplotlib.use("Agg")  # backend sin display -- necesario para correr en servidores/CI
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  (requerido para projection="3d")
import numpy as np

from ..engine.potential_profile import PotentialFieldResult
from ..engine.models import GridGeometry

VIEW_LABELS = {
    "potential": "Potencial de superficie",
    "touch": "Tensión de contacto aproximada",
    "step": "Tensión de paso aproximada",
}


def _render_surface(
    X: np.ndarray, Y: np.ndarray, Z: np.ndarray,
    title: str, zlabel: str, cmap: str,
    grid: GridGeometry, output_path: str,
) -> str:
    XX, YY = np.meshgrid(X, Y)

    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111, projection="3d")
    surf = ax.plot_surface(XX, YY, Z, cmap=cmap, linewidth=0, antialiased=True, alpha=0.92)

    # Referencia visual de los conductores de la malla, proyectados en la base
    z_base = float(np.min(Z))
    Dx = grid.Lx / (grid.n_x - 1)
    for i in range(grid.n_x):
        x = i * Dx
        ax.plot([x, x], [0, grid.Ly], [z_base, z_base], color="black", linewidth=0.8)
    Dy = grid.Ly / (grid.n_y - 1)
    for j in range(grid.n_y):
        y = j * Dy
        ax.plot([0, grid.Lx], [y, y], [z_base, z_base], color="black", linewidth=0.8)

    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_zlabel(zlabel)
    ax.set_title(title, fontsize=11)
    fig.colorbar(surf, shrink=0.6, aspect=12, label=zlabel)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)

    return output_path


def render_static_views(
    field: PotentialFieldResult,
    grid: GridGeometry,
    output_dir: str,
    touch_field: Optional[np.ndarray] = None,
    step_field: Optional[np.ndarray] = None,
) -> Dict[str, str]:
    """
    Genera imágenes PNG estáticas del perfil de potencial (y,
    opcionalmente, de las tensiones de contacto y de paso derivadas),
    listas para embeber en el informe Word.

    Devuelve un dict {"potential": ruta, "touch": ruta, "step": ruta}
    -- las claves "touch"/"step" solo aparecen si se pasaron esos campos.
    """
    os.makedirs(output_dir, exist_ok=True)
    paths: Dict[str, str] = {}

    paths["potential"] = _render_surface(
        field.X, field.Y, field.V,
        VIEW_LABELS["potential"], "Potencial (V)", "viridis",
        grid, os.path.join(output_dir, "potential_3d.png"),
    )

    if touch_field is not None:
        paths["touch"] = _render_surface(
            field.X, field.Y, touch_field,
            VIEW_LABELS["touch"], "Tensión (V)", "inferno",
            grid, os.path.join(output_dir, "touch_voltage_3d.png"),
        )

    if step_field is not None:
        paths["step"] = _render_surface(
            field.X, field.Y, step_field,
            VIEW_LABELS["step"], "Tensión (V)", "plasma",
            grid, os.path.join(output_dir, "step_voltage_3d.png"),
        )

    return paths
