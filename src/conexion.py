"""Conexión a Neo4j AuraDB con un driver único para toda la aplicación.

Las credenciales se leen de variables de entorno cargadas desde `.env` (ver
`.env.example`). Este módulo nunca imprime ni registra la contraseña ni la URI
completa: los errores solo nombran las variables que faltan.

Uso típico::

    from src.conexion import leer, escribir

    filas = leer("MATCH (p:Pelicula) RETURN p.titulo AS titulo")
    escribir("CREATE (g:Genero {nombre: $nombre})", nombre="Drama")

El driver se crea la primera vez que se usa y se reutiliza (pool de conexiones).
Al terminar el programa se llama a `cerrar_driver()`.
"""

from __future__ import annotations

import os
import ssl
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from neo4j import Driver, GraphDatabase, ManagedTransaction, RoutingControl

RAIZ = Path(__file__).resolve().parents[1]
ARCHIVO_ENV = RAIZ / ".env"

# Variables obligatorias. NEO4J_DATABASE es opcional: sin ella se usa la base por
# defecto del servidor.
VARIABLES = ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD")
AYUDA = (
    "Copia .env.example como .env en la raíz del repo y llena los datos de tu "
    "instancia de Neo4j AuraDB."
)

_driver: Driver | None = None
# Streamlit atiende cada sesión en su propio hilo: el candado evita crear dos drivers.
_candado = threading.Lock()


def _credenciales() -> dict[str, str]:
    """Carga el `.env` y devuelve las variables obligatorias, o falla con un mensaje claro."""
    load_dotenv(ARCHIVO_ENV)
    faltantes = [variable for variable in VARIABLES if not os.getenv(variable)]
    if faltantes:
        raise RuntimeError(f"Faltan variables de entorno: {', '.join(faltantes)}. {AYUDA}")
    return {variable: os.environ[variable] for variable in VARIABLES}


def _base_de_datos() -> str | None:
    """Base configurada en NEO4J_DATABASE (en Aura es el id de la instancia)."""
    return os.getenv("NEO4J_DATABASE") or None


def _configurar_certificados() -> None:
    """Da un trust store al proceso solo si el intérprete no tiene ninguno.

    Los Python que se instalan desde python.org en macOS no incluyen los
    certificados raíz, así que el TLS contra AuraDB falla con
    `SSL: CERTIFICATE_VERIFY_FAILED` o, de forma menos obvia,
    `ServiceUnavailable: Unable to retrieve routing information`. `certifi`
    trae un bundle actualizado y se usa como `SSL_CERT_FILE`.

    Se toca el entorno lo mínimo: si el usuario ya definió `SSL_CERT_FILE` o si
    el contexto TLS por defecto sí trae CAs (una red con proxy que inspecciona
    TLS y una CA corporativa instalada en el sistema), no se cambia nada; pisar
    esas CAs rompería conexiones que hoy funcionan.
    """
    if os.getenv("SSL_CERT_FILE"):
        return
    if ssl.create_default_context().get_ca_certs():
        return
    try:
        import certifi
    except ImportError:
        # Sin certifi se deja todo como estaba: el error de TLS lo explicará el driver.
        return
    os.environ["SSL_CERT_FILE"] = certifi.where()


def obtener_driver() -> Driver:
    """Devuelve el driver único, creándolo la primera vez (singleton seguro entre hilos)."""
    global _driver
    if _driver is None:
        with _candado:
            # Doble verificación: otro hilo pudo crearlo mientras esperábamos.
            if _driver is None:
                credenciales = _credenciales()
                _configurar_certificados()
                _driver = GraphDatabase.driver(
                    credenciales["NEO4J_URI"],
                    auth=(credenciales["NEO4J_USERNAME"], credenciales["NEO4J_PASSWORD"]),
                )
    return _driver


def cerrar_driver() -> None:
    """Cierra el driver y limpia el singleton para que se pueda volver a crear."""
    global _driver
    with _candado:
        if _driver is None:
            return
        driver = _driver
        try:
            driver.close()
        finally:
            # Aunque close() falle, el singleton queda limpio y no se reutiliza a medias.
            _driver = None


def _ejecutar(
    consulta: str, enrutamiento: RoutingControl, parametros: dict[str, Any]
) -> list[dict[str, Any]]:
    """Corre una consulta en una transacción administrada y devuelve las filas como dicts."""
    driver = obtener_driver()
    resultado = driver.execute_query(
        consulta,
        parameters_=parametros or None,
        database_=_base_de_datos(),
        routing_=enrutamiento,
    )
    return [registro.data() for registro in resultado.records]


def leer(consulta: str, **parametros: Any) -> list[dict[str, Any]]:
    """Ejecuta una consulta de lectura (routing READ) y devuelve las filas como dicts."""
    return _ejecutar(consulta, RoutingControl.READ, parametros)


def escribir(consulta: str, **parametros: Any) -> list[dict[str, Any]]:
    """Ejecuta una consulta de escritura (routing WRITE) y devuelve las filas como dicts."""
    return _ejecutar(consulta, RoutingControl.WRITE, parametros)


def en_transaccion[T](funcion: Callable[[ManagedTransaction], T]) -> T:
    """Corre varias escrituras en una sola transacción y devuelve lo que devuelva `funcion`.

    `funcion` recibe la transacción abierta y hace sus `tx.run(...)` en orden::

        def crear(tx):
            tx.run("CREATE (p:Pelicula {id: $id})", id="x-2000")
            tx.run("MERGE (:Genero {nombre: 'Drama'})")

        en_transaccion(crear)

    Si cualquier escritura falla, el commit no ocurre y el grafo queda como
    estaba: no quedan películas a medias ni relaciones sueltas. `execute_write`
    reintenta ante errores transitorios (un corte de red contra Aura, por
    ejemplo), así que las escrituras de `funcion` deben ser idempotentes; con
    `MERGE` y `CREATE` de nodos que se acaban de insertar, lo son.

    Para una sola sentencia alcanza `escribir()`; esta función es para las
    operaciones que necesitan varias.
    """
    driver = obtener_driver()
    with driver.session(database=_base_de_datos()) as sesion:
        return sesion.execute_write(funcion)


def verificar_conexion() -> dict[str, Any]:
    """Comprueba la conexión real y resume servidor, versión, base y cantidad de nodos."""
    componentes = leer(
        """
        CALL dbms.components() YIELD name, versions
        RETURN name AS servidor, versions[0] AS version
        """
    )
    # La base real la dice el servidor: en Aura es el id de la instancia y no
    # siempre coincide con NEO4J_DATABASE. `db.name()` no existe en 5.x, por eso
    # se usa el procedimiento `db.info()`.
    base = leer("CALL db.info() YIELD name RETURN name AS base")
    total = leer("MATCH (n) RETURN count(n) AS nodos")
    return {
        "servidor": componentes[0]["servidor"],
        "version": componentes[0]["version"],
        "base": base[0]["base"],
        "nodos": int(total[0]["nodos"]),
    }
