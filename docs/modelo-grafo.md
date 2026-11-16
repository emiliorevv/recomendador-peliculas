# Modelo del grafo

## Nodos

| Etiqueta | Propiedades | Llave única | Notas |
|---|---|---|---|
| `Pelicula` | `id`, `titulo`, `anio`, `duracion` (min) | `id` | `id` = título y año en minúsculas, ej. `inception-2010` |
| `Persona` | `nombre` | `nombre` | Actores y directores en la misma etiqueta: una persona puede tener los dos papeles |
| `Genero` | `nombre` | `nombre` | Es nodo y no propiedad para poder recorrer por género |
| `Usuario` | `id`, `nombre` | `id` | `id` = `u01`, `u02`… |

## Relaciones

| Relación | Dirección | Propiedades | Significado |
|---|---|---|---|
| `CALIFICO` | `Usuario → Pelicula` | `estrellas` (1–5), `fecha` | La calificación le pertenece a la pareja usuario-película, por eso vive en la relación |
| `SIGUE` | `Usuario → Usuario` | — | Red social |
| `ACTUO_EN` | `Persona → Pelicula` | — | |
| `DIRIGIO` | `Persona → Pelicula` | — | |
| `DE_GENERO` | `Pelicula → Genero` | — | |

Todas las relaciones tienen dirección. Las consultas de caminos y vecindad las recorren en los dos sentidos.

## Restricciones e índices

Cada restricción de unicidad también crea un índice, así que los `MATCH` por `id` o `nombre` encuentran el nodo de inicio directo y de ahí solo recorren relaciones.

```cypher
CREATE CONSTRAINT pelicula_id    IF NOT EXISTS FOR (p:Pelicula) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT usuario_id     IF NOT EXISTS FOR (u:Usuario)  REQUIRE u.id IS UNIQUE;
CREATE CONSTRAINT persona_nombre IF NOT EXISTS FOR (p:Persona)  REQUIRE p.nombre IS UNIQUE;
CREATE CONSTRAINT genero_nombre  IF NOT EXISTS FOR (g:Genero)   REQUIRE g.nombre IS UNIQUE;
CREATE INDEX pelicula_titulo     IF NOT EXISTS FOR (p:Pelicula) ON (p.titulo);
```

## Buenas prácticas que seguimos

- Etiquetas en singular y PascalCase; relaciones en MAYÚSCULAS con verbo.
- `MERGE` para todo lo que no debe duplicarse (géneros, personas, calificaciones).
- `DETACH DELETE` al borrar un nodo, para no dejar relaciones colgadas.
- Consultas siempre con parámetros, para evitar inyección y reutilizar el plan de ejecución.
- Patrones de longitud variable siempre con tope (`*..12`) para no recorrer todo el grafo.

## Datos iniciales (PR 4)

35 películas, ~73 personas, 10 géneros, 12 usuarios, ~90 calificaciones y ~36 relaciones `SIGUE`.
