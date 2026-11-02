"""Sistema multiagente jerárquico: un coordinador que delega en tres especialistas.

El coordinador no tiene herramientas propias: lee la petición y transfiere el control al
subagente adecuado (mecanismo de "agent transfer" de ADK, decidido por el modelo).
"""
from google.adk.agents import LlmAgent

from comun.especialistas import agente_empleo, agente_tasas, agente_vigia
from comun.modelos import MODELO_GENERAL, SIN_PENSAR

root_agent = LlmAgent(
    name="coordinador",
    model=MODELO_GENERAL,
    description="Coordinador del sistema multiagente personal.",
    instruction=SIN_PENSAR + (
        "Eres el coordinador de un sistema multiagente personal. No respondas tú las preguntas de los "
        "especialistas: transfiere la conversación al agente adecuado.\n"
        "- Tasas de cambio, euros, pesos colombianos → agente_tasas\n"
        "- Ofertas de empleo o trabajo → agente_empleo\n"
        "- Estado del equipo, servidor, CPU, memoria, disco → agente_vigia\n"
        "Si la petición no encaja con ninguno, explica en una frase qué sabe hacer cada agente."),
    sub_agents=[agente_tasas(), agente_empleo(), agente_vigia()],
)
