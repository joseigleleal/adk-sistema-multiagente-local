"""Modelos locales servidos con Ollama, conectados a ADK a través de LiteLLM (sin cuentas ni nube)."""
import os

from google.adk.models.lite_llm import LiteLlm

os.environ.setdefault("OLLAMA_API_BASE", "http://localhost:11434")

# Modelo general para razonar y llamar herramientas (Qwen3 8B, con capacidad de tool calling).
# think=False apaga el "modo pensamiento" de Qwen3 en Ollama: sin él cada llamada tarda ~30 veces más
# (en las pruebas, 60 s frente a 2 s para la misma respuesta corta).
MODELO_GENERAL = LiteLlm(model=os.environ.get("MODELO_GENERAL", "ollama_chat/qwen3:8b"), think=False)

SIN_PENSAR = ""  # se mantiene por compatibilidad con las instrucciones de los agentes
