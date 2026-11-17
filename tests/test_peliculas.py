"""Pruebas del CRUD de películas.

Las de integración usan la fixture `base_de_pruebas` de `conftest.py`, que
apunta el driver a `NEO4J_TEST_URI` (nunca a AuraDB) y deja el grafo limpio.
Las validaciones corren antes de tocar la base, así que se prueban sin ella.
"""

from __future__ import annotations

import pytest
from neo4j.exceptions import ClientError
from src import peliculas

PELICULA = {
    "titulo": "El origen",
    "anio": 2010,
    "duracion": 148,
    "generos": ["Ciencia ficción", "Acción"],
    "director": "Christopher Nolan",
    "actores": ["Leonardo DiCaprio", "Elliot Page"],
}


def crear(**cambios):
    """Crea la película de prueba con los campos que se quieran cambiar."""
    return peliculas.crear_pelicula(**{**PELICULA, **cambios})


def test_slug_quita_acentos_y_une_con_guiones():
    """El id es título y año en minúsculas, sin acentos ni signos."""
    assert peliculas.slug("Batman Begins", 2005) == "batman-begins-2005"
    assert peliculas.slug("Amélie", 2001) == "amelie-2001"
    assert peliculas.slug("  ¡Wall-E!  ", 2008) == "wall-e-2008"
    assert peliculas.slug("Spider-Man: No Way Home", 2021) == "spider-man-no-way-home-2021"


def test_slug_de_un_titulo_sin_letras_falla():
    """Un título que solo tiene signos no puede ser id de nada."""
    with pytest.raises(ValueError, match="no deja un id usable"):
        peliculas.slug("¡¿!?", 2020)


@pytest.mark.parametrize(
    ("cambios", "mensaje"),
    [
        ({"titulo": "   "}, "título no puede estar vacío"),
        ({"anio": 1887}, "año debe estar entre 1888 y 2027"),
        ({"anio": 2028}, "año debe estar entre 1888 y 2027"),
        ({"duracion": 0}, "duración debe estar entre 1 y 600"),
        ({"duracion": 601}, "duración debe estar entre 1 y 600"),
        ({"duracion": 90.5}, "duración debe ser un número entero"),
        ({"generos": []}, "al menos un género"),
        ({"generos": "Drama"}, "lista de textos"),
        ({"anio": "mil"}, "año debe ser un número entero"),
    ],
)
def test_validaciones_de_crear(cambios, mensaje):
    """Los datos fuera de rango fallan con `ValueError` antes de tocar la base."""
    with pytest.raises(ValueError, match=mensaje):
        crear(**cambios)


def test_actualizar_valida_antes_de_buscar():
    """Los mismos rangos se validan al actualizar, sin importar si la película existe."""
    with pytest.raises(ValueError, match="año debe estar entre"):
        peliculas.actualizar_pelicula("no-existe-2010", anio=1800)
    with pytest.raises(ValueError, match="al menos un género"):
        peliculas.actualizar_pelicula("no-existe-2010", generos=[])


@pytest.mark.integration
def test_crear_pelicula_con_generos_director_y_actores(base_de_pruebas):
    """Alta completa: propiedades, id derivado del título y relaciones conectadas."""
    creada = crear()

    assert creada == {
        "id": "el-origen-2010",
        "titulo": "El origen",
        "anio": 2010,
        "duracion": 148,
        "generos": ["Acción", "Ciencia ficción"],
        "director": "Christopher Nolan",
        "actores": ["Elliot Page", "Leonardo DiCaprio"],
    }
    with base_de_pruebas.session() as sesion:
        relaciones = sesion.run(
            """
            MATCH (p:Pelicula {id: $id})-[r]-()
            RETURN type(r) AS tipo, count(*) AS total
            """,
            id=creada["id"],
        ).data()
    assert {fila["tipo"]: fila["total"] for fila in relaciones} == {
        "DE_GENERO": 2,
        "DIRIGIO": 1,
        "ACTUO_EN": 2,
    }


@pytest.mark.integration
def test_crear_sin_director_ni_actores_deja_solo_generos(base_de_pruebas):
    """El director y el reparto son opcionales; los géneros no."""
    creada = peliculas.crear_pelicula(
        titulo="Sin Reparto", anio=1999, duracion=90, generos=["Drama"]
    )

    assert creada["director"] is None
    assert creada["actores"] == []
    assert creada["generos"] == ["Drama"]


@pytest.mark.integration
def test_crear_con_id_existente_falla(base_de_pruebas):
    """El id es la llave: la segunda alta del mismo título y año no se permite."""
    crear()

    with pytest.raises(ValueError, match="Ya existe una película con el id 'el-origen-2010'"):
        crear(duracion=100)


@pytest.mark.integration
def test_listar_y_obtener(base_de_pruebas):
    """Listar no trae reparto y ordena por título; obtener sí y con `None` si falta."""
    crear()
    peliculas.crear_pelicula(
        titulo="Amélie", anio=2001, duracion=122, generos=["Romance", "Comedia"]
    )

    listado = peliculas.listar_peliculas()

    assert [fila["titulo"] for fila in listado] == ["Amélie", "El origen"]
    assert set(listado[0]) == {"id", "titulo", "anio", "duracion", "generos", "director"}
    assert listado[0]["generos"] == ["Comedia", "Romance"]
    assert listado[0]["director"] is None

    detalle = peliculas.obtener_pelicula("el-origen-2010")
    assert detalle is not None
    assert detalle["director"] == "Christopher Nolan"
    assert detalle["actores"] == ["Elliot Page", "Leonardo DiCaprio"]
    assert peliculas.obtener_pelicula("no-existe-2020") is None


@pytest.mark.integration
def test_actualizar_campos_y_reemplazar_relaciones(base_de_pruebas):
    """Actualizar cambia las propiedades y las listas nuevas reemplazan, no suman."""
    crear(generos=["Drama"], actores=["Leonardo DiCaprio"])

    actualizada = peliculas.actualizar_pelicula(
        "el-origen-2010",
        titulo="El origen (doblada)",
        anio=2011,
        duracion=150,
        generos=["Terror", "Suspenso"],
        director="Denis Villeneuve",
        actores=["Elliot Page"],
    )

    assert actualizada["titulo"] == "El origen (doblada)"
    assert actualizada["anio"] == 2011
    assert actualizada["duracion"] == 150
    assert actualizada["generos"] == ["Suspenso", "Terror"]
    assert actualizada["director"] == "Denis Villeneuve"
    assert actualizada["actores"] == ["Elliot Page"]
    # El id no se recalcula: es la llave que ya referencian las calificaciones.
    assert actualizada["id"] == "el-origen-2010"

    with base_de_pruebas.session() as sesion:
        relaciones = sesion.run(
            """
            MATCH (p:Pelicula {id: $id})<-[r]-(:Persona)
            RETURN type(r) AS tipo, count(*) AS total
            """,
            id="el-origen-2010",
        ).data()
        generos = sesion.run(
            """
            MATCH (p:Pelicula {id: $id})-[:DE_GENERO]->(g:Genero)
            RETURN collect(g.nombre) AS generos
            """,
            id="el-origen-2010",
        ).single()["generos"]
    assert {fila["tipo"]: fila["total"] for fila in relaciones} == {
        "DIRIGIO": 1,
        "ACTUO_EN": 1,
    }
    assert sorted(generos) == ["Suspenso", "Terror"]
    # Los nodos que quedaron sin relación no se borran: son compartidos.
    assert peliculas.obtener_pelicula("el-origen-2010")["director"] == "Denis Villeneuve"


@pytest.mark.integration
def test_actualizar_sin_argumentos_no_cambia_nada(base_de_pruebas):
    """Todo es opcional: llamar sin campos devuelve la misma película."""
    creada = crear()

    assert peliculas.actualizar_pelicula("el-origen-2010") == creada


@pytest.mark.integration
def test_actualizar_con_actores_vacios_quita_el_reparto(base_de_pruebas):
    """`actores=[]` deja la película sin reparto, pero conserva el director."""
    crear()

    actualizada = peliculas.actualizar_pelicula("el-origen-2010", actores=[])

    assert actualizada["actores"] == []
    assert actualizada["director"] == "Christopher Nolan"


@pytest.mark.integration
def test_actualizar_pelicula_inexistente_falla(base_de_pruebas):
    """Actualizar algo que no está es un error, no un alta silenciosa."""
    with pytest.raises(ValueError, match="No existe la película 'no-existe-2020'"):
        peliculas.actualizar_pelicula("no-existe-2020", duracion=100)


@pytest.mark.integration
def test_actualizar_con_director_vacio_quita_la_relacion(base_de_pruebas):
    """`director=""` (o solo espacios) borra `DIRIGIO`; el nodo `:Persona` queda."""
    crear()

    assert peliculas.actualizar_pelicula("el-origen-2010", director="")["director"] is None

    detalle = peliculas.obtener_pelicula("el-origen-2010")
    assert detalle["actores"] == ["Elliot Page", "Leonardo DiCaprio"]
    with base_de_pruebas.session() as sesion:
        fila = sesion.run(
            """
            MATCH (p:Pelicula {id: 'el-origen-2010'})<-[r:DIRIGIO]-(:Persona)
            RETURN count(r) AS directores
            """
        ).single()
        persona = sesion.run(
            "MATCH (p:Persona {nombre: 'Christopher Nolan'}) RETURN count(p) AS total"
        ).single()
    assert fila["directores"] == 0
    # El director anterior no se borra como nodo: es compartido con otras películas.
    assert persona["total"] == 1


@pytest.mark.integration
def test_crear_es_atomico_si_falla_una_escritura(base_de_pruebas, monkeypatch):
    """Si revienta el reparto (la última escritura), no queda película ni géneros."""
    monkeypatch.setattr(
        peliculas,
        "MERGE_ACTORES",
        "MATCH (p:Pelicula {id: $id}) RETURN $parametro_inexistente",
    )

    with pytest.raises(ClientError):
        crear()

    assert peliculas.obtener_pelicula("el-origen-2010") is None
    with base_de_pruebas.session() as sesion:
        fila = sesion.run(
            """
            RETURN COUNT { (p:Pelicula) } AS peliculas,
                   COUNT { (g:Genero) } AS generos,
                   COUNT { (a:Persona) } AS personas
            """
        ).single()
    # Nada de la alta sobrevivió: ni el nodo, ni los géneros que se habían creado.
    assert dict(fila) == {"peliculas": 0, "generos": 0, "personas": 0}


@pytest.mark.integration
def test_actualizar_es_atomico_si_falla_una_escritura(base_de_pruebas, monkeypatch):
    """Si falla el reemplazo del reparto, la película conserva todo lo anterior."""
    original = crear(generos=["Drama"], actores=["Leonardo DiCaprio"])
    monkeypatch.setattr(
        peliculas,
        "MERGE_ACTORES",
        "MATCH (p:Pelicula {id: $id}) RETURN $parametro_inexistente",
    )

    with pytest.raises(ClientError):
        peliculas.actualizar_pelicula(
            "el-origen-2010",
            titulo="Otro título",
            generos=["Terror"],
            director="David Fincher",
            actores=["Elliot Page"],
        )

    assert peliculas.obtener_pelicula("el-origen-2010") == original


@pytest.mark.integration
def test_eliminar_pelicula_y_sus_relaciones(base_de_pruebas):
    """`DETACH DELETE` se lleva la película y sus `DE_GENERO`, `DIRIGIO` y `ACTUO_EN`."""
    crear()

    assert peliculas.eliminar_pelicula("el-origen-2010") is True

    assert peliculas.obtener_pelicula("el-origen-2010") is None
    assert peliculas.listar_peliculas() == []
    with base_de_pruebas.session() as sesion:
        fila = sesion.run(
            """
            MATCH ()-[r]->()
            RETURN count(r) AS relaciones
            """
        ).single()
        pelicula = sesion.run("MATCH (p:Pelicula) RETURN count(p) AS total").single()
    assert fila["relaciones"] == 0
    assert pelicula["total"] == 0


@pytest.mark.integration
def test_eliminar_pelicula_inexistente_falla(base_de_pruebas):
    """Borrar dos veces la misma película es un error con mensaje claro."""
    crear()
    assert peliculas.eliminar_pelicula("el-origen-2010") is True

    with pytest.raises(ValueError, match="No existe la película 'el-origen-2010'"):
        peliculas.eliminar_pelicula("el-origen-2010")
