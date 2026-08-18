"""Tests de los helpers de entrada de consola (src/cli/prompts.py)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.cli.prompts import ask_float, ask_int, ask_yes_no, ask_text, ask_choice


def _inputs(monkeypatch, values):
    it = iter(values)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(it))


def test_ask_float_parses_valid_number(monkeypatch):
    _inputs(monkeypatch, ["123.5"])
    assert ask_float("x") == 123.5


def test_ask_float_uses_default_on_blank(monkeypatch):
    _inputs(monkeypatch, [""])
    assert ask_float("x", default=42.0) == 42.0


def test_ask_float_reprompts_on_invalid_text(monkeypatch, capsys):
    _inputs(monkeypatch, ["no_es_numero", "50"])
    assert ask_float("x") == 50.0
    assert "número válido" in capsys.readouterr().out


def test_ask_float_reprompts_below_min_value(monkeypatch, capsys):
    _inputs(monkeypatch, ["-5", "10"])
    assert ask_float("x", min_value=0) == 10.0
    assert "mayor a 0" in capsys.readouterr().out


def test_ask_int_parses_valid_int(monkeypatch):
    _inputs(monkeypatch, ["7"])
    assert ask_int("x") == 7


def test_ask_int_rejects_float_string(monkeypatch):
    _inputs(monkeypatch, ["7.5", "7"])
    assert ask_int("x") == 7


def test_ask_yes_no_true_variants(monkeypatch):
    for word in ["s", "si", "sí", "y", "yes"]:
        _inputs(monkeypatch, [word])
        assert ask_yes_no("x") is True


def test_ask_yes_no_false_variants(monkeypatch):
    for word in ["n", "no"]:
        _inputs(monkeypatch, [word])
        assert ask_yes_no("x", default=True) is False


def test_ask_yes_no_blank_uses_default(monkeypatch):
    _inputs(monkeypatch, [""])
    assert ask_yes_no("x", default=True) is True
    _inputs(monkeypatch, [""])
    assert ask_yes_no("x", default=False) is False


def test_ask_text_returns_typed_value(monkeypatch):
    _inputs(monkeypatch, ["Subestación Norte"])
    assert ask_text("x") == "Subestación Norte"


def test_ask_text_blank_uses_default(monkeypatch):
    _inputs(monkeypatch, [""])
    assert ask_text("x", default="valor por defecto") == "valor por defecto"


def test_ask_choice_valid_key(monkeypatch):
    _inputs(monkeypatch, ["2"])
    result = ask_choice("x", {"1": "Uno", "2": "Dos"})
    assert result == "2"


def test_ask_choice_blank_uses_default(monkeypatch):
    _inputs(monkeypatch, [""])
    result = ask_choice("x", {"1": "Uno", "2": "Dos"}, default="1")
    assert result == "1"


def test_ask_choice_reprompts_on_invalid_key(monkeypatch, capsys):
    _inputs(monkeypatch, ["9", "1"])
    result = ask_choice("x", {"1": "Uno", "2": "Dos"})
    assert result == "1"
    assert "inválida" in capsys.readouterr().out
