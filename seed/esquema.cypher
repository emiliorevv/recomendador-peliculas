// Restricciones e índices del grafo (PR 3).
// Se aplican con `python seed/esquema.py` y todas son idempotentes (IF NOT EXISTS).
// Cada restricción de unicidad crea además su índice.

CREATE CONSTRAINT pelicula_id    IF NOT EXISTS FOR (p:Pelicula) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT usuario_id     IF NOT EXISTS FOR (u:Usuario)  REQUIRE u.id IS UNIQUE;
CREATE CONSTRAINT persona_nombre IF NOT EXISTS FOR (p:Persona)  REQUIRE p.nombre IS UNIQUE;
CREATE CONSTRAINT genero_nombre  IF NOT EXISTS FOR (g:Genero)   REQUIRE g.nombre IS UNIQUE;
CREATE INDEX pelicula_titulo     IF NOT EXISTS FOR (p:Pelicula) ON (p.titulo);
