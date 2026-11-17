"""Pruebas de la interfaz Streamlit.

Dos grupos: las que solo leen `app.py` (compila y declara las cuatro secciones,
para que un error de sintaxis tumbe el CI antes de la demo) y las que corren la
app con `AppTest` y un backend falso, sin tocar AuraDB. Esas cubren lo que más
duele en la exposición: que un fallo de conexión se explique en pantalla y no
termine en traceback.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import src.conexion as conexion
import src.consultas as consultas
import src.peliculas as peliculas
import src.usuarios as usuarios
from neo4j.exceptions import ServiceUnavailable, SessionExpired
from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parents[1]
APP = RAIZ / "app.py"
SECCIONES = ("Películas", "Usuarios", "Recomendaciones", "Caminos")

PELICULA = {
    "id": "demo-2020",
    "titulo": "Demo",
    "anio": 2020,
    "duracion": 90,
    "generos": ["Drama"],
    "director": "Directora Demo",
}
DETALLE = {**PELICULA, "actores": ["Ana Demo"]}
USUARIO = {"id": "u01", "nombre": "Ana"}
ESTADO = {"servidor": "Neo4j Kernel", "version": "5.27-aura", "base": "pruebas", "nodos": 1}
ERROR_DE_AURA = "No se pudo hablar con AuraDB"


def caer(*args, **kwargs):
    """Sustituto de una función del backend que simula Aura desconectada."""
    raise ServiceUnavailable("sin ruta al servidor")


@pytest.fixture
def backend_falso(monkeypatch):
    """Hace que la app corra sin AuraDB y devuelve el `monkeypatch` para seguir cambiando."""
    monkeypatch.setattr(conexion, "verificar_conexion", lambda: dict(ESTADO))
    monkeypatch.setattr(peliculas, "listar_peliculas", lambda: [dict(PELICULA)])
    monkeypatch.setattr(peliculas, "obtener_pelicula", lambda pelicula_id: dict(DETALLE))
    monkeypatch.setattr(usuarios, "listar_usuarios", lambda: [dict(USUARIO)])
    return monkeypatch


def abrir_app() -> AppTest:
    """Levanta la app con el ScriptRunner de Streamlit, como `streamlit run`."""
    return AppTest.from_file(str(APP), default_timeout=60).run()


def test_app_compila():
    """Un error de sintaxis en la interfaz se ve aquí y no en la demo."""
    compile(APP.read_text(encoding="utf-8"), "app.py", "exec")


def test_app_declara_las_cuatro_secciones():
    """La navegación de la demo tiene las cuatro secciones del PR 7."""
    codigo = APP.read_text(encoding="utf-8")
    for seccion in SECCIONES:
        assert f'"{seccion}"' in codigo, f"falta la sección {seccion}"


def test_app_muestra_cypher_y_tiempo():
    """El Cypher sale del catálogo y el tiempo se mide con perf_counter."""
    codigo = APP.read_text(encoding="utf-8")
    assert "catalogo()" in codigo
    assert "perf_counter" in codigo
    assert "st.expander" in codigo


def test_app_arranca_con_el_backend_falso(backend_falso):
    """Sin Aura real, la app dibuja la primera sección sin errores ni excepciones."""
    at = abrir_app()
    assert not at.exception
    assert not at.error
    assert any("1 nodos" in caption.value for caption in at.caption)


def test_avisa_si_aura_falla_al_arrancar(monkeypatch):
    """Si `verificar_conexion` no responde, hay st.error y no traceback."""

    def sin_aura():
        raise ServiceUnavailable("no se pudo enrutar")

    monkeypatch.setattr(conexion, "verificar_conexion", sin_aura)

    at = abrir_app()
    assert not at.exception
    assert any("No se pudo conectar con Neo4j AuraDB" in error.value for error in at.error)


def test_avisa_si_falla_una_escritura(backend_falso):
    """Una caída de Aura al crear una película se explica y no revienta."""
    backend_falso.setattr(peliculas, "crear_pelicula", caer)

    at = abrir_app()
    at.get_by_key("operacion_peliculas").set_value("Agregar").run()
    at.get_by_key("alta_titulo").set_value("Demo nueva")
    at.form_submit_button[0].click().run()

    assert not at.exception
    assert any(f"{ERROR_DE_AURA}: ServiceUnavailable" in error.value for error in at.error), [
        error.value for error in at.error
    ]


def test_avisa_si_falla_quitar_una_calificacion(backend_falso):
    """Las rutas que antes no tenían `try` (quitar calificación) también avisan."""

    def sesion_vencida(*args, **kwargs):
        raise SessionExpired("la sesión venció")

    backend_falso.setattr(
        usuarios,
        "calificaciones_de",
        lambda usuario_id: [
            {
                "pelicula_id": PELICULA["id"],
                "titulo": PELICULA["titulo"],
                "estrellas": 4,
                "fecha": "2026-01-01",
            }
        ],
    )
    backend_falso.setattr(usuarios, "quitar_calificacion", sesion_vencida)

    at = abrir_app()
    at.sidebar.radio(key="seccion").set_value("Usuarios").run()
    at.get_by_key("operacion_usuarios").set_value("Calificaciones").run()
    for boton in at.button:
        if boton.label == "Quitar la calificación":
            boton.click().run()
            break
    else:
        pytest.fail("no apareció el botón de quitar calificación")

    assert not at.exception
    assert any(f"{ERROR_DE_AURA}: SessionExpired" in error.value for error in at.error), [
        error.value for error in at.error
    ]


def test_avisa_si_falla_una_consulta(backend_falso):
    """Una consulta del catálogo que falla deja el mensaje, no el traceback."""
    backend_falso.setattr(consultas, "recomendar", caer)

    at = abrir_app()
    at.sidebar.radio(key="seccion").set_value("Recomendaciones").run()

    assert not at.exception
    assert any(f"{ERROR_DE_AURA}: ServiceUnavailable" in error.value for error in at.error)
    assert not at.expander, "no debe mostrarse el Cypher de una consulta que no corrió"


def test_el_alta_conserva_lo_escrito_si_falla_y_limpia_si_funciona(backend_falso):
    """El formulario no se borra con un error de validación y sí tras un alta exitosa."""

    def repetida(*args, **kwargs):
        raise ValueError("Ya existe una película con el id 'demo-2020'")

    backend_falso.setattr(peliculas, "crear_pelicula", repetida)

    at = abrir_app()
    at.get_by_key("operacion_peliculas").set_value("Agregar").run()
    at.get_by_key("alta_titulo").set_value("Demo repetida")
    at.form_submit_button[0].click().run()

    assert any("Ya existe" in error.value for error in at.error)
    assert at.get_by_key("alta_titulo").value == "Demo repetida"

    backend_falso.setattr(peliculas, "crear_pelicula", lambda **kwargs: dict(PELICULA))
    at.form_submit_button[0].click().run()

    assert not at.error
    assert any("Se agregó" in success.value for success in at.success)
    assert at.get_by_key("alta_titulo").value == ""
    assert at.get_by_key("alta_generos").value == []


def test_editar_sin_tocar_el_reparto_no_lo_reemplaza(backend_falso):
    """Cambiar la duración manda `actores=None`, así un nombre con coma no se parte."""
    detalle = {**DETALLE, "actores": ["Sammy Davis, Jr."]}
    backend_falso.setattr(peliculas, "obtener_pelicula", lambda pelicula_id: dict(detalle))
    guardado = {}

    def guardar(pelicula_id, **kwargs):
        guardado.update(kwargs)
        return dict(detalle)

    backend_falso.setattr(peliculas, "actualizar_pelicula", guardar)

    at = abrir_app()
    at.get_by_key("operacion_peliculas").set_value("Editar").run()
    at.get_by_key(f"editar_duracion_{PELICULA['id']}").set_value(100)
    at.form_submit_button[0].click().run()

    assert not at.exception
    assert not at.error
    assert guardado["duracion"] == 100
    assert guardado["actores"] is None

    at.get_by_key(f"editar_actores_{PELICULA['id']}").set_value("Ana Demo")
    at.form_submit_button[0].click().run()

    assert guardado["actores"] == ["Ana Demo"]
