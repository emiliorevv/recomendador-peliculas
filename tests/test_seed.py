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

# Números del entregable, escritos a mano a propósito: si alguien edita los JSON,
# esta prueba es la que lo nota.
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


def test_los_json_tienen_los_datos_del_entregable():
    """Los JSON traen 35 películas, 12 usuarios y los conteos esperados, sin tocar la base."""
    peliculas, usuarios = leer_datos()

    assert len(peliculas) == 35
    assert len(usuarios) == 12
    assert esperados(peliculas, usuarios) == ESPERADOS_DEL_ENTREGABLE
    # Y las claves sin repetir dan lo mismo que los conteos de relaciones.
    assert len(personas(peliculas)) == ESPERADOS_DEL_ENTREGABLE["personas"]
    assert len(generos(peliculas)) == ESPERADOS_DEL_ENTREGABLE["generos"]
    assert len(filas_de_calificaciones(usuarios)) == ESPERADOS_DEL_ENTREGABLE["califico"]
    assert len(filas_de_seguidores(usuarios)) == ESPERADOS_DEL_ENTREGABLE["sigue"]


def test_esperados_no_cuentan_duplicados():
    """MERGE colapsa los duplicados de los JSON, así que los esperados también."""
    peliculas = [
        {
            "id": "x-2000",
            "titulo": "X",
            "anio": 2000,
            "duracion": 90,
            "generos": ["Drama", "Drama"],
            "director": "D",
            "actores": ["A", "A"],
        },
        {
            "id": "x-2000",
            "titulo": "X",
            "anio": 2000,
            "duracion": 90,
            "generos": ["Drama"],
            "director": "D",
            "actores": ["A"],
        },
    ]
    usuarios = [
        {
            "id": "u01",
            "nombre": "Ana",
            "sigue": ["u01"],
            "calificaciones": [
                {"pelicula_id": "x-2000", "estrellas": 5, "fecha": "2025-01-01"},
                {"pelicula_id": "x-2000", "estrellas": 4, "fecha": "2025-01-02"},
            ],
        }
    ]

    assert esperados(peliculas, usuarios) == {
        "peliculas": 1,
        "personas": 2,
        "generos": 1,
        "usuarios": 1,
        "actuo_en": 1,
        "dirigio": 1,
        "de_genero": 1,
        "califico": 1,
        "sigue": 1,
    }


def test_faltantes_reporta_solo_lo_que_no_esta():
    """La validación normal mira presencia, no igualdad: lo que sobra en el grafo no es problema."""
    esperadas = {"peliculas": {"a", "b"}, "califico": {"u01|a"}}

    assert seed.faltantes(esperadas, {"peliculas": {"a"}, "califico": {"u01|a"}}) == {
        "peliculas": ["b"]
    }
    assert seed.faltantes(esperadas, {"peliculas": {"a", "b", "z"}, "califico": {"u01|a"}}) == {}


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


@pytest.mark.integration
def test_el_crud_puede_agregar_datos_sin_romper_el_seed(base_de_pruebas):
    """Un usuario y una calificación del CRUD no hacen fallar el seed ni duplican lo suyo."""
    assert seed.main([]) == 0
    antes = seed.contar()

    # Lo que hará el CRUD del PR 5: un usuario nuevo que califica una película.
    with base_de_pruebas.session() as sesion:
        sesion.run(
            """
            CREATE (u:Usuario {id: 'u99', nombre: 'Invitada'})
            WITH u
            MATCH (p:Pelicula {id: 'inception-2010'})
            CREATE (u)-[:CALIFICO {estrellas: 5, fecha: '2026-11-16'}]->(p)
            """
        ).consume()

    assert seed.main([]) == 0

    despues = seed.contar()
    assert despues["usuarios"] == antes["usuarios"] + 1
    assert despues["califico"] == antes["califico"] + 1
    # Lo del seed no se duplicó.
    assert despues["peliculas"] == antes["peliculas"]
    assert despues["sigue"] == antes["sigue"]

    peliculas, usuarios = leer_datos()
    assert seed.faltantes(seed.claves_del_seed(peliculas, usuarios), seed.claves_del_grafo()) == {}
