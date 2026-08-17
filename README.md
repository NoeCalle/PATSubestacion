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

🚧 En construcción. Próximos pasos:
1. Motor de cálculo IEEE 80 (fórmulas, inputs, outputs)
2. Stack técnico de orquestación multi-agente
3. Definición de roles/prompts de cada agente
4. Documentación de flujo (README/diagrama)

## Licencia

Por definir.
