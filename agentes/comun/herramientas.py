"""Herramientas (function tools) compartidas por los agentes del caso práctico.

Cada función es una herramienta de ADK: el framework lee su nombre, su docstring y sus tipos para
describírsela al modelo, y el modelo decide cuándo llamarla. Todo corre en local: los datos de
ejemplo están en `datos/` y los modelos se sirven con Ollama.
"""
import csv
import json
import os
import shutil
import statistics
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import psutil

DATOS = Path(__file__).resolve().parent / "datos"
OLLAMA_URL = os.environ.get("OLLAMA_API_BASE", "http://localhost:11434")
MODELO_PUNTUADOR = os.environ.get("MODELO_PUNTUADOR", "empleo-puntuador-r2-q5-k-m")

# Perfil ficticio de candidato (no corresponde a ninguna persona real)
PERFIL = ("Ingeniero de software con 6 años de experiencia en Python, backend, datos e IA (LLM, agentes). "
          "Busca trabajo remoto o en Salamanca, a tiempo parcial (máximo 30 h/semana).")

PROMPT_PUNTUADOR = """You evaluate a job offer in Spain for a specific candidate. Be strict and skeptical.
Never guess: if the offer does not state something, answer "unknown", null or false.
Return ONLY this JSON object:
{
  "main_role": "<the role being hired, max 8 words>",
  "role_is_technical": <true if the job is mainly software development, data, AI/ML or automation>,
  "skill_match": <integer 0-10: how well the REQUIRED skills and seniority match the candidate>,
  "schedule": "part_time" | "full_time" | "unknown",
  "weekly_hours": <integer hours per week if stated, else null>,
  "work_mode": "remote" | "hybrid" | "onsite" | "unknown",
  "red_flags": <true if unpaid, scam-like or requires paying>,
  "reason": "<one short sentence in Spanish explaining the fit>"
}"""


# ----------------------------------------------------------------------------- agente de tasas
CACHE_TASAS = DATOS / "tasas_eur_cop_90d.csv"


def _get_json(url: str):
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.load(r)


def _historico_en_vivo(dias: int = 90) -> list[tuple[str, float]]:
    """EUR/COP diario = TRM oficial (datos.gov.co) × EUR/USD del BCE (Frankfurter). Fuentes públicas."""
    desde = (date.today() - timedelta(days=dias)).isoformat()
    q = urllib.parse.urlencode({"$where": f"vigenciadesde >= '{desde}'", "$order": "vigenciadesde ASC",
                                "$limit": 1000})
    trm = {}
    for fila in _get_json(f"https://www.datos.gov.co/resource/32sa-8pi3.json?{q}"):
        d, hasta = date.fromisoformat(fila["vigenciadesde"][:10]), date.fromisoformat(fila["vigenciahasta"][:10])
        while d <= hasta:
            trm[d] = float(fila["valor"])
            d += timedelta(days=1)
    eurusd = {date.fromisoformat(k): v["USD"] for k, v in
              _get_json(f"https://api.frankfurter.dev/v1/{desde}..?base=EUR&symbols=USD")["rates"].items()}
    serie, ultimo = [], None
    for d in sorted(trm):
        ultimo = eurusd.get(d, ultimo)
        if ultimo and d <= date.today():
            serie.append((d.isoformat(), round(trm[d] * ultimo, 2)))
    with open(CACHE_TASAS, "w", newline="") as f:  # copia local por si no hay conexión
        w = csv.writer(f)
        w.writerow(["fecha", "tasa"])
        w.writerows(serie)
    return serie


def _historico() -> tuple[list[tuple[str, float]], str]:
    try:
        return _historico_en_vivo(), "TRM (Banco de la República) × EUR/USD (BCE), en vivo"
    except Exception:
        with open(CACHE_TASAS, newline="") as f:
            return [(r["fecha"], float(r["tasa"])) for r in csv.DictReader(f)], "copia local de la última consulta"


def consultar_tasa_eur_cop() -> dict:
    """Consulta la tasa de cambio EUR → COP de hoy y la compara con los últimos 90 días.

    Returns:
        Un diccionario con la tasa actual, su fuente, el mínimo, la media y el máximo de 90 días,
        el percentil de la tasa actual y si conviene cambiar euros (tasa alta = buen momento).
    """
    historico, fuente = _historico()
    valores = [v for _, v in historico]
    actual = valores[-1]
    percentil = round(100 * sum(v <= actual for v in valores) / len(valores))
    return {
        "fecha": historico[-1][0],
        "tasa_actual": round(actual, 2),
        "fuente": fuente,
        "minimo_90d": min(valores),
        "media_90d": round(statistics.mean(valores), 2),
        "maximo_90d": max(valores),
        "percentil_actual": percentil,
        "conviene_cambiar": percentil >= 80,
    }


# ----------------------------------------------------------------------------- agente de empleo
def puntuar_oferta(texto_oferta: str) -> dict:
    """Puntúa una oferta de empleo para el perfil del candidato con un modelo local afinado con LoRA.

    Args:
        texto_oferta: El texto completo de la oferta de empleo.

    Returns:
        Los datos extraídos por el modelo (rol, encaje, jornada, modalidad, señales de alerta) y una
        puntuación final de 0 a 10 calculada con reglas.
    """
    cuerpo = {
        "model": MODELO_PUNTUADOR,
        "stream": False,
        "think": False,  # sin "modo pensamiento" si el modelo lo tiene (p. ej. qwen3)
        "format": "json",
        "options": {"temperature": 0},
        "messages": [
            {"role": "system", "content": PROMPT_PUNTUADOR},
            {"role": "user", "content": f"Candidate: {PERFIL}\n\nJob offer:\n{texto_oferta}"},
        ],
    }
    req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=json.dumps(cuerpo).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        datos = json.loads(json.load(r)["message"]["content"])
    puntos = max(0, min(10, int(datos.get("skill_match") or 0)))
    if not datos.get("role_is_technical", False):
        puntos = min(puntos, 3)
    horas = datos.get("weekly_hours")
    if datos.get("schedule") == "full_time" or (horas and horas > 30):
        puntos = max(0, puntos - 2)
    if datos.get("red_flags"):
        puntos = 0
    datos["puntuacion_final"] = puntos
    datos["modelo"] = MODELO_PUNTUADOR
    return datos


# ----------------------------------------------------------------------------- agente vigía
def estado_sistema() -> dict:
    """Mide el estado del equipo donde corren los agentes: CPU, memoria, disco y si Ollama responde.

    Returns:
        Un diccionario con el uso de CPU, RAM y disco en porcentaje, si Ollama está disponible y un
        nivel de alerta ("ok", "leve" o "grave").
    """
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    disco = shutil.disk_usage("/")
    disco_pct = round(100 * disco.used / disco.total, 1)
    try:
        urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=3)
        ollama = True
    except Exception:
        ollama = False
    peor = max(cpu, ram, disco_pct)
    nivel = "grave" if peor > 90 or not ollama else "leve" if peor > 75 else "ok"
    return {"cpu_pct": cpu, "ram_pct": ram, "disco_pct": disco_pct, "ollama_disponible": ollama,
            "nivel": nivel}
