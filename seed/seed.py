"""Carga los datos iniciales de `data/*.json` en el grafo.

Se corre desde la raíz del repo::

    python seed/seed.py            # carga sin borrar (idempotente)
    python seed/seed.py --reset    # borra todo el grafo y carga desde cero

Los nodos y las relaciones se crean con `MERGE` sobre la llave del modelo
(`Pelicula.id`, `Persona.nombre`, `Genero.nombre`, `Usuario.id`), y cada tipo de
nodo o relación se escribe con una sola consulta: las filas viajan como una lista
de parámetros y el Cypher las recorre con `UNWIND`. Nunca es una consulta por
fila.

Antes de correrlo conviene aplicar el esquema (`python seed/esquema.py`): las
restricciones de unicidad son las que respaldan el `MERGE`.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.conexion import cerrar_driver, escribir, leer  # noqa: E402

ARCHIVO_PELICULAS = RAIZ / "data" / "peliculas.json"
ARCHIVO_USUARIOS = RAIZ / "data" / "usuarios.json"

# Conteos fijos del entregable. Si alguien edita los JSON sin querer, esto lo dice.
ESPERADOS_NODOS = {"peliculas": 35, "personas": 74, "generos": 10, "usuarios": 12}
ESPERADOS_RELACIONES = {"califico": 95, "sigue": 36}

MERGE_GENEROS = """
UNWIND $nombres AS nombre
MERGE (:Genero {nombre: nombre})
"""

MERGE_PERSONAS = """
UNWIND $nombres AS nombre
MERGE (:Persona {nombre: nombre})
"""

MERGE_PELICULAS = """
UNWIND $peliculas AS fila
MERGE (p:Pelicula {id: fila.id})
SET p.titulo = fila.titulo, p.anio = fila.anio, p.duracion = fila.duracion
"""

MERGE_USUARIOS = """
UNWIND $usuarios AS fila
MERGE (u:Usuario {id: fila.id})
SET u.nombre = fila.nombre
"""

MERGE_DE_GENERO = """
UNWIND $filas AS fila
MATCH (p:Pelicula {id: fila.pelicula})
MATCH (g:Genero {nombre: fila.genero})
MERGE (p)-[:DE_GENERO]->(g)
"""

MERGE_DIRIGIO = """
UNWIND $filas AS fila
MATCH (persona:Persona {nombre: fila.persona})
MATCH (p:Pelicula {id: fila.pelicula})
MERGE (persona)-[:DIRIGIO]->(p)
"""

MERGE_ACTUO_EN = """
UNWIND $filas AS fila
MATCH (persona:Persona {nombre: fila.persona})
MATCH (p:Pelicula {id: fila.pelicula})
MERGE (persona)-[:ACTUO_EN]->(p)
"""

# La calificación vive en la relación: si ya existe, se actualiza en vez de duplicarse.
MERGE_CALIFICO = """
UNWIND $filas AS fila
MATCH (u:Usuario {id: fila.usuario})
MATCH (p:Pelicula {id: fila.pelicula})
MERGE (u)-[c:CALIFICO]->(p)
SET c.estrellas = fila.estrellas, c.fecha = fila.fecha
"""

MERGE_SIGUE = """
UNWIND $filas AS fila
MATCH (a:Usuario {id: fila.seguidor})
MATCH (b:Usuario {id: fila.seguido})
MERGE (a)-[:SIGUE]->(b)
"""

BORRAR_TODO = "MATCH (n) DETACH DELETE n"

CONSULTA_CONTEO = """
RETURN COUNT { (p:Pelicula) } AS peliculas,
       COUNT { (p:Persona) } AS personas,
       COUNT { (g:Genero) } AS generos,
       COUNT { (u:Usuario) } AS usuarios,
       COUNT { ()-[:ACTUO_EN]->() } AS actuo_en,
       COUNT { ()-[:DIRIGIO]->() } AS dirigio,
       COUNT { ()-[:DE_GENERO]->() } AS de_genero,
       COUNT { ()-[:CALIFICO]->() } AS califico,
       COUNT { ()-[:SIGUE]->() } AS sigue
"""


def leer_datos(
    peliculas: Path = ARCHIVO_PELICULAS, usuarios: Path = ARCHIVO_USUARIOS
) -> tuple[list[dict], list[dict]]:
    """Devuelve las películas y los usuarios de los JSON de `data/`."""
    return (
        json.loads(peliculas.read_text(encoding="utf-8")),
        json.loads(usuarios.read_text(encoding="utf-8")),
    )


def generos(peliculas: list[dict]) -> list[str]:
    """Nombres de género sin repetir, ordenados."""
    return sorted({genero for pelicula in peliculas for genero in pelicula["generos"]})


def personas(peliculas: list[dict]) -> list[str]:
    """Directores y actores sin repetir: una sola etiqueta para las dos cosas."""
    nombres = {pelicula["director"] for pelicula in peliculas if pelicula.get("director")}
    nombres |= {actor for pelicula in peliculas for actor in pelicula["actores"]}
    return sorted(nombres)


def filas_de_genero(peliculas: list[dict]) -> list[dict]:
    """Parejas película-género que se convierten en relaciones `DE_GENERO`."""
    return [
        {"pelicula": pelicula["id"], "genero": genero}
        for pelicula in peliculas
        for genero in pelicula["generos"]
    ]


def filas_de_direccion(peliculas: list[dict]) -> list[dict]:
    """Parejas director-película que se convierten en relaciones `DIRIGIO`."""
    return [
        {"pelicula": pelicula["id"], "persona": pelicula["director"]}
        for pelicula in peliculas
        if pelicula.get("director")
    ]


def filas_de_reparto(peliculas: list[dict]) -> list[dict]:
    """Parejas actor-película que se convierten en relaciones `ACTUO_EN`."""
    return [
        {"pelicula": pelicula["id"], "persona": actor}
        for pelicula in peliculas
        for actor in pelicula["actores"]
    ]


def filas_de_calificaciones(usuarios: list[dict]) -> list[dict]:
    """Calificaciones con estrellas y fecha, que se convierten en relaciones `CALIFICO`."""
    return [
        {
            "usuario": usuario["id"],
            "pelicula": calificacion["pelicula_id"],
            "estrellas": calificacion["estrellas"],
            "fecha": calificacion["fecha"],
        }
        for usuario in usuarios
        for calificacion in usuario["calificaciones"]
    ]


def filas_de_seguidores(usuarios: list[dict]) -> list[dict]:
    """Parejas seguidor-seguido que se convierten en relaciones `SIGUE`."""
    return [
        {"seguidor": usuario["id"], "seguido": seguido}
        for usuario in usuarios
        for seguido in usuario["sigue"]
    ]


def esperados(peliculas: list[dict], usuarios: list[dict]) -> dict[str, int]:
    """Conteos que debe dejar la carga en el grafo.

    Los de nodos, `CALIFICO` y `SIGUE` son los del entregable; los de `ACTUO_EN`,
    `DIRIGIO` y `DE_GENERO` se cuentan en los JSON para que agregar una película no
    obligue a tocar el script.
    """
    return {
        **ESPERADOS_NODOS,
        "actuo_en": sum(len(pelicula["actores"]) for pelicula in peliculas),
        "dirigio": sum(1 for pelicula in peliculas if pelicula.get("director")),
        "de_genero": sum(len(pelicula["generos"]) for pelicula in peliculas),
        **ESPERADOS_RELACIONES,
    }


def resetear(ejecutar: Callable[..., object] = escribir) -> None:
    """Borra todos los nodos y relaciones del grafo."""
    ejecutar(BORRAR_TODO)


def cargar(
    peliculas: list[dict],
    usuarios: list[dict],
    ejecutar: Callable[..., object] = escribir,
) -> None:
    """Crea o actualiza nodos y relaciones: una consulta por tipo, con `UNWIND`."""
    ejecutar(MERGE_GENEROS, nombres=generos(peliculas))
    ejecutar(MERGE_PERSONAS, nombres=personas(peliculas))
    ejecutar(MERGE_PELICULAS, peliculas=peliculas)
    ejecutar(MERGE_USUARIOS, usuarios=usuarios)

    ejecutar(MERGE_DE_GENERO, filas=filas_de_genero(peliculas))
    ejecutar(MERGE_DIRIGIO, filas=filas_de_direccion(peliculas))
    ejecutar(MERGE_ACTUO_EN, filas=filas_de_reparto(peliculas))
    ejecutar(MERGE_CALIFICO, filas=filas_de_calificaciones(usuarios))
    ejecutar(MERGE_SIGUE, filas=filas_de_seguidores(usuarios))


def contar(leer_filas: Callable[..., list[dict]] = leer) -> dict[str, int]:
    """Cuenta nodos por etiqueta y relaciones por tipo en todo el grafo."""
    fila = leer_filas(CONSULTA_CONTEO)[0]
    return {clave: int(valor) for clave, valor in fila.items()}


def diferencias(conteos: dict[str, int], esperados: dict[str, int]) -> dict[str, tuple[int, int]]:
    """Tipo que no coincide, con el conteo real y el esperado."""
    return {
        tipo: (conteos.get(tipo, 0), esperado)
        for tipo, esperado in esperados.items()
        if conteos.get(tipo, 0) != esperado
    }


def _imprimir_resumen(conteos: dict[str, int], esperados: dict[str, int]) -> None:
    """Imprime una línea por tipo, con el conteo real al lado del esperado."""
    ancho = max(len(tipo) for tipo in esperados)
    for tipo, esperado in esperados.items():
        real = conteos.get(tipo, 0)
        marca = "ok" if real == esperado else "FALLA"
        print(f"  {tipo:<{ancho}}  {real:>4}  esperado {esperado:>4}  {marca}")


def _argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Carga los datos iniciales del recomendador.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="borra todo el grafo antes de cargar (MATCH (n) DETACH DELETE n)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Carga los datos e informa los conteos; devuelve 0 solo si todos coinciden."""
    argumentos = _argumentos(argv)
    peliculas, usuarios = leer_datos()
    esperados_por_tipo = esperados(peliculas, usuarios)

    try:
        if argumentos.reset:
            print("Borrando el grafo (--reset)…")
            resetear()
        print(f"Cargando {len(peliculas)} películas y {len(usuarios)} usuarios…")
        cargar(peliculas, usuarios)
        conteos = contar()
    finally:
        cerrar_driver()

    print("Resumen del seed:")
    _imprimir_resumen(conteos, esperados_por_tipo)

    fallidos = diferencias(conteos, esperados_por_tipo)
    if fallidos:
        detalle = ", ".join(
            f"{tipo}: {real} (esperado {esperado})" for tipo, (real, esperado) in fallidos.items()
        )
        print(f"Seed incompleto: los conteos no coinciden. {detalle}", file=sys.stderr)
        return 1

    print("Seed completo: los conteos coinciden.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
