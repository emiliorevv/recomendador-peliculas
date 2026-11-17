"""Consultas propias del grafo: recomendaciones, parecidas, top, caminos y vecindad.

Son las seis consultas del catálogo de `docs/catalogo-consultas.md` (§8 a §13),
las que justifican usar un grafo y no una base relacional. Ninguna escribe: todas
leen con `leer()` y reciben sus valores como parámetros (`$id`, `$nombre`, …), así
que el texto que llega desde la interfaz nunca se pega en el Cypher.

Cada Cypher vive en una constante de módulo y `catalogo()` los devuelve todos con
un nombre legible: la app del PR 7 los muestra en pantalla junto al resultado.

Uso típico::

    from src.consultas import recomendar, camino_entre_personas

    for fila in recomendar("u01", limite=5):
        print(fila["pelicula"], fila["usuarios_parecidos"])
    print(camino_entre_personas("Tom Hanks", "Scarlett Johansson")["camino"])

Si el usuario o la persona no existen se lanza `ValueError` con un mensaje claro;
un usuario válido sin recomendaciones devuelve una lista vacía, que no es un error.
"""

from __future__ import annotations

from typing import Any

from src.conexion import leer
from src.validacion import entero, texto

LIMITE_MAXIMO = 100
GRADOS_MINIMOS = 1
GRADOS_MAXIMOS = 3

# Comprobaciones de existencia: `count()` siempre devuelve una fila, así que no
# hay que distinguir entre "no existe" y "no hubo resultados".
EXISTE_USUARIO = """
MATCH (u:Usuario {id: $id})
RETURN count(u) > 0 AS existe
"""

EXISTE_PELICULA = """
MATCH (p:Pelicula {id: $id})
RETURN count(p) > 0 AS existe
"""

EXISTE_PERSONA = """
MATCH (p:Persona {nombre: $nombre})
RETURN count(p) > 0 AS existe
"""

EXISTEN_PERSONAS = """
RETURN EXISTS { MATCH (:Persona {nombre: $origen}) } AS origen,
       EXISTS { MATCH (:Persona {nombre: $destino}) } AS destino
"""

# Gustos parecidos: otro usuario que calificó con 4 o 5 una película que a mí
# también me gustó. `WITH DISTINCT yo, otro` deja un solo registro por usuario,
# así `count(otro)` no se pondera por las películas que tenemos en común y el
# `avg()` mide una calificación por usuario. Se excluye TODO lo que yo ya
# califiqué, sin importar las estrellas: una película vista no se recomienda.
RECOMENDAR = """
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
"""

# Puntaje = actores_comunes + 2*mismo_director + generos_comunes: compartir
# reparto pesa uno, compartir director pesa el doble y cada género en común suma
# uno. Se cuentan con subconsultas `COUNT { }`, que no multiplican filas como
# harían tres MATCH encadenados. Las películas sin nada en común (puntaje 0) no
# son "parecidas" y se descartan con el WHERE.
PELICULAS_PARECIDAS = """
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
"""

# Solo entran las películas con al menos una calificación: sin votos no hay
# promedio que ordenar. El empate se rompe por votos y después por título, para
# que el resultado no dependa del plan de ejecución.
TOP_POR_GENERO = """
MATCH (p:Pelicula)-[:DE_GENERO]->(:Genero {nombre: $genero})
MATCH (p)<-[c:CALIFICO]-(:Usuario)
RETURN p.titulo AS titulo,
       round(avg(c.estrellas), 2) AS promedio,
       count(c) AS votos
ORDER BY promedio DESC, votos DESC, titulo
LIMIT $limite
"""

# Camino más corto de persona a persona. El tope `*..12` es obligatorio: sin él
# el recorrido se escapa por los géneros y deja de ser "seis grados". Se recorre
# sin dirección porque las relaciones van de persona a película y de película a
# persona. Si no hay camino la consulta no devuelve filas (no es un error).
CAMINO_ENTRE_PERSONAS = """
MATCH (a:Persona {nombre: $origen}), (b:Persona {nombre: $destino})
MATCH camino = shortestPath((a)-[:ACTUO_EN|DIRIGIO*..12]-(b))
RETURN [n IN nodes(camino) | coalesce(n.nombre, n.titulo)] AS camino,
       length(camino) AS saltos
"""

# Vecindad por grados de separación. Las personas solo se tocan a través de una
# película, así que un grado son dos saltos: el patrón va de persona en persona
# en longitudes pares (`*2..6`) y el filtro corta en `$grados * 2` (1 a 3).
VECINDAD = """
MATCH (a:Persona {nombre: $nombre})
MATCH ruta = (a)-[:ACTUO_EN|DIRIGIO*2..6]-(otra:Persona)
WHERE otra <> a AND length(ruta) <= $grados * 2
WITH otra, min(length(ruta)) AS saltos
RETURN otra.nombre AS persona, saltos / 2 AS distancia
ORDER BY distancia, persona
LIMIT $limite
"""

# Amigos de amigos: usuarios que siguen a alguien que yo sigo, sin contar a los
# que ya sigo ni a mí mismo. `count(DISTINCT amigo)` mide los amigos en común,
# no las veces que aparece cada uno.
A_QUIEN_SEGUIR = """
MATCH (yo:Usuario {id: $id})-[:SIGUE]->(amigo:Usuario)-[:SIGUE]->(sugerido:Usuario)
WHERE sugerido <> yo AND NOT (yo)-[:SIGUE]->(sugerido)
WITH sugerido, count(DISTINCT amigo) AS amigos_en_comun
RETURN sugerido.id AS usuario_id,
       sugerido.nombre AS nombre,
       amigos_en_comun
ORDER BY amigos_en_comun DESC, nombre, usuario_id
LIMIT $limite
"""

# Nombre legible -> Cypher, en el orden del catálogo. La app del PR 7 lo usa para
# mostrar la consulta exacta que produjo cada resultado.
_CATALOGO = {
    "Recomendación colaborativa": RECOMENDAR,
    "Películas parecidas": PELICULAS_PARECIDAS,
    "Top por género": TOP_POR_GENERO,
    "Camino más corto entre personas": CAMINO_ENTRE_PERSONAS,
    "Vecindad de una persona": VECINDAD,
    "A quién seguir": A_QUIEN_SEGUIR,
}


def catalogo() -> dict[str, str]:
    """Las seis consultas con su nombre legible para mostrarlas en la app."""
    return dict(_CATALOGO)


def _limite(valor: Any) -> int:
    """Cantidad de filas a devolver: entero de 1 a `LIMITE_MAXIMO`."""
    return entero(valor, "límite", 1, LIMITE_MAXIMO)


def _exigir_usuario(usuario_id: str) -> str:
    """Nombre normalizado del usuario, o `ValueError` si no existe."""
    usuario_id = texto(usuario_id, "id del usuario")
    if not leer(EXISTE_USUARIO, id=usuario_id)[0]["existe"]:
        raise ValueError(f"No existe el usuario {usuario_id!r}")
    return usuario_id


def _exigir_pelicula(pelicula_id: str) -> str:
    """Id normalizado de la película, o `ValueError` si no existe."""
    pelicula_id = texto(pelicula_id, "id de la película")
    if not leer(EXISTE_PELICULA, id=pelicula_id)[0]["existe"]:
        raise ValueError(f"No existe la película {pelicula_id!r}")
    return pelicula_id


def _exigir_personas(origen: str, destino: str) -> tuple[str, str]:
    """Nombres normalizados de las dos personas, o `ValueError` si falta alguna."""
    origen = texto(origen, "nombre de la persona de origen")
    destino = texto(destino, "nombre de la persona de destino")
    fila = leer(EXISTEN_PERSONAS, origen=origen, destino=destino)[0]
    for nombre, existe in ((origen, fila["origen"]), (destino, fila["destino"])):
        if not existe:
            raise ValueError(f"No existe la persona {nombre!r}")
    return origen, destino


def recomendar(usuario_id: str, limite: int = 10) -> list[dict[str, Any]]:
    """Películas que le gustaron a usuarios con gustos parecidos y no ha visto.

    Devuelve `pelicula`, `usuarios_parecidos` y `promedio` (dos decimales),
    ordenado por cantidad de usuarios parecidos y después por promedio. Un
    usuario válido sin coincidencias devuelve `[]`.
    """
    usuario_id = _exigir_usuario(usuario_id)
    limite = _limite(limite)
    return leer(RECOMENDAR, id=usuario_id, limite=limite)


def peliculas_parecidas(pelicula_id: str, limite: int = 10) -> list[dict[str, Any]]:
    """Películas con reparto, director o géneros en común, de más a menos parecida.

    Devuelve `pelicula_id`, `titulo`, `puntos`, `actores_comunes`,
    `mismo_director` y `generos_comunes`. La fórmula del puntaje es
    `actores_comunes + 2 * mismo_director + generos_comunes`.
    """
    pelicula_id = _exigir_pelicula(pelicula_id)
    limite = _limite(limite)
    return leer(PELICULAS_PARECIDAS, id=pelicula_id, limite=limite)


def top_por_genero(genero: str, limite: int = 10) -> list[dict[str, Any]]:
    """Mejores películas de un género: `titulo`, `promedio` y `votos`.

    Ordena por promedio descendente y, en caso de empate, por cantidad de votos.
    Solo aparecen películas calificadas al menos una vez.
    """
    genero = texto(genero, "género")
    limite = _limite(limite)
    return leer(TOP_POR_GENERO, genero=genero, limite=limite)


def camino_entre_personas(origen: str, destino: str) -> dict[str, Any]:
    """Camino más corto entre dos personas (estilo "seis grados").

    Devuelve `encontrado`, `saltos` y `camino` (nombres de personas y títulos de
    películas alternados). Si no hay camino dentro de 12 saltos devuelve
    `encontrado: False`, `saltos: 0` y `camino: []`; no lanza excepción.
    """
    origen, destino = _exigir_personas(origen, destino)
    filas = leer(CAMINO_ENTRE_PERSONAS, origen=origen, destino=destino)
    if not filas:
        return {"encontrado": False, "saltos": 0, "camino": []}
    fila = filas[0]
    return {
        "encontrado": True,
        "saltos": int(fila["saltos"]),
        "camino": fila["camino"],
    }


def vecindad(nombre: str, grados: int = 2, limite: int = 25) -> list[dict[str, Any]]:
    """Personas a 1, 2 o 3 grados de separación, con su distancia.

    Un grado es compartir una película (actor o director); dos grados es estar a
    una persona de distancia, y así. Devuelve `persona` y `distancia`, ordenado
    de la más cercana a la más lejana. `grados` fuera de 1..3 es un `ValueError`.
    """
    nombre = texto(nombre, "nombre de la persona")
    grados = entero(grados, "número de grados", GRADOS_MINIMOS, GRADOS_MAXIMOS)
    limite = _limite(limite)
    if not leer(EXISTE_PERSONA, nombre=nombre)[0]["existe"]:
        raise ValueError(f"No existe la persona {nombre!r}")
    return leer(VECINDAD, nombre=nombre, grados=grados, limite=limite)


def a_quien_seguir(usuario_id: str, limite: int = 10) -> list[dict[str, Any]]:
    """Amigos de mis amigos a los que todavía no sigo.

    Devuelve `usuario_id`, `nombre` y `amigos_en_comun`, ordenado por amigos en
    común. Nunca incluye al propio usuario ni a quien ya sigue.
    """
    usuario_id = _exigir_usuario(usuario_id)
    limite = _limite(limite)
    return leer(A_QUIEN_SEGUIR, id=usuario_id, limite=limite)
