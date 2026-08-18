"""
Tests del sistema de agentes.

Como estos tests corren en CI/sandbox sin credenciales reales de
Anthropic/OpenAI, usamos un FakeProvider (test double) que simula las
decisiones del LLM de forma scripteada. Esto SÍ valida con confianza:
  - El loop de tool-calling del Agent (ejecución de tools, formato de
    mensajes, manejo de errores, límite de turnos)
  - La lógica de orquestación del coordinador (secuencia, loop de
    retroalimentación diseñador<->revisor)
  - La integración real entre una tool call y el motor de cálculo
    (engine) -- acá NO se simula nada, se ejecuta el cálculo real.

Lo que estos tests NO validan (y no pueden, sin una API key real):
  - Que Claude/GPT efectivamente decidan llamar a las tools correctas
    en una conversación real, ni la calidad de sus respuestas en
    lenguaje natural. Eso requiere probar con credenciales propias
    (ver examples/agents_pipeline_example.py).
"""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from src.agents.providers.base import LLMProvider, ProviderResponse, ToolCall
from src.agents.base_agent import Agent
from src.agents.tools import get_tool_schemas, get_tool_dispatch
from src.agents.coordinator import run_design_pipeline


class FakeProvider(LLMProvider):
    """Proveedor simulado: devuelve respuestas pre-programadas en orden,
    una por cada llamada a .chat(). Permite testear la lógica de
    orquestación sin pegarle a una API real."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []  # historial de argumentos recibidos, para poder inspeccionar en los tests

    def chat(self, system, messages, tools):
        self.calls.append({"system": system, "messages": messages, "tools": tools})
        if not self.script:
            raise AssertionError("FakeProvider se quedó sin respuestas scripteadas")
        return self.script.pop(0)

    def format_assistant_message(self, response):
        return {"role": "assistant", "content": response.text, "_tool_calls": response.tool_calls}

    def format_tool_result(self, tool_call_id, content):
        return {"role": "tool_result", "tool_call_id": tool_call_id, "content": content}


def text_response(text: str) -> ProviderResponse:
    return ProviderResponse(text=text, tool_calls=[])


def tool_call_response(name: str, input_: dict, call_id: str = "call_1") -> ProviderResponse:
    return ProviderResponse(text=None, tool_calls=[ToolCall(id=call_id, name=name, input=input_)])


VALID_UNIFORM_INPUT = {
    "rho": 100.0, "Lx": 60.0, "Ly": 60.0, "h": 0.5, "d": 0.01,
    "n_x": 7, "n_y": 7, "n_rods": 8, "L_rod": 3.0,
    "If_sym": 10000.0, "Sf": 0.6,
}


# ---------- Agent: loop de tool-calling ----------

def test_agent_returns_text_immediately_when_no_tool_call_needed():
    provider = FakeProvider([text_response("Respuesta directa, sin tools.")])
    agent = Agent("test_agent", "system prompt", provider)

    result = agent.run("Hola")

    assert result.final_text == "Respuesta directa, sin tools."
    assert result.tool_calls_made == []
    assert result.hit_max_turns is False


def test_agent_executes_real_engine_tool_and_returns_valid_result():
    """Este test SÍ ejecuta el motor de cálculo real (no está mockeado) --
    valida el cableado completo tool -> engine -> resultado."""
    provider = FakeProvider([
        tool_call_response("run_design_check_uniform", VALID_UNIFORM_INPUT),
        text_response("El diseño no cumple con la norma."),
    ])
    agent = Agent("designer_test", "system", provider, tool_names=["run_design_check_uniform"])

    result = agent.run("Verificá esta malla de 60x60m")

    assert result.final_text == "El diseño no cumple con la norma."
    assert len(result.tool_calls_made) == 1

    tool_result = json.loads(result.tool_calls_made[0]["result"])
    assert "Em" in tool_result and "Es" in tool_result and "GPR" in tool_result
    assert tool_result["Em"] > 0
    assert isinstance(tool_result["passes"], bool)
    # Con estos parámetros (mismo caso que examples/basic_grid_example.py)
    # sabemos que el diseño no pasa -- confirma que el resultado es real,
    # no un placeholder.
    assert tool_result["passes"] is False


def test_agent_handles_unknown_tool_gracefully():
    provider = FakeProvider([
        tool_call_response("herramienta_inexistente", {}),
        text_response("ok"),
    ])
    agent = Agent("test", "system", provider, tool_names=["run_design_check_uniform"])

    result = agent.run("test")

    tool_result = json.loads(result.tool_calls_made[0]["result"])
    assert "error" in tool_result


def test_agent_handles_tool_exception_gracefully():
    """Si la tool recibe parámetros inválidos (ej. geometría negativa),
    el motor lanza ValueError -- el agente debe capturarlo, no crashear."""
    invalid_input = dict(VALID_UNIFORM_INPUT)
    invalid_input["rho"] = -10.0  # inválido, ver models.py

    provider = FakeProvider([
        tool_call_response("run_design_check_uniform", invalid_input),
        text_response("Hubo un error con los parámetros."),
    ])
    agent = Agent("test", "system", provider, tool_names=["run_design_check_uniform"])

    result = agent.run("test")

    tool_result = json.loads(result.tool_calls_made[0]["result"])
    assert "error" in tool_result


def test_agent_hits_max_turns_if_never_stops_calling_tools():
    responses = [tool_call_response("run_design_check_uniform", VALID_UNIFORM_INPUT) for _ in range(3)]
    provider = FakeProvider(responses)
    agent = Agent("test", "system", provider, tool_names=["run_design_check_uniform"], max_turns=3)

    result = agent.run("test")

    assert result.hit_max_turns is True


# ---------- tools.py: registro de herramientas ----------

def test_tool_schemas_have_required_fields():
    schemas = get_tool_schemas()
    assert len(schemas) >= 3
    for schema in schemas:
        assert "name" in schema and "description" in schema and "parameters" in schema
        assert schema["parameters"]["type"] == "object"


def test_get_tool_dispatch_filters_by_name():
    dispatch = get_tool_dispatch(["fit_two_layer_soil_model"])
    assert set(dispatch.keys()) == {"fit_two_layer_soil_model"}


# ---------- Coordinador: orquestación soil -> designer -> reviewer ----------

def test_pipeline_approved_on_first_iteration():
    provider = FakeProvider([
        text_response("Suelo uniforme, rho=100 Ohm*m."),           # soil_agent
        text_response("Propuesta: malla 60x60m, 7x7, 8 varillas."),  # designer_agent
        text_response("APROBADO: cumple Em y Es."),                  # reviewer_agent
    ])

    session = run_design_pipeline(
        provider, "Resistividad medida: 100 Ohm*m", "Falla 10kA, 60x60m disponibles"
    )

    assert session.final_verdict == "APROBADO"
    assert session.iterations == 1
    assert len(session.designer_results) == 1
    assert len(session.reviewer_results) == 1


def test_pipeline_retries_after_rejection_then_approves():
    provider = FakeProvider([
        text_response("Suelo uniforme, rho=100 Ohm*m."),                    # soil_agent
        text_response("Propuesta A: malla 60x60m, 5x5."),                    # designer_agent (iter 1)
        text_response("RECHAZADO: Es supera el límite tolerable."),          # reviewer_agent (iter 1)
        text_response("Propuesta B: malla 60x60m, 10x10, con varillas."),    # designer_agent (iter 2)
        text_response("APROBADO: cumple Em y Es tras el ajuste."),           # reviewer_agent (iter 2)
    ])

    session = run_design_pipeline(
        provider, "Resistividad medida: 100 Ohm*m", "Falla 10kA, 60x60m disponibles",
        max_review_iterations=3,
    )

    assert session.final_verdict == "APROBADO"
    assert session.iterations == 2
    assert len(session.designer_results) == 2

    # La segunda llamada al diseñador debe incluir el feedback del rechazo
    designer_call_2 = provider.calls[3]  # orden: soil, designer1, reviewer1, designer2
    assert "RECHAZADO" in designer_call_2["messages"][0]["content"]


def test_pipeline_returns_no_resuelto_after_max_iterations():
    provider = FakeProvider([
        text_response("Suelo uniforme, rho=100 Ohm*m."),
        text_response("Propuesta A"), text_response("RECHAZADO: falla Es."),
        text_response("Propuesta B"), text_response("RECHAZADO: sigue fallando Es."),
    ])

    session = run_design_pipeline(
        provider, "Resistividad medida: 100 Ohm*m", "Falla 10kA",
        max_review_iterations=2,
    )

    assert session.final_verdict == "NO_RESUELTO"
    assert session.iterations == 2
    assert len(session.designer_results) == 2
    assert len(session.reviewer_results) == 2
