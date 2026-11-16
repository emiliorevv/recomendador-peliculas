"""Pruebas del seed de datos iniciales.

Las de integración corren contra el Neo4j de pruebas de `NEO4J_TEST_URI`. La
fixture `base_de_pruebas` redirige `src.conexion` a esa base antes de que se cree
el driver: `load_dotenv` no sobreescribe variables ya definidas, así que el
`monkeypatch` gana sobre el `.env` (que apunta a AuraDB). El driver se cierra
antes y después para que no quede abierto con credenciales de la base real.
"""

from __future__ import annotations

import os

import pytest
import src.conexion as conexion
from seed import seed
from seed.seed import (
    esperados,
    filas_de_calificaciones,
    filas_de_seguidores,
    generos,
    leer_datos,
    personas,
)

ESPERADOS_DEL_ENTREGABLE = {
    "peliculas": 35,
    "personas": 74,
    "generos": 10,
    "usuarios": 12,
    "actuo_en": 116,
    "dirigio": 35,
    "de_genero": 86,
    "califico": 95,
    "sigue": 36,
}


@pytest.fixture
def base_de_pruebas(monkeypatch, grafo_limpio):
    """Redirige el driver de la app al Neo4j de pruebas y deja el grafo limpio."""
    monkeypatch.setenv("NEO4J_URI", os.environ["NEO4J_TEST_URI"])
    monkeypatch.setenv("NEO4J_USERNAME", os.environ.get("NEO4J_TEST_USER", "neo4j"))
    monkeypatch.setenv("NEO4J_PASSWORD", os.environ.get("NEO4J_TEST_PASSWORD", "testpassword"))
    monkeypatch.setenv("NEO4J_DATABASE", "neo4j")
    conexion.cerrar_driver()

    yield grafo_limpio

    conexion.cerrar_driver()


def test_esperados_salen_de_los_json():
    """Los conteos esperados son los del entregable, sin hablar con la base."""
    peliculas, usuarios = leer_datos()

    assert esperados(peliculas, usuarios) == ESPERADOS_DEL_ENTREGABLE
    # Y los JSON de verdad tienen esa cantidad de personas y géneros distintos.
    assert len(personas(peliculas)) == ESPERADOS_DEL_ENTREGABLE["personas"]
    assert len(generos(peliculas)) == ESPERADOS_DEL_ENTREGABLE["generos"]
    assert len(filas_de_calificaciones(usuarios)) == ESPERADOS_DEL_ENTREGABLE["califico"]
    assert len(filas_de_seguidores(usuarios)) == ESPERADOS_DEL_ENTREGABLE["sigue"]


@pytest.mark.integration
def test_carga_completa_deja_los_conteos_esperados(base_de_pruebas):
    """Una corrida sobre el grafo vacío carga nodos, relaciones y calificaciones."""
    assert seed.main([]) == 0

    assert seed.contar() == ESPERADOS_DEL_ENTREGABLE


@pytest.mark.integration
def test_correr_dos_veces_no_duplica(base_de_pruebas):
    """Sin `--reset` el seed es idempotente: los mismos conteos después de la segunda corrida."""
    assert seed.main([]) == 0
    primera = seed.contar()

    assert seed.main([]) == 0

    assert seed.contar() == primera


@pytest.mark.integration
def test_reset_vuelve_al_estado_inicial(base_de_pruebas):
    """Con `--reset` el grafo queda igual que en una carga limpia, sin basura."""
    assert seed.main([]) == 0
    antes = seed.contar()

    with base_de_pruebas.session() as sesion:
        sesion.run("CREATE (:Pelicula {id: 'basura-1999', titulo: 'Basura'})").consume()
    assert seed.contar()["peliculas"] == antes["peliculas"] + 1

    assert seed.main(["--reset"]) == 0

    assert seed.contar() == antes
