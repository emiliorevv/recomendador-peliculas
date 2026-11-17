"""Carga los datos iniciales de `data/*.json` en el grafo.

Se corre desde la raíz del repo::

    python seed/seed.py            # carga sin borrar (idempotente)
    python seed/seed.py --reset    # borra todo el grafo y carga desde cero

Los nodos y las relaciones se crean con `MERGE` sobre la llave del modelo
(`Pelicula.id`, `Persona.nombre`, `Genero.nombre`, `Usuario.id`), y cada tipo de
nodo o relación se escribe con una sola consulta: las filas viajan como una lista
de parámetros y el Cypher las recorre con `UNWIND`. Nunca es una consulta por
fila.

El esquema (restricciones e índices de `seed/esquema.py`) se aplica en cada
corrida, porque es idempotente. El orden cambia según el modo:

- con `--reset` se borra primero y el esquema va después, así las restricciones
  se pueden crear aunque el grafo anterior tuviera datos que las violaran (por
  ejemplo ids duplicados creados a mano);
- sin `--reset` el esquema va antes de cargar: los `MERGE` siempre corren con sus
  restricciones e índices ya puestos.

Qué valida al final:

- con `--reset` el grafo debe quedar con exactamente los conteos que declaran los
  JSON, porque se acaba de borrar todo;
- sin `--reset` el grafo puede tener más datos (el CRUD agrega usuarios,
  calificaciones y seguidores), así que solo se exige que todo lo del seed siga
  presente: cada id de película, usuario, persona y género, y cada pareja
  `CALIFICO`, `SIGUE`, `ACTUO_EN`, `DIRIGIO` y `DE_GENERO`.

El código de salida 0 significa "el seed está aplicado", no "el grafo tiene
exactamente estos números".
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

# Las claves de las relaciones se arman como "origen|destino" para compararlas
# como texto; es el mismo formato que usa `claves_del_seed`.
CONSULTA_CLAVES = """
RETURN COLLECT { MATCH (p:Pelicula) RETURN p.id } AS peliculas,
       COLLECT { MATCH (p:Persona) RETURN p.nombre } AS personas,
       COLLECT { MATCH (g:Genero) RETURN g.nombre } AS generos,
       COLLECT { MATCH (u:Usuario) RETURN u.id } AS usuarios,
       COLLECT { MATCH (a:Persona)-[:ACTUO_EN]->(p:Pelicula)
                 RETURN a.nombre + '|' + p.id } AS actuo_en,
       COLLECT { MATCH (d:Persona)-[:DIRIGIO]->(p:Pelicula)
                 RETURN d.nombre + '|' + p.id } AS dirigio,
       COLLECT { MATCH (p:Pelicula)-[:DE_GENERO]->(g:Genero)
                 RETURN p.id + '|' + g.nombre } AS de_genero,
       COLLECT { MATCH (u:Usuario)-[:CALIFICO]->(p:Pelicula)
                 RETURN u.id + '|' + p.id } AS califico,
       COLLECT { MATCH (a:Usuario)-[:SIGUE]->(b:Usuario)
                 RETURN a.id + '|' + b.id } AS sigue
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


def _pareja(origen: str, destino: str) -> str:
    """Clave de una relación: sus dos extremos unidos con `|`."""
    return f"{origen}|{destino}"


def claves_del_seed(peliculas: list[dict], usuarios: list[dict]) -> dict[str, set[str]]:
    """Claves que el seed declara, en el mismo formato que las del grafo.

    Se guardan como `set` para que los duplicados de los JSON no cuenten doble:
    `MERGE` también los colapsa en el grafo.
    """
    return {
        "peliculas": {pelicula["id"] for pelicula in peliculas},
        "personas": set(personas(peliculas)),
        "generos": set(generos(peliculas)),
        "usuarios": {usuario["id"] for usuario in usuarios},
        "actuo_en": {_pareja(f["persona"], f["pelicula"]) for f in filas_de_reparto(peliculas)},
        "dirigio": {_pareja(f["persona"], f["pelicula"]) for f in filas_de_direccion(peliculas)},
        "de_genero": {_pareja(f["pelicula"], f["genero"]) for f in filas_de_genero(peliculas)},
        "califico": {
            _pareja(f["usuario"], f["pelicula"]) for f in filas_de_calificaciones(usuarios)
        },
        "sigue": {_pareja(f["seguidor"], f["seguido"]) for f in filas_de_seguidores(usuarios)},
    }


def esperados(peliculas: list[dict], usuarios: list[dict]) -> dict[str, int]:
    """Conteos que declaran los JSON, derivados de sus claves sin repetir."""
    return {tipo: len(claves) for tipo, claves in claves_del_seed(peliculas, usuarios).items()}


def resetear(ejecutar: Callable[..., object] = escribir) -> None:
    """Borra todos los nodos y relaciones del grafo."""
    ejecutar(BORRAR_TODO)


def aplicar_esquema() -> int:
    """Aplica restricciones e índices (`seed/esquema.py`) y devuelve cuántos ejecutó.

    El import va adentro para que el módulo funcione igual como script
    (`python seed/seed.py`) y como paquete (`from seed import seed`): cuando corre
    como script, `seed` no está en el camino hasta que `RAIZ` entra en `sys.path`.
    """
    from seed.esquema import aplicar

    return aplicar()


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


def claves_del_grafo(leer_filas: Callable[..., list[dict]] = leer) -> dict[str, set[str]]:
    """Las claves que hoy están en el grafo, con el formato de `claves_del_seed`."""
    fila = leer_filas(CONSULTA_CLAVES)[0]
    return {tipo: set(valores) for tipo, valores in fila.items()}


def faltantes(esperadas: dict[str, set[str]], reales: dict[str, set[str]]) -> dict[str, list[str]]:
    """Claves del seed que no están en el grafo, por tipo."""
    return {
        tipo: sorted(claves - reales.get(tipo, set()))
        for tipo, claves in esperadas.items()
        if claves - reales.get(tipo, set())
    }


def diferencias(conteos: dict[str, int], esperados: dict[str, int]) -> dict[str, tuple[int, int]]:
    """Tipo cuyo conteo no coincide exacto, con el real y el esperado."""
    return {
        tipo: (conteos.get(tipo, 0), esperado)
        for tipo, esperado in esperados.items()
        if conteos.get(tipo, 0) != esperado
    }


def _problemas_exactos(
    conteos: dict[str, int], esperados_por_tipo: dict[str, int]
) -> dict[str, str]:
    """Problemas del modo `--reset`: el conteo real debe ser igual al esperado."""
    return {
        tipo: f"{real} en el grafo, esperado {esperado}"
        for tipo, (real, esperado) in diferencias(conteos, esperados_por_tipo).items()
    }


def _problemas_por_faltantes(faltan: dict[str, list[str]]) -> dict[str, str]:
    """Problemas del modo normal: qué claves del seed no llegaron al grafo."""
    problemas = {}
    for tipo, claves in faltan.items():
        muestra = ", ".join(claves[:4])
        resto = f" y {len(claves) - 4} más" if len(claves) > 4 else ""
        problemas[tipo] = f"faltan {len(claves)}: {muestra}{resto}"
    return problemas


def _imprimir_resumen(
    conteos: dict[str, int],
    esperados_por_tipo: dict[str, int],
    problemas: dict[str, str],
) -> None:
    """Imprime una línea por tipo, con el conteo real al lado del que declaran los JSON."""
    ancho = max(len(tipo) for tipo in esperados_por_tipo)
    for tipo, esperado in esperados_por_tipo.items():
        real = conteos.get(tipo, 0)
        marca = "FALLA" if tipo in problemas else "ok"
        print(f"  {tipo:<{ancho}}  {real:>4}  seed {esperado:>4}  {marca}")


def _argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Carga los datos iniciales del recomendador.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="borra todo el grafo antes de cargar (MATCH (n) DETACH DELETE n)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Carga los datos y valida; devuelve 0 solo si el seed quedó aplicado."""
    argumentos = _argumentos(argv)
    peliculas, usuarios = leer_datos()
    claves = claves_del_seed(peliculas, usuarios)
    esperados_por_tipo = {tipo: len(valores) for tipo, valores in claves.items()}

    try:
        if argumentos.reset:
            print("Borrando el grafo (--reset)…")
            resetear()
        # Con --reset va después del borrado: así las restricciones se crean aunque
        # el grafo anterior tuviera datos que las violaran.
        aplicar_esquema()

        print(f"Cargando {len(peliculas)} películas y {len(usuarios)} usuarios…")
        cargar(peliculas, usuarios)

        conteos = contar()
        if argumentos.reset:
            problemas = _problemas_exactos(conteos, esperados_por_tipo)
        else:
            problemas = _problemas_por_faltantes(faltantes(claves, claves_del_grafo()))
    finally:
        cerrar_driver()

    print("Resumen del seed:")
    _imprimir_resumen(conteos, esperados_por_tipo, problemas)

    if problemas:
        print("Seed incompleto: el grafo no quedó como lo declaran los JSON.", file=sys.stderr)
        for tipo, detalle in problemas.items():
            print(f"  {tipo}: {detalle}", file=sys.stderr)
        return 1

    if argumentos.reset:
        print("Seed completo: los conteos coinciden exactamente.")
    else:
        print("Seed completo: todo lo del seed está en el grafo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
