"""Módulo de visualización. Sin lógica de cálculo -- solo renderizado
del output del motor de cálculo (src/engine/)."""

from .plot3d import build_potential_dashboard, save_html

__all__ = ["build_potential_dashboard", "save_html"]
