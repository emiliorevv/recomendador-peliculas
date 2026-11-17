"""Pruebas de las consultas de grafo.

Las de integración cargan el seed real (`data/*.json` con `seed.seed.cargar`) en
la base de pruebas de `conftest.py`: nunca contra AuraDB. Los valores esperados
salen de `docs/demo-resultados.md`.
"""

from __future__ import annotations

import pytest
from seed import seed
from src import consultas, usuarios


@pytest.fixture
def grafo_del_seed(base_de_pruebas):
    """Carga las 35 películas y los 12 usuarios del seed en el grafo de pruebas."""
    peliculas, gente = seed.leer_datos()
    seed.cargar(peliculas, gente)
    return base_de_pruebas


@pytest.fixture
def con_persona_aislada(grafo_del_seed):
    """Agrega una persona sin relaciones, para probar un camino que no existe."""
    with grafo_del_seed.session() as sesion:
        sesion.run("CREATE (:Persona {nombre: 'Persona Aislada'})").consume()
    return grafo_del_seed


def test_catalogo_devuelve_las_seis_consultas_con_su_cypher():
    """La app del PR 7 muestra un nombre legible y el Cypher de cada consulta."""
    catalogo = consultas.catalogo()

    assert len(catalogo) == 6
    assert list(catalogo) == [
        "Recomendación colaborativa",
        "Películas parecidas",
        "Top por género",
        "Camino más corto entre personas",
        "Vecindad de una persona",
        "A quién seguir",
    ]
    for nombre, cypher in catalogo.items():
        assert nombre and isinstance(cypher, str) and "MATCH" in cypher


@pytest.mark.integration
def test_recomendar_u01_trae_oppenheimer_primero(grafo_del_seed):
    """Los usuarios parecidos de u01 son tres y Oppenheimer queda arriba."""
    recomendaciones = consultas.recomendar("u01")

    assert recomendaciones[0] == {
        "pelicula": "Oppenheimer",
        "usuarios_parecidos": 3,
        "promedio": 4.33,
    }
    assert len(recomendaciones) == 10

    # Ninguna película ya calificada por u01, aunque tenga pocas estrellas.
    vistas = {fila["titulo"] for fila in usuarios.calificaciones_de("u01")}
    assert vistas & {fila["pelicula"] for fila in recomendaciones} == set()

    parecidos = [fila["usuarios_parecidos"] for fila in recomendaciones]
    assert parecidos == sorted(parecidos, reverse=True)


@pytest.mark.integration
def test_recomendar_respeta_el_limite(grafo_del_seed):
    """El límite se pasa como parámetro y corta la lista."""
    assert len(consultas.recomendar("u01", limite=3)) == 3


@pytest.mark.integration
def test_recomendar_usuario_sin_gustos_devuelve_lista_vacia(grafo_del_seed):
    """Un usuario válido sin calificaciones no es un error: no hay recomendaciones."""
    usuarios.crear_usuario("Nueva", "u99")

    assert consultas.recomendar("u99") == []


@pytest.mark.integration
def test_recomendar_usuario_inexistente_falla(grafo_del_seed):
    """Un usuario que no está lanza `ValueError` con su id."""
    with pytest.raises(ValueError, match="No existe el usuario 'u99'"):
        consultas.recomendar("u99")


@pytest.mark.integration
def test_peliculas_parecidas_de_inception_trae_the_dark_knight_rises_primero(grafo_del_seed):
    """El puntaje suma actores, el doble por director y los géneros en común."""
    parecidas = consultas.peliculas_parecidas("inception-2010")

    assert parecidas[0] == {
        "pelicula_id": "the-dark-knight-rises-2012",
        "titulo": "The Dark Knight Rises",
        "puntos": 6,
        "actores_comunes": 2,
        "mismo_director": 1,
        "generos_comunes": 2,
    }
    assert parecidas[0]["puntos"] == (
        parecidas[0]["actores_comunes"]
        + 2 * parecidas[0]["mismo_director"]
        + parecidas[0]["generos_comunes"]
    )
    puntajes = [fila["puntos"] for fila in parecidas]
    assert puntajes == sorted(puntajes, reverse=True)
    assert all(puntos > 0 for puntos in puntajes)


@pytest.mark.integration
def test_peliculas_parecidas_de_una_pelicula_inexistente_falla(grafo_del_seed):
    """Una película que no está lanza `ValueError` con su id."""
    with pytest.raises(ValueError, match="No existe la película 'no-existe-2020'"):
        consultas.peliculas_parecidas("no-existe-2020")


@pytest.mark.integration
def test_top_por_genero_drama_empieza_con_pulp_fiction(grafo_del_seed):
    """Ordena por promedio y desempata por votos; el promedio va a dos decimales."""
    top = consultas.top_por_genero("Drama", limite=3)

    assert top[0] == {"titulo": "Pulp Fiction", "promedio": 4.67, "votos": 3}
    assert [fila["titulo"] for fila in top] == [
        "Pulp Fiction",
        "The Green Mile",
        "Titanic",
    ]
    assert all(fila["promedio"] == 4.67 and fila["votos"] == 3 for fila in top)


@pytest.mark.integration
def test_top_por_genero_inexistente_devuelve_lista_vacia(grafo_del_seed):
    """Un género sin películas no es un error: no hay nada que ordenar."""
    assert consultas.top_por_genero("Musical") == []


@pytest.mark.integration
def test_camino_entre_tom_hanks_y_scarlett_johansson(grafo_del_seed):
    """Cuatro saltos por The Green Mile y Jojo Rabbit."""
    camino = consultas.camino_entre_personas("Tom Hanks", "Scarlett Johansson")

    assert camino["encontrado"] is True
    assert camino["saltos"] == 4
    assert camino["camino"] == [
        "Tom Hanks",
        "The Green Mile",
        "Sam Rockwell",
        "Jojo Rabbit",
        "Scarlett Johansson",
    ]


@pytest.mark.integration
def test_camino_sin_ruta_no_lanza_excepcion(con_persona_aislada):
    """Sin camino devuelve `encontrado: False` y una lista vacía."""
    assert consultas.camino_entre_personas("Tom Hanks", "Persona Aislada") == {
        "encontrado": False,
        "saltos": 0,
        "camino": [],
    }


@pytest.mark.integration
def test_camino_con_persona_inexistente_falla(grafo_del_seed):
    """Si una de las dos personas no está, es un `ValueError`."""
    with pytest.raises(ValueError, match="No existe la persona 'Nadie Conocido'"):
        consultas.camino_entre_personas("Tom Hanks", "Nadie Conocido")


@pytest.mark.integration
def test_vecindad_de_tom_hanks_a_un_grado_no_esta_vacia(grafo_del_seed):
    """A un grado están los compañeros de reparto y los directores de sus películas."""
    vecinos = consultas.vecindad("Tom Hanks", grados=1)

    assert vecinos
    assert all(fila["distancia"] == 1 for fila in vecinos)
    assert "Sam Rockwell" in {fila["persona"] for fila in vecinos}


@pytest.mark.integration
def test_vecindad_crece_con_los_grados(grafo_del_seed):
    """Dos grados incluyen a los vecinos de los vecinos, con distancia 2."""
    un_grado = consultas.vecindad("Tom Hanks", grados=1, limite=100)
    dos_grados = consultas.vecindad("Tom Hanks", grados=2, limite=100)

    assert len(dos_grados) > len(un_grado)
    assert {fila["distancia"] for fila in dos_grados} == {1, 2}
    assert "Scarlett Johansson" in {fila["persona"] for fila in dos_grados}


@pytest.mark.integration
def test_vecindad_con_persona_inexistente_falla(grafo_del_seed):
    """Una persona que no está lanza `ValueError`."""
    with pytest.raises(ValueError, match="No existe la persona 'Nadie Conocido'"):
        consultas.vecindad("Nadie Conocido")


@pytest.mark.parametrize("grados", [0, 4, -1, 1.5, "dos"])
def test_grados_fuera_de_rango_fallan(grados):
    """Los grados son un entero de 1 a 3 y se validan antes de tocar la base."""
    with pytest.raises(ValueError, match="grados"):
        consultas.vecindad("Tom Hanks", grados=grados)


@pytest.mark.integration
def test_a_quien_seguir_no_repite_a_quien_ya_sigue(grafo_del_seed):
    """Sugiere amigos de amigos, ordenados por amigos en común, sin repetir ni a mí."""
    sugerencias = consultas.a_quien_seguir("u01")
    ya_sigo = {fila["id"] for fila in usuarios.a_quien_sigue("u01")}

    assert sugerencias
    assert {fila["usuario_id"] for fila in sugerencias} & ya_sigo == set()
    assert "u01" not in {fila["usuario_id"] for fila in sugerencias}
    assert sugerencias[0]["amigos_en_comun"] == 2
    amigos = [fila["amigos_en_comun"] for fila in sugerencias]
    assert amigos == sorted(amigos, reverse=True)


@pytest.mark.integration
def test_a_quien_seguir_con_usuario_inexistente_falla(grafo_del_seed):
    """Un usuario que no está lanza `ValueError`."""
    with pytest.raises(ValueError, match="No existe el usuario 'u99'"):
        consultas.a_quien_seguir("u99")
