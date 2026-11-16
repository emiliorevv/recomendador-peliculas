"""Aplica las restricciones e índices del grafo.

Se corre desde la raíz del repo con `python seed/esquema.py`. Lee
`seed/esquema.cypher`, lo parte por `;` y ejecuta cada sentencia. El archivo usa
`IF NOT EXISTS`, así que correrlo dos veces no falla ni duplica nada.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.conexion import cerrar_driver, escribir  # noqa: E402

ARCHIVO_ESQUEMA = Path(__file__).with_name("esquema.cypher")


def sentencias(archivo: Path = ARCHIVO_ESQUEMA) -> list[str]:
    """Devuelve las sentencias del `.cypher`, sin comentarios ni bloques vacíos."""
    # Los comentarios se quitan antes de partir por ';' para que un ';' dentro de
    # un comentario no genere una sentencia falsa.
    lineas = [
        linea
        for linea in archivo.read_text(encoding="utf-8").splitlines()
        if linea.strip() and not linea.strip().startswith("//")
    ]
    return [bloque.strip() for bloque in "\n".join(lineas).split(";") if bloque.strip()]


def aplicar(
    archivo: Path = ARCHIVO_ESQUEMA,
    ejecutar: Callable[[str], object] = escribir,
) -> int:
    """Ejecuta cada sentencia del esquema y devuelve cuántas se aplicaron."""
    lista = sentencias(archivo)
    for sentencia in lista:
        ejecutar(sentencia)
    return len(lista)


def main() -> None:
    """Aplica el esquema contra la base configurada en el `.env` e imprime el resumen."""
    try:
        aplicadas = aplicar()
    finally:
        cerrar_driver()
    print(f"Esquema aplicado: {aplicadas} sentencias (restricciones e índices).")


if __name__ == "__main__":
    main()
