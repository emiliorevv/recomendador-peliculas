"""CRUD de películas: crear, listar, ver detalle, actualizar y eliminar.

El `id` de una película es un slug de `titulo-anio` (minúsculas, sin acentos y
con guiones), igual que en `data/peliculas.json`:

    "Batman Begins", 2005  ->  "batman-begins-2005"

Crear y actualizar usan `MERGE` para los géneros (`:Genero`) y las personas
(`:Persona`), que se comparten entre películas, y crean las relaciones
`DE_GENERO`, `DIRIGIO` y `ACTUO_EN`. Cuando se pasa una lista nueva se borran
antes las relaciones anteriores de ese tipo, así el grafo refleja lo que se
pidió y no la unión con lo que había.

Todas las consultas van con parámetros (`$id`, `$generos`, …): el texto que
llega desde la interfaz nunca se pega en el Cypher.

Uso típico::

    from src.peliculas import crear_pelicula, listar_peliculas

    pelicula = crear_pelicula(
        titulo="El origen",
        anio=2010,
        duracion=148,
        generos=["Ciencia ficción", "Acción"],
        director="Christopher Nolan",
        actores=["Leonardo DiCaprio"],
    )
    for fila in listar_peliculas():
        print(fila["titulo"], fila["anio"])
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from src.conexion import escribir, leer

ANIO_MINIMO = 1888
ANIO_MAXIMO = 2027
DURACION_MINIMA = 1
DURACION_MAXIMA = 600

# Detalle completo de una película: propiedades, géneros, director y reparto.
# Los OPTIONAL MATCH van en cadena para que una película sin director o sin
# actores igual salga, con listas vacías o null.
CONSULTA_DETALLE = """
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
"""

CONSULTA_LISTA = """
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
"""

CREAR_PELICULA = """
CREATE (p:Pelicula {id: $id, titulo: $titulo, anio: $anio, duracion: $duracion})
RETURN p.id AS id
"""

ACTUALIZAR_PELICULA = """
MATCH (p:Pelicula {id: $id})
SET p.titulo = coalesce($titulo, p.titulo),
    p.anio = coalesce($anio, p.anio),
    p.duracion = coalesce($duracion, p.duracion)
RETURN p.id AS id
"""

MERGE_GENEROS = """
MATCH (p:Pelicula {id: $id})
UNWIND $generos AS nombre
MERGE (g:Genero {nombre: nombre})
MERGE (p)-[:DE_GENERO]->(g)
"""

MERGE_DIRECTOR = """
MATCH (p:Pelicula {id: $id})
MERGE (persona:Persona {nombre: $director})
MERGE (persona)-[:DIRIGIO]->(p)
"""

MERGE_ACTORES = """
MATCH (p:Pelicula {id: $id})
UNWIND $actores AS nombre
MERGE (persona:Persona {nombre: nombre})
MERGE (persona)-[:ACTUO_EN]->(p)
"""

# Un MATCH sin resultados borra cero relaciones: sirve igual cuando la película
# todavía no tenía género, director o reparto.
BORRAR_GENEROS = """
MATCH (p:Pelicula {id: $id})-[r:DE_GENERO]->(:Genero)
DELETE r
"""

BORRAR_DIRECTOR = """
MATCH (p:Pelicula {id: $id})<-[r:DIRIGIO]-(:Persona)
DELETE r
"""

BORRAR_ACTORES = """
MATCH (p:Pelicula {id: $id})<-[r:ACTUO_EN]-(:Persona)
DELETE r
"""

ELIMINAR_PELICULA = """
MATCH (p:Pelicula {id: $id})
DETACH DELETE p
"""


def slug(titulo: str, anio: int) -> str:
    """Id de la película: título sin acentos ni signos, en minúsculas, más el año."""
    sin_acentos = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode("ascii")
    partes = re.sub(r"[^a-z0-9]+", "-", sin_acentos.lower()).strip("-")
    if not partes:
        raise ValueError(f"El título {titulo!r} no deja un id usable")
    return f"{partes}-{anio}"


def _texto(valor: Any, campo: str) -> str:
    """Texto obligatorio, sin espacios sobrantes."""
    texto = str(valor).strip() if valor is not None else ""
    if not texto:
        raise ValueError(f"El {campo} no puede estar vacío")
    return texto


def _texto_opcional(valor: Any, campo: str) -> str | None:
    """Texto opcional: `None` o vacío quedan en `None` (no se toca la relación)."""
    if valor is None:
        return None
    texto = str(valor).strip()
    if not texto:
        return None
    return texto


def _entero(valor: Any, campo: str) -> int:
    """Entero obligatorio; acepta `"2005"` pero no `True` ni texto con letras."""
    if isinstance(valor, bool):
        raise ValueError(f"El {campo} debe ser un número entero, no un booleano")
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise ValueError(f"El {campo} debe ser un número entero, recibí {valor!r}") from None


def _rango(valor: int, campo: str, minimo: int, maximo: int) -> int:
    """Entero dentro de un rango cerrado."""
    if not minimo <= valor <= maximo:
        raise ValueError(f"El {campo} debe estar entre {minimo} y {maximo}, recibí {valor}")
    return valor


def _lista_de_textos(valor: Any, campo: str) -> list[str]:
    """Lista de textos sin vacíos ni repetidos, conservando el orden recibido."""
    if valor is None:
        return []
    if isinstance(valor, str):
        raise ValueError(f"{campo} debe ser una lista de textos, no un texto suelto")
    vistos: list[str] = []
    for elemento in valor:
        texto = str(elemento).strip()
        if texto and texto not in vistos:
            vistos.append(texto)
    return vistos


def _generos_validos(generos: Any) -> list[str]:
    """Géneros obligatorios: al menos uno y sin repetir."""
    lista = _lista_de_textos(generos, "generos")
    if not lista:
        raise ValueError("La película necesita al menos un género")
    return lista


def _existe(pelicula_id: str) -> bool:
    """True si la película ya está en el grafo."""
    return obtener_pelicula(pelicula_id) is not None


def _convertir(fila: dict[str, Any]) -> dict[str, Any]:
    """Ordena géneros y actores para que el resultado no dependa del plan de ejecución."""
    return {
        "id": fila["id"],
        "titulo": fila["titulo"],
        "anio": fila["anio"],
        "duracion": fila["duracion"],
        "generos": sorted(fila["generos"]),
        "director": fila["director"],
        "actores": sorted(fila["actores"]),
    }


def crear_pelicula(
    *,
    titulo: str,
    anio: int,
    duracion: int,
    generos: list[str],
    director: str | None = None,
    actores: list[str] | None = None,
) -> dict[str, Any]:
    """Crea una película con sus géneros, director y actores y devuelve el detalle.

    El `id` sale de `titulo` y `anio`; si ya existe, lanza `ValueError`: para
    cambiar una película se usa `actualizar_pelicula`.
    """
    titulo = _texto(titulo, "título")
    anio = _rango(_entero(anio, "año"), "año", ANIO_MINIMO, ANIO_MAXIMO)
    duracion = _rango(_entero(duracion, "duración"), "duración", DURACION_MINIMA, DURACION_MAXIMA)
    generos = _generos_validos(generos)
    director = _texto_opcional(director, "director")
    actores = _lista_de_textos(actores, "actores")

    pelicula_id = slug(titulo, anio)
    if _existe(pelicula_id):
        raise ValueError(
            f"Ya existe una película con el id {pelicula_id!r}; "
            "usa actualizar_pelicula para cambiar la que está"
        )

    escribir(CREAR_PELICULA, id=pelicula_id, titulo=titulo, anio=anio, duracion=duracion)
    escribir(MERGE_GENEROS, id=pelicula_id, generos=generos)
    if director:
        escribir(MERGE_DIRECTOR, id=pelicula_id, director=director)
    if actores:
        escribir(MERGE_ACTORES, id=pelicula_id, actores=actores)

    detalle = obtener_pelicula(pelicula_id)
    assert detalle is not None  # se acaba de crear
    return detalle


def listar_peliculas() -> list[dict[str, Any]]:
    """Todas las películas, ordenadas por título, sin el reparto."""
    return [
        {
            "id": fila["id"],
            "titulo": fila["titulo"],
            "anio": fila["anio"],
            "duracion": fila["duracion"],
            "generos": sorted(fila["generos"]),
            "director": fila["director"],
        }
        for fila in leer(CONSULTA_LISTA)
    ]


def obtener_pelicula(pelicula_id: str) -> dict[str, Any] | None:
    """Detalle de una película (con reparto), o `None` si no existe."""
    filas = leer(CONSULTA_DETALLE, id=str(pelicula_id))
    return _convertir(filas[0]) if filas else None


def actualizar_pelicula(
    pelicula_id: str,
    *,
    titulo: str | None = None,
    anio: int | None = None,
    duracion: int | None = None,
    generos: list[str] | None = None,
    director: str | None = None,
    actores: list[str] | None = None,
) -> dict[str, Any]:
    """Actualiza los campos que llegan y devuelve el detalle.

    `None` significa "no cambiar". Las listas nuevas **reemplazan** las
    relaciones: los géneros, el director o el reparto anteriores se borran.
    `actores=[]` deja la película sin reparto; los géneros no pueden quedar
    vacíos. El `id` no se recalcula aunque cambien `titulo` o `anio`: es la
    llave que ya referencian las calificaciones.
    """
    pelicula_id = str(pelicula_id)
    if titulo is not None:
        titulo = _texto(titulo, "título")
    if anio is not None:
        anio = _rango(_entero(anio, "año"), "año", ANIO_MINIMO, ANIO_MAXIMO)
    if duracion is not None:
        duracion = _rango(
            _entero(duracion, "duración"), "duración", DURACION_MINIMA, DURACION_MAXIMA
        )
    if generos is not None:
        generos = _generos_validos(generos)
    director = _texto_opcional(director, "director")
    actores = None if actores is None else _lista_de_textos(actores, "actores")

    if not _existe(pelicula_id):
        raise ValueError(f"No existe la película {pelicula_id!r}")

    escribir(ACTUALIZAR_PELICULA, id=pelicula_id, titulo=titulo, anio=anio, duracion=duracion)

    if generos is not None:
        escribir(BORRAR_GENEROS, id=pelicula_id)
        escribir(MERGE_GENEROS, id=pelicula_id, generos=generos)
    if director is not None:
        escribir(BORRAR_DIRECTOR, id=pelicula_id)
        escribir(MERGE_DIRECTOR, id=pelicula_id, director=director)
    if actores is not None:
        escribir(BORRAR_ACTORES, id=pelicula_id)
        if actores:
            escribir(MERGE_ACTORES, id=pelicula_id, actores=actores)

    detalle = obtener_pelicula(pelicula_id)
    assert detalle is not None  # se acaba de validar que existe
    return detalle


def eliminar_pelicula(pelicula_id: str) -> bool:
    """Borra la película y todas sus relaciones (`DETACH DELETE`).

    Devuelve `True` si la borró y lanza `ValueError` si no existía.
    """
    pelicula_id = str(pelicula_id)
    if not _existe(pelicula_id):
        raise ValueError(f"No existe la película {pelicula_id!r}")

    escribir(ELIMINAR_PELICULA, id=pelicula_id)
    return True
