"""Los tres agentes especialistas del caso práctico.

Se crean con funciones (y no como objetos globales) porque en ADK un agente solo puede tener un
padre: cada sistema multiagente pide sus propias instancias.
"""
from google.adk.agents import LlmAgent

from .herramientas import consultar_tasa_eur_cop, estado_sistema, puntuar_oferta
from .modelos import MODELO_GENERAL, SIN_PENSAR


def agente_tasas() -> LlmAgent:
    return LlmAgent(
        name="agente_tasas",
        model=MODELO_GENERAL,
        description="Especialista en la tasa de cambio EUR → COP: dice si hoy conviene cambiar euros.",
        instruction=SIN_PENSAR + (
            "Eres el agente de tasas. Llama siempre a la herramienta consultar_tasa_eur_cop y responde en "
            "español, en 2 o 3 frases: tasa de hoy, cómo está frente a los últimos 90 días (mínimo, media, "
            "máximo y percentil) y si conviene cambiar. Cita la fuente. No inventes cifras."),
        tools=[consultar_tasa_eur_cop],
        output_key="informe_tasas",
    )


def agente_empleo() -> LlmAgent:
    return LlmAgent(
        name="agente_empleo",
        model=MODELO_GENERAL,
        description="Especialista en ofertas de empleo: puntúa una oferta para el perfil del candidato.",
        instruction=SIN_PENSAR + (
            "Eres el agente de empleo. Cuando te den el texto de una oferta, llama a puntuar_oferta con el "
            "texto completo. Responde en español: rol, puntuación final de 0 a 10, jornada, modalidad y el "
            "motivo que da el modelo. Si no hay ninguna oferta en el mensaje, pide que la peguen."),
        tools=[puntuar_oferta],
        output_key="informe_empleo",
    )


def agente_vigia() -> LlmAgent:
    return LlmAgent(
        name="agente_vigia",
        model=MODELO_GENERAL,
        description="Vigila el equipo donde corren los agentes: CPU, memoria, disco y el servidor de modelos.",
        instruction=SIN_PENSAR + (
            "Eres el agente vigía. Llama a estado_sistema y resume en español, en 2 frases, el nivel de "
            "alerta y el recurso más cargado. Si el nivel es 'grave', recomienda qué revisar."),
        tools=[estado_sistema],
        output_key="informe_vigia",
    )
