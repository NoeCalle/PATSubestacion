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
  reporting/  # Memoria de cálculo en Word (python-docx) — solo formatea, no calcula
  agents/     # Sistema de agentes (coordinador, suelo, diseñador, revisor) — agnóstico de proveedor LLM
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
- ✅ **Sistema de agentes** (`src/agents/`) — agnóstico de proveedor
  (Anthropic o OpenAI, vía un adaptador común `LLMProvider`).
  Coordinador (orquestador Python plano, no LLM) que corre:
  `soil_agent` → `designer_agent` ↔ `reviewer_agent` (con loop de
  retroalimentación si el revisor rechaza). Los agentes nunca calculan
  directamente — todo pasa por `src/engine` vía tools con JSON Schema.
  La lógica de orquestación está testeada con un proveedor simulado
  (sin necesidad de API key); el ejemplo real (`examples/agents_pipeline_example.py`)
  requiere tu propia key de Anthropic u OpenAI.
- ✅ **Módulo de reportes** (`src/reporting/report_builder.py`, python-docx) —
  genera la memoria de cálculo en Word (.docx): datos de entrada, resultados
  completos, veredicto, notas/advertencias íntegras (nunca se ocultan), y
  espacio de firma del ingeniero responsable. Ver ejemplo en
  `examples/generate_report_example.py`.
- ✅ **Integración agentes → reportes** (`src/agents/report_integration.py`) —
  `run_design_pipeline(..., report_output_path=...)` genera la memoria
  de cálculo automáticamente al finalizar, extraída de la última tool
  call de verificación REAL ejecutada (prioriza al revisor sobre el
  diseñador, nunca texto del LLM). Si ningún agente llegó a llamar la
  herramienta de cálculo, no genera un documento — `session.report_path`
  queda en `None` en vez de fabricar un informe con datos inventados.
- **79 tests pasando** (`pytest tests/ -v`).
- ⏳ Documentación de flujo (diagrama)

### Arquitectura de agentes

```
src/agents/
├── providers/              # Adaptadores de proveedor (Anthropic, OpenAI)
│   ├── base.py              # Interfaz común LLMProvider
│   ├── anthropic_provider.py
│   └── openai_provider.py
├── tools.py                 # Envuelve el motor de cálculo como tools con JSON Schema
├── base_agent.py            # Loop de tool-calling genérico
├── session.py                # Estado del pipeline (DesignSession)
├── soil_agent.py              # Interpreta datos de resistividad
├── designer_agent.py          # Propone y verifica geometrías de malla
├── reviewer_agent.py          # Auditoría independiente (QA interno)
├── coordinator.py             # Orquesta el flujo (Python plano, no LLM)
└── report_integration.py      # Puente hacia src/reporting (extrae la última tool call real)
```

**Principio de diseño**: ningún agente calcula tensiones de paso/contacto
"a mano" — todos llaman a las mismas funciones deterministas de
`src/engine` (ya testeadas independientemente) a través de tools. El
coordinador tampoco es un LLM: la secuencia y los reintentos son lógica
Python fija y auditable, no una decisión que dependa de que un modelo
"razone bien".

### Cómo correr el pipeline de agentes con tu propia API key

```bash
pip install -r requirements.txt -r requirements-agents.txt
cp .env.example .env   # completá tu API key
export $(cat .env | xargs)  # o cargalo con python-dotenv / tu método preferido

python examples/agents_pipeline_example.py --provider anthropic
# o
python examples/agents_pipeline_example.py --provider openai
```

> ⚠️ Este ejemplo consume créditos de tu cuenta (a diferencia del resto
> de los ejemplos del repo, que no requieren ninguna API). El resultado
> del pipeline (incluso "APROBADO") sigue siendo un insumo para el
> ingeniero eléctrico habilitado que revisa y firma el informe final.

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
python examples/generate_report_example.py      # memoria de cálculo en Word (genera examples/output/*.docx)
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
