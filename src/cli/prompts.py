"""
Helpers de entrada de datos por consola.

Leen input(), validan, y vuelven a preguntar si el valor no es válido
-- en vez de crashear con un ValueError si alguien tipea algo raro.
Separados en su propio módulo para poder testearlos de forma aislada
(monkeypatch de builtins.input) sin depender de todo el flujo del
modelador.
"""

from typing import Dict, Optional


def ask_float(prompt: str, default: Optional[float] = None, min_value: Optional[float] = None) -> float:
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw = input(f"{prompt}{suffix}: ").strip()
        if not raw and default is not None:
            return default
        try:
            value = float(raw)
        except ValueError:
            print("  → Ingresá un número válido.")
            continue
        if min_value is not None and value <= min_value:
            print(f"  → El valor debe ser mayor a {min_value}.")
            continue
        return value


def ask_int(prompt: str, default: Optional[int] = None, min_value: Optional[int] = None) -> int:
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw = input(f"{prompt}{suffix}: ").strip()
        if not raw and default is not None:
            return default
        try:
            value = int(raw)
        except ValueError:
            print("  → Ingresá un número entero válido.")
            continue
        if min_value is not None and value < min_value:
            print(f"  → El valor debe ser mayor o igual a {min_value}.")
            continue
        return value


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    suffix = " [S/n]" if default else " [s/N]"
    while True:
        raw = input(f"{prompt}{suffix}: ").strip().lower()
        if not raw:
            return default
        if raw in ("s", "si", "sí", "y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("  → Respondé 's' o 'n'.")


def ask_text(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    raw = input(f"{prompt}{suffix}: ").strip()
    return raw or default


def ask_choice(prompt: str, options: Dict[str, str], default: Optional[str] = None) -> str:
    """options: {"1": "Suelo uniforme", "2": "Dos capas"} -- devuelve la
    CLAVE elegida (ej. "1"), no el texto."""
    print(prompt)
    for key, label in options.items():
        print(f"  {key}) {label}")
    suffix = f" [{default}]" if default else ""
    while True:
        raw = input(f"Elegí una opción{suffix}: ").strip()
        if not raw and default:
            return default
        if raw in options:
            return raw
        print(f"  → Opción inválida. Elegí una de: {', '.join(options.keys())}")
