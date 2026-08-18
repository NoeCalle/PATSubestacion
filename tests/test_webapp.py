"""
Tests del backend Flask (src/webapp/app.py).

No hacemos llamadas de red reales a Anthropic/OpenAI -- se reemplaza
run_design_pipeline por una versión simulada que sí ejercita el
mecanismo real de WebHumanInterface (hilo de fondo + cola bloqueante),
para validar el cableado completo servidor <-> hilo del pipeline sin
depender de una API key válida ni de conectividad.
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

import src.webapp.app as app_module
from src.webapp.app import app
from src.agents.session import DesignSession
from src.agents.tools import get_human_interface


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app_module._session = None
    with app.test_client() as c:
        yield c
    app_module._session = None


def test_index_serves_html_with_title(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"IEEE 80" in res.data


def test_status_is_idle_without_session(client):
    res = client.get("/status")
    data = res.get_json()
    assert data["status"] == "idle"
    assert data["log"] == []


def test_start_without_api_key_returns_400(client):
    res = client.post("/start", json={
        "provider": "anthropic", "api_key": "",
        "soil_data": "", "project_requirements": "",
    })
    assert res.status_code == 400
    assert "api key" in res.get_json()["error"].lower()


def test_start_with_unknown_provider_returns_400(client):
    res = client.post("/start", json={
        "provider": "not_a_real_provider", "api_key": "sk-test",
        "soil_data": "", "project_requirements": "",
    })
    assert res.status_code == 400


def test_start_openai_without_model_returns_400(client):
    res = client.post("/start", json={
        "provider": "openai", "api_key": "sk-test", "model": "",
        "soil_data": "", "project_requirements": "",
    })
    assert res.status_code == 400


def test_answer_without_session_returns_400(client):
    res = client.post("/answer", json={"answer": "100"})
    assert res.status_code == 400


def test_report_without_session_returns_404(client):
    res = client.get("/report")
    assert res.status_code == 404


def _wait_for(predicate, timeout=2.0, interval=0.05):
    elapsed = 0.0
    while elapsed < timeout:
        result = predicate()
        if result:
            return result
        time.sleep(interval)
        elapsed += interval
    return None


def test_full_flow_ask_human_unblocks_via_answer_endpoint(client, monkeypatch):
    """Integración de punta a punta del mecanismo real (sin red):
    /start dispara el hilo -> el hilo llama ask_human y bloquea ->
    /status expone la pregunta -> /answer la responde -> el hilo se
    desbloquea, termina, y /status refleja 'done' con el veredicto."""

    captured = {}

    def fake_pipeline(provider, soil_data, project_requirements,
                       report_output_path=None, project_info=None,
                       visualization_reference=None, on_event=None,
                       max_review_iterations=3):
        if on_event:
            on_event({"type": "soil_started"})
        answer = get_human_interface().ask("¿Cuál es la resistividad del suelo?")
        captured["answer"] = answer
        if on_event:
            on_event({"type": "soil_done", "text": f"Resistividad recibida: {answer}"})
        return DesignSession(final_verdict="APROBADO", report_path=None, iterations=1)

    monkeypatch.setattr(app_module, "run_design_pipeline", fake_pipeline)
    monkeypatch.setattr(app_module, "AnthropicProvider", lambda model=None, api_key=None: object())

    res = client.post("/start", json={
        "provider": "anthropic", "api_key": "sk-test-fake",
        "soil_data": "", "project_requirements": "",
    })
    assert res.status_code == 200

    pending = _wait_for(lambda: client.get("/status").get_json()["pending_question"])
    assert pending == "¿Cuál es la resistividad del suelo?"

    res = client.post("/answer", json={"answer": "120"})
    assert res.status_code == 200

    def check_done():
        status = client.get("/status").get_json()
        return status if status["status"] == "done" else None

    final = _wait_for(check_done)
    assert final is not None
    assert final["final_verdict"] == "APROBADO"
    assert captured["answer"] == "120"

    types = [e["type"] for e in final["log"]]
    assert "soil_started" in types
    assert "soil_done" in types


def test_start_rejects_concurrent_session(client, monkeypatch):
    """No debería poder arrancar un segundo diseño mientras el primero
    sigue corriendo (estado global de un solo usuario local)."""

    def blocking_pipeline(provider, soil_data, project_requirements, **kwargs):
        get_human_interface().ask("Esto se queda esperando...")
        return DesignSession(final_verdict="APROBADO")

    monkeypatch.setattr(app_module, "run_design_pipeline", blocking_pipeline)
    monkeypatch.setattr(app_module, "AnthropicProvider", lambda model=None, api_key=None: object())

    res1 = client.post("/start", json={
        "provider": "anthropic", "api_key": "sk-test",
        "soil_data": "", "project_requirements": "",
    })
    assert res1.status_code == 200

    _wait_for(lambda: client.get("/status").get_json()["pending_question"])

    res2 = client.post("/start", json={
        "provider": "anthropic", "api_key": "sk-test",
        "soil_data": "", "project_requirements": "",
    })
    assert res2.status_code == 409

    client.post("/answer", json={"answer": "fin"})
