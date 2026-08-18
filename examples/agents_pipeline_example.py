"""
Ejemplo del pipeline completo de agentes: soil -> designer -> reviewer,
contra una API real de LLM (Anthropic o OpenAI).

⚠️ Este ejemplo REQUIERE tu propia API key y va a consumir créditos de
tu cuenta -- a diferencia de los otros ejemplos del repo, este no corre
"gratis" ni sin configuración. Los tests de tests/test_agents.py ya
validan la lógica de orquestación con un proveedor simulado; este
script es para probar contra un modelo real.

Configuración (elegí un proveedor):

  export ANTHROPIC_API_KEY="sk-ant-..."
  python examples/agents_pipeline_example.py --provider anthropic

  export OPENAI_API_KEY="sk-..."
  export OPENAI_MODEL="gpt-4o"   # o el modelo vigente que prefieras
  python examples/agents_pipeline_example.py --provider openai
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agents import AnthropicProvider, OpenAIProvider, run_design_pipeline


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["anthropic", "openai"], default="anthropic")
    args = parser.parse_args()

    if args.provider == "anthropic":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("⚠️  Falta la variable de entorno ANTHROPIC_API_KEY.")
            return
        provider = AnthropicProvider(model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5"))
    else:
        if not os.environ.get("OPENAI_API_KEY"):
            print("⚠️  Falta la variable de entorno OPENAI_API_KEY.")
            return
        model = os.environ.get("OPENAI_MODEL")
        if not model:
            print("⚠️  Falta la variable de entorno OPENAI_MODEL (ej. 'gpt-4o').")
            return
        provider = OpenAIProvider(model=model)

    soil_data = (
        "Ensayo de Wenner realizado en el predio de la subestación:\n"
        "a=1m -> 62 Ohm*m\n"
        "a=2m -> 68 Ohm*m\n"
        "a=4m -> 95 Ohm*m\n"
        "a=8m -> 160 Ohm*m\n"
        "a=16m -> 280 Ohm*m\n"
        "a=32m -> 410 Ohm*m\n"
        "a=64m -> 520 Ohm*m\n"
    )

    project_requirements = (
        "Subestación con corriente de falla simétrica a tierra de 10 kA, "
        "factor de división de corriente Sf=0.6, tiempo de despeje de falla "
        "0.5s, relación X/R=15. Terreno disponible: 60m x 60m. Se prioriza "
        "un diseño económico (mínima cantidad de conductor y varillas) que "
        "cumpla la norma para persona de 50 kg."
    )

    print(f"Corriendo pipeline con proveedor: {args.provider}\n")

    session = run_design_pipeline(provider, soil_data, project_requirements)

    print("=" * 70)
    print("RESULTADO DEL AGENTE DE SUELO")
    print("=" * 70)
    print(session.soil_result.final_text)

    print("\n" + "=" * 70)
    print(f"PROPUESTA FINAL DEL DISEÑADOR (iteración {session.iterations})")
    print("=" * 70)
    print(session.final_design)

    print("\n" + "=" * 70)
    print("VEREDICTO DEL REVISOR")
    print("=" * 70)
    print(session.final_review)

    print("\n" + "=" * 70)
    print(f"VEREDICTO FINAL DEL PIPELINE: {session.final_verdict}")
    print("=" * 70)
    print(
        "\n⚠️ Recordatorio: este veredicto es un insumo para el ingeniero "
        "eléctrico habilitado que debe revisar y firmar el informe final."
    )


if __name__ == "__main__":
    main()
