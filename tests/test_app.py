"""Pruebas de la interfaz Streamlit.

No levantan Streamlit ni tocan la base: comprueban que `app.py` compila (un
error de sintaxis tumbe el CI antes de la demo) y que las cuatro secciones
siguen existiendo en el archivo. El recorrido real de la app se hace a mano
contra AuraDB.
"""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
APP = RAIZ / "app.py"
SECCIONES = ("Películas", "Usuarios", "Recomendaciones", "Caminos")


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
