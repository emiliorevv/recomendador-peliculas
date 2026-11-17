"""Interfaz Streamlit de la demo del recomendador de películas.

Cuatro secciones sobre las funciones reales de `src/`:

- **Películas**: tabla con búsqueda, detalle, alta, edición y borrado.
- **Usuarios**: CRUD, calificaciones y seguidores.
- **Recomendaciones**: colaborativa, parecidas y top por género.
- **Caminos**: camino más corto, vecindad y a quién seguir.

Cada consulta del catálogo muestra el Cypher que corrió (tomado de
`src.consultas.catalogo`) y su tiempo de respuesta en milisegundos. No hay
caché de datos: cada interacción vuelve a leer el grafo, así que lo que se
escribe se ve de inmediato.

    streamlit run app.py
"""

from __future__ import annotations

import time
import unicodedata
from collections.abc import Callable
from typing import Any

import streamlit as st
from src.conexion import leer, verificar_conexion
from src.consultas import (
    VECINDAD_POR_GRADOS,
    a_quien_seguir,
    camino_entre_personas,
    catalogo,
    peliculas_parecidas,
    recomendar,
    top_por_genero,
    vecindad,
)
from src.peliculas import (
    actualizar_pelicula,
    crear_pelicula,
    eliminar_pelicula,
    listar_peliculas,
    obtener_pelicula,
)
from src.usuarios import (
    a_quien_sigue,
    calificaciones_de,
    calificar,
    crear_usuario,
    dejar_de_seguir,
    eliminar_usuario,
    listar_usuarios,
    quitar_calificacion,
    renombrar_usuario,
    seguidores_de,
    seguir,
)

SECCIONES = ("Películas", "Usuarios", "Recomendaciones", "Caminos")
OPERACIONES_PELICULAS = ("Ver detalle", "Agregar", "Editar", "Eliminar")
OPERACIONES_USUARIOS = ("Ver y crear", "Renombrar y borrar", "Calificaciones", "Seguir")
CONSULTAS_RECOMENDACION = (
    "Recomendación colaborativa",
    "Películas parecidas",
    "Top por género",
)
CONSULTAS_CAMINOS = (
    "Camino más corto entre personas",
    "Vecindad de una persona",
    "A quién seguir",
)

# Valores por defecto de la demo: existen en el grafo del seed, así que la
# primera pantalla de cada consulta ya trae un resultado.
PELICULA_EJEMPLO = "inception-2010"
USUARIO_EJEMPLO = "u01"
PERSONA_EJEMPLO = "Tom Hanks"
PERSONA_DESTINO_EJEMPLO = "Scarlett Johansson"
GENERO_EJEMPLO = "Ciencia ficción"

# Nombres de personas para llenar los selectores de caminos y vecindad. No es
# una de las seis consultas del catálogo: es el índice que alimenta los menús.
CONSULTA_PERSONAS = "MATCH (p:Persona) RETURN p.nombre AS nombre ORDER BY p.nombre"


# --------------------------------------------------------------------------- #
# Utilidades de la interfaz
# --------------------------------------------------------------------------- #


def _milisegundos(funcion: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[Any, float]:
    """Ejecuta `funcion` y devuelve su resultado con el tiempo que tardó, en ms."""
    inicio = time.perf_counter()
    resultado = funcion(*args, **kwargs)
    return resultado, (time.perf_counter() - inicio) * 1000


def _indice(opciones: list[str], preferido: str) -> int:
    """Posición de `preferido` en `opciones`, o 0 si no está."""
    return opciones.index(preferido) if preferido in opciones else 0


def _sin_acentos(valor: str) -> str:
    """Texto en minúsculas y sin tildes, para buscar sin pelearse con los acentos."""
    sin_tildes = unicodedata.normalize("NFKD", valor).encode("ascii", "ignore").decode("ascii")
    return sin_tildes.lower()


def _lista_de_nombres(valor: str) -> list[str]:
    """Separa "A, B, C" en una lista de nombres, sin vacíos."""
    return [nombre.strip() for nombre in valor.split(",") if nombre.strip()]


def leer_datos(funcion: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Corre una lectura del backend y muestra un `st.error` claro si la base falla."""
    try:
        return funcion(*args, **kwargs)
    except Exception as error:  # el driver lanza errores de red y de servidor
        st.error(f"No se pudo leer de la base: {error.__class__.__name__}: {error}")
        st.stop()


def avisar(mensaje: str) -> None:
    """Guarda un aviso para mostrarlo después del `st.rerun()` que refresca la vista."""
    st.session_state["aviso"] = mensaje


def mostrar_aviso() -> None:
    """Muestra el aviso pendiente, si hay, una sola vez."""
    mensaje = st.session_state.pop("aviso", None)
    if mensaje:
        st.success(mensaje)


def refrescar() -> None:
    """Redibuja la app con los datos recién escritos: no hay caché que los esconda."""
    st.session_state.pop("estado_conexion", None)
    st.rerun()


def mostrar_estado() -> None:
    """Línea de estado con el resultado real de `verificar_conexion()`."""
    estado = st.session_state.get("estado_conexion")
    if estado is None:
        try:
            estado = verificar_conexion()
        except Exception as error:  # Aura caída, credenciales malas o sin red
            st.error(
                "No se pudo conectar con Neo4j AuraDB. Revisa NEO4J_URI, NEO4J_USERNAME "
                "y NEO4J_PASSWORD en el archivo .env, y que la instancia esté encendida. "
                f"Detalle: {error.__class__.__name__}: {error}"
            )
            st.stop()
        st.session_state["estado_conexion"] = estado
    st.caption(
        f"Conectado a {estado['servidor']} {estado['version']} · base {estado['base']} · "
        f"{estado['nodos']} nodos en el grafo"
    )


def mostrar_cypher(
    cypher: str, milisegundos: float, parametros: dict[str, Any] | None = None
) -> None:
    """Expander con el Cypher que corrió y el tiempo de respuesta."""
    with st.expander(f"Ver el Cypher ejecutado · {milisegundos:.0f} ms"):
        st.code(cypher, language="cypher")
        st.caption(f"Tiempo de respuesta: {milisegundos:.1f} ms (time.perf_counter)")
        if parametros:
            resumen = ", ".join(f"{clave} = {valor!r}" for clave, valor in parametros.items())
            st.caption(f"Parámetros enviados: {resumen}")


def consulta_de_grafo(
    nombre: str,
    funcion: Callable[..., Any],
    *args: Any,
    parametros: dict[str, Any] | None = None,
    cypher: str | None = None,
    **kwargs: Any,
) -> Any:
    """Corre una consulta del catálogo, muestra su Cypher y sus ms, y devuelve el resultado.

    Devuelve `None` si el backend rechaza los datos; para la vecindad se puede
    pasar el Cypher exacto del grado pedido, porque el catálogo documenta la
    variante de 3 grados.
    """
    try:
        resultado, milisegundos = _milisegundos(funcion, *args, **kwargs)
    except ValueError as error:
        st.error(str(error))
        return None
    mostrar_cypher(cypher or catalogo()[nombre], milisegundos, parametros)
    return resultado


def tabla(filas: list[dict[str, Any]], vacio: str, **opciones: Any) -> None:
    """Dataframe de filas ya rotuladas en español, o un texto si no hay ninguna."""
    if filas:
        st.dataframe(filas, hide_index=True, **opciones)
    else:
        st.caption(vacio)


def listar_personas() -> list[str]:
    """Nombres de todas las personas del grafo, para llenar los selectores."""
    return [fila["nombre"] for fila in leer(CONSULTA_PERSONAS)]


def selector_pelicula(
    etiqueta: str,
    peliculas: list[dict[str, Any]],
    clave: str,
    ayuda: str | None = None,
) -> str:
    """Selectbox de películas: muestra "Título (año)" y devuelve el id."""
    etiquetas = {p["id"]: f"{p['titulo']} ({p['anio']})" for p in peliculas}
    opciones = list(etiquetas)
    return st.selectbox(
        etiqueta,
        opciones,
        index=_indice(opciones, PELICULA_EJEMPLO),
        format_func=lambda pelicula_id: etiquetas[pelicula_id],
        key=clave,
        help=ayuda,
    )


def selector_usuario(
    etiqueta: str,
    usuarios: list[dict[str, Any]],
    clave: str,
    ayuda: str | None = None,
) -> str:
    """Selectbox de usuarios: muestra "Nombre (id)" y devuelve el id."""
    etiquetas = {u["id"]: f"{u['nombre']} ({u['id']})" for u in usuarios}
    opciones = list(etiquetas)
    return st.selectbox(
        etiqueta,
        opciones,
        index=_indice(opciones, USUARIO_EJEMPLO),
        format_func=lambda usuario_id: etiquetas[usuario_id],
        key=clave,
        help=ayuda,
    )


def selector_persona(
    etiqueta: str,
    personas: list[str],
    clave: str,
    preferida: str,
    ayuda: str | None = None,
) -> str:
    """Selectbox con las personas reales del grafo."""
    return st.selectbox(
        etiqueta,
        personas,
        index=_indice(personas, preferida),
        key=clave,
        help=ayuda,
    )


# --------------------------------------------------------------------------- #
# Sección 1: películas
# --------------------------------------------------------------------------- #


def seccion_peliculas() -> None:
    """Tabla con búsqueda, detalle y CRUD de películas."""
    st.header("Películas")
    peliculas = leer_datos(listar_peliculas)
    generos_conocidos = sorted({genero for p in peliculas for genero in p["generos"]})

    if peliculas:
        busqueda = st.text_input(
            "Buscar por título",
            placeholder="origen",
            key="buscar_pelicula",
            help="No importan las mayúsculas ni los acentos.",
        )
        filtro = _sin_acentos(busqueda.strip())
        filtradas = (
            [p for p in peliculas if filtro in _sin_acentos(p["titulo"])] if filtro else peliculas
        )
        tabla(
            [
                {
                    "Título": p["titulo"],
                    "Año": p["anio"],
                    "Duración (min)": p["duracion"],
                    "Géneros": ", ".join(p["generos"]),
                    "Director": p["director"] or "sin director",
                }
                for p in filtradas
            ],
            "Ninguna película coincide con la búsqueda.",
            column_config={
                "Año": st.column_config.NumberColumn(format="%d"),
                "Duración (min)": st.column_config.NumberColumn(format="%d"),
            },
        )
        st.caption(f"{len(filtradas)} de {len(peliculas)} películas")
    else:
        st.info("La base no tiene películas. Empieza agregando una.")

    operacion = st.radio(
        "¿Qué quieres hacer?",
        OPERACIONES_PELICULAS,
        horizontal=True,
        key="operacion_peliculas",
    )

    if operacion == "Agregar":
        st.subheader("Agregar una película")
        with st.form("alta_pelicula", clear_on_submit=True):
            titulo = st.text_input("Título", placeholder="El origen", key="alta_titulo")
            izquierda, derecha = st.columns(2)
            anio = izquierda.number_input(
                "Año",
                min_value=1888,
                max_value=2027,
                value=2024,
                step=1,
                key="alta_anio",
                help="Año de estreno. Junto con el título forma el id de la película.",
            )
            duracion = derecha.number_input(
                "Duración (minutos)",
                min_value=1,
                max_value=600,
                value=120,
                step=1,
                key="alta_duracion",
            )
            generos = st.multiselect(
                "Géneros",
                generos_conocidos,
                accept_new_options=True,
                key="alta_generos",
                help="Elige uno o varios. Si el género no está en la lista, escríbelo y se crea.",
            )
            director = st.text_input("Director (opcional)", key="alta_director")
            actores = st.text_input(
                "Actores (opcional, separados por coma)",
                placeholder="Leonardo DiCaprio, Joseph Gordon-Levitt",
                key="alta_actores",
            )
            guardar = st.form_submit_button("Agregar película", type="primary")

        if guardar:
            try:
                nueva, milisegundos = _milisegundos(
                    crear_pelicula,
                    titulo=titulo,
                    anio=anio,
                    duracion=duracion,
                    generos=generos,
                    director=director,
                    actores=_lista_de_nombres(actores),
                )
            except ValueError as error:
                st.error(str(error))
            else:
                avisar(f"Se agregó {nueva['titulo']} ({nueva['anio']}) en {milisegundos:.0f} ms")
                refrescar()

    elif not peliculas:
        st.info("No hay películas para esta operación.")

    elif operacion == "Ver detalle":
        pelicula_id = selector_pelicula(
            "Película",
            peliculas,
            "detalle_pelicula",
            "El detalle trae géneros, director y reparto completo.",
        )
        detalle = leer_datos(obtener_pelicula, pelicula_id)
        if detalle is None:
            st.warning("Esa película ya no está en la base.")
            return
        st.subheader(f"{detalle['titulo']} ({detalle['anio']})")
        st.write(f"**Duración:** {detalle['duracion']} minutos")
        st.write(f"**Géneros:** {', '.join(detalle['generos'])}")
        st.write(f"**Director:** {detalle['director'] or 'sin director registrado'}")
        reparto = ", ".join(detalle["actores"]) or "sin reparto registrado"
        st.write(f"**Reparto:** {reparto}")
        st.caption(f"id: {detalle['id']}")

    elif operacion == "Editar":
        pelicula_id = selector_pelicula(
            "Película para editar",
            peliculas,
            "editar_pelicula",
            "Los cambios se guardan sobre el mismo id, que es lo que califican los usuarios.",
        )
        actual = leer_datos(obtener_pelicula, pelicula_id)
        if actual is None:
            st.warning("Esa película ya no está en la base.")
            return

        st.subheader(f"Editar {actual['titulo']} ({actual['anio']})")
        with st.form(f"form_editar_{pelicula_id}"):
            titulo = st.text_input(
                "Título", value=actual["titulo"], key=f"editar_titulo_{pelicula_id}"
            )
            izquierda, derecha = st.columns(2)
            anio = izquierda.number_input(
                "Año",
                min_value=1888,
                max_value=2027,
                value=int(actual["anio"]),
                step=1,
                key=f"editar_anio_{pelicula_id}",
            )
            duracion = derecha.number_input(
                "Duración (minutos)",
                min_value=1,
                max_value=600,
                value=int(actual["duracion"]),
                step=1,
                key=f"editar_duracion_{pelicula_id}",
            )
            generos = st.multiselect(
                "Géneros",
                sorted(set(generos_conocidos) | set(actual["generos"])),
                default=actual["generos"],
                accept_new_options=True,
                key=f"editar_generos_{pelicula_id}",
                help="Reemplaza los géneros actuales. No se puede quedar sin ninguno.",
            )
            director = st.text_input(
                "Director",
                value=actual["director"] or "",
                key=f"editar_director_{pelicula_id}",
                help="Déjalo vacío para quitar al director actual.",
            )
            actores = st.text_input(
                "Actores separados por coma",
                value=", ".join(actual["actores"]),
                key=f"editar_actores_{pelicula_id}",
                help="Reemplaza el reparto actual. Vacío deja la película sin actores.",
            )
            guardar = st.form_submit_button("Guardar cambios", type="primary")

        if guardar:
            try:
                cambiada, milisegundos = _milisegundos(
                    actualizar_pelicula,
                    pelicula_id,
                    titulo=titulo,
                    anio=anio,
                    duracion=duracion,
                    generos=generos,
                    director=director,
                    actores=_lista_de_nombres(actores),
                )
            except ValueError as error:
                st.error(str(error))
            else:
                avisar(
                    f"Se actualizó {cambiada['titulo']} ({cambiada['anio']}) "
                    f"en {milisegundos:.0f} ms"
                )
                refrescar()

    elif operacion == "Eliminar":
        pelicula_id = selector_pelicula(
            "Película para eliminar",
            peliculas,
            "eliminar_pelicula",
            "El borrado arrastra sus calificaciones y relaciones (DETACH DELETE).",
        )
        etiqueta = next(f"{p['titulo']} ({p['anio']})" for p in peliculas if p["id"] == pelicula_id)
        confirmacion = st.text_input(
            "Para confirmar, escribe el id de la película",
            key=f"confirmar_borrar_{pelicula_id}",
            help=f"El id de {etiqueta} es {pelicula_id}.",
        )
        if st.button(
            "Eliminar película",
            disabled=confirmacion.strip() != pelicula_id,
            help="El botón se habilita cuando el id escrito coincide.",
        ):
            try:
                eliminar_pelicula(pelicula_id)
            except ValueError as error:
                st.error(str(error))
            else:
                avisar(f"Se eliminó {etiqueta}")
                refrescar()


# --------------------------------------------------------------------------- #
# Sección 2: usuarios
# --------------------------------------------------------------------------- #


def seccion_usuarios() -> None:
    """Listado y CRUD de usuarios, calificaciones y seguidores."""
    st.header("Usuarios")
    usuarios = leer_datos(listar_usuarios)

    operacion = st.radio(
        "¿Qué quieres hacer?",
        OPERACIONES_USUARIOS,
        horizontal=True,
        key="operacion_usuarios",
    )

    if operacion == "Ver y crear":
        tabla(
            [{"Id": u["id"], "Nombre": u["nombre"]} for u in usuarios],
            "Todavía no hay usuarios en la base.",
        )
        st.subheader("Crear un usuario")
        with st.form("alta_usuario", clear_on_submit=True):
            nombre = st.text_input("Nombre", placeholder="Emilia", key="alta_usuario_nombre")
            crear = st.form_submit_button("Crear usuario", type="primary")
            st.caption("El id lo asigna la base: el siguiente libre (u13, u14, …).")
        if crear:
            try:
                usuario = crear_usuario(nombre)
            except ValueError as error:
                st.error(str(error))
            else:
                avisar(f"Se creó {usuario['nombre']} con el id {usuario['id']}")
                refrescar()
        return

    if not usuarios:
        st.info("Primero crea un usuario en «Ver y crear».")
        return

    if operacion == "Renombrar y borrar":
        st.subheader("Renombrar")
        usuario_id = selector_usuario("Usuario", usuarios, "renombrar_usuario")
        actual = next(u for u in usuarios if u["id"] == usuario_id)
        with st.form(f"form_renombrar_{usuario_id}"):
            nombre = st.text_input(
                "Nombre nuevo",
                value=actual["nombre"],
                key=f"renombrar_nombre_{usuario_id}",
            )
            guardar = st.form_submit_button("Guardar el nombre", type="primary")
        if guardar:
            try:
                cambiado = renombrar_usuario(usuario_id, nombre)
            except ValueError as error:
                st.error(str(error))
            else:
                avisar(f"{actual['nombre']} ahora se llama {cambiado['nombre']}")
                refrescar()

        st.divider()
        st.subheader("Borrar")
        borrar_id = selector_usuario(
            "Usuario para eliminar",
            usuarios,
            "borrar_usuario",
            "Se borran también sus calificaciones y sus relaciones de seguimiento.",
        )
        borrar = next(u for u in usuarios if u["id"] == borrar_id)
        confirmacion = st.text_input(
            "Para confirmar, escribe el nombre del usuario",
            key=f"confirmar_borrar_usuario_{borrar_id}",
            help=f"El usuario {borrar['id']} se llama {borrar['nombre']}.",
        )
        if st.button(
            "Eliminar usuario",
            disabled=confirmacion.strip() != borrar["nombre"],
            help="El botón se habilita cuando el nombre escrito coincide.",
        ):
            try:
                eliminar_usuario(borrar_id)
            except ValueError as error:
                st.error(str(error))
            else:
                avisar(f"Se eliminó {borrar['nombre']} ({borrar['id']})")
                refrescar()

    elif operacion == "Calificaciones":
        peliculas = leer_datos(listar_peliculas)
        if not peliculas:
            st.info("La base no tiene películas para calificar.")
            return

        usuario_id = selector_usuario("Usuario", usuarios, "calificar_usuario")
        st.subheader("Calificar una película")
        pelicula_id = selector_pelicula("Película", peliculas, "calificar_pelicula")
        estrellas = st.slider(
            "Estrellas",
            min_value=1,
            max_value=5,
            value=4,
            key="calificar_estrellas",
            help="1 es la peor nota y 5 la mejor. Calificar de nuevo actualiza la relación.",
        )
        if st.button("Calificar o actualizar", type="primary"):
            try:
                fila, milisegundos = _milisegundos(calificar, usuario_id, pelicula_id, estrellas)
            except ValueError as error:
                st.error(str(error))
            else:
                avisar(
                    f"{fila['titulo']} quedó con {fila['estrellas']} estrellas "
                    f"({milisegundos:.0f} ms)"
                )
                refrescar()

        st.divider()
        calificaciones = leer_datos(calificaciones_de, usuario_id)
        st.subheader("Calificaciones del usuario")
        tabla(
            [
                {
                    "Película": c["titulo"],
                    "Estrellas": c["estrellas"],
                    "Fecha": c["fecha"],
                }
                for c in calificaciones
            ],
            "Ese usuario todavía no calificó nada.",
            column_config={"Estrellas": st.column_config.NumberColumn(format="%d")},
        )
        if calificaciones:
            quitar = st.selectbox(
                "Calificación para quitar",
                [c["pelicula_id"] for c in calificaciones],
                format_func=lambda pid: next(
                    f"{c['titulo']} ({c['estrellas']} ★)"
                    for c in calificaciones
                    if c["pelicula_id"] == pid
                ),
                key="quitar_calificacion",
                help="Solo se borra la relación CALIFICO de ese usuario con esa película.",
            )
            if st.button("Quitar la calificación"):
                if quitar_calificacion(usuario_id, quitar):
                    avisar("Se quitó la calificación")
                    refrescar()
                else:
                    st.warning("Esa calificación ya no estaba en la base.")

    elif operacion == "Seguir":
        usuario_id = selector_usuario("Usuario", usuarios, "seguir_usuario")
        otros = [u for u in usuarios if u["id"] != usuario_id]

        st.subheader("Seguir a alguien")
        if otros:
            etiquetas = {u["id"]: f"{u['nombre']} ({u['id']})" for u in otros}
            seguido_id = st.selectbox(
                "Usuario a seguir",
                list(etiquetas),
                format_func=lambda otro_id: etiquetas[otro_id],
                key=f"seguir_a_{usuario_id}",
            )
            if st.button("Seguir", type="primary"):
                try:
                    seguir(usuario_id, seguido_id)
                except ValueError as error:
                    st.error(str(error))
                else:
                    avisar(f"{etiquetas[seguido_id]} quedó seguido")
                    refrescar()
        else:
            st.caption("No hay otro usuario al que seguir.")

        sigue, _ = _milisegundos(a_quien_sigue, usuario_id)
        seguidores, _ = _milisegundos(seguidores_de, usuario_id)
        izquierda, derecha = st.columns(2)
        with izquierda:
            st.write("**A quién sigue**")
            tabla(
                [{"Id": s["id"], "Nombre": s["nombre"]} for s in sigue],
                "No sigue a nadie todavía.",
            )
        with derecha:
            st.write("**Quién lo sigue**")
            tabla(
                [{"Id": s["id"], "Nombre": s["nombre"]} for s in seguidores],
                "Nadie lo sigue todavía.",
            )

        if sigue:
            etiquetas_sigue = {s["id"]: f"{s['nombre']} ({s['id']})" for s in sigue}
            dejar_id = st.selectbox(
                "Dejar de seguir a",
                list(etiquetas_sigue),
                format_func=lambda otro_id: etiquetas_sigue[otro_id],
                key=f"dejar_de_seguir_{usuario_id}",
            )
            if st.button("Dejar de seguir"):
                if dejar_de_seguir(usuario_id, dejar_id):
                    avisar(f"Dejó de seguir a {etiquetas_sigue[dejar_id]}")
                    refrescar()
                else:
                    st.warning("Ese seguimiento ya no estaba en la base.")


# --------------------------------------------------------------------------- #
# Sección 3: recomendaciones
# --------------------------------------------------------------------------- #


def seccion_recomendaciones() -> None:
    """Las tres consultas de recomendación, una a la vez."""
    st.header("Recomendaciones")
    usuarios = leer_datos(listar_usuarios)
    peliculas = leer_datos(listar_peliculas)
    generos = sorted({genero for p in peliculas for genero in p["generos"]})

    if not usuarios or not peliculas:
        st.info("La base necesita usuarios y películas para recomendar.")
        return

    consulta = st.radio(
        "¿Qué consulta quieres ver?",
        CONSULTAS_RECOMENDACION,
        horizontal=True,
        key="consulta_recomendacion",
    )
    limite = st.slider(
        "Máximo de resultados",
        min_value=1,
        max_value=20,
        value=5,
        key="limite_recomendaciones",
        help="Es el LIMIT del Cypher, no un recorte en Python.",
    )

    if consulta == "Recomendación colaborativa":
        st.subheader("Lo que le gustó a usuarios con gustos parecidos")
        usuario_id = selector_usuario(
            "Usuario",
            usuarios,
            "recomendar_usuario",
            "Solo entran películas que el usuario no haya calificado.",
        )
        filas = consulta_de_grafo(
            consulta,
            recomendar,
            usuario_id,
            limite=limite,
            parametros={"id": usuario_id, "limite": limite},
        )
        if filas is None:
            return
        tabla(
            [
                {
                    "Película": fila["pelicula"],
                    "Usuarios parecidos": fila["usuarios_parecidos"],
                    "Promedio": fila["promedio"],
                }
                for fila in filas
            ],
            "Sin recomendaciones: nadie con gustos parecidos calificó algo nuevo.",
            column_config={"Promedio": st.column_config.NumberColumn(format="%.2f")},
        )

    elif consulta == "Películas parecidas":
        st.subheader("Películas parecidas por reparto, director y género")
        pelicula_id = selector_pelicula(
            "Película base",
            peliculas,
            "parecidas_pelicula",
            "El puntaje pesa el doble compartir director.",
        )
        filas = consulta_de_grafo(
            consulta,
            peliculas_parecidas,
            pelicula_id,
            limite=limite,
            parametros={"id": pelicula_id, "limite": limite},
        )
        if filas is None:
            return
        st.caption("Puntos = actores en común + 2 × mismo director + géneros en común")
        tabla(
            [
                {
                    "Película": fila["titulo"],
                    "Puntos": fila["puntos"],
                    "Actores en común": fila["actores_comunes"],
                    "Mismo director": "Sí" if fila["mismo_director"] else "No",
                    "Géneros en común": fila["generos_comunes"],
                }
                for fila in filas
            ],
            "No hay películas con reparto, director o género en común.",
        )

    elif consulta == "Top por género":
        st.subheader("Mejores películas de un género")
        genero = st.selectbox(
            "Género",
            generos,
            index=_indice(generos, GENERO_EJEMPLO),
            key="top_genero",
            help="Solo aparecen películas calificadas al menos una vez.",
        )
        filas = consulta_de_grafo(
            consulta,
            top_por_genero,
            genero,
            limite=limite,
            parametros={"genero": genero, "limite": limite},
        )
        if filas is None:
            return
        tabla(
            [
                {
                    "Película": fila["titulo"],
                    "Promedio": fila["promedio"],
                    "Votos": fila["votos"],
                }
                for fila in filas
            ],
            "Ese género todavía no tiene películas calificadas.",
            column_config={"Promedio": st.column_config.NumberColumn(format="%.2f")},
        )


# --------------------------------------------------------------------------- #
# Sección 4: caminos
# --------------------------------------------------------------------------- #


def seccion_caminos() -> None:
    """Camino más corto, vecindad y a quién seguir."""
    st.header("Caminos")
    personas = leer_datos(listar_personas)
    usuarios = leer_datos(listar_usuarios)

    if not personas:
        st.info("La base no tiene personas: carga el seed antes de la demo.")
        return

    consulta = st.radio(
        "¿Qué consulta quieres ver?",
        CONSULTAS_CAMINOS,
        horizontal=True,
        key="consulta_caminos",
    )

    if consulta == "Camino más corto entre personas":
        st.subheader("Seis grados de separación")
        origen = selector_persona(
            "Persona de origen",
            personas,
            "camino_origen",
            PERSONA_EJEMPLO,
            "Personas y películas se alternan: cada salto es una relación ACTUO_EN o DIRIGIO.",
        )
        destino = selector_persona(
            "Persona de destino",
            personas,
            "camino_destino",
            PERSONA_DESTINO_EJEMPLO,
        )
        resultado = consulta_de_grafo(
            consulta,
            camino_entre_personas,
            origen,
            destino,
            parametros={"origen": origen, "destino": destino},
        )
        if resultado is None:
            return
        if not resultado["encontrado"]:
            st.warning("No hay camino entre esas dos personas dentro de 12 saltos.")
            return
        st.write(f"**Saltos:** {resultado['saltos']}")
        st.write("**Camino:** " + " → ".join(resultado["camino"]))
        st.caption("Las personas y las películas se alternan a lo largo del camino.")

    elif consulta == "Vecindad de una persona":
        st.subheader("Vecindad por grados de separación")
        persona = selector_persona(
            "Persona",
            personas,
            "vecindad_persona",
            PERSONA_EJEMPLO,
            "Un grado es compartir una película como actor o director.",
        )
        grados = st.radio(
            "Grados de separación",
            (1, 2, 3),
            index=1,
            horizontal=True,
            format_func=lambda valor: "1 grado" if valor == 1 else f"{valor} grados",
            key="grados_vecindad",
            help="A más grados, más gente alcanzable y más trabajo para el recorrido.",
        )
        # El catálogo documenta la variante de 3 grados; para 1 y 2 se muestra
        # el Cypher exacto que corre, con el tope del grado pedido.
        cypher = catalogo()[consulta] if grados == 3 else VECINDAD_POR_GRADOS[grados]
        filas = consulta_de_grafo(
            consulta,
            vecindad,
            persona,
            grados=grados,
            parametros={"nombre": persona, "limite": 25},
            cypher=cypher,
        )
        if filas is None:
            return
        tabla(
            [
                {"Persona": fila["persona"], "Grados de separación": fila["distancia"]}
                for fila in filas
            ],
            "No hay personas a esa distancia.",
            column_config={"Grados de separación": st.column_config.NumberColumn(format="%d")},
        )

    elif consulta == "A quién seguir":
        st.subheader("Amigos de mis amigos")
        if not usuarios:
            st.info("La base no tiene usuarios: crea uno en la sección Usuarios.")
            return
        usuario_id = selector_usuario(
            "Usuario",
            usuarios,
            "a_quien_seguir_usuario",
            "Sugiere a quien siguen las personas que tú sigues, sin repetir a los que ya sigues.",
        )
        filas = consulta_de_grafo(
            consulta,
            a_quien_seguir,
            usuario_id,
            parametros={"id": usuario_id, "limite": 10},
        )
        if filas is None:
            return
        tabla(
            [
                {
                    "Usuario": fila["nombre"],
                    "Id": fila["usuario_id"],
                    "Amigos en común": fila["amigos_en_comun"],
                }
                for fila in filas
            ],
            "No hay sugerencias: ese usuario no sigue a nadie o sus amigos no siguen a nadie más.",
            column_config={"Amigos en común": st.column_config.NumberColumn(format="%d")},
        )


# --------------------------------------------------------------------------- #
# Punto de entrada
# --------------------------------------------------------------------------- #


def main() -> None:
    """Dibuja la app: estado de la conexión, navegación y la sección elegida."""
    st.set_page_config(
        page_title="Recomendador de películas",
        page_icon="🎬",
        layout="wide",
    )
    st.title("Recomendador de películas con Neo4j")
    st.caption(
        "Demo del parcial de Bases de Datos Avanzadas: todo sale de Neo4j AuraDB, "
        "no hay datos locales ni caché en medio."
    )
    mostrar_estado()
    mostrar_aviso()

    seccion = st.sidebar.radio("Sección", SECCIONES, key="seccion")
    st.sidebar.caption("Cada consulta de grafo muestra su Cypher y sus milisegundos.")
    if st.sidebar.button("Comprobar la conexión de nuevo"):
        st.session_state.pop("estado_conexion", None)
        st.rerun()

    match seccion:
        case "Películas":
            seccion_peliculas()
        case "Usuarios":
            seccion_usuarios()
        case "Recomendaciones":
            seccion_recomendaciones()
        case "Caminos":
            seccion_caminos()


if __name__ == "__main__":
    main()
