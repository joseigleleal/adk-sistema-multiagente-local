# Sistema multiagente local con Google ADK

Tres agentes de IA que cooperan entre sí, construidos con **Google Agent Development Kit (ADK) 2.13.0**. Todo
corre **en tu propio ordenador**: los modelos de lenguaje se sirven con [Ollama](https://ollama.com), no hace
falta ninguna cuenta de Google ni de ningún servicio en la nube, y no se paga nada.

Es el caso práctico del trabajo final de *Inteligencia Ambiental y Sistemas Multiagente* (Máster en Sistemas
Inteligentes, Universidad de Salamanca, curso 2026/27). La memoria completa, con la teoría, la comparativa con
otras herramientas y la proyección a futuro, se entregó aparte en PDF; aquí está el código para replicarlo.

---

## La idea en dos minutos

Tenía un sistema personal de agentes: pequeños programas que trabajan solos en segundo plano. Uno vigila la
tasa de cambio de euros a pesos colombianos, otro busca y puntúa ofertas de empleo, otro vigila que el servidor
esté bien. Funcionan, pero **cada uno va por su cuenta**: ninguno habla con los demás. Según la definición
clásica (Wooldridge y Jennings, 1995), eso es un conjunto de agentes autónomos, pero **no un sistema
multiagente**, porque le falta la parte social: que los agentes se comuniquen y se coordinen.

Este proyecto reconstruye tres de esos agentes con ADK y los hace cooperar de **tres formas distintas**:

| Sistema | Cómo cooperan los agentes | Con qué se parece en la vida real |
|---|---|---|
| `sma_personal` | Un **coordinador** lee tu pregunta y se la pasa al especialista adecuado | La recepción de una empresa que te deriva al departamento correcto |
| `parte_diario` | Dos especialistas trabajan **a la vez** y un tercero junta sus informes | Dos personas preparan cada una su parte y una tercera redacta el resumen |
| `sma_a2a` | El especialista vive en **otro programa** y se le habla por un protocolo estándar (A2A) | Llamar por teléfono a un experto de otra empresa en vez de tenerlo en tu oficina |

---

## Los agentes, uno por uno

Hay **tres especialistas**. Cada uno es un agente con su propio modelo de lenguaje y una sola herramienta, que
es una función de Python que hace el trabajo de verdad.

### `agente_tasas`: ¿conviene cambiar euros hoy?

- **Qué hace:** te dice cuánto vale hoy un euro en pesos colombianos y si es buen momento para cambiar.
- **Cómo lo sabe:** su herramienta `consultar_tasa_eur_cop` calcula la tasa diaria de los últimos 90 días con
  datos públicos y oficiales:
  - la **TRM** del Banco de la República de Colombia (dólar a peso), vía [datos.gov.co](https://www.datos.gov.co/resource/32sa-8pi3.json);
  - el **EUR/USD** del Banco Central Europeo, vía [Frankfurter](https://api.frankfurter.dev/v1).

  Multiplica ambas y mira en qué **percentil** está la tasa de hoy respecto a esos 90 días. Si está en el 20 %
  más alto, conviene cambiar.
- **Sin internet:** usa la última copia guardada en `agentes/comun/datos/tasas_eur_cop_90d.csv`.

### `agente_empleo`: ¿me sirve esta oferta?

- **Qué hace:** le pegas el texto de una oferta de trabajo y te devuelve el rol, la jornada, la modalidad
  (remoto, híbrido o presencial), posibles señales de alerta y una **puntuación de 0 a 10**.
- **Cómo lo sabe:** su herramienta `puntuar_oferta` le pide a un modelo pequeño que extraiga esos datos en
  JSON, y luego unas reglas fijas calculan la puntuación. Por ejemplo, si la oferta es de jornada completa y el
  perfil busca media jornada, baja la nota.
- **El modelo:** por defecto es `empleo-puntuador-r2-q5-k-m`, un Qwen2.5 de 1,5B parámetros **afinado con LoRA**:
  aprendió de las respuestas de un modelo mucho más grande. Si no lo tienes, puedes usar cualquier otro modelo
  de Ollama (más abajo se explica cómo).
- **Perfil del candidato:** es **ficticio** y está en `herramientas.py`. Cámbialo por el tuyo si quieres.

### `agente_vigia`: ¿cómo está el equipo?

- **Qué hace:** mide la CPU, la memoria y el disco del ordenador y comprueba que Ollama responde. Te da un
  nivel de alerta: `ok`, `leve` o `grave`.
- **Cómo lo sabe:** su herramienta `estado_sistema` usa `psutil`, la librería estándar para leer el estado del
  sistema.

### Los que coordinan

| Agente | Dónde está | Qué hace |
|---|---|---|
| `coordinador` | `sma_personal` | No responde nada por sí mismo: decide a qué especialista pasar la conversación |
| `recoger_informes` | `parte_diario` | Ejecuta tasas y vigía **en paralelo** (es un `ParallelAgent`, no usa modelo) |
| `redactor` | `parte_diario` | Lee los dos informes del estado compartido y escribe el parte diario |
| `coordinador_a2a` | `sma_a2a` | Igual que el coordinador, pero su especialista de tasas está en otro proceso |

---

## Cómo se coordinan, por dentro

```
sma_personal                         parte_diario                          sma_a2a
────────────                         ────────────                          ───────
     coordinador (LLM)               SequentialAgent                      coordinador_a2a (LLM)
     │  "esto es de tasas"           ├─ ParallelAgent                      │
     ├─▶ agente_tasas                │   ├─ agente_tasas ─┐ escriben en     ├─▶ agente_vigia (local)
     ├─▶ agente_empleo               │   └─ agente_vigia ─┘ el estado       └─▶ agente_tasas_remoto ──A2A──▶ servidor_a2a.py
     └─▶ agente_vigia                └─ redactor ◀─ lee el estado                (otro proceso, puerto 8001)
```

1. **Delegación (`sub_agents`).** El coordinador tiene una lista de subagentes, cada uno con una descripción.
   ADK le da automáticamente una herramienta `transfer_to_agent`, y el modelo decide a quién pasar el control
   leyendo esas descripciones. Por eso las descripciones importan tanto: son lo que el modelo lee para decidir.
2. **Flujo con estado compartido (`SequentialAgent`, `ParallelAgent` y `output_key`).** Aquí el orden lo fija el
   código, no el modelo:
   - cada especialista guarda su respuesta en el estado de la sesión con `output_key`, en `informe_tasas` e
     `informe_vigia`;
   - el redactor la lee escribiendo `{informe_tasas}` en sus instrucciones.

   Funciona como una pizarra compartida.
3. **Agente remoto (`to_a2a` y `RemoteA2aAgent`).**
   - `servidor_a2a.py` publica el agente de tasas como un servicio web que habla
     [A2A (Agent2Agent)](https://a2a-protocol.org), el protocolo abierto para que agentes de distintos
     programas, o incluso de distintos frameworks, se comuniquen.
   - ADK genera sola su **Agent Card**, su "tarjeta de visita": quién es, qué sabe hacer y dónde escucha. Está
     en `http://localhost:8001/.well-known/agent-card.json`.
   - El coordinador solo necesita esa URL para usarlo.

---

## Cómo replicarlo paso a paso

Probado en un Mac con Apple Silicon y 16 GB de RAM. Debería funcionar igual en Linux. En Windows cambian las
rutas del entorno virtual (`.venv\Scripts\python`).

### 1. Instala Ollama y descarga el modelo

```bash
# macOS: brew install ollama   ·   Linux: curl -fsSL https://ollama.com/install.sh | sh
ollama serve &                 # si no está ya corriendo
ollama pull qwen3:8b           # ~5 GB; es el modelo que razona y decide qué herramienta usar
```

`qwen3:8b` sabe llamar herramientas (*tool calling*), que es imprescindible. Si tu equipo va justo de memoria,
otros modelos con herramientas también sirven (`ollama show <modelo>` te dice si las soporta). Cambia la
variable `MODELO_GENERAL`.

### 2. Crea el entorno de Python e instala las dependencias

```bash
git clone https://github.com/joseigleleal/adk-sistema-multiagente-local.git
cd adk-sistema-multiagente-local
python3.12 -m venv .venv                       # Python 3.11 o superior
.venv/bin/pip install -r requirements.txt
```

### 3. ¿No tienes el modelo afinado con LoRA? Usa otro

El agente de empleo usa por defecto un modelo propio que no está publicado. Para probarlo con un modelo
estándar:

```bash
export MODELO_PUNTUADOR=qwen3:8b
```

### 4. Ejecuta los escenarios automáticos

```bash
export OLLAMA_API_BASE=http://localhost:11434
.venv/bin/python correr_escenarios.py
```

Hace cinco preguntas a los agentes y guarda en `resultados/` qué agente respondió, qué herramientas llamó y
cuánto tardó (`traza.json` y `traza.md`). Cuenta con entre 30 y 100 segundos por pregunta con un modelo de 8B.

### 5. Prueba la comunicación entre procesos (A2A)

En una terminal deja corriendo el servidor:

```bash
.venv/bin/python servidor_a2a.py
```

En otra, lanza el escenario que lo usa:

```bash
.venv/bin/python correr_a2a.py
```

### 6. Juega con la interfaz web

```bash
.venv/bin/adk web agentes          # abre http://localhost:8000
```

Elige una de las tres aplicaciones arriba a la izquierda y escribe. Por ejemplo:

- *"¿Hoy conviene cambiar euros a pesos colombianos?"*
- *"Puntúa esta oferta para mí: Desarrollador Python remoto, 25 h/semana, FastAPI y PostgreSQL."*
- *"¿Cómo está el servidor?"*
- *"Genera el parte diario"*, en la aplicación `parte_diario`.

En la interfaz verás cada paso:
- la transferencia del coordinador al especialista;
- la llamada a la herramienta con su resultado;
- en la pestaña **Traces**, cuánto tardó cada parte;
- en **State**, los informes que se comparten entre agentes;
- con el botón del árbol (`account_tree`), el grafo de agentes.

`sma_a2a` necesita que `servidor_a2a.py` esté corriendo.

---

## Variables de entorno

| Variable | Por defecto | Para qué |
|---|---|---|
| `OLLAMA_API_BASE` | `http://localhost:11434` | Dónde escucha Ollama |
| `MODELO_GENERAL` | `ollama_chat/qwen3:8b` | Modelo de los agentes (formato LiteLLM; usa el prefijo `ollama_chat/`, no `ollama/`) |
| `MODELO_PUNTUADOR` | `empleo-puntuador-r2-q5-k-m` | Modelo que extrae los datos de las ofertas (nombre de Ollama) |

---

## Qué hay en cada carpeta

```
adk-sistema-multiagente-local/
├── agentes/                    ← lo que carga `adk web` (una subcarpeta = una aplicación)
│   ├── comun/                  ← piezas compartidas (no es una aplicación)
│   │   ├── herramientas.py     ← las 3 herramientas: tasas, ofertas, estado del sistema
│   │   ├── especialistas.py    ← los 3 agentes especialistas
│   │   ├── modelos.py          ← conexión con Ollama a través de LiteLLM
│   │   └── datos/              ← copia local de las tasas de 90 días
│   ├── sma_personal/agent.py   ← coordinador + 3 especialistas
│   ├── parte_diario/agent.py   ← flujo paralelo + redactor
│   └── sma_a2a/agent.py        ← coordinador + agente remoto por A2A
├── servidor_a2a.py             ← publica el agente de tasas como servicio A2A (puerto 8001)
├── correr_escenarios.py        ← escenarios E1–E5 con el Runner de ADK
├── correr_a2a.py               ← escenario E6 (A2A)
├── resultados/                 ← trazas de la ejecución del 2-nov-2026 y la Agent Card generada
└── requirements.txt
```

Cada aplicación de ADK es una carpeta con un `__init__.py` y un `agent.py` que define una variable llamada
`root_agent`. Es lo único que ADK necesita para encontrarla.

---

## Resultados obtenidos

Ejecución del 2 de noviembre de 2026 en un MacBook con Apple Silicon y 16 GB de RAM, con `qwen3:8b`:

| | Pregunta | Qué pasó | Tiempo |
|---|---|---|---|
| E1 | ¿Conviene cambiar euros hoy? | El coordinador derivó a tasas: 3570,04 COP/EUR, percentil 26 → no conviene | 49,7 s |
| E2 | Puntúa esta oferta | Derivó a empleo; el modelo LoRA la puntuó con 8/10 (backend Python, 25 h, remoto) | 49,9 s |
| E3 | ¿Cómo está el servidor? | Derivó a vigía: RAM al 90 % → nivel "grave" (los modelos estaban cargados) | 30,2 s |
| E4 | Recomiéndame una película | No derivó a nadie: explicó que ningún especialista cubre eso (caso de control) | 4,4 s |
| E5 | Genera el parte diario | Tasas y vigía en paralelo; el redactor juntó los dos informes | 100,2 s |
| E6 | ¿Conviene cambiar euros hoy? (A2A) | Igual que E1, pero el especialista respondió desde otro proceso por A2A | 42,9 s |

**Lo más interesante:** casi todo el tiempo lo gasta el modelo en pensar y redactar. Las herramientas tardan
menos de un segundo. Con un modelo en la nube iría mucho más rápido; en local el precio se paga en tiempo, no
en dinero ni en privacidad.

---

## Problemas conocidos y cómo resolverlos

| Síntoma | Causa | Solución |
|---|---|---|
| Cada respuesta tarda más de un minuto | Qwen3 tiene un "modo pensamiento" que genera mucho texto antes de responder | Ya está desactivado con `think=False` en `modelos.py`. Si cambias de modelo, revisa que no lo active |
| `No module named 'mcp'` en la primera llamada | La versión de LiteLLM que instala pip lo necesita, aunque ADK no lo declara | `pip install mcp` (ya está en `requirements.txt`) |
| El agente llama a la herramienta en bucle | Se usó el prefijo `ollama/` | Usa `ollama_chat/<modelo>` (lo advierte la documentación de ADK) |
| `sma_a2a` no responde | El servidor A2A no está corriendo | Lanza `servidor_a2a.py` en otra terminal |
| `.venv/bin/pip: bad interpreter` | Moviste la carpeta y el entorno virtual guarda rutas absolutas | Borra `.venv` y vuelve a crearlo (paso 2) |
| El ordenador va muy lento | El modelo de 8B ocupa unos 5 GB de RAM | Cierra otras aplicaciones o usa un modelo más pequeño con soporte de herramientas |

---

## Añadir un agente nuevo

1. Escribe su herramienta en `agentes/comun/herramientas.py`. Es una función de Python normal con un
   **docstring claro** y tipos en los parámetros, porque eso es lo que lee el modelo para saber cuándo usarla.
2. Crea el agente en `agentes/comun/especialistas.py`, copiando uno de los existentes. Dale un `name`, una
   `description` (el coordinador la lee para decidir si derivarle algo) y unas instrucciones.
3. Añádelo a la lista `sub_agents` del coordinador en `agentes/sma_personal/agent.py`, y una línea en sus
   instrucciones indicando qué tipo de preguntas le corresponden.
4. Reinicia `adk web` y pruébalo.

---

## Créditos y fuentes

- [Google ADK](https://adk.dev/), licencia Apache 2.0.
- [Ollama](https://ollama.com) y los modelos Qwen3 y Qwen2.5 (Alibaba).
- Datos de tipo de cambio:
  - TRM del [Banco de la República](https://www.datos.gov.co/resource/32sa-8pi3.json), vía datos.gov.co;
  - EUR/USD del BCE, vía [Frankfurter](https://frankfurter.dev).
- Protocolo [A2A](https://a2a-protocol.org) (Linux Foundation / Agentic AI Foundation).

Autor: Jose Iglesias · Máster en Sistemas Inteligentes · Universidad de Salamanca.
