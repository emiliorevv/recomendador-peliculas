"""Fixtures compartidas por las pruebas.

Las pruebas marcadas con @pytest.mark.integration se omiten cuando no existe
NEO4J_TEST_URI. Nunca usan NEO4J_URI, que en el `.env` apunta a la base real de
AuraDB: las pruebas borran datos y no deben tocar la instancia de la demo.
"""

import os

import pytest
from neo4j import GraphDatabase

TEST_URI = os.getenv("NEO4J_TEST_URI")
TEST_USER = os.getenv("NEO4J_TEST_USER", "neo4j")
TEST_PASSWORD = os.getenv("NEO4J_TEST_PASSWORD", "testpassword")

# Todo Bolt de Aura vive en databases.neo4j.io, sin importar el esquema
# (neo4j+s, neo4j+ssc) ni una barra final.
HOSTS_DE_AURA = ("databases.neo4j.io", "mcp-instances.neo4j.io")

necesita_neo4j = pytest.mark.skipif(
    not TEST_URI, reason="NEO4J_TEST_URI no está definido: se omite la prueba de integración"
)


def es_base_de_aura(uri: str) -> bool:
    return any(host in uri for host in HOSTS_DE_AURA)


def pytest_collection_modifyitems(items):
    """Omite las pruebas de integración si no hay base de pruebas.

    Sin este hook, una prueba marcada que arme su propio driver correría igual
    contra la base real aunque NEO4J_TEST_URI no exista.
    """
    if TEST_URI:
        return

    for item in items:
        if "integration" in item.keywords:
            item.add_marker(necesita_neo4j)


@pytest.fixture(scope="session")
def driver():
    """Driver hacia la base de pruebas, apagado al terminar la sesión."""
    if not TEST_URI:
        pytest.skip("NEO4J_TEST_URI no está definido")

    if es_base_de_aura(TEST_URI):
        pytest.fail("NEO4J_TEST_URI apunta a AuraDB; usa una instancia de pruebas desechable")

    driver = GraphDatabase.driver(TEST_URI, auth=(TEST_USER, TEST_PASSWORD))
    driver.verify_connectivity()
    yield driver
    driver.close()


@pytest.fixture
def grafo_limpio(driver):
    """Deja la base de pruebas vacía antes y después de cada prueba."""
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n").consume()

    yield driver

    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n").consume()
