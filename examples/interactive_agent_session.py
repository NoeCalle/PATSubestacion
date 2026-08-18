"""
Sesión interactiva real con los agentes.

Arranca con dos preguntas abiertas por terminal (contame de tu suelo,
contame de tu proyecto) y a partir de ahí los agentes (soil_agent,
designer_agent) pueden seguir preguntando lo que les falte usando la
herramienta ask_human -- una conversación real, no un guion de una
sola pasada con todos los datos precargados.

⚠️ Requiere:
  - Tu propia API key (ANTHROPIC_API_KEY u OPENAI_API_KEY)
  - Una terminal real (usa input() para leer tus respuestas) -- no se
    puede correr en un entorno no interactivo (ej. un notebook sin
    stdin, o un pipe).
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agents import AnthropicProvider, OpenAIProvider, run_design_pipeline, ProjectInfo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["anthropic", "openai"], default="anthropic")
    args = parser.parse_args()

    if args.provider == "anthropic":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("Falta la variable de entorno ANTHROPIC_API_KEY.")
            return
        provider = AnthropicProvider(model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5"))
    else:
        if not os.environ.get("OPENAI_API_KEY"):
            print("Falta la variable de entorno OPENAI_API_KEY.")
            return
        model = os.environ.get("OPENAI_MODEL")
        if not model:
            print("Falta la variable de entorno OPENAI_MODEL (ej. 'gpt-4o').")
            return
        provider = OpenAIProvider(model=model)

    print("=" * 70)
    print("Diseño interactivo de puesta a tierra (IEEE 80)")
    print("=" * 70)
    print(
        "\nContame lo que sepas. Si falta algún dato, el sistema te lo va "
        "a volver a preguntar durante el proceso -- no hace falta que "
        "completes todo ahora mismo.\n"
    )

    soil_data = input(
        "Datos de suelo (mediciones de resistividad de campo, o lo que sepas): "
    )
    project_requirements = input(
        "\nDatos del proyecto (corriente de falla, tiempo de despeje, terreno disponible): "
    )

    print("\nProcesando... (el sistema puede volver a preguntarte algo si falta un dato)\n")

    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)
    report_path = os.path.join(output_dir, "memoria_de_calculo_interactiva.docx")

    session = run_design_pipeline(
        provider, soil_data, project_requirements,
        report_output_path=report_path,
        project_info=ProjectInfo(
            prepared_by=f"Sistema de agentes IEEE 80 ({args.provider}) — sesión interactiva"
        ),
    )

    print("\n" + "=" * 70)
    print(f"VEREDICTO FINAL: {session.final_verdict}")
    print("=" * 70)

    if session.report_path:
        print(f"\n📄 Memoria de cálculo generada en: {session.report_path}")
    else:
        print(
            "\n⚠️ No se generó memoria de cálculo -- ningún agente llegó a "
            "confirmar un resultado con la herramienta de verificación."
        )

    print(
        "\n⚠️ Recordatorio: este resultado requiere revisión y firma de un "
        "ingeniero eléctrico habilitado."
    )


if __name__ == "__main__":
    main()
