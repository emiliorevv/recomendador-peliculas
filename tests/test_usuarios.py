"""Pruebas del CRUD de usuarios, calificaciones y seguidores.

Las de integración usan la fixture `base_de_pruebas` de `conftest.py`, que apunta
el driver a `NEO4J_TEST_URI` (nunca a AuraDB) y deja el grafo limpio.
"""

from __future__ import annotations

from datetime import date

import pytest
from src import peliculas, usuarios


@pytest.fixture
def dos_peliculas(base_de_pruebas):
    """Un par de películas para calificar y un par de usuarios para seguir."""
    peliculas.crear_pelicula(
        titulo="El origen", anio=2010, duracion=148, generos=["Ciencia ficción"]
    )
    peliculas.crear_pelicula(titulo="Amélie", anio=2001, duracion=122, generos=["Romance"])
    usuarios.crear_usuario("Ana", "u01")
    usuarios.crear_usuario("Bruno", "u02")
    return base_de_pruebas


@pytest.mark.integration
def test_crear_usuario_sin_id_genera_el_siguiente_libre(base_de_pruebas):
    """El id por defecto es `u` + número: u01 en un grafo vacío y u13 tras u12."""
    assert usuarios.crear_usuario("Ana") == {"id": "u01", "nombre": "Ana"}

    for numero in range(2, 13):
        usuarios.crear_usuario(f"Persona {numero}")

    assert usuarios.crear_usuario("Invitada")["id"] == "u13"


@pytest.mark.integration
def test_crear_usuario_con_id_explicito_y_duplicado(base_de_pruebas):
    """Un id explícito se respeta, y repetirlo es un error."""
    assert usuarios.crear_usuario("Ana", "u99")["id"] == "u99"

    with pytest.raises(ValueError, match="Ya existe un usuario con el id 'u99'"):
        usuarios.crear_usuario("Otra", "u99")


@pytest.mark.parametrize("nombre", ["", "   ", None])
def test_crear_usuario_sin_nombre_falla(nombre):
    """El nombre es obligatorio."""
    with pytest.raises(ValueError, match="nombre no puede estar vacío"):
        usuarios.crear_usuario(nombre)


@pytest.mark.integration
def test_listar_obtener_renombrar_y_eliminar(base_de_pruebas):
    """El ciclo completo de un usuario contra la base."""
    usuarios.crear_usuario("Ana", "u01")
    usuarios.crear_usuario("Bruno", "u02")

    assert usuarios.listar_usuarios() == [
        {"id": "u01", "nombre": "Ana"},
        {"id": "u02", "nombre": "Bruno"},
    ]
    assert usuarios.obtener_usuario("u02") == {"id": "u02", "nombre": "Bruno"}
    assert usuarios.obtener_usuario("u77") is None

    assert usuarios.renombrar_usuario("u01", "Ana María") == {
        "id": "u01",
        "nombre": "Ana María",
    }
    assert usuarios.eliminar_usuario("u02") is True
    assert usuarios.obtener_usuario("u02") is None


@pytest.mark.integration
def test_renombrar_y_eliminar_usuario_inexistente_falla(base_de_pruebas):
    """Operar sobre un usuario que no está lanza `ValueError` con su id."""
    with pytest.raises(ValueError, match="No existe el usuario 'u77'"):
        usuarios.renombrar_usuario("u77", "Nadie")
    with pytest.raises(ValueError, match="No existe el usuario 'u77'"):
        usuarios.eliminar_usuario("u77")


@pytest.mark.integration
def test_calificar_crea_y_actualiza_la_misma_relacion(dos_peliculas):
    """`MERGE` hace que calificar dos veces actualice en vez de duplicar."""
    creada = usuarios.calificar("u01", "el-origen-2010", 4, fecha="2026-01-01")

    assert creada == {
        "usuario_id": "u01",
        "pelicula_id": "el-origen-2010",
        "titulo": "El origen",
        "estrellas": 4,
        "fecha": "2026-01-01",
    }

    actualizada = usuarios.calificar("u01", "el-origen-2010", 5, fecha="2026-02-02")

    assert actualizada["estrellas"] == 5
    assert actualizada["fecha"] == "2026-02-02"
    assert usuarios.calificaciones_de("u01") == [
        {
            "pelicula_id": "el-origen-2010",
            "titulo": "El origen",
            "estrellas": 5,
            "fecha": "2026-02-02",
        }
    ]


@pytest.mark.integration
def test_calificar_sin_fecha_usa_hoy(base_de_pruebas):
    """La fecha por defecto es la de hoy en ISO."""
    peliculas.crear_pelicula(titulo="Amélie", anio=2001, duracion=122, generos=["Romance"])
    usuarios.crear_usuario("Ana", "u01")

    calificacion = usuarios.calificar("u01", "amelie-2001", 5)

    assert calificacion["fecha"] == date.today().isoformat()


@pytest.mark.integration
def test_calificaciones_de_ordena_por_fecha_descendente(dos_peliculas):
    """La más reciente va primero y cada fila trae el título de la película."""
    usuarios.calificar("u01", "el-origen-2010", 3, fecha="2025-01-01")
    usuarios.calificar("u01", "amelie-2001", 5, fecha="2026-01-01")

    assert usuarios.calificaciones_de("u01") == [
        {
            "pelicula_id": "amelie-2001",
            "titulo": "Amélie",
            "estrellas": 5,
            "fecha": "2026-01-01",
        },
        {
            "pelicula_id": "el-origen-2010",
            "titulo": "El origen",
            "estrellas": 3,
            "fecha": "2025-01-01",
        },
    ]
    # Sin calificaciones (o con un usuario que no existe) la lista va vacía.
    assert usuarios.calificaciones_de("u02") == []
    assert usuarios.calificaciones_de("u77") == []


@pytest.mark.parametrize("estrellas", [0, 6, -1, "cinco"])
def test_estrellas_fuera_de_rango_fallan(estrellas):
    """Las estrellas son un entero de 1 a 5 y se validan antes de tocar la base."""
    with pytest.raises(ValueError, match="estrellas"):
        usuarios.calificar("u01", "el-origen-2010", estrellas)


@pytest.mark.integration
def test_calificar_algo_inexistente_falla(dos_peliculas):
    """No se puede calificar sin usuario o sin película."""
    with pytest.raises(ValueError, match="No existe el usuario 'u77'"):
        usuarios.calificar("u77", "el-origen-2010", 4)
    with pytest.raises(ValueError, match="No existe la película 'no-existe-2020'"):
        usuarios.calificar("u01", "no-existe-2020", 4)


@pytest.mark.integration
def test_quitar_calificacion(dos_peliculas):
    """Quitar devuelve `True` la primera vez y `False` cuando ya no estaba."""
    usuarios.calificar("u01", "el-origen-2010", 4)

    assert usuarios.quitar_calificacion("u01", "el-origen-2010") is True
    assert usuarios.calificaciones_de("u01") == []
    assert usuarios.quitar_calificacion("u01", "el-origen-2010") is False
    assert usuarios.quitar_calificacion("u77", "el-origen-2010") is False


@pytest.mark.integration
def test_seguir_y_dejar_de_seguir(dos_peliculas):
    """`SIGUE` es una sola relación por pareja y se ve desde los dos lados."""
    assert usuarios.seguir("u01", "u02") == {
        "usuario_id": "u01",
        "nombre": "Ana",
        "seguido_id": "u02",
        "seguido": "Bruno",
    }

    assert usuarios.a_quien_sigue("u01") == [{"id": "u02", "nombre": "Bruno"}]
    assert usuarios.seguidores_de("u02") == [{"id": "u01", "nombre": "Ana"}]
    assert usuarios.a_quien_sigue("u02") == []

    # Seguir dos veces no duplica: MERGE sobre la misma pareja.
    usuarios.seguir("u01", "u02")
    assert usuarios.dejar_de_seguir("u01", "u02") is True
    assert usuarios.a_quien_sigue("u01") == []
    assert usuarios.seguidores_de("u02") == []
    assert usuarios.dejar_de_seguir("u01", "u02") is False


def test_auto_seguimiento_falla():
    """Nadie se sigue a sí mismo, y se rechaza antes de consultar la base."""
    with pytest.raises(ValueError, match="no puede seguirse a sí mismo"):
        usuarios.seguir("u01", "u01")


@pytest.mark.integration
def test_seguir_a_quien_no_existe_falla(dos_peliculas):
    """El seguidor y el seguido tienen que existir."""
    with pytest.raises(ValueError, match="No existe el usuario 'u77'"):
        usuarios.seguir("u01", "u77")
    with pytest.raises(ValueError, match="No existe el usuario 'u77'"):
        usuarios.seguir("u77", "u01")


@pytest.mark.integration
def test_eliminar_usuario_no_deja_relaciones_colgadas(dos_peliculas):
    """`DETACH DELETE` se lleva sus `CALIFICO` y `SIGUE`; las películas quedan."""
    usuarios.calificar("u01", "el-origen-2010", 4)
    usuarios.calificar("u02", "el-origen-2010", 5)
    usuarios.seguir("u01", "u02")
    usuarios.seguir("u02", "u01")

    assert usuarios.eliminar_usuario("u01") is True

    assert usuarios.obtener_usuario("u01") is None
    with dos_peliculas.session() as sesion:
        relaciones = sesion.run(
            """
            MATCH (u:Usuario {id: 'u01'})-[r]-()
            RETURN count(r) AS total
            """
        ).single()
        restantes = sesion.run(
            """
            RETURN COUNT { ()-[:CALIFICO]->() } AS califico,
                   COUNT { ()-[:SIGUE]->() } AS sigue,
                   COUNT { (p:Pelicula) } AS peliculas
            """
        ).single()
    assert relaciones["total"] == 0
    # Queda la calificación de u02 y las películas; los dos SIGUE tocaban a u01,
    # así que el DETACH DELETE se los llevó a ambos.
    assert dict(restantes) == {"califico": 1, "sigue": 0, "peliculas": 2}
