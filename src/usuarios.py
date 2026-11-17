"""CRUD de usuarios, calificaciones y seguidores.

Los usuarios son nodos `:Usuario` con `id` (`u01`, `u02`, …) y `nombre`. La
calificación vive en la relación `CALIFICO` (`Usuario` → `Pelicula`) porque le
pertenece a la pareja usuario-película: calificar dos veces la misma película
actualiza las estrellas en vez de duplicar la relación, y el seguimiento es
`SIGUE` (`Usuario` → `Usuario`).

Las listas (`calificaciones_de`, `a_quien_sigue`, `seguidores_de`) devuelven
`[]` si el usuario no existe; el resto de las operaciones lanza `ValueError`
con un mensaje claro cuando el usuario, la película o la relación no existen.

Todas las consultas van con parámetros (`$id`, `$estrellas`, …): el texto que
llega desde la interfaz nunca se pega en el Cypher.

Uso típico::

    from src.usuarios import calificar, crear_usuario, seguir

    usuario = crear_usuario("Emilia")          # -> u13, el siguiente libre
    calificar(usuario["id"], "inception-2010", 5)
    seguir(usuario["id"], "u01")
"""

from __future__ import annotations

from datetime import date
from typing import Any

from src.conexion import escribir, leer

ESTRELLAS_MINIMAS = 1
ESTRELLAS_MAXIMAS = 5

LISTAR_USUARIOS = """
MATCH (u:Usuario)
RETURN u.id AS id, u.nombre AS nombre
ORDER BY u.id
"""

DETALLE_USUARIO = """
MATCH (u:Usuario {id: $id})
RETURN u.id AS id, u.nombre AS nombre
"""

# toInteger ignora los ids que no son `u` + número, así que un id raro no
# rompe el cálculo del siguiente libre.
MAYOR_ID = """
MATCH (u:Usuario) WHERE u.id STARTS WITH 'u'
RETURN max(toInteger(substring(u.id, 1))) AS mayor
"""

CREAR_USUARIO = """
CREATE (u:Usuario {id: $id, nombre: $nombre})
RETURN u.id AS id, u.nombre AS nombre
"""

RENOMBRAR_USUARIO = """
MATCH (u:Usuario {id: $id})
SET u.nombre = $nombre
RETURN u.id AS id, u.nombre AS nombre
"""

ELIMINAR_USUARIO = """
MATCH (u:Usuario {id: $id})
DETACH DELETE u
"""

# La calificación es propiedad de la relación: MERGE crea o actualiza.
CALIFICAR = """
MATCH (u:Usuario {id: $usuario})
MATCH (p:Pelicula {id: $pelicula})
MERGE (u)-[c:CALIFICO]->(p)
SET c.estrellas = $estrellas, c.fecha = $fecha
RETURN p.id AS pelicula_id, p.titulo AS titulo, c.estrellas AS estrellas, c.fecha AS fecha
"""

CALIFICACIONES_DE = """
MATCH (:Usuario {id: $id})-[c:CALIFICO]->(p:Pelicula)
RETURN p.id AS pelicula_id, p.titulo AS titulo, c.estrellas AS estrellas, c.fecha AS fecha
ORDER BY c.fecha DESC, p.titulo
"""

QUITAR_CALIFICACION = """
MATCH (:Usuario {id: $usuario})-[c:CALIFICO]->(:Pelicula {id: $pelicula})
DELETE c
RETURN count(*) AS borradas
"""

SEGUIR = """
MATCH (u:Usuario {id: $usuario})
MATCH (s:Usuario {id: $seguido})
MERGE (u)-[:SIGUE]->(s)
RETURN u.id AS usuario_id, u.nombre AS nombre,
       s.id AS seguido_id, s.nombre AS seguido
"""

DEJAR_DE_SEGUIR = """
MATCH (:Usuario {id: $usuario})-[r:SIGUE]->(:Usuario {id: $seguido})
DELETE r
RETURN count(*) AS borradas
"""

A_QUIEN_SIGUE = """
MATCH (:Usuario {id: $id})-[:SIGUE]->(s:Usuario)
RETURN s.id AS id, s.nombre AS nombre
ORDER BY s.nombre, s.id
"""

SEGUIDORES_DE = """
MATCH (s:Usuario)-[:SIGUE]->(:Usuario {id: $id})
RETURN s.id AS id, s.nombre AS nombre
ORDER BY s.nombre, s.id
"""


def _texto(valor: Any, campo: str) -> str:
    """Texto obligatorio, sin espacios sobrantes."""
    texto = str(valor).strip() if valor is not None else ""
    if not texto:
        raise ValueError(f"El {campo} no puede estar vacío")
    return texto


def _existe(usuario_id: str) -> bool:
    """True si el usuario ya está en el grafo."""
    return obtener_usuario(usuario_id) is not None


def _obtener_o_fallar(usuario_id: str) -> dict[str, Any]:
    """Usuario por id, o `ValueError` si no existe."""
    usuario = obtener_usuario(usuario_id)
    if usuario is None:
        raise ValueError(f"No existe el usuario {usuario_id!r}")
    return usuario


def _pelicula_existe(pelicula_id: str) -> bool:
    """True si la película está en el grafo (solo se consulta su id)."""
    return bool(leer("MATCH (p:Pelicula {id: $id}) RETURN p.id AS id", id=pelicula_id))


def _siguiente_id() -> str:
    """Siguiente id libre con el formato `u01`, `u13`, …"""
    fila = leer(MAYOR_ID)[0]
    mayor = fila["mayor"] or 0
    return f"u{int(mayor) + 1:02d}"


def crear_usuario(nombre: str, usuario_id: str | None = None) -> dict[str, Any]:
    """Crea un usuario y lo devuelve.

    Sin `usuario_id` se usa el siguiente libre (`u13` si están `u01`…`u12`).
    Con un id repetido lanza `ValueError`.
    """
    nombre = _texto(nombre, "nombre")
    if usuario_id is None:
        usuario_id = _siguiente_id()
    else:
        usuario_id = _texto(usuario_id, "id")
        if _existe(usuario_id):
            raise ValueError(f"Ya existe un usuario con el id {usuario_id!r}")

    return escribir(CREAR_USUARIO, id=usuario_id, nombre=nombre)[0]


def listar_usuarios() -> list[dict[str, Any]]:
    """Todos los usuarios, ordenados por id."""
    return leer(LISTAR_USUARIOS)


def obtener_usuario(usuario_id: str) -> dict[str, Any] | None:
    """Usuario por id, o `None` si no existe."""
    filas = leer(DETALLE_USUARIO, id=str(usuario_id))
    return filas[0] if filas else None


def renombrar_usuario(usuario_id: str, nombre: str) -> dict[str, Any]:
    """Cambia el nombre del usuario y lo devuelve."""
    usuario_id = str(usuario_id)
    nombre = _texto(nombre, "nombre")
    filas = escribir(RENOMBRAR_USUARIO, id=usuario_id, nombre=nombre)
    if not filas:
        raise ValueError(f"No existe el usuario {usuario_id!r}")
    return filas[0]


def eliminar_usuario(usuario_id: str) -> bool:
    """Borra el usuario con sus `CALIFICO` y `SIGUE` (`DETACH DELETE`).

    Devuelve `True` si lo borró y lanza `ValueError` si no existía.
    """
    usuario_id = str(usuario_id)
    _obtener_o_fallar(usuario_id)
    escribir(ELIMINAR_USUARIO, id=usuario_id)
    return True


def calificar(
    usuario_id: str,
    pelicula_id: str,
    estrellas: int,
    fecha: str | None = None,
) -> dict[str, Any]:
    """Califica una película: crea la relación o actualiza estrellas y fecha.

    `estrellas` es un entero de 1 a 5 y `fecha` va en ISO; por defecto, hoy.
    """
    usuario_id = str(usuario_id)
    pelicula_id = str(pelicula_id)
    if isinstance(estrellas, bool):
        raise ValueError("Las estrellas deben ser un número entero de 1 a 5")
    try:
        estrellas = int(estrellas)
    except (TypeError, ValueError):
        raise ValueError(
            f"Las estrellas deben ser un número entero de 1 a 5, recibí {estrellas!r}"
        ) from None
    if not ESTRELLAS_MINIMAS <= estrellas <= ESTRELLAS_MAXIMAS:
        raise ValueError(f"Las estrellas deben estar entre 1 y 5, recibí {estrellas}")

    fecha = date.today().isoformat() if fecha is None else _texto(fecha, "fecha")

    _obtener_o_fallar(usuario_id)
    if not _pelicula_existe(pelicula_id):
        raise ValueError(f"No existe la película {pelicula_id!r}")

    fila = escribir(
        CALIFICAR, usuario=usuario_id, pelicula=pelicula_id, estrellas=estrellas, fecha=fecha
    )[0]
    return {"usuario_id": usuario_id, **fila}


def calificaciones_de(usuario_id: str) -> list[dict[str, Any]]:
    """Calificaciones del usuario, de la más reciente a la más vieja."""
    return leer(CALIFICACIONES_DE, id=str(usuario_id))


def quitar_calificacion(usuario_id: str, pelicula_id: str) -> bool:
    """Quita la calificación; `False` si esa pareja no tenía ninguna."""
    fila = escribir(QUITAR_CALIFICACION, usuario=str(usuario_id), pelicula=str(pelicula_id))[0]
    return int(fila["borradas"]) > 0


def seguir(usuario_id: str, seguido_id: str) -> dict[str, Any]:
    """Hace que `usuario_id` siga a `seguido_id` y devuelve la relación."""
    usuario_id = str(usuario_id)
    seguido_id = str(seguido_id)
    if usuario_id == seguido_id:
        raise ValueError("Un usuario no puede seguirse a sí mismo")

    _obtener_o_fallar(usuario_id)
    _obtener_o_fallar(seguido_id)
    return escribir(SEGUIR, usuario=usuario_id, seguido=seguido_id)[0]


def dejar_de_seguir(usuario_id: str, seguido_id: str) -> bool:
    """Deja de seguir; `False` si no lo seguía."""
    fila = escribir(DEJAR_DE_SEGUIR, usuario=str(usuario_id), seguido=str(seguido_id))[0]
    return int(fila["borradas"]) > 0


def a_quien_sigue(usuario_id: str) -> list[dict[str, Any]]:
    """Usuarios que sigue, ordenados por nombre."""
    return leer(A_QUIEN_SIGUE, id=str(usuario_id))


def seguidores_de(usuario_id: str) -> list[dict[str, Any]]:
    """Usuarios que lo siguen, ordenados por nombre."""
    return leer(SEGUIDORES_DE, id=str(usuario_id))
