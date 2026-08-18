"""
Tests del webapp del modelador determinista (src/webapp_wizard/).

Al ser completamente sincrónico (sin hilos ni LLM), estos tests son
mucho más simples que los de src/webapp -- cada request se resuelve
sola, sin necesidad de polling ni monkeypatch de builtins.input().

Reutiliza el mismo caso de referencia que test_reporting.py y
test_design_wizard.py (rho=100, malla 60x60 7x7 con 8 varillas,
falla 10kA) para no inventar números nuevos de comparación.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from werkzeug.datastructures import MultiDict

from src.webapp_wizard.app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


KNOWN_CASE_FORM = {
    "soil_type": "uniform",
    "rho": "100",
    "Lx": "60", "Ly": "60", "h": "0.5", "d": "0.01",
    "n_x": "7", "n_y": "7",
    "use_rods": "on", "n_rods": "8", "L_rod": "3", "rods_on_perimeter": "on",
    "If_sym": "10000", "Sf": "0.6", "tf": "0.5", "ts": "0.5",
    "X_R": "15", "freq": "60", "Cp": "1.0", "body_kg": "50",
}


# ---------- Página inicial ----------

def test_index_serves_html_with_title(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"IEEE 80" in res.data
    assert b"Sin cuenta de IA" in res.data


# ---------- /calculate ----------

def test_calculate_known_case_matches_expected_values(client):
    res = client.post("/calculate", data=KNOWN_CASE_FORM)
    assert res.status_code == 200
    html = res.data.decode("utf-8")

    # Mismos valores que test_reporting.py::sample_uniform_case
    assert "1120.8" in html  # Em
    assert "611.0" in html   # Es
    assert "5284.7" in html  # GPR
    assert "NO PASA" in html
    assert "NO CUMPLE" in html


def test_calculate_passing_case_shows_ok_verdict(client):
    """Un suelo de muy baja resistividad con malla densa debería pasar
    -- confirma que el banner de veredicto también funciona para el
    caso positivo, no solo para el negativo."""
    form = dict(KNOWN_CASE_FORM)
    form["rho"] = "5"  # suelo muy conductor
    form["n_x"] = "15"
    form["n_y"] = "15"

    res = client.post("/calculate", data=form)
    html = res.data.decode("utf-8")
    assert "PASA" in html
    assert "NO PASA" not in html


def test_calculate_missing_required_field_shows_friendly_error(client):
    form = dict(KNOWN_CASE_FORM)
    del form["rho"]

    res = client.post("/calculate", data=form)
    html = res.data.decode("utf-8")
    assert "No se pudo calcular" in html
    assert "Resistividad del suelo" in html


def test_calculate_preserves_submitted_values_in_form(client):
    """Los valores enviados deben quedar reflejados en los inputs del
    formulario (para poder ajustar sin re-tipear todo)."""
    res = client.post("/calculate", data=KNOWN_CASE_FORM)
    html = res.data.decode("utf-8")
    assert 'value="100"' in html  # rho
    assert 'value="60"' in html   # Lx/Ly


def test_calculate_two_layer_known_params(client):
    form = dict(KNOWN_CASE_FORM)
    form["soil_type"] = "two_layer_known"
    del form["rho"]
    form["rho1"] = "60"
    form["rho2"] = "800"
    form["h1"] = "4"

    res = client.post("/calculate", data=form)
    html = res.data.decode("utf-8")
    assert "Modelo de dos capas" in html
    assert "60.0" in html  # rho1 mostrado


def test_calculate_two_layer_from_wenner_measurements(client):
    form = dict(KNOWN_CASE_FORM)
    form["soil_type"] = "two_layer_wenner"
    del form["rho"]

    res = client.post("/calculate", data=_with_wenner(form))

    html = res.data.decode("utf-8")
    assert "Modelo de dos capas" in html


def _with_wenner(form):
    items = list(form.items())
    for a, rho_a in [(1, 62), (2, 68), (4, 95), (8, 160)]:
        items.append(("wenner_a", str(a)))
        items.append(("wenner_rho", str(rho_a)))
    return MultiDict(items)


def test_calculate_wenner_requires_minimum_three_measurements(client):
    form = dict(KNOWN_CASE_FORM)
    form["soil_type"] = "two_layer_wenner"
    del form["rho"]
    items = MultiDict(list(form.items()) + [("wenner_a", "1"), ("wenner_rho", "62")])  # solo 1 medición

    res = client.post("/calculate", data=items)
    html = res.data.decode("utf-8")
    assert "No se pudo calcular" in html
    assert "al menos 3" in html


def test_calculate_without_rods(client):
    form = dict(KNOWN_CASE_FORM)
    del form["use_rods"]

    res = client.post("/calculate", data=form)
    assert res.status_code == 200  # no debe crashear


def test_calculate_with_surface_layer(client):
    form = dict(KNOWN_CASE_FORM)
    form["use_surface_layer"] = "on"
    form["rho_s"] = "3000"
    form["h_s"] = "0.1"

    res = client.post("/calculate", data=form)
    html = res.data.decode("utf-8")
    assert res.status_code == 200
    # La capa superficial sube la tensión tolerable -- debería ser
    # distinta a la del caso base sin capa
    assert "188.7" not in html  # ese era el tolerable SIN capa superficial


# ---------- /report ----------

def test_report_generates_downloadable_docx(client, monkeypatch, tmp_path):
    monkeypatch.setattr("src.webapp_wizard.app.OUTPUT_DIR", str(tmp_path))

    form = dict(KNOWN_CASE_FORM)
    form["project_name"] = "Subestación de Prueba"

    res = client.post("/report", data=form)
    assert res.status_code == 200
    assert res.headers["Content-Type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert len(res.data) > 1000


def test_report_missing_required_field_shows_error_not_crash(client):
    form = dict(KNOWN_CASE_FORM)
    del form["If_sym"]

    res = client.post("/report", data=form)
    assert res.status_code == 200
    assert b"No se pudo calcular" in res.data
