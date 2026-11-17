"""Validaciones compartidas por el CRUD.

Cada función devuelve el valor normalizado o lanza `ValueError` con un mensaje
que nombra el campo, para que la interfaz lo pueda mostrar tal cual. Están aquí
y no en cada módulo porque películas y usuarios validan lo mismo (texto, enteros
y fechas), y dos copias terminan aceptando cosas distintas.
"""

from __future__ import annotations

from datetime import date
from typing import Any


def texto(valor: Any, campo: str) -> str:
    """Texto obligatorio, sin espacios sobrantes."""
    limpio = str(valor).strip() if valor is not None else ""
    if not limpio:
        raise ValueError(f"El {campo} no puede estar vacío")
    return limpio


def texto_opcional(valor: Any) -> str | None:
    """Texto opcional: `None` o vacío quedan en `None`."""
    if valor is None:
        return None
    limpio = str(valor).strip()
    return limpio or None


def entero(
    valor: Any,
    campo: str,
    minimo: int | None = None,
    maximo: int | None = None,
) -> int:
    """Entero obligatorio, opcionalmente dentro de un rango cerrado.

    Acepta `"2005"` y `2005.0`, porque vienen de formularios, pero rechaza los
    booleanos (son `int` en Python) y los números con decimales distintos de
    cero: `4.5` no se guarda como 4 ni como 5.
    """
    if isinstance(valor, bool):
        raise ValueError(f"El {campo} debe ser un número entero, no un booleano")
    if isinstance(valor, float) and not valor.is_integer():
        raise ValueError(f"El {campo} debe ser un número entero, recibí {valor!r}")
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        raise ValueError(f"El {campo} debe ser un número entero, recibí {valor!r}") from None
    if (minimo is not None and numero < minimo) or (maximo is not None and numero > maximo):
        raise ValueError(f"El {campo} debe estar entre {minimo} y {maximo}, recibí {numero}")
    return numero


def fecha_iso(valor: Any, campo: str = "fecha") -> str:
    """Fecha en `AAAA-MM-DD`, normalizada.

    Acepta un `date` o cualquier texto que `date.fromisoformat` entienda y
    devuelve siempre el formato largo, porque las fechas se guardan como texto y
    así `calificaciones_de` las puede ordenar. `"20261105"` se guarda como
    `"2026-11-05"`; un formato inválido es un `ValueError`.
    """
    try:
        return date.fromisoformat(str(valor).strip()).isoformat()
    except (TypeError, ValueError):
        raise ValueError(
            f"El {campo} debe estar en formato ISO (AAAA-MM-DD), recibí {valor!r}"
        ) from None
