"""Flujo de trabajo determinista: dos especialistas en paralelo y un redactor que junta sus informes.

ParallelAgent ejecuta a la vez los agentes de tasas y vigía (cada uno guarda su resultado en el
estado de la sesión con output_key); después SequentialAgent pasa al redactor, que lee ese estado.
Aquí el orden no lo decide el modelo: lo fija el código.
"""
from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent

from comun.especialistas import agente_tasas, agente_vigia
from comun.modelos import MODELO_GENERAL, SIN_PENSAR

redactor = LlmAgent(
    name="redactor",
    model=MODELO_GENERAL,
    description="Junta los informes de los especialistas en un parte diario.",
    instruction=SIN_PENSAR + (
        "Redacta el parte diario en español con dos apartados cortos, 'Tasas' y 'Sistema', usando SOLO "
        "estos informes, sin añadir datos:\n"
        "Tasas: {informe_tasas}\n"
        "Sistema: {informe_vigia}\n"
        "Termina con una línea 'Acción recomendada:'."),
)

root_agent = SequentialAgent(
    name="parte_diario",
    description="Parte diario: tasas y estado del sistema en paralelo, y luego un resumen.",
    sub_agents=[
        ParallelAgent(name="recoger_informes", sub_agents=[agente_tasas(), agente_vigia()]),
        redactor,
    ],
)
