# Resultados reales para la demo

Salida de las consultas de `docs/catalogo-consultas.md` contra la instancia de AuraDB
(`Neo4j Kernel 5.27-aura`, base `79af95ef`) después de `python seed/seed.py --reset`.
Sirve para la demo del miércoles: es lo que muestra la app, que usa las consultas de
`src/consultas.py` (PR 6).

> Son los números de hoy con estos datos, **no** una expectativa fija: las pruebas del PR 6
> validan la forma y el orden de cada consulta, no estos valores. Si cambia el seed, se
> regenera este documento.

## Estado del grafo tras el seed

| Tipo | Conteo |
|---|---|
| `Pelicula` | 35 |
| `Persona` | 74 |
| `Genero` | 10 |
| `Usuario` | 12 |
| `ACTUO_EN` | 116 |
| `DIRIGIO` | 35 |
| `DE_GENERO` | 86 |
| `CALIFICO` | 95 |
| `SIGUE` | 36 |

131 nodos y 368 relaciones. Correr el seed otra vez **sin** `--reset` deja los mismos
131/368: todo se crea con `MERGE`.

## 8. Recomendación colaborativa para `u01`

Gustos parecidos = otros usuarios que calificaron con 4 o 5 estrellas **una película que a `u01`
también le gustó** (4 o 5 estrellas). Se recomienda lo que ellos calificaron bien y `u01` no ha
visto. El `WITH DISTINCT yo, otro` deja un solo registro por usuario parecido, así que `avg()` no
se pondera por películas en común.

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

## 11. Camino más corto entre personas

```cypher
MATCH (a:Persona {nombre: $origen}), (b:Persona {nombre: $destino})
MATCH camino = shortestPath((a)-[:ACTUO_EN|DIRIGIO*..12]-(b))
RETURN [n IN nodes(camino) | coalesce(n.nombre, n.titulo)] AS camino, length(camino) AS saltos
```

`Tom Hanks` ↔ `Scarlett Johansson`, 4 saltos:

```
Tom Hanks → The Green Mile → Sam Rockwell → Jojo Rabbit → Scarlett Johansson
```

## 9. Películas parecidas a `inception-2010`

Puntaje = actores en común + 2 por director + géneros en común. La implementación
del PR 6 usa esta fórmula; el bosquejo anterior de este documento usaba 3 por actor,
2 por género y 4 por director, que daba 14 para The Dark Knight Rises. Los puntajes
bajaron y el orden de la tabla no cambió.

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
RETURN otra.id AS pelicula_id, otra.titulo AS titulo, puntos,
       actores_comunes, mismo_director, generos_comunes
ORDER BY puntos DESC, titulo
LIMIT $limite
```

| Película | Puntos | Actores | Géneros | Director |
|---|---|---|---|---|
| The Dark Knight Rises | 6 | 2 | 2 | 1 |
| The Dark Knight | 5 | 1 | 2 | 1 |
| Batman Begins | 4 | 1 | 1 | 1 |
| Captain America: The Winter Soldier | 3 | 0 | 3 | 0 |
| Interstellar | 3 | 0 | 1 | 1 |

## 10. Top 3 de `Drama`

```cypher
MATCH (p:Pelicula)-[:DE_GENERO]->(:Genero {nombre: $genero})
MATCH (p)<-[c:CALIFICO]-(:Usuario)
RETURN p.titulo AS titulo, round(avg(c.estrellas), 2) AS promedio, count(c) AS votos
ORDER BY promedio DESC, votos DESC, titulo
LIMIT $limite
```

| Película | Votos | Promedio |
|---|---|---|
| Pulp Fiction | 3 | 4.67 |
| The Green Mile | 3 | 4.67 |
| Titanic | 3 | 4.67 |

## 12. Vecindad de `Tom Hanks` a 2 grados

Un grado de separación son dos saltos (persona → película → persona). El patrón va de
persona en persona y se corta con `length(ruta) <= $grados * 2`, con `grados` entre 1 y 3.

```cypher
MATCH (a:Persona {nombre: $nombre})
MATCH ruta = (a)-[:ACTUO_EN|DIRIGIO*2..6]-(otra:Persona)
WHERE otra <> a AND length(ruta) <= $grados * 2
WITH otra, min(length(ruta)) AS saltos
RETURN otra.nombre AS persona, saltos / 2 AS distancia
ORDER BY distancia, persona
LIMIT $limite
```

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

## 13. A quién seguir desde `u01`

```cypher
MATCH (yo:Usuario {id: $id})-[:SIGUE]->(amigo:Usuario)-[:SIGUE]->(sugerido:Usuario)
WHERE sugerido <> yo AND NOT (yo)-[:SIGUE]->(sugerido)
WITH sugerido, count(DISTINCT amigo) AS amigos_en_comun
RETURN sugerido.id AS usuario_id, sugerido.nombre AS nombre, amigos_en_comun
ORDER BY amigos_en_comun DESC, nombre, usuario_id
LIMIT $limite
```

| usuario_id | Nombre | Amigos en común |
|---|---|---|
| `u05` | Elena | 2 |
| `u06` | Fabián | 2 |
| `u08` | Hugo | 2 |
| `u09` | Irene | 2 |
| `u10` | Javier | 2 |
