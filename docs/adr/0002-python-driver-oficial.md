# ADR-0002: Python con el driver oficial de Neo4j

- Estado: Aceptado
- Fecha: 2026-11-16

## Contexto
El enunciado permite cualquier lenguaje, pero pide usar el SDK o driver oficial del motor.

## Decisión
Python 3.12+ con el paquete oficial `neo4j` (versión 5.x), usando `driver.execute_query()` y un solo driver para toda la app.

## Alternativas consideradas
| Opción | A favor | En contra |
|---|---|---|
| **Python + `neo4j`** | Driver oficial, lo conozco mejor, `execute_query` maneja reintentos y transacciones | — |
| Python + py2neo / neomodel (OGM) | Mapea nodos a clases | py2neo ya no se mantiene; un OGM esconde el Cypher, que es justo lo que se evalúa |
| Node.js + `neo4j-driver` | También oficial | Menos práctica en JavaScript para la defensa |

## Consecuencias
- Un solo driver con pool de conexiones, reutilizado en cada consulta (crear uno por consulta sería lento).
- `execute_query` corre cada consulta en una transacción administrada y reintenta solo ante errores transitorios.
- Las lecturas se marcan con `routing_=READ` y las escrituras con `routing_=WRITE`.
- El Cypher queda visible en el código como constantes, lo que facilita el catálogo de consultas y la defensa.
