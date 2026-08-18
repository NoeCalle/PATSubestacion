"""
Abstracción de la interfaz humana usada por la tool ask_human.

Permite que el mismo agente (mismo código, mismo prompt) funcione con
distintas interfaces sin ningún cambio: terminal (CLI, input()/print())
o navegador (Web, servida localmente por Flask). El agente solo sabe
que "le pregunta algo a una HumanInterface y espera una respuesta" --
no le importa si esa respuesta viene de una terminal o de un formulario
HTML.
"""

import queue
import threading
from abc import ABC, abstractmethod
from typing import Optional


class HumanInterface(ABC):
    @abstractmethod
    def ask(self, question: str) -> str:
        """Debe BLOQUEAR hasta tener una respuesta real de la persona."""
        ...


class CLIHumanInterface(HumanInterface):
    """Comportamiento original: imprime la pregunta y usa input()."""

    def ask(self, question: str) -> str:
        print(f"\n🧑‍🔧 Pregunta del agente: {question}")
        try:
            return input("> ")
        except EOFError:
            return ""


class WebHumanInterface(HumanInterface):
    """
    Para la interfaz web (src/webapp). No imprime nada -- expone la
    pregunta pendiente vía get_pending_question() para que el endpoint
    /status del servidor Flask la muestre en el navegador, y bloquea
    el hilo del pipeline hasta que submit_answer() reciba la respuesta
    que el usuario escribió en la página.
    """

    def __init__(self):
        self._pending_question: Optional[str] = None
        self._answer_queue: "queue.Queue[str]" = queue.Queue(maxsize=1)
        self._lock = threading.Lock()

    def ask(self, question: str) -> str:
        with self._lock:
            self._pending_question = question
        answer = self._answer_queue.get()  # bloquea hasta submit_answer()
        with self._lock:
            self._pending_question = None
        return answer

    def get_pending_question(self) -> Optional[str]:
        with self._lock:
            return self._pending_question

    def submit_answer(self, answer: str) -> None:
        self._answer_queue.put(answer)
