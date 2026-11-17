# Catálogo de consultas

Cada consulta se agrega aquí en el PR que la implementa, con el Cypher exacto que corre la app y un ejemplo de resultado contra AuraDB. Este archivo es la base de la sección 5 del PDF.

| # | Consulta | Tipo | PR | Estado |
|---|---|---|---|---|
| 1 | Restricciones e índices | Esquema | 3 | Implementado |
| 2 | Crear película con géneros, director y actores | CRUD (C) | 5 | Implementado |
| 3 | Listar y ver detalle de película | CRUD (R) | 5 | Implementado |
| 4 | Actualizar película y sus géneros | CRUD (U) | 5 | Implementado |
| 5 | Eliminar película (`DETACH DELETE`) | CRUD (D) | 5 | Implementado |
| 6 | Crear, listar, renombrar y eliminar usuario | CRUD | 5 | Implementado |
| 7 | Calificar (`MERGE` = crear o actualizar) y quitar calificación | CRUD | 5 | Implementado |
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

## 2. Crear película con géneros, director y actores

`src/peliculas.py::crear_pelicula` valida los datos en Python (título no vacío, año 1888–2027, duración 1–600 min, al menos un género) y deriva el `id` como `titulo-anio`: "Batman Begins", 2005 → `batman-begins-2005`. Después corre cuatro consultas con parámetros. Los nodos `:Genero` y `:Persona` se comparten entre películas, así que se crean con `MERGE` y nunca se duplican.

```cypher
CREATE (p:Pelicula {id: $id, titulo: $titulo, anio: $anio, duracion: $duracion})
RETURN p.id AS id
```

```cypher
MATCH (p:Pelicula {id: $id})
UNWIND $generos AS nombre
MERGE (g:Genero {nombre: nombre})
MERGE (p)-[:DE_GENERO]->(g)
```

```cypher
MATCH (p:Pelicula {id: $id})
MERGE (persona:Persona {nombre: $director})
MERGE (persona)-[:DIRIGIO]->(p)
```

```cypher
MATCH (p:Pelicula {id: $id})
UNWIND $actores AS nombre
MERGE (persona:Persona {nombre: nombre})
MERGE (persona)-[:ACTUO_EN]->(p)
```

Resultado contra AuraDB (alta de una película de prueba con un género, un director y dos actores que ya existían en el grafo; se eliminó después, ver §5):

| id | titulo | anio | duracion | generos | director | actores |
|---|---|---|---|---|---|---|
| `pelicula-de-prueba-2026` | Película de Prueba | 2026 | 101 | `["Drama", "Terror"]` | Christopher Nolan | `["Christian Bale", "Michael Caine"]` |

Con eso el grafo pasó de 35 a 36 películas y de 86 a 88 relaciones `DE_GENERO`, sin crear personas ni géneros nuevos.

## 3. Listar y ver detalle de película

`listar_peliculas` devuelve todas las películas ordenadas por título, sin el reparto; `obtener_pelicula` devuelve una sola con actores, o `None` si el id no existe. Los `OPTIONAL MATCH` van en cadena para que una película sin director o sin actores también salga.

```cypher
MATCH (p:Pelicula)
OPTIONAL MATCH (p)-[:DE_GENERO]->(g:Genero)
WITH p, collect(DISTINCT g.nombre) AS generos
OPTIONAL MATCH (d:Persona)-[:DIRIGIO]->(p)
RETURN p.id AS id,
       p.titulo AS titulo,
       p.anio AS anio,
       p.duracion AS duracion,
       generos,
       head(collect(DISTINCT d.nombre)) AS director
ORDER BY titulo
```

```cypher
MATCH (p:Pelicula {id: $id})
OPTIONAL MATCH (p)-[:DE_GENERO]->(g:Genero)
WITH p, collect(DISTINCT g.nombre) AS generos
OPTIONAL MATCH (d:Persona)-[:DIRIGIO]->(p)
WITH p, generos, collect(DISTINCT d.nombre) AS directores
OPTIONAL MATCH (a:Persona)-[:ACTUO_EN]->(p)
RETURN p.id AS id,
       p.titulo AS titulo,
       p.anio AS anio,
       p.duracion AS duracion,
       generos,
       head(directores) AS director,
       collect(DISTINCT a.nombre) AS actores
```

Las tres primeras filas del listado contra AuraDB (son 35 en total):

| id | titulo | anio | duracion | generos | director |
|---|---|---|---|---|---|
| `28-days-later-2002` | 28 Days Later | 2002 | 113 | `["Ciencia ficción", "Suspenso", "Terror"]` | Danny Boyle |
| `a-quiet-place-2018` | A Quiet Place | 2018 | 90 | `["Ciencia ficción", "Terror"]` | John Krasinski |
| `batman-begins-2005` | Batman Begins | 2005 | 140 | `["Acción", "Aventura"]` | Christopher Nolan |

Detalle de `inception-2010`:

```text
{"id": "inception-2010", "titulo": "Inception", "anio": 2010, "duracion": 148,
 "generos": ["Acción", "Ciencia ficción", "Suspenso"],
 "director": "Christopher Nolan",
 "actores": ["Leonardo DiCaprio", "Michael Caine", "Tom Hardy"]}
```

## 4. Actualizar película y sus géneros

`actualizar_pelicula` solo toca lo que llega: `None` significa "no cambiar". Primero actualiza las propiedades y después, si llegan listas nuevas, borra las relaciones anteriores de ese tipo y crea las nuevas: reemplaza, no acumula. El `id` no se recalcula aunque cambie el título o el año, porque es la llave que ya referencian las calificaciones.

```cypher
MATCH (p:Pelicula {id: $id})
SET p.titulo = coalesce($titulo, p.titulo),
    p.anio = coalesce($anio, p.anio),
    p.duracion = coalesce($duracion, p.duracion)
RETURN p.id AS id
```

```cypher
MATCH (p:Pelicula {id: $id})-[r:DE_GENERO]->(:Genero)
DELETE r
```

```cypher
MATCH (p:Pelicula {id: $id})<-[r:DIRIGIO]-(:Persona)
DELETE r
```

```cypher
MATCH (p:Pelicula {id: $id})<-[r:ACTUO_EN]-(:Persona)
DELETE r
```

Después de cada borrado corren los `MERGE` de §2 con la lista nueva (`DE_GENERO`, `DIRIGIO` o `ACTUO_EN`). Un `MATCH` sin resultados borra cero relaciones, así que el reemplazo funciona igual si la película no tenía ese tipo de relación. `actores=[]` deja la película sin reparto; los géneros no pueden quedar vacíos.

Resultado contra AuraDB de actualizar la película del ejemplo (duración 101 → 112, géneros `["Drama", "Terror"]` → `["Suspenso"]`, director y un actor nuevos):

| id | titulo | anio | duracion | generos | director | actores |
|---|---|---|---|---|---|---|
| `pelicula-de-prueba-2026` | Película de Prueba | 2026 | 112 | `["Suspenso"]` | David Fincher | `["Christian Bale"]` |

Quedó una sola relación de cada tipo: las dos `DE_GENERO`, el `DIRIGIO` de Christopher Nolan y el `ACTUO_EN` de Michael Caine se borraron antes de crear los nuevos. Los nodos `:Genero` y `:Persona` que dejaron de estar relacionados no se borran, porque son compartidos con otras películas.

## 5. Eliminar película (`DETACH DELETE`)

```cypher
MATCH (p:Pelicula {id: $id})
DETACH DELETE p
```

`DETACH DELETE` se lleva la película y todas sus relaciones (`DE_GENERO`, `DIRIGIO`, `ACTUO_EN` y las `CALIFICO` de los usuarios) en una sola operación, sin dejar relaciones colgadas apuntando a un nodo que ya no existe. `eliminar_pelicula` devuelve `True`; si el id no existe lanza `ValueError` en vez de fallar en silencio.

Resultado contra AuraDB, eliminando la película de los ejemplos anteriores: el grafo pasó de 132 nodos y 371 relaciones a 131 nodos y 368 relaciones, y `obtener_pelicula("pelicula-de-prueba-2026")` devolvió `None`.

## 6. Crear, listar, renombrar y eliminar usuario

`crear_usuario(nombre)` sin id usa el siguiente libre: mira el mayor `u` + número del grafo y suma uno (`u13` con los 12 usuarios del seed). Con un id repetido lanza `ValueError`.

```cypher
MATCH (u:Usuario) WHERE u.id STARTS WITH 'u'
RETURN max(toInteger(substring(u.id, 1))) AS mayor
```

```cypher
CREATE (u:Usuario {id: $id, nombre: $nombre})
RETURN u.id AS id, u.nombre AS nombre
```

```cypher
MATCH (u:Usuario)
RETURN u.id AS id, u.nombre AS nombre
ORDER BY u.id
```

```cypher
MATCH (u:Usuario {id: $id})
SET u.nombre = $nombre
RETURN u.id AS id, u.nombre AS nombre
```

```cypher
MATCH (u:Usuario {id: $id})
DETACH DELETE u
```

Resultado contra AuraDB: `crear_usuario("Prueba Demo")` devolvió `{"id": "u13", "nombre": "Prueba Demo"}`, `renombrar_usuario("u13", "Prueba Demo 2")` devolvió `{"id": "u13", "nombre": "Prueba Demo 2"}` y el listado pasó a tener 13 usuarios, con `u13` al final. Al final del ejemplo se eliminó `u13` con `DETACH DELETE`: sus `CALIFICO` y `SIGUE` se fueron con él y los demás usuarios quedaron intactos.

### Seguir y dejar de seguir

Son relaciones `:SIGUE` entre usuarios. `seguir` usa `MERGE`, así que seguir dos veces a la misma persona no duplica la relación, y rechaza el auto-seguimiento antes de tocar la base. `dejar_de_seguir` devuelve `False` si esa pareja no tenía relación.

```cypher
MATCH (u:Usuario {id: $usuario})
MATCH (s:Usuario {id: $seguido})
MERGE (u)-[:SIGUE]->(s)
RETURN u.id AS usuario_id, u.nombre AS nombre,
       s.id AS seguido_id, s.nombre AS seguido
```

```cypher
MATCH (:Usuario {id: $usuario})-[r:SIGUE]->(:Usuario {id: $seguido})
DELETE r
RETURN count(*) AS borradas
```

Para leerlos en los dos sentidos cambia el nodo fijo: `a_quien_sigue` filtra por el usuario de origen y `seguidores_de` por el de destino. Ambos ordenan por nombre.

```cypher
MATCH (:Usuario {id: $id})-[:SIGUE]->(s:Usuario)
RETURN s.id AS id, s.nombre AS nombre
ORDER BY s.nombre, s.id
```

```cypher
MATCH (s:Usuario)-[:SIGUE]->(:Usuario {id: $id})
RETURN s.id AS id, s.nombre AS nombre
ORDER BY s.nombre, s.id
```

Resultado contra AuraDB: `seguir("u13", "u01")` devolvió `{"usuario_id": "u13", "nombre": "Prueba Demo 2", "seguido_id": "u01", "seguido": "Ana"}`, `a_quien_sigue("u13")` devolvió `[{"id": "u01", "nombre": "Ana"}]` y `u13` apareció al final de `seguidores_de("u01")`. Después `dejar_de_seguir("u13", "u01")` devolvió `True` y la segunda llamada `False`.

## 7. Calificar (`MERGE` = crear o actualizar) y quitar calificación

Las estrellas viven en la relación `CALIFICO` porque le pertenecen a la pareja usuario-película: con `MERGE` + `SET`, calificar otra vez la misma película actualiza la relación en vez de duplicarla. `estrellas` es un entero de 1 a 5 y `fecha` va en ISO; por defecto, la de hoy (`date.today().isoformat()`). Calificar un usuario o una película que no existe lanza `ValueError`.

```cypher
MATCH (u:Usuario {id: $usuario})
MATCH (p:Pelicula {id: $pelicula})
MERGE (u)-[c:CALIFICO]->(p)
SET c.estrellas = $estrellas, c.fecha = $fecha
RETURN p.id AS pelicula_id, p.titulo AS titulo, c.estrellas AS estrellas, c.fecha AS fecha
```

```cypher
MATCH (:Usuario {id: $id})-[c:CALIFICO]->(p:Pelicula)
RETURN p.id AS pelicula_id, p.titulo AS titulo, c.estrellas AS estrellas, c.fecha AS fecha
ORDER BY c.fecha DESC, p.titulo
```

```cypher
MATCH (:Usuario {id: $usuario})-[c:CALIFICO]->(:Pelicula {id: $pelicula})
DELETE c
RETURN count(*) AS borradas
```

Resultado contra AuraDB, con `u13` y `inception-2010`: `calificar("u13", "inception-2010", 4, fecha="2026-11-16")` devolvió `{"usuario_id": "u13", "pelicula_id": "inception-2010", "titulo": "Inception", "estrellas": 4, "fecha": "2026-11-16"}`; la misma llamada con 5 estrellas devolvió `estrellas: 5` y `calificaciones_de("u13")` una sola fila:

| pelicula_id | titulo | estrellas | fecha |
|---|---|---|---|
| `inception-2010` | Inception | 5 | 2026-11-16 |

`quitar_calificacion("u13", "inception-2010")` devolvió `True` y la segunda llamada `False` porque la relación ya no estaba. El grafo quedó en los 131 nodos y 368 relaciones del seed.
