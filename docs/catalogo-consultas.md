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
| 8 | Recomendación colaborativa | Recorrido | 6 | Implementado |
| 9 | Películas parecidas | Vecindad | 6 | Implementado |
| 10 | Top por género | Agregación | 6 | Implementado |
| 11 | Camino más corto entre personas | Camino | 6 | Implementado |
| 12 | Vecindad de una persona a N grados | Vecindad | 6 | Implementado |
| 13 | A quién seguir | Recorrido | 6 | Implementado |

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

`src/peliculas.py::crear_pelicula` valida los datos en Python (título no vacío, año 1888–2027, duración 1–600 min, al menos un género) y deriva el `id` como `titulo-anio`: "Batman Begins", 2005 → `batman-begins-2005`. Después corre estas cuatro consultas con parámetros, todas dentro de una sola transacción (`sesion.execute_write`): si una falla, la película no queda creada a medias. Los nodos `:Genero` y `:Persona` se comparten entre películas, así que se crean con `MERGE` y nunca se duplican.

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

Después de cada borrado corren los `MERGE` de §2 con la lista nueva (`DE_GENERO`, `DIRIGIO` o `ACTUO_EN`). Un `MATCH` sin resultados borra cero relaciones, así que el reemplazo funciona igual si la película no tenía ese tipo de relación. `actores=[]` deja la película sin reparto; los géneros no pueden quedar vacíos. Para el director hay tres casos: `None` no cambia nada, `director=""` **quita** el director (borra `DIRIGIO` sin crear otra) y un texto lo reemplaza. Todas las escrituras de la actualización van en una sola transacción: si una falla, la película queda exactamente como estaba.

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

## 8. Recomendación colaborativa

`recomendar(usuario_id, limite=10)` en `src/consultas.py` recorre usuario → película → usuario. Gustos parecidos son los usuarios que calificaron con 4 o 5 estrellas **una película que al usuario también le gustó** (4 o 5). Después se recomienda lo que esos usuarios calificaron bien y el usuario no ha visto.

Dos detalles hacen que el resultado sea el correcto: `WITH DISTINCT yo, otro` deja un solo registro por usuario parecido, así `count(otro)` no se pondera por las películas que comparten; y el `NOT (yo)-[:CALIFICO]->(recomendada)` excluye **todo** lo que el usuario ya calificó, tenga las estrellas que tenga. Un usuario inexistente lanza `ValueError`; un usuario válido sin coincidencias devuelve `[]`.

```cypher
MATCH (yo:Usuario {id: $id})-[mia:CALIFICO]->(:Pelicula)<-[suya:CALIFICO]-(otro:Usuario)
WHERE otro <> yo AND mia.estrellas >= 4 AND suya.estrellas >= 4
WITH DISTINCT yo, otro
MATCH (otro)-[otra:CALIFICO]->(recomendada:Pelicula)
WHERE otra.estrellas >= 4 AND NOT (yo)-[:CALIFICO]->(recomendada)
RETURN recomendada.titulo AS pelicula,
       count(otro) AS usuarios_parecidos,
       round(avg(otra.estrellas), 2) AS promedio
ORDER BY usuarios_parecidos DESC, promedio DESC, pelicula
LIMIT $limite
```

Resultado contra AuraDB para `recomendar("u01")`:

| Película | Usuarios parecidos | Promedio |
|---|---|---|
| Oppenheimer | 3 | 4.33 |
| Toy Story | 2 | 5.0 |
| Eternal Sunshine of the Spotless Mind | 2 | 4.5 |
| Iron Man | 2 | 4.5 |
| La La Land | 2 | 4.0 |
| The Sixth Sense | 2 | 4.0 |
| Toy Story 2 | 2 | 4.0 |
| A Quiet Place | 1 | 5.0 |
| Django Unchained | 1 | 5.0 |
| Fight Club | 1 | 5.0 |

## 9. Películas parecidas

`peliculas_parecidas(pelicula_id, limite=10)` compara la película base contra todas las demás con tres subconsultas `COUNT { }`, que cuentan sin multiplicar filas como harían tres `MATCH` encadenados. El puntaje es:

```text
puntos = actores_comunes + 2 * mismo_director + generos_comunes
```

Compartir un actor suma uno, compartir director pesa el doble y cada género en común suma uno. Las películas con puntaje 0 no son parecidas y se descartan. El resultado trae el desglose (`actores_comunes`, `mismo_director`, `generos_comunes`) para que la app pueda explicar el puntaje. Una película inexistente lanza `ValueError`.

```cypher
MATCH (base:Pelicula {id: $id})
MATCH (otra:Pelicula)
WHERE otra <> base
WITH base, otra,
     COUNT { (base)-[:DE_GENERO]->(:Genero)<-[:DE_GENERO]-(otra) } AS generos_comunes,
     COUNT { (base)<-[:ACTUO_EN]-(:Persona)-[:ACTUO_EN]->(otra) } AS actores_comunes,
     COUNT { (base)<-[:DIRIGIO]-(:Persona)-[:DIRIGIO]->(otra) } AS mismo_director
WITH otra, generos_comunes, actores_comunes, mismo_director,
     actores_comunes + 2 * mismo_director + generos_comunes AS puntos
WHERE puntos > 0
RETURN otra.id AS pelicula_id,
       otra.titulo AS titulo,
       puntos,
       actores_comunes,
       mismo_director,
       generos_comunes
ORDER BY puntos DESC, titulo
LIMIT $limite
```

Resultado contra AuraDB para `peliculas_parecidas("inception-2010")`, primeras cinco:

| Película | Puntos | Actores | Director | Géneros |
|---|---|---|---|---|
| The Dark Knight Rises | 6 | 2 | 1 | 2 |
| The Dark Knight | 5 | 1 | 1 | 2 |
| Batman Begins | 4 | 1 | 1 | 1 |
| Captain America: The Winter Soldier | 3 | 0 | 0 | 3 |
| Interstellar | 3 | 0 | 1 | 1 |

## 10. Top por género

`top_por_genero(genero, limite=10)` ordena por promedio descendente y desempata por cantidad de votos y después por título, para que dos corridas den lo mismo. Solo entran películas con al menos una calificación: sin votos no hay promedio que ordenar. El promedio va redondeado a dos decimales y se devuelve el conteo de votos para que la app muestre "4.67 (3 votos)". Un género sin películas calificadas devuelve `[]`, no un error.

```cypher
MATCH (p:Pelicula)-[:DE_GENERO]->(:Genero {nombre: $genero})
MATCH (p)<-[c:CALIFICO]-(:Usuario)
RETURN p.titulo AS titulo,
       round(avg(c.estrellas), 2) AS promedio,
       count(c) AS votos
ORDER BY promedio DESC, votos DESC, titulo
LIMIT $limite
```

Resultado contra AuraDB para `top_por_genero("Drama", limite=3)`:

| Película | Promedio | Votos |
|---|---|---|
| Pulp Fiction | 4.67 | 3 |
| The Green Mile | 4.67 | 3 |
| Titanic | 4.67 | 3 |

## 11. Camino más corto entre personas

`camino_entre_personas(origen, destino)` usa `shortestPath` sobre `ACTUO_EN` y `DIRIGIO` recorridas en los dos sentidos. El patrón va de persona a persona alternando películas, así que el tope `*..12` mantiene la idea de "seis grados" (12 saltos = 6 personas intermedias) y evita que el recorrido variable se expanda sin límite. Si alguna de las dos personas no existe, `ValueError`; si existe pero no hay camino, `{"encontrado": False, "saltos": 0, "camino": []}`.

```cypher
MATCH (a:Persona {nombre: $origen}), (b:Persona {nombre: $destino})
MATCH camino = shortestPath((a)-[:ACTUO_EN|DIRIGIO*..12]-(b))
RETURN [n IN nodes(camino) | coalesce(n.nombre, n.titulo)] AS camino,
       length(camino) AS saltos
```

Resultado contra AuraDB para `camino_entre_personas("Tom Hanks", "Scarlett Johansson")`:

```text
Tom Hanks → The Green Mile → Sam Rockwell → Jojo Rabbit → Scarlett Johansson
```

`saltos: 4`, contando cada relación del camino; las personas y las películas se alternan.

## 12. Vecindad de una persona a N grados

`vecindad(nombre, grados=2, limite=25)` devuelve las personas alrededor de una persona con su distancia. En este grafo las personas solo se tocan a través de una película, así que **un grado de separación son dos saltos**: compartir película. El patrón va de persona en persona (`*2..6`, longitudes pares) y el `WHERE` corta en `$grados * 2`; `grados` se valida como entero de 1 a 3. Una persona inexistente lanza `ValueError`.

```cypher
MATCH (a:Persona {nombre: $nombre})
MATCH ruta = (a)-[:ACTUO_EN|DIRIGIO*2..6]-(otra:Persona)
WHERE otra <> a AND length(ruta) <= $grados * 2
WITH otra, min(length(ruta)) AS saltos
RETURN otra.nombre AS persona, saltos / 2 AS distancia
ORDER BY distancia, persona
LIMIT $limite
```

Resultado contra AuraDB para `vecindad("Tom Hanks", grados=2)`:

| Persona | Distancia |
|---|---|
| Don Rickles | 1 |
| Frank Darabont | 1 |
| John Lasseter | 1 |
| Lee Unkrich | 1 |
| Michael Clarke Duncan | 1 |
| Sam Rockwell | 1 |
| Tim Allen | 1 |
| Scarlett Johansson | 2 |
| Taika Waititi | 2 |

Con `grados=1` salen solo las siete personas de distancia 1: los compañeros de reparto de sus películas y sus directores.

## 13. A quién seguir

`a_quien_seguir(usuario_id, limite=10)` busca usuarios que siguen a alguien que el usuario sigue (amigos de amigos), excluye al propio usuario y a quien ya sigue, y cuenta los amigos en común con `count(DISTINCT amigo)`. Un usuario inexistente lanza `ValueError`; uno sin amigos de amigos devuelve `[]`.

```cypher
MATCH (yo:Usuario {id: $id})-[:SIGUE]->(amigo:Usuario)-[:SIGUE]->(sugerido:Usuario)
WHERE sugerido <> yo AND NOT (yo)-[:SIGUE]->(sugerido)
WITH sugerido, count(DISTINCT amigo) AS amigos_en_comun
RETURN sugerido.id AS usuario_id,
       sugerido.nombre AS nombre,
       amigos_en_comun
ORDER BY amigos_en_comun DESC, nombre, usuario_id
LIMIT $limite
```

Resultado contra AuraDB para `a_quien_seguir("u01")`:

| usuario_id | Nombre | Amigos en común |
|---|---|---|
| `u05` | Elena | 2 |
| `u06` | Fabián | 2 |
| `u08` | Hugo | 2 |
| `u09` | Irene | 2 |
| `u10` | Javier | 2 |

`u01` sigue a `u02`, `u03`, `u04` y `u07`; ninguno de esos cuatro aparece en la lista, y tampoco el propio `u01`.
