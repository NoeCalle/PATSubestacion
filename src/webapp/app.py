"""
Servidor web local (Flask) para el pipeline de agentes IEEE 80.

Corre en tu laptop, sirve una página HTML en localhost, y actúa de
puente entre el navegador y el pipeline de agentes:

  - El pipeline corre en un hilo de fondo (es bloqueante: llama a la
    API del LLM y puede esperar respuestas humanas).
  - Cuando un agente llama a ask_human, en vez de bloquear una
    terminal, la pregunta queda expuesta en el estado de la sesión y
    el navegador la muestra vía polling a /status.
  - Cuando la persona responde en el navegador, POST /answer la
    entrega de vuelta al hilo del pipeline, que estaba bloqueado
    esperándola.

Herramienta de un solo usuario local -- no está pensada para
exponerse a internet ni para múltiples sesiones concurrentes. La API
key que escribís en la página nunca sale de tu máquina: el navegador
se la manda a este mismo servidor local (127.0.0.1), que la usa
directo para llamar a la API del proveedor elegido.
"""

import os
import sys
import threading
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from flask import Flask, jsonify, request, send_file, render_template

from src.agents.providers import AnthropicProvider, OpenAIProvider
from src.agents.human_interface import WebHumanInterface
from src.agents.tools import set_human_interface
from src.agents.coordinator import run_design_pipeline
from src.reporting import ProjectInfo

app = Flask(__name__)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


@dataclass
class WebSession:
    human_interface: WebHumanInterface = field(default_factory=WebHumanInterface)
    log: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "idle"  # idle | running | done | error
    final_verdict: Optional[str] = None
    report_path: Optional[str] = None
    error: Optional[str] = None
    thread: Optional[threading.Thread] = None

    def append_log(self, event: Dict[str, Any]) -> None:
        self.log.append(event)


_session: Optional[WebSession] = None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/start", methods=["POST"])
def start():
    global _session

    if _session is not None and _session.status == "running":
        return jsonify({"error": "Ya hay un diseño en curso. Esperá a que termine."}), 409

    data = request.get_json(force=True)
    provider_name = data.get("provider")
    api_key = (data.get("api_key") or "").strip()
    model = (data.get("model") or "").strip() or None
    soil_data = data.get("soil_data", "")
    project_requirements = data.get("project_requirements", "")

    if not api_key:
        return jsonify({"error": "Falta la API key."}), 400

    try:
        if provider_name == "anthropic":
            provider = AnthropicProvider(model=model or "claude-sonnet-5", api_key=api_key)
        elif provider_name == "openai":
            if not model:
                return jsonify({"error": "Para OpenAI hay que indicar el modelo (ej. gpt-4o)."}), 400
            provider = OpenAIProvider(model=model, api_key=api_key)
        else:
            return jsonify({"error": f"Proveedor desconocido: {provider_name}"}), 400
    except Exception as e:
        return jsonify({"error": f"No se pudo inicializar el proveedor: {e}"}), 400

    _session = WebSession()
    set_human_interface(_session.human_interface)

    def on_event(event: Dict[str, Any]) -> None:
        _session.append_log(event)

    def run():
        _session.status = "running"
        try:
            report_path = os.path.join(OUTPUT_DIR, "memoria_de_calculo_web.docx")
            result = run_design_pipeline(
                provider, soil_data, project_requirements,
                report_output_path=report_path,
                project_info=ProjectInfo(prepared_by=f"Sistema de agentes IEEE 80 ({provider_name}) — sesión web"),
                on_event=on_event,
            )
            _session.final_verdict = result.final_verdict
            _session.report_path = result.report_path
            _session.status = "done"
        except Exception as e:
            _session.error = f"{e}\n\n{traceback.format_exc()}"
            _session.status = "error"

    _session.thread = threading.Thread(target=run, daemon=True)
    _session.thread.start()

    return jsonify({"ok": True})


@app.route("/status")
def status():
    if _session is None:
        return jsonify({"status": "idle", "log": [], "pending_question": None})

    return jsonify({
        "status": _session.status,
        "log": _session.log,
        "pending_question": _session.human_interface.get_pending_question(),
        "final_verdict": _session.final_verdict,
        "has_report": _session.report_path is not None,
        "error": _session.error,
    })


@app.route("/answer", methods=["POST"])
def answer():
    if _session is None:
        return jsonify({"error": "No hay una sesión activa."}), 400

    data = request.get_json(force=True)
    answer_text = data.get("answer", "")
    _session.human_interface.submit_answer(answer_text)
    return jsonify({"ok": True})


@app.route("/report")
def report():
    if _session is None or not _session.report_path or not os.path.exists(_session.report_path):
        return jsonify({"error": "Todavía no hay un informe disponible."}), 404
    return send_file(_session.report_path, as_attachment=True, download_name="memoria_de_calculo.docx")


def main():
    port = int(os.environ.get("PORT", 5000))
    print(f"\nAbrí http://127.0.0.1:{port} en tu navegador.\n")
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
