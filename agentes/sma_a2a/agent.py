"""Coordinador que usa un agente remoto por A2A.

El agente de tasas ya no vive en este proceso: corre en `servidor_a2a.py` (otro proceso, que podría
estar en otra máquina o escrito con otro framework). El coordinador solo conoce su Agent Card.
Requiere tener `servidor_a2a.py` corriendo.
"""
from google.adk.agents import LlmAgent
from google.adk.agents.remote_a2a_agent import AGENT_CARD_WELL_KNOWN_PATH, RemoteA2aAgent

from comun.especialistas import agente_vigia
from comun.modelos import MODELO_GENERAL, SIN_PENSAR

tasas_remoto = RemoteA2aAgent(
    name="agente_tasas_remoto",
    description="Agente remoto (A2A) especialista en la tasa EUR → COP.",
    agent_card=f"http://localhost:8001{AGENT_CARD_WELL_KNOWN_PATH}",
)

root_agent = LlmAgent(
    name="coordinador_a2a",
    model=MODELO_GENERAL,
    description="Coordinador que combina un agente local y uno remoto por A2A.",
    instruction=SIN_PENSAR + (
        "Eres el coordinador. Transfiere las preguntas sobre tasas de cambio a agente_tasas_remoto y "
        "las del estado del equipo a agente_vigia. No respondas tú esas preguntas."),
    sub_agents=[tasas_remoto, agente_vigia()],
)
