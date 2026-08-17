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
  agents/     # Definición de agentes y orquestación (multi-proveedor)
docs/         # Documentación técnica y de arquitectura
tests/        # Tests del motor de cálculo
examples/     # Casos de ejemplo (inputs/outputs)
```

## Estado del proyecto

🚧 En construcción.

- ✅ **Motor de cálculo normativo IEEE 80** (`src/engine/`) — suelo uniforme,
  Em, Es, GPR, Rg (Sverak), factor de decremento, factores geométricos
  Km/Ki/Kii/Kh/Ks. 21 tests pasando (`pytest tests/`). Ver ejemplo en
  `examples/basic_grid_example.py`.
- ⏳ Modelo de suelo de dos capas
- ⏳ Perfil de potencial en grilla completa (base para gráfico 3D)
- ⏳ Stack técnico de orquestación multi-agente
- ⏳ Definición de roles/prompts de cada agente (coordinador, suelo,
  diseñador, revisor, visualización 3D, reportes)
- ⏳ Documentación de flujo (diagrama)

### Cómo correr los tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

### Cómo correr el ejemplo

```bash
python examples/basic_grid_example.py
```

> **Nota metodológica**: los tests del motor verifican consistencia interna
> y comportamiento físico esperado (sanity checks de ingeniería), no
> reproducen un ejemplo numérico específico del libro IEEE 80-2013 dígito
> por dígito. Validación manual adicional por un ingeniero habilitado es
> necesaria antes de usar este motor en un proyecto real.

## Licencia

Por definir.
