"""Expone el agente de tasas como servicio A2A (Agent2Agent) en http://localhost:8001.

ADK genera la Agent Card automáticamente y la publica en /.well-known/agent-card.json.
Cualquier cliente A2A, sea de ADK o de otro framework, puede descubrirlo y pedirle tareas.

Uso:  .venv/bin/python servidor_a2a.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "agentes"))
os.environ.setdefault("ADK_SUPPRESS_A2A_EXPERIMENTAL_FEATURE_WARNINGS", "1")

import uvicorn  # noqa: E402
from google.adk.a2a.utils.agent_to_a2a import to_a2a  # noqa: E402

from comun.especialistas import agente_tasas  # noqa: E402

app = to_a2a(agente_tasas(), port=8001)

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8001)
