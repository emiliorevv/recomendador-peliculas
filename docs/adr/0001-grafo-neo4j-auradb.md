# ADR-0001: Base de grafos en Neo4j AuraDB

- Estado: Aceptado
- Fecha: 2026-11-16

## Contexto
El enunciado pide una base NoSQL de clave-valor o de grafo, alojada en un servicio administrado en la nube (no localhost). Las funciones del recomendador son recorridos de relaciones (ver [02-justificacion.md](../02-justificacion.md)). El presupuesto es cero.

## Decisión
Usar el paradigma de **grafo** con **Neo4j AuraDB Free** (DaaS) y el lenguaje Cypher.

## Alternativas consideradas
| Opción | A favor | En contra |
|---|---|---|
| **Neo4j AuraDB Free** | Gratis sin tarjeta, Cypher, `shortestPath` nativo, consola web para enseñar el grafo, driver oficial para Python | Límite de 200 mil nodos y 400 mil relaciones; se pausa tras 3 días sin uso |
| AWS Neptune | Administrado por AWS, Gremlin y openCypher | Sin capa gratuita, requiere VPC; se complica para un parcial |
| Memgraph Cloud | Compatible con Cypher, en memoria | Solo prueba temporal; menos documentación |
| Redis Cloud (clave-valor) | Muy rápido, TTL nativo | Los recorridos se harían en el código, con un viaje de red por salto |

## Consecuencias
- Los límites de la versión Free sobran para ~200 nodos de ejemplo.
- La instancia se pausa si pasan 3 días sin uso: hay que abrirla en console.neo4j.io antes de la exposición.
- El respaldo, el parcheo y el cifrado en reposo los maneja Neo4j (responsabilidad compartida).
- La conexión siempre va cifrada (`neo4j+s://`).
