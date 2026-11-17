"""Pruebas de la conexión y del esquema.

Las que hablan con una base llevan @pytest.mark.integration y usan la fixture
`driver` de conftest.py, que apunta a un Neo4j de pruebas (NEO4J_TEST_URI) y se
omite si no está definida. Nunca se usa NEO4J_URI, que apunta a AuraDB.
"""

from __future__ import annotations

import os
import threading
from types import SimpleNamespace

import pytest
import src.conexion as conexion
from seed.esquema import aplicar, sentencias


@pytest.fixture
def sin_driver():
    """Deja el singleton vacío antes y después de la prueba."""
    conexion.cerrar_driver()
    yield
    conexion.cerrar_driver()


def test_obtener_driver_sin_variables_lanza_runtime_error(monkeypatch, sin_driver):
    """Sin variables de entorno falla al crear el driver con un mensaje que apunta al .env."""
    for variable in conexion.VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setattr(conexion, "load_dotenv", lambda *args, **kwargs: None)

    with pytest.raises(RuntimeError) as error:
        conexion.obtener_driver()

    mensaje = str(error.value)
    assert "NEO4J_URI" in mensaje
    assert ".env.example" in mensaje
    # No se creó ningún driver a medias.
    assert conexion._driver is None


def test_cerrar_driver_sin_driver_no_falla(sin_driver):
    """Cerrar dos veces (o cerrar sin haber abierto) es seguro."""
    conexion.cerrar_driver()
    conexion.cerrar_driver()


def test_cerrar_driver_limpia_el_singleton_si_close_falla(monkeypatch, sin_driver):
    """Si el driver falla al cerrarse, el singleton igual queda vacío."""

    class _DriverRoto:
        def close(self) -> None:
            raise RuntimeError("fallo al cerrar")

    monkeypatch.setattr(conexion, "_driver", _DriverRoto())

    with pytest.raises(RuntimeError):
        conexion.cerrar_driver()

    assert conexion._driver is None


def test_configurar_certificados_usa_certifi(monkeypatch):
    """Sin SSL_CERT_FILE el módulo apunta el trust store al bundle de certifi."""
    certificados = pytest.importorskip("certifi")
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)

    conexion._configurar_certificados()

    assert os.environ["SSL_CERT_FILE"] == certificados.where()


def test_configurar_certificados_respeta_el_valor_del_usuario(monkeypatch):
    """Si ya hay SSL_CERT_FILE, no se pisa: puede ser una configuración a propósito."""
    monkeypatch.setenv("SSL_CERT_FILE", "/ruta/a/mis/certificados.pem")

    conexion._configurar_certificados()

    assert os.environ["SSL_CERT_FILE"] == "/ruta/a/mis/certificados.pem"


def test_obtener_driver_crea_uno_solo_entre_hilos(monkeypatch, sin_driver):
    """Varios hilos pidiendo el driver a la vez comparten una única instancia."""

    class _DriverFalso:
        def close(self) -> None:
            pass

    creados = []

    def fabrica(uri: str, auth: tuple[str, str]) -> _DriverFalso:
        creados.append((uri, auth))
        return _DriverFalso()

    monkeypatch.setattr(conexion, "GraphDatabase", SimpleNamespace(driver=fabrica))
    monkeypatch.setenv("NEO4J_URI", "bolt://pruebas:7687")
    monkeypatch.setenv("NEO4J_USERNAME", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "secreto-de-prueba")

    barrera = threading.Barrier(8)
    obtenidos = []

    def pedirlo() -> None:
        barrera.wait()
        obtenidos.append(conexion.obtener_driver())

    hilos = [threading.Thread(target=pedirlo) for _ in range(8)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()

    assert len(creados) == 1
    assert len({id(driver) for driver in obtenidos}) == 1


def test_sentencias_del_esquema():
    """El .cypher se parte en 5 sentencias limpias, sin comentarios ni ';'."""
    lista = sentencias()

    assert len(lista) == 5
    assert all(";" not in sentencia for sentencia in lista)
    assert all(not sentencia.startswith("//") for sentencia in lista)
    assert sum("CREATE CONSTRAINT" in sentencia for sentencia in lista) == 4
    assert sum("CREATE INDEX" in sentencia for sentencia in lista) == 1


def test_sentencias_ignora_puntos_y_coma_en_comentarios(tmp_path):
    """Un ';' dentro de un comentario no genera una sentencia falsa."""
    archivo = tmp_path / "esquema.cypher"
    archivo.write_text("// uno; y otro\nRETURN 1;\n// final\n", encoding="utf-8")

    assert sentencias(archivo) == ["RETURN 1"]


def test_sentencias_ignora_comentario_al_final_con_punto_y_coma(tmp_path):
    """Un comentario al final de la sentencia, con ';' adentro, no la parte en dos."""
    archivo = tmp_path / "esquema.cypher"
    archivo.write_text(
        "CREATE INDEX pelicula_titulo IF NOT EXISTS FOR (p:Pelicula) ON (p.titulo); "
        "// ver PR 5; pendiente\n"
        "RETURN 1;\n",
        encoding="utf-8",
    )

    assert sentencias(archivo) == [
        "CREATE INDEX pelicula_titulo IF NOT EXISTS FOR (p:Pelicula) ON (p.titulo)",
        "RETURN 1",
    ]


@pytest.mark.integration
def test_verificar_conexion(monkeypatch, driver):
    """verificar_conexion() responde contra la base de pruebas con datos reales."""
    monkeypatch.setattr(conexion, "obtener_driver", lambda: driver)
    monkeypatch.delenv("NEO4J_DATABASE", raising=False)

    info = conexion.verificar_conexion()

    assert info["servidor"]
    assert info["version"]
    assert info["base"]
    assert isinstance(info["nodos"], int)
    assert info["nodos"] >= 0


@pytest.mark.integration
def test_verificar_conexion_reporta_la_base_del_servidor(monkeypatch, driver):
    """La base la dice el servidor y coincide con NEO4J_DATABASE cuando está definida."""
    monkeypatch.setattr(conexion, "obtener_driver", lambda: driver)
    monkeypatch.setenv("NEO4J_DATABASE", "neo4j")

    assert conexion.verificar_conexion()["base"] == os.environ["NEO4J_DATABASE"]


@pytest.mark.integration
def test_esquema_idempotente(driver):
    """Aplicar el esquema dos veces no falla y deja las mismas restricciones e índices."""

    def ejecutar(sentencia: str) -> object:
        return driver.execute_query(sentencia)

    assert aplicar(ejecutar=ejecutar) == 5
    assert aplicar(ejecutar=ejecutar) == 5

    constraints = driver.execute_query("SHOW CONSTRAINTS YIELD name RETURN name").records
    indexes = driver.execute_query("SHOW INDEXES YIELD name RETURN name").records
    nombres = {registro["name"] for registro in constraints}
    nombres |= {registro["name"] for registro in indexes}

    assert {"pelicula_id", "usuario_id", "persona_nombre", "genero_nombre"} <= nombres
    assert "pelicula_titulo" in nombres
