# Catálogo de consultas

Cada consulta se agrega aquí en el PR que la implementa, con el Cypher exacto que corre la app y un ejemplo de resultado contra AuraDB. Este archivo es la base de la sección 5 del PDF.

| # | Consulta | Tipo | PR | Estado |
|---|---|---|---|---|
| 1 | Restricciones e índices | Esquema | 3 | Implementado |
| 2 | Crear película con géneros, director y actores | CRUD (C) | 5 | Pendiente |
| 3 | Listar y ver detalle de película | CRUD (R) | 5 | Pendiente |
| 4 | Actualizar película y sus géneros | CRUD (U) | 5 | Pendiente |
| 5 | Eliminar película (`DETACH DELETE`) | CRUD (D) | 5 | Pendiente |
| 6 | Crear, listar, renombrar y eliminar usuario | CRUD | 5 | Pendiente |
| 7 | Calificar (`MERGE` = crear o actualizar) y quitar calificación | CRUD | 5 | Pendiente |
| 8 | Recomendación colaborativa | Recorrido | 6 | Pendiente |
| 9 | Películas parecidas | Vecindad | 6 | Pendiente |
| 10 | Top por género | Agregación | 6 | Pendiente |
| 11 | Camino más corto entre personas | Camino | 6 | Pendiente |
| 12 | Vecindad de una persona a N grados | Vecindad | 6 | Pendiente |
| 13 | A quién seguir | Recorrido | 6 | Pendiente |

## 1. Restricciones e índices

Se aplican con `python seed/esquema.py`, que ejecuta las sentencias de `seed/esquema.cypher` una por una. Todas llevan `IF NOT EXISTS`, así que el script es idempotente.

```cypher
CREATE CONSTRAINT pelicula_id    IF NOT EXISTS FOR (p:Pelicula) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT usuario_id     IF NOT EXISTS FOR (u:Usuario)  REQUIRE u.id IS UNIQUE;
CREATE CONSTRAINT persona_nombre IF NOT EXISTS FOR (p:Persona)  REQUIRE p.nombre IS UNIQUE;
CREATE CONSTRAINT genero_nombre  IF NOT EXISTS FOR (g:Genero)   REQUIRE g.nombre IS UNIQUE;
CREATE INDEX pelicula_titulo     IF NOT EXISTS FOR (p:Pelicula) ON (p.titulo);
```

Resultado contra AuraDB (`Neo4j Kernel 5.27-aura`, base `79af95ef`): las 5 sentencias corren sin error dos veces seguidas y `SHOW CONSTRAINTS` devuelve las 4 restricciones de unicidad (cada una crea su índice) más el índice `pelicula_titulo`.
