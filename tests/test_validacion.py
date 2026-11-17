"""Pruebas de las validaciones compartidas por el CRUD."""

from __future__ import annotations

from datetime import date

import pytest
from src.validacion import entero, fecha_iso, texto, texto_opcional


def test_texto_recorta_espacios():
    assert texto("  Drama  ", "título") == "Drama"


@pytest.mark.parametrize("valor", [None, "", "   "])
def test_texto_obligatorio_no_admite_vacios(valor):
    with pytest.raises(ValueError, match="título no puede estar vacío"):
        texto(valor, "título")


def test_texto_opcional():
    """`None` y vacío son lo mismo; el texto se recorta."""
    assert texto_opcional(None) is None
    assert texto_opcional("  ") is None
    assert texto_opcional("  Denis Villeneuve ") == "Denis Villeneuve"


def test_entero_normaliza_lo_que_viene_de_un_formulario():
    assert entero("2005", "año") == 2005
    assert entero(2005.0, "año") == 2005


@pytest.mark.parametrize("valor", [4.5, True, "mil", None, [1]])
def test_entero_rechaza_lo_que_no_es_entero(valor):
    with pytest.raises(ValueError, match="número entero"):
        entero(valor, "año")


@pytest.mark.parametrize("valor", [0, 6])
def test_entero_respeta_el_rango(valor):
    with pytest.raises(ValueError, match="entre 1 y 5"):
        entero(valor, "estrellas", 1, 5)


def test_fecha_iso_normaliza():
    assert fecha_iso("20261105") == "2026-11-05"
    assert fecha_iso(date(2026, 11, 5)) == "2026-11-05"
    assert fecha_iso("2026-11-05") == "2026-11-05"


@pytest.mark.parametrize("valor", ["5/1/2026", "2026-1-5", "", "mañana"])
def test_fecha_iso_rechaza_formatos_invalidos(valor):
    with pytest.raises(ValueError, match="formato ISO"):
        fecha_iso(valor)
