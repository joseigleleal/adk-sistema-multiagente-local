"""Ejecuta los escenarios del caso práctico con el Runner de ADK y guarda la traza de eventos.

Uso:  .venv/bin/python correr_escenarios.py
Salida: resultados/traza.json y resultados/traza.md (qué agente habló, qué herramientas llamó, tiempos).
"""
import asyncio
import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "agentes"))

from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.genai import types  # noqa: E402

import parte_diario.agent as parte_diario  # noqa: E402
import sma_personal.agent as sma_personal  # noqa: E402

OFERTA = ("Desarrollador/a Backend Python (remoto, España). Jornada parcial de 25 h/semana. Buscamos "
          "experiencia con FastAPI, PostgreSQL e integración de modelos de lenguaje (LLM). Contrato laboral "
          "indefinido. Salario según experiencia.")

ESCENARIOS = [
    ("E1", "sma_personal", sma_personal.root_agent, "¿Hoy conviene cambiar euros a pesos colombianos?"),
    ("E2", "sma_personal", sma_personal.root_agent, f"Puntúa esta oferta para mí:\n{OFERTA}"),
    ("E3", "sma_personal", sma_personal.root_agent, "¿Cómo está el servidor donde corren los agentes?"),
    ("E4", "sma_personal", sma_personal.root_agent, "¿Me recomiendas una película para esta noche?"),
    ("E5", "parte_diario", parte_diario.root_agent, "Genera el parte diario."),
]


async def correr(cod, app, agente, mensaje):
    sesiones = InMemorySessionService()
    runner = Runner(agent=agente, app_name=app, session_service=sesiones)
    sesion = await sesiones.create_session(app_name=app, user_id="demo")
    eventos, t0 = [], time.time()
    contenido = types.Content(role="user", parts=[types.Part(text=mensaje)])
    async for ev in runner.run_async(user_id="demo", session_id=sesion.id, new_message=contenido):
        t = round(time.time() - t0, 1)
        for p in (ev.content.parts if ev.content and ev.content.parts else []):
            if p.function_call:
                eventos.append({"t": t, "autor": ev.author, "tipo": "llamada",
                                "detalle": f"{p.function_call.name}({json.dumps(p.function_call.args, ensure_ascii=False)[:120]})"})
            elif p.function_response:
                eventos.append({"t": t, "autor": ev.author, "tipo": "resultado",
                                "detalle": json.dumps(p.function_response.response, ensure_ascii=False)[:400]})
            elif p.text and not getattr(p, "thought", False):
                eventos.append({"t": t, "autor": ev.author, "tipo": "texto", "detalle": p.text.strip()})
        if ev.actions and ev.actions.transfer_to_agent:
            eventos.append({"t": t, "autor": ev.author, "tipo": "transferencia",
                            "detalle": f"→ {ev.actions.transfer_to_agent}"})
    final = await sesiones.get_session(app_name=app, user_id="demo", session_id=sesion.id)
    estado = {k: v for k, v in final.state.items() if k.startswith("informe_")}
    return {"escenario": cod, "app": app, "mensaje": mensaje, "segundos": round(time.time() - t0, 1),
            "eventos": eventos, "estado": estado}


async def main():
    resultados = []
    for esc in ESCENARIOS:
        print(f"== {esc[0]} ({esc[1]}): {esc[3][:60]}", flush=True)
        r = await correr(*esc)
        for e in r["eventos"]:
            print(f"  [{e['t']:>5}s] {e['autor']:<17} {e['tipo']:<13} {e['detalle'][:160]}", flush=True)
        resultados.append(r)
    out = RAIZ / "resultados"
    out.mkdir(exist_ok=True)
    (out / "traza.json").write_text(json.dumps(resultados, ensure_ascii=False, indent=2))
    with open(out / "traza.md", "w") as f:
        for r in resultados:
            f.write(f"## {r['escenario']} · {r['app']} · {r['segundos']} s\n\n> {r['mensaje']}\n\n")
            f.write("| t (s) | Autor | Tipo | Detalle |\n|---|---|---|---|\n")
            for e in r["eventos"]:
                f.write(f"| {e['t']} | {e['autor']} | {e['tipo']} | {e['detalle'][:300].replace('|', '/').replace(chr(10), ' ')} |\n")
            f.write("\n")
    print("Traza guardada en", out)


if __name__ == "__main__":
    asyncio.run(main())
