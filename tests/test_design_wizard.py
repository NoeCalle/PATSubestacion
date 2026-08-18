"""
Tests del modelador determinista (src/cli/design_wizard.py).

Cada función de recolección se testea por separado simulando input()
con monkeypatch. El test de integración (test_full_wizard_flow_*)
recorre TODO el flujo con una secuencia de respuestas scripteada, y
verifica contra los mismos valores numéricos ya validados en
tests/test_reporting.py (mismo caso: rho=100, malla 60x60 7x7 con 8
varillas, falla 10kA) -- así no estamos inventando números nuevos
para comparar, reutilizamos un resultado ya confirmado.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from docx import Document

from src.engine.models import SoilModel, TwoLayerSoilModel, GridGeometry, FaultData
from src.cli.design_wizard import (
    collect_soil_model,
    collect_grid_geometry,
    collect_fault_data,
    collect_project_info,
    run_design_for,
    run_wizard,
)


def _inputs(monkeypatch, values):
    it = iter(values)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(it))


# ---------- collect_soil_model ----------

def test_collect_soil_model_uniform_no_surface_layer(monkeypatch):
    _inputs(monkeypatch, [
        "",       # elección -> "1" uniforme (default)
        "100",    # rho
        "",       # capa superficial -> No
    ])
    soil = collect_soil_model()
    assert isinstance(soil, SoilModel)
    assert soil.rho == 100.0
    assert soil.rho_s is None


def test_collect_soil_model_uniform_with_surface_layer(monkeypatch):
    _inputs(monkeypatch, [
        "1", "80", "s", "3000", "0.1",
    ])
    soil = collect_soil_model()
    assert soil.rho == 80.0
    assert soil.rho_s == 3000.0
    assert soil.h_s == 0.1


def test_collect_soil_model_two_layer_known_params(monkeypatch):
    _inputs(monkeypatch, [
        "3",      # ya conozco rho1/rho2/h1
        "60", "800", "4",
        "",       # sin capa superficial
    ])
    soil = collect_soil_model()
    assert isinstance(soil, TwoLayerSoilModel)
    assert soil.rho1 == 60.0
    assert soil.rho2 == 800.0
    assert soil.h1 == 4.0


def test_collect_soil_model_two_layer_from_wenner_measurements(monkeypatch):
    _inputs(monkeypatch, [
        "2",  # tengo mediciones de campo
        "1", "62", "2", "68", "4", "95", "8", "160",
        "",   # termina la carga de mediciones
        "",   # sin capa superficial
    ])
    soil = collect_soil_model()
    assert isinstance(soil, TwoLayerSoilModel)
    # No forzamos valores exactos (viene de un ajuste numérico), solo
    # que sea un resultado físicamente razonable
    assert soil.rho1 > 0 and soil.rho2 > soil.rho1


# ---------- collect_grid_geometry ----------

def test_collect_grid_geometry_with_rods(monkeypatch):
    _inputs(monkeypatch, [
        "60", "60",   # Lx, Ly
        "", "",       # h, d -> defaults
        "7", "7",     # n_x, n_y
        "",           # varillas -> sí (default)
        "8", "3", "",  # n_rods, L_rod, perímetro (default sí)
    ])
    grid = collect_grid_geometry()
    assert grid.Lx == 60.0 and grid.Ly == 60.0
    assert grid.h == 0.5 and grid.d == 0.01
    assert grid.n_x == 7 and grid.n_y == 7
    assert grid.n_rods == 8 and grid.L_rod == 3.0
    assert grid.rods_on_perimeter is True


def test_collect_grid_geometry_without_rods(monkeypatch):
    _inputs(monkeypatch, [
        "40", "40", "", "", "5", "5",
        "n",  # sin varillas
    ])
    grid = collect_grid_geometry()
    assert grid.n_rods == 0
    assert grid.L_rod == 0.0


# ---------- collect_fault_data ----------

def test_collect_fault_data_with_defaults(monkeypatch):
    _inputs(monkeypatch, ["10000", "0.6", "", "", "", "", ""])
    fault = collect_fault_data()
    assert fault.If_sym == 10000.0
    assert fault.Sf == 0.6
    assert fault.tf == 0.5
    assert fault.ts == 0.5  # default = tf
    assert fault.X_R == 15.0
    assert fault.freq == 60.0
    assert fault.Cp == 1.0


# ---------- collect_project_info ----------

def test_collect_project_info_with_values(monkeypatch):
    _inputs(monkeypatch, ["Subestación Norte", "Arequipa", "Cliente SA", "Ing. Pérez"])
    info = collect_project_info()
    assert info.project_name == "Subestación Norte"
    assert info.location == "Arequipa"
    assert info.client == "Cliente SA"
    assert info.prepared_by == "Ing. Pérez"


# ---------- run_design_for (dispatch) ----------

def test_run_design_for_dispatches_uniform_vs_two_layer():
    grid = GridGeometry(Lx=60, Ly=60, h=0.5, d=0.01, n_x=7, n_y=7, n_rods=8, L_rod=3.0)
    fault = FaultData(If_sym=10000.0, Sf=0.6)

    uniform_result = run_design_for(SoilModel(rho=100.0), grid, fault, body_kg=50)
    assert uniform_result.Em > 0

    two_layer_result = run_design_for(TwoLayerSoilModel(rho1=60, rho2=800, h1=4), grid, fault, body_kg=50)
    assert two_layer_result.Em > 0
    assert any("aproximación" in n.lower() for n in two_layer_result.notes)


# ---------- Integración completa: run_wizard() ----------

def test_full_wizard_flow_matches_known_reporting_case(monkeypatch, tmp_path):
    """
    Mismo caso exacto que tests/test_reporting.py::sample_uniform_case:
    rho=100, malla 60x60 7x7 con 8 varillas de 3m, falla 10kA Sf=0.6.
    Ya sabemos por ese test (y por examples/basic_grid_example.py) que
    este caso NO CUMPLE -- lo reusamos para no inventar un nuevo
    resultado de referencia.
    """
    inputs = [
        "",        # 1  elección suelo -> "1" uniforme
        "100",     # 2  rho
        "",        # 3  capa superficial -> No
        "10000",   # 4  If_sym
        "0.6",     # 5  Sf
        "",        # 6  tf -> 0.5
        "",        # 7  ts -> 0.5
        "",        # 8  X_R -> 15
        "",        # 9  freq -> 60
        "",        # 10 Cp -> 1.0
        "",        # 11 body_kg -> 50kg (default)
        "60",      # 12 Lx
        "60",      # 13 Ly
        "",        # 14 h -> 0.5
        "",        # 15 d -> 0.01
        "7",       # 16 n_x
        "7",       # 17 n_y
        "",        # 18 varillas -> sí
        "8",       # 19 n_rods
        "3",       # 20 L_rod
        "",        # 21 perímetro -> sí
        "n",       # 22 ¿ajustar geometría? -> No (aceptamos el NO CUMPLE)
        "",        # 23 ¿generar memoria? -> Sí (default)
        "",        # 24 project_name -> default
        "",        # 25 location
        "",        # 26 client
        "",        # 27 prepared_by
    ]
    _inputs(monkeypatch, inputs)

    result, report_path = run_wizard(output_dir=str(tmp_path))

    # Mismos valores que en tests/test_reporting.py (motor determinista,
    # mismo input -> mismo output, siempre)
    assert result.passes is False
    assert result.Em == pytest.approx(1120.8, abs=0.5)
    assert result.Es == pytest.approx(611.0, abs=0.5)
    assert result.GPR == pytest.approx(5284.7, abs=0.5)

    assert report_path is not None
    assert os.path.exists(report_path)

    doc = Document(report_path)
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "NO CUMPLE" in text


def test_wizard_can_decline_report_generation(monkeypatch, tmp_path):
    inputs = [
        "", "100", "",             # suelo uniforme, sin capa superficial
        "10000", "0.6", "", "", "", "", "",  # falla, todos default
        "",                         # body_kg -> 50kg
        "60", "60", "", "", "7", "7", "", "8", "3", "",  # grid con varillas
        "n",                        # no ajustar
        "n",                        # NO generar memoria
    ]
    _inputs(monkeypatch, inputs)

    result, report_path = run_wizard(output_dir=str(tmp_path))

    assert report_path is None
    assert result is not None
