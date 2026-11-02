"""Escenario E6: coordinador local + agente de tasas remoto por A2A.

Requiere `servidor_a2a.py` corriendo en otra terminal.
Uso:  .venv/bin/python correr_a2a.py   →   resultados/traza_a2a.json
"""
import asyncio
import json

import correr_escenarios as base
import sma_a2a.agent as sma_a2a


async def main():
    r = await base.correr("E6", "sma_a2a", sma_a2a.root_agent, "¿Hoy conviene cambiar euros a pesos colombianos?")
    for e in r["eventos"]:
        print(f"  [{e['t']:>5}s] {e['autor']:<20} {e['tipo']:<13} {e['detalle'][:160]}", flush=True)
    (base.RAIZ / "resultados" / "traza_a2a.json").write_text(json.dumps(r, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
