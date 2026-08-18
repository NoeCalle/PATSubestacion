"""
Interfaz web del modelador determinista (sin LLM).

A diferencia de src/webapp (que orquesta agentes con LLM y necesita
hilos de fondo + sondeo por las llamadas bloqueantes a la API), este
servidor es puramente sincrónico: cada cálculo es instantáneo, sin
threading ni estado de sesión entre requests -- el navegador manda
todos los datos en cada POST y el servidor responde con el resultado
completo de una.

Sin dependencia de src/agents -- solo usa src/engine y src/reporting.
No requiere ninguna API key ni SDK de LLM, solo Flask.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from flask import Flask, render_template, request, send_file

from src.engine.design_check import run_design_check, run_design_check_two_layer
from src.engine.models import TwoLayerSoilModel
from src.reporting import build_calculation_report, ProjectInfo
from src.webapp_wizard.params import build_soil_from_form, build_grid_from_form, build_fault_from_form

app = Flask(__name__)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def run_design(soil, grid, fault, body_kg):
    if isinstance(soil, TwoLayerSoilModel):
        return run_design_check_two_layer(soil, grid, fault, body_kg=body_kg)
    return run_design_check(soil, grid, fault, body_kg=body_kg)


def _compute_from_form(form):
    soil = build_soil_from_form(form)
    grid = build_grid_from_form(form)
    fault = build_fault_from_form(form)
    body_kg = float(form.get("body_kg") or 50)
    result = run_design(soil, grid, fault, body_kg)
    return soil, grid, fault, result


@app.route("/", methods=["GET"])
def index():
    return render_template("wizard.html", result=None, soil=None, form=None, error=None, hidden_fields=[])


@app.route("/calculate", methods=["POST"])
def calculate():
    form = request.form
    hidden_fields = list(form.items(multi=True))

    try:
        soil, grid, fault, result = _compute_from_form(form)
    except Exception as e:
        return render_template("wizard.html", result=None, soil=None, form=form, error=str(e), hidden_fields=hidden_fields)

    return render_template(
        "wizard.html", result=result, soil=soil, form=form, error=None, hidden_fields=hidden_fields
    )


@app.route("/report", methods=["POST"])
def report():
    form = request.form
    try:
        soil, grid, fault, result = _compute_from_form(form)

        project_info = ProjectInfo(
            project_name=form.get("project_name") or "Proyecto sin nombre",
            location=form.get("location", ""),
            client=form.get("client", ""),
            prepared_by=form.get("prepared_by", ""),
        )

        report_path = os.path.join(OUTPUT_DIR, "memoria_de_calculo_wizard_web.docx")
        build_calculation_report(soil, grid, fault, result, report_path, project_info=project_info)
    except Exception as e:
        hidden_fields = list(form.items(multi=True))
        return render_template("wizard.html", result=None, soil=None, form=form, error=str(e), hidden_fields=hidden_fields)

    return send_file(report_path, as_attachment=True, download_name="memoria_de_calculo.docx")


def main():
    port = int(os.environ.get("PORT", 5050))
    print(f"\nAbrí http://127.0.0.1:{port} en tu navegador.\n")
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
