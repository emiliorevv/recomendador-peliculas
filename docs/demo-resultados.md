# Resultados reales para la demo

Salida de las consultas de `docs/catalogo-consultas.md` contra la instancia de AuraDB
(`Neo4j Kernel 5.27-aura`, base `79af95ef`) después de `python seed/seed.py --reset`.
Sirve para la demo del miércoles: son los números que debe mostrar la app cuando
el PR 6 implemente las consultas.

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

Gustos parecidos = otros usuarios que calificaron con 4 o 5 estrellas alguna película
que `u01` calificó; se recomienda lo que ellos calificaron bien y `u01` no ha visto.

```cypher
MATCH (yo:Usuario {id: $usuario})-[mia:CALIFICO]->(vista:Pelicula)
MATCH (otro:Usuario)-[suya:CALIFICO]->(vista)
WHERE otro <> yo AND suya.estrellas >= 4
MATCH (otro)-[otra:CALIFICO]->(recomendada:Pelicula)
WHERE NOT (yo)-[:CALIFICO]->(recomendada) AND otra.estrellas >= 4
RETURN recomendada.titulo AS pelicula,
       count(DISTINCT otro) AS usuarios_parecidos,
       round(avg(otra.estrellas), 2) AS promedio
ORDER BY usuarios_parecidos DESC, promedio DESC, pelicula
LIMIT 10
```

| Película | Usuarios parecidos | Promedio |
|---|---|---|
| Oppenheimer | 3 | 4.38 |
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
MATCH (a:Persona {nombre: $desde}), (b:Persona {nombre: $hasta})
MATCH camino = shortestPath((a)-[:ACTUO_EN|DIRIGIO*..12]-(b))
RETURN [n IN nodes(camino) | coalesce(n.nombre, n.titulo)] AS camino, length(camino) AS saltos
```

`Tom Hanks` ↔ `Scarlett Johansson`, 4 saltos:

```
Tom Hanks → The Green Mile → Sam Rockwell → Jojo Rabbit → Scarlett Johansson
```

## 9. Películas parecidas a `inception-2010`

Puntaje = 3 por actor en común + 2 por género + 4 por director.

```cypher
MATCH (base:Pelicula {id: $id})
MATCH (otra:Pelicula)
WHERE otra <> base
WITH base, otra,
     COUNT { (base)-[:DE_GENERO]->(:Genero)<-[:DE_GENERO]-(otra) } AS generos,
     COUNT { (base)<-[:ACTUO_EN]-(:Persona)-[:ACTUO_EN]->(otra) } AS actores,
     COUNT { (base)<-[:DIRIGIO]-(:Persona)-[:DIRIGIO]->(otra) } AS directores
WITH otra, generos, actores, directores,
     actores * 3 + generos * 2 + directores * 4 AS puntaje
WHERE puntaje > 0
RETURN otra.titulo AS pelicula, puntaje, actores, generos, directores
ORDER BY puntaje DESC, pelicula
LIMIT 5
```

| Película | Puntaje | Actores | Géneros | Director |
|---|---|---|---|---|
| The Dark Knight Rises | 14 | 2 | 2 | 1 |
| The Dark Knight | 11 | 1 | 2 | 1 |
| Batman Begins | 9 | 1 | 1 | 1 |
| Captain America: The Winter Soldier | 6 | 0 | 3 | 0 |
| Interstellar | 6 | 0 | 1 | 1 |

## 10. Top 3 de `Drama`

```cypher
MATCH (p:Pelicula)-[:DE_GENERO]->(:Genero {nombre: $genero})
OPTIONAL MATCH (p)<-[c:CALIFICO]-(:Usuario)
RETURN p.titulo AS pelicula, count(c) AS calificaciones, round(avg(c.estrellas), 2) AS promedio
ORDER BY promedio DESC, calificaciones DESC, pelicula
LIMIT 3
```

| Película | Calificaciones | Promedio |
|---|---|---|
| Pulp Fiction | 3 | 4.67 |
| The Green Mile | 3 | 4.67 |
| Titanic | 3 | 4.67 |
