# 02 — Justificación del paradigma

¿Por qué este problema pide una base de **grafos** y no una relacional (SQL) ni una de clave-valor?

## Cómo quedaría en SQL

Tablas: `usuarios`, `peliculas`, `personas`, `generos`, y tablas intermedias `calificaciones`, `actuaciones`, `direcciones`, `pelicula_genero` y `seguidores`.

**Recomendación colaborativa:** la tabla `calificaciones` se une consigo misma tres veces (mis películas → otros usuarios → sus películas), más el filtro de las que ya vi:

```sql
SELECT p2.titulo, COUNT(DISTINCT c2.usuario_id) AS votos
FROM calificaciones c1
JOIN calificaciones c2 ON c2.pelicula_id = c1.pelicula_id AND c2.usuario_id <> c1.usuario_id
JOIN calificaciones c3 ON c3.usuario_id = c2.usuario_id
JOIN peliculas p2      ON p2.id = c3.pelicula_id
WHERE c1.usuario_id = 'u01' AND c1.estrellas >= 4 AND c2.estrellas >= 4 AND c3.estrellas >= 4
  AND c3.pelicula_id NOT IN (SELECT pelicula_id FROM calificaciones WHERE usuario_id = 'u01')
GROUP BY p2.titulo ORDER BY votos DESC;
```

**Camino más corto entre dos actores:** no se sabe cuántos saltos hay, así que hace falta una consulta recursiva (`WITH RECURSIVE`) que une `actuaciones` consigo misma en cada nivel, guarda los nodos visitados para no ciclarse y al final busca el camino de menor longitud. Es larga, difícil de leer y cada nivel multiplica las filas.

## Cómo queda en el grafo

```cypher
MATCH ruta = shortestPath((a:Persona {nombre: $origen})-[:ACTUO_EN|DIRIGIO*..12]-(b:Persona {nombre: $destino}))
RETURN ruta
```

## Por qué el grafo es más rápido en estos recorridos

- En SQL, cada JOIN busca las filas que coinciden en el índice de **toda** la tabla. El costo crece con el tamaño de la tabla y se repite en cada salto.
- En Neo4j cada nodo guarda apuntadores directos a sus relaciones (*index-free adjacency*). Pasar de un nodo a su vecino no busca en ninguna tabla, así que el costo depende de cuántos nodos se visitan, no de cuántos hay en total.
- Las relaciones son datos de primera clase y pueden tener propiedades: las estrellas de una calificación viven en la relación `CALIFICO`.
- El esquema es flexible: agregar premios o plataformas es crear nodos y relaciones nuevos, sin migrar tablas.

## Por qué no clave-valor

Redis o DynamoDB son ideales para leer o escribir un dato por su llave (una sesión, un carrito, una caché). Aquí casi nada se consulta por llave: todo es recorrer relaciones. En clave-valor habría que guardar listas de vecinos a mano (por ejemplo un Set `pelicula:123:actores`) y hacer los recorridos en el código de la aplicación, con un viaje de red por salto.

## Dónde SQL sí sería mejor

Reportes con sumas y agrupaciones sobre toda la base (ventas, contabilidad) o datos muy tabulares con transacciones entre muchas tablas. No es el caso de este proyecto, donde las consultas importantes son recorridos.

## Resumen

| Criterio | SQL | Clave-valor | Grafo (Neo4j) |
|---|---|---|---|
| Recomendación (3 saltos) | 3 JOINs + subconsulta | Varios viajes de red y lógica en la app | Un patrón `MATCH` |
| Camino más corto | `WITH RECURSIVE` complejo | No aplica | `shortestPath` |
| Costo por salto | Crece con el tamaño de la tabla | Un viaje de red por salto | Constante por vecino |
| Agregar un tipo de relación | Nueva tabla y migración | Nuevas llaves a mano | Nueva relación, sin migrar |
| Reportes agregados | Muy bueno | Malo | Aceptable |
