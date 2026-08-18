"""
Visualización 3D interactiva del perfil de potencial de superficie.

Este módulo NO calcula nada — es puramente de renderizado (toma el
output de `engine/potential_profile.py` y lo dibuja). Consistente con
la separación motor/herramienta del resto del repo: no es un agente,
no decide nada, solo presenta datos ya calculados.
"""

from typing import Optional, List, Tuple

import numpy as np
import plotly.graph_objects as go

from ..engine.potential_profile import PotentialFieldResult
from ..engine.models import GridGeometry


def _grid_conductor_traces(grid: GridGeometry, z_level: float) -> List[go.Scatter3d]:
    """
    Genera líneas 3D que representan los conductores de la malla,
    proyectadas a una altura z_level fija — sirven como referencia
    espacial visual (dónde está físicamente enterrada la malla) en el
    gráfico de potencial.
    """
    traces = []

    Dx = grid.Lx / (grid.n_x - 1)
    for i in range(grid.n_x):
        x = i * Dx
        traces.append(
            go.Scatter3d(
                x=[x, x], y=[0, grid.Ly], z=[z_level, z_level],
                mode="lines", line=dict(color="black", width=4),
                showlegend=False, hoverinfo="skip",
            )
        )

    Dy = grid.Ly / (grid.n_y - 1)
    for j in range(grid.n_y):
        y = j * Dy
        traces.append(
            go.Scatter3d(
                x=[0, grid.Lx], y=[y, y], z=[z_level, z_level],
                mode="lines", line=dict(color="black", width=4),
                showlegend=False, hoverinfo="skip",
            )
        )

    return traces


def build_potential_dashboard(
    field: PotentialFieldResult,
    grid: GridGeometry,
    touch_field: Optional[np.ndarray] = None,
    step_field: Optional[np.ndarray] = None,
    title: str = "Perfil de potencial de superficie",
) -> go.Figure:
    """
    Construye un dashboard 3D interactivo con un selector (dropdown)
    para alternar entre: potencial de superficie V(x,y), tensión de
    contacto aproximada, y tensión de paso aproximada (los dos últimos
    son opcionales).

    Cada superficie incluye una referencia visual de los conductores
    de la malla proyectados en su base.
    """
    surfaces: List[Tuple[str, np.ndarray, str]] = [
        ("Potencial de superficie V(x,y)", field.V, "Viridis"),
    ]
    if touch_field is not None:
        surfaces.append(("Tensión de contacto aprox.", touch_field, "Inferno"))
    if step_field is not None:
        surfaces.append(("Tensión de paso aprox.", step_field, "Plasma"))

    fig = go.Figure()
    trace_ranges = []

    for idx, (name, Z, colorscale) in enumerate(surfaces):
        visible = (idx == 0)
        start_index = len(fig.data)

        fig.add_trace(
            go.Surface(
                x=field.X, y=field.Y, z=Z,
                colorscale=colorscale,
                showscale=True,
                colorbar=dict(title="V", x=1.0),
                visible=visible,
                name=name,
            )
        )

        z_base = float(np.min(Z))
        for line_trace in _grid_conductor_traces(grid, z_base):
            line_trace.visible = visible
            fig.add_trace(line_trace)

        trace_ranges.append((start_index, len(fig.data)))

    total_traces = len(fig.data)
    buttons = []
    for idx, (name, _, _) in enumerate(surfaces):
        visibility = [False] * total_traces
        start, end = trace_ranges[idx]
        for k in range(start, end):
            visibility[k] = True
        buttons.append(
            dict(
                label=name,
                method="update",
                args=[{"visible": visibility}, {"title": f"{title} — {name}"}],
            )
        )

    fig.update_layout(
        title=f"{title} — {surfaces[0][0]}",
        scene=dict(
            xaxis_title="X (m)",
            yaxis_title="Y (m)",
            zaxis_title="Tensión (V)",
            aspectmode="cube",
        ),
        updatemenus=[
            dict(active=0, buttons=buttons, x=0.02, y=1.08, xanchor="left")
        ],
        margin=dict(l=0, r=0, t=70, b=0),
        height=700,
    )

    return fig


def save_html(fig: go.Figure, path: str, embed_plotly_js: bool = True) -> None:
    """
    Guarda el dashboard como HTML autocontenido e interactivo.

    embed_plotly_js=True: incrusta la librería completa en el archivo
    (~3 MB, pero funciona sin conexión a internet -- recomendado para
    un repo que la gente descarga y puede abrir offline).
    embed_plotly_js=False: usa un link a CDN (archivo más liviano, pero
    requiere internet para renderizar al abrirlo).
    """
    fig.write_html(path, include_plotlyjs=(True if embed_plotly_js else "cdn"))
