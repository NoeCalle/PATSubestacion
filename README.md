# IEEE 80 Grounding Design Agents

Sistema multi-agente para asistir en el diseño de mallas de puesta a tierra según **IEEE Std 80** (Guide for Safety in AC Substation Grounding).

> ⚠️ Este proyecto es una **herramienta de apoyo al cálculo**. Todo resultado debe ser revisado y firmado por un ingeniero eléctrico habilitado antes de su uso en un proyecto real.

## Objetivo

Un repo descargable, agnóstico de proveedor de LLM (funciona con tu propia cuenta/API key de Claude, ChatGPT, u otros), que combina:

- Un **motor de cálculo** determinístico (Python puro) con las fórmulas normativas de IEEE 80 — nunca se le pide al LLM que "calcule" tensiones de paso/contacto de memoria.
- Un **sistema de agentes** que orquesta el flujo de diseño: datos de suelo → geometría de malla → cálculo → revisión → informe.

## Estructura del repo

```
src/
  engine/     # Motor de cálculo IEEE 80 (Python puro, testeado, sin LLM)
  visual/     # Visualización 3D interactiva (plotly) — solo renderiza, no calcula
  agents/     # Definición de agentes y orquestación (multi-proveedor)
docs/         # Documentación técnica y de arquitectura
tests/        # Tests del motor de cálculo
examples/     # Casos de ejemplo (inputs/outputs)
```

## Estado del proyecto

🚧 En construcción.

- ✅ **Motor de cálculo normativo IEEE 80** (`src/engine/`) — suelo uniforme,
  Em, Es, GPR, Rg (Sverak), factor de decremento, factores geométricos
  Km/Ki/Kii/Kh/Ks. Ver ejemplo en `examples/basic_grid_example.py`.
- ✅ **Modelo de suelo de dos capas** (`src/engine/soil_two_layer.py`) —
  resistividad aparente de Wenner, ajuste (curve fitting) de ρ1/ρ2/h1
  desde mediciones de campo, y resistividad efectiva para diseño
  (aproximación de ingeniería, documentada como tal — ver docstring).
  Ver ejemplo en `examples/two_layer_soil_example.py`.
- ✅ **Perfil de potencial en grilla** (`src/engine/potential_profile.py`) —
  campo de potencial de superficie numérico (discretización de electrodos +
  método de imágenes), base para el gráfico 3D. Usa una simplificación
  documentada (corriente uniforme entre segmentos) — es una herramienta
  exploratoria/visual, el valor que rige el informe sigue siendo el
  Em/Es normativo de fórmula cerrada. Ver ejemplo en
  `examples/potential_profile_example.py`.
- ✅ **Visualización 3D interactiva** (`src/visual/plot3d.py`, plotly) —
  dashboard HTML autocontenido con selector entre potencial, tensión de
  contacto y tensión de paso, con la malla superpuesta como referencia
  espacial. Ver ejemplo en `examples/visualize_potential_3d.py`.
- **50 tests pasando** (`pytest tests/ -v`).
- ⏳ Stack técnico de orquestación multi-agente
- ⏳ Definición de roles/prompts de cada agente (coordinador, suelo,
  diseñador, revisor, reportes)
- ⏳ Módulo de reportes (memoria de cálculo)
- ⏳ Documentación de flujo (diagrama)

### Cómo correr los tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

### Cómo correr los ejemplos

```bash
python examples/basic_grid_example.py           # suelo uniforme
python examples/two_layer_soil_example.py       # suelo de dos capas (desde datos de campo)
python examples/potential_profile_example.py    # perfil de potencial en grilla
python examples/visualize_potential_3d.py       # dashboard 3D interactivo (genera examples/output/*.html)
```

> **Nota sobre el modelo de dos capas**: la conversión de un modelo de dos
> capas a una resistividad "efectiva" para el cálculo de Rg/Em/Es es una
> **aproximación de ingeniería** (radio equivalente + resistividad aparente
> de Wenner), no una fórmula literal única de IEEE 80. Para diseños
> críticos se recomienda contrastar con software especializado (CDEGS,
> ETAP) o el criterio del ingeniero revisor. Queda documentado en el
> docstring de `soil_two_layer.py` y en las notas del resultado.

> **Nota metodológica**: los tests del motor verifican consistencia interna
> y comportamiento físico esperado (sanity checks de ingeniería), no
> reproducen un ejemplo numérico específico del libro IEEE 80-2013 dígito
> por dígito. Validación manual adicional por un ingeniero habilitado es
> necesaria antes de usar este motor en un proyecto real.

## Licencia

Por definir.
