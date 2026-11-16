# ADR-0003: Interfaz de la demo en Streamlit

- Estado: Aceptado
- Fecha: 2026-11-16

## Contexto
La demo en vivo dura 4 minutos y tiene que enseñar el flujo completo y la persistencia. Lo que se evalúa es la integración con la base, no el frontend.

## Decisión
Una interfaz web en **Streamlit**, en un solo `app.py`, que llama a los módulos de `src/`.

## Alternativas consideradas
| Opción | A favor | En contra |
|---|---|---|
| **Streamlit** | Formularios y tablas en pocas líneas de Python, sin JavaScript | No sirve para una app grande |
| CLI en terminal | Lo más simple | Se ve pobre en la demo y cuesta enseñar resultados |
| FastAPI + React | Arquitectura más realista | Mucho más trabajo para un parcial individual |

## Consecuencias
- La app corre en la laptop; la base sigue en la nube, que es lo que pide el enunciado.
- Cada sección enseña el Cypher que ejecuta y el tiempo de respuesta, útil para la defensa.
- El driver se guarda con `st.cache_resource` para no crearlo en cada recarga.
