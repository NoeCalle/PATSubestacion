"""
Tests de la herramienta ask_human -- la pieza que permite una
conversación real entre el agente y la persona (no solo un guion
precargado de una sola pasada).

Como ask_human hace E/S real (input() por la terminal), estos tests
simulan la respuesta de la persona con monkeypatch en vez de requerir
una terminal interactiva de verdad -- eso valida toda la lógica de
integración (la tool se ejecuta, el agente recibe la respuesta y
puede seguir razonando con ella) sin depender de que alguien esté
tipeando en vivo.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from src.agents.providers.base import LLMProvider, ProviderResponse, ToolCall
from src.agents.base_agent import Agent
from src.agents.tools import get_tool_dispatch


class FakeProvider(LLMProvider):
    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def chat(self, system, messages, tools):
        self.calls.append({"system": system, "messages": messages, "tools": tools})
        if not self.script:
            raise AssertionError("FakeProvider se quedó sin respuestas scripteadas")
        return self.script.pop(0)

    def format_assistant_message(self, response):
        return {"role": "assistant", "content": response.text, "_tool_calls": response.tool_calls}

    def format_tool_result(self, tool_call_id, content):
        return {"role": "tool_result", "tool_call_id": tool_call_id, "content": content}


def text_response(text):
    return ProviderResponse(text=text, tool_calls=[])


def tool_call_response(name, input_, call_id="call_1"):
    return ProviderResponse(text=None, tool_calls=[ToolCall(id=call_id, name=name, input=input_)])


# ---------- La función ask_human en aislamiento ----------

def test_ask_human_returns_typed_input(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _prompt="": "150")

    dispatch = get_tool_dispatch(["ask_human"])
    answer = dispatch["ask_human"](question="¿Cuál es la resistividad del suelo?")

    assert answer == "150"
    captured = capsys.readouterr()
    assert "resistividad del suelo" in captured.out


def test_ask_human_handles_eof_gracefully(monkeypatch):
    """En un entorno no interactivo (sin terminal real), input() puede
    lanzar EOFError -- no debe crashear el pipeline."""
    def raise_eof(_prompt=""):
        raise EOFError()

    monkeypatch.setattr("builtins.input", raise_eof)

    dispatch = get_tool_dispatch(["ask_human"])
    answer = dispatch["ask_human"](question="¿Algo?")

    assert answer == ""


# ---------- Integración con el loop del agente ----------

def test_agent_asks_human_and_uses_the_answer(monkeypatch):
    """Simula el caso real: el agente decide que le falta un dato,
    llama a ask_human, recibe la respuesta simulada de la persona, y
    la usa en su siguiente decisión (acá, simplemente la repite en su
    respuesta final -- lo que importa es que el dato viajó de ida y
    vuelta correctamente por el loop de tools)."""
    monkeypatch.setattr("builtins.input", lambda _prompt="": "120 Ohm*m")

    provider = FakeProvider([
        tool_call_response("ask_human", {"question": "¿Cuál es la resistividad del suelo?"}),
        text_response("El usuario indicó una resistividad de 120 Ohm*m. Modelo: suelo uniforme."),
    ])
    agent = Agent("soil_test", "system", provider, tool_names=["ask_human"])

    result = agent.run("No tengo datos de suelo todavía.")

    assert "120 Ohm*m" in result.final_text
    assert len(result.tool_calls_made) == 1
    assert result.tool_calls_made[0]["tool"] == "ask_human"
    # El resultado de la tool (json.dumps de un string) debe contener la respuesta real
    assert "120 Ohm*m" in result.tool_calls_made[0]["result"]


def test_agent_can_ask_multiple_questions_before_finishing(monkeypatch):
    """El agente puede necesitar más de un dato -- confirma que el loop
    soporta varias rondas de ask_human seguidas."""
    answers = iter(["100 Ohm*m", "60x60 metros"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    provider = FakeProvider([
        tool_call_response("ask_human", {"question": "¿Resistividad?"}, call_id="q1"),
        tool_call_response("ask_human", {"question": "¿Dimensiones del terreno?"}, call_id="q2"),
        text_response("Datos completos: 100 Ohm*m, terreno 60x60 metros."),
    ])
    agent = Agent("test", "system", provider, tool_names=["ask_human"], max_turns=5)

    result = agent.run("Ayudame con mi diseño.")

    assert "100 Ohm*m" in result.final_text
    assert "60x60 metros" in result.final_text
    assert len(result.tool_calls_made) == 2


def test_reviewer_agent_does_not_have_ask_human():
    """El agente revisor audita de forma independiente -- no debería
    poder reabrir la recolección de datos preguntándole a la persona."""
    from src.agents.reviewer_agent import create_reviewer_agent

    provider = FakeProvider([text_response("APROBADO")])
    agent = create_reviewer_agent(provider)

    tool_names = [t["name"] for t in agent.tool_schemas]
    assert "ask_human" not in tool_names


def test_soil_and_designer_agents_have_ask_human():
    from src.agents.soil_agent import create_soil_agent
    from src.agents.designer_agent import create_designer_agent

    provider = FakeProvider([])  # no se llega a usar en este test
    soil_tool_names = [t["name"] for t in create_soil_agent(provider).tool_schemas]
    designer_tool_names = [t["name"] for t in create_designer_agent(provider).tool_schemas]

    assert "ask_human" in soil_tool_names
    assert "ask_human" in designer_tool_names
