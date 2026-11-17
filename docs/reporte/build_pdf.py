"""Genera `reporte.pdf`: el reporte técnico del recomendador de películas.

El documento tiene portada y cinco secciones (introducción, justificación,
arquitectura, diseño del modelo y catálogo de consultas) más las conclusiones.
Los dos diagramas se dibujan aquí mismo con primitivas de reportlab (cajas,
elipses y flechas), así que el PDF se reproduce sin Graphviz ni imágenes
externas.

Uso::

    python docs/reporte/build_pdf.py

Escribe `docs/reporte/reporte.pdf` junto a este archivo y comprueba que las
fuentes Arial del sistema existan antes de empezar.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    HRFlowable,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)

# --------------------------------------------------------------------------- #
# Datos de la portada
# --------------------------------------------------------------------------- #

ALUMNO = ""
MATERIA = "Bases de Datos Avanzadas"
PARCIAL = "Parcial — Desarrollo e Integración de Aplicaciones con Bases de Datos NoSQL en la Nube"
FECHA = "18 de noviembre de 2026"
TITULO = "Recomendador de películas"
SUBTITULO = "Diseño, justificación y catálogo sobre Neo4j AuraDB"
REPO = "github.com/emiliorevv/recomendador-peliculas"

AQUI = Path(__file__).resolve().parent
SALIDA = AQUI / "reporte.pdf"
FUENTES = Path("/System/Library/Fonts/Supplemental")

ANCHO_PAGINA, ALTO_PAGINA = A4
MARGEN = 2.5 * cm
ANCHO = ANCHO_PAGINA - 2 * MARGEN  # 16 cm

# --------------------------------------------------------------------------- #
# Fuentes y estilos
# --------------------------------------------------------------------------- #

FUENTES_Arial = [
    ("Arial", "Arial.ttf"),
    ("Arial-Bold", "Arial Bold.ttf"),
    ("Arial-Italic", "Arial Italic.ttf"),
    ("Arial-BoldItalic", "Arial Bold Italic.ttf"),
]


def registrar_fuentes() -> None:
    """Registra Arial y sus variantes desde las fuentes del sistema."""
    faltantes = [nombre for _, nombre in FUENTES_Arial if not (FUENTES / nombre).exists()]
    if faltantes:
        raise SystemExit(f"No encuentro las fuentes Arial: {', '.join(faltantes)}")
    for alias, nombre in FUENTES_Arial:
        pdfmetrics.registerFont(TTFont(alias, str(FUENTES / nombre)))
    pdfmetrics.registerFontFamily(
        "Arial",
        normal="Arial",
        bold="Arial-Bold",
        italic="Arial-Italic",
        boldItalic="Arial-BoldItalic",
    )


GRIS = colors.HexColor("#555555")
GRIS_CLARO = colors.HexColor("#EDEDED")
GRIS_CAJA = colors.HexColor("#F6F6F6")
GRIS_BORDE = colors.HexColor("#9A9A9A")

CUERPO = ParagraphStyle(
    "cuerpo",
    fontName="Arial",
    fontSize=11,
    leading=14.4,
    alignment=TA_JUSTIFY,
    spaceAfter=6,
)
H1 = ParagraphStyle(
    "h1",
    fontName="Arial-Bold",
    fontSize=15,
    leading=18,
    spaceBefore=16,
    spaceAfter=6,
    keepWithNext=1,
)
H2 = ParagraphStyle(
    "h2",
    fontName="Arial-Bold",
    fontSize=11.8,
    leading=14.5,
    spaceBefore=10,
    spaceAfter=4,
    keepWithNext=1,
)
BULLET = ParagraphStyle(
    "bullet",
    parent=CUERPO,
    leftIndent=13,
    bulletIndent=3,
    bulletFontName="Arial",
    spaceAfter=2,
)
CELDA = ParagraphStyle("celda", fontName="Arial", fontSize=8.2, leading=10.2)
CELDA_ENC = ParagraphStyle("celda_enc", parent=CELDA, fontName="Arial-Bold")
LEYENDA = ParagraphStyle(
    "leyenda",
    fontName="Arial-Italic",
    fontSize=8.2,
    leading=10.4,
    textColor=GRIS,
    spaceBefore=3,
    spaceAfter=9,
    alignment=TA_LEFT,
)
CODIGO = ParagraphStyle(
    "codigo",
    fontName="Courier",
    fontSize=7.1,
    leading=8.55,
    textColor=colors.black,
)
PORTADA_KICKER = ParagraphStyle(
    "kicker",
    fontName="Arial",
    fontSize=9.5,
    leading=12,
    alignment=TA_LEFT,
    textColor=GRIS,
)
PORTADA_TITULO = ParagraphStyle(
    "portada_titulo",
    fontName="Arial-Bold",
    fontSize=26,
    leading=31,
    alignment=TA_LEFT,
)
PORTADA_SUBTITULO = ParagraphStyle(
    "portada_subtitulo",
    fontName="Arial",
    fontSize=13,
    leading=17,
    alignment=TA_LEFT,
    textColor=colors.HexColor("#333333"),
)
PORTADA_DATO = ParagraphStyle(
    "portada_dato",
    fontName="Arial",
    fontSize=10.5,
    leading=14.5,
    alignment=TA_LEFT,
)


# --------------------------------------------------------------------------- #
# Tablas y bloques de código
# --------------------------------------------------------------------------- #


def tabla(cabecera: list[str], filas: list[list[str]], anchos: list[float]) -> Table:
    """Tabla con encabezado gris y bordes finos, con celdas que sí hacen wrap."""
    datos = [[Paragraph(texto, CELDA_ENC) for texto in cabecera]]
    datos += [[Paragraph(texto, CELDA) for texto in fila] for fila in filas]
    tabla_ = Table(datos, colWidths=anchos, repeatRows=1, hAlign="LEFT")
    tabla_.spaceAfter = 7
    tabla_.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, GRIS_BORDE),
                ("BACKGROUND", (0, 0), (-1, 0), GRIS_CLARO),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2.6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.8),
            ]
        )
    )
    return tabla_


def codigo(texto: str, ancho: float = ANCHO) -> Table:
    """Cypher o SQL en un recuadro gris con letra monoespaciada."""
    bloque = Preformatted(texto.strip("\n"), CODIGO)
    tabla_ = Table([[bloque]], colWidths=[ancho], hAlign="LEFT")
    tabla_.spaceAfter = 7
    tabla_.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#B5B5B5")),
                ("BACKGROUND", (0, 0), (-1, -1), GRIS_CAJA),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return tabla_


def recuadro(texto: str) -> Table:
    """Resultado de una consulta en un recuadro gris, con la tipografía del cuerpo."""
    celda = ParagraphStyle(
        "recuadro", fontName="Arial", fontSize=9.2, leading=12, textColor=colors.black
    )
    tabla_ = Table([[Paragraph(texto, celda)]], colWidths=[ANCHO], hAlign="LEFT")
    tabla_.spaceAfter = 7
    tabla_.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#B5B5B5")),
                ("BACKGROUND", (0, 0), (-1, -1), GRIS_CAJA),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return tabla_


def parrafo(texto: str, estilo: ParagraphStyle = CUERPO) -> Paragraph:
    return Paragraph(texto, estilo)


def vineta(texto: str) -> Paragraph:
    return Paragraph(texto, BULLET, bulletText="•")


def titulo_seccion(texto: str) -> Paragraph:
    return Paragraph(texto, H1)


def leyenda(texto: str) -> Paragraph:
    return Paragraph(texto, LEYENDA)


# --------------------------------------------------------------------------- #
# Diagramas: primitivas compartidas
# --------------------------------------------------------------------------- #


def _texto(
    canv: Canvas,
    x: float,
    y: float,
    texto: str,
    tam: float = 8,
    negrita: bool = False,
    centrado: bool = True,
    color: colors.Color = colors.black,
) -> None:
    canv.setFont("Arial-Bold" if negrita else "Arial", tam)
    canv.setFillColor(color)
    if centrado:
        canv.drawCentredString(x, y, texto)
    else:
        canv.drawString(x, y, texto)


def _etiqueta(
    canv: Canvas,
    x: float,
    y: float,
    linea: str,
    sub: str = "",
    tam: float = 7.4,
    centrado: bool = True,
) -> None:
    """Texto de relación con fondo blanco, para que la flecha no lo atraviese."""
    ancho = max(
        pdfmetrics.stringWidth(linea, "Arial-Bold", tam),
        pdfmetrics.stringWidth(sub, "Arial", tam - 0.5) if sub else 0,
    )
    alto = tam + (tam - 0.5) + 3 if sub else tam + 3
    x0 = x - ancho / 2 - 2 if centrado else x - 2
    canv.setFillColor(colors.white)
    canv.rect(x0, y - 2, ancho + 4, alto, stroke=0, fill=1)
    _texto(canv, x, y + (tam - 0.5) + 1 if sub else y, linea, tam, True, centrado)
    if sub:
        _texto(canv, x, y - 1, sub, tam - 0.5, False, centrado)


def _flecha(
    canv: Canvas,
    inicio: tuple[float, float],
    fin: tuple[float, float],
    linea: str,
    sub: str = "",
    desplazamiento: tuple[float, float] = (0, 0),
) -> None:
    """Línea con punta de flecha y su etiqueta en el punto medio."""
    x1, y1 = inicio
    x2, y2 = fin
    canv.setStrokeColor(colors.black)
    canv.setLineWidth(0.9)
    canv.line(x1, y1, x2, y2)

    angulo = math.atan2(y2 - y1, x2 - x1)
    largo, semi = 5.6, 2.7
    base_x = x2 - largo * math.cos(angulo)
    base_y = y2 - largo * math.sin(angulo)
    punta = canv.beginPath()
    punta.moveTo(x2, y2)
    punta.lineTo(base_x + semi * math.sin(angulo), base_y - semi * math.cos(angulo))
    punta.lineTo(base_x - semi * math.sin(angulo), base_y + semi * math.cos(angulo))
    punta.close()
    canv.setFillColor(colors.black)
    canv.drawPath(punta, stroke=0, fill=1)

    medio_x = (x1 + x2) / 2 + desplazamiento[0]
    medio_y = (y1 + y2) / 2 + desplazamiento[1]
    _etiqueta(canv, medio_x, medio_y, linea, sub)


def _borde_elipse(
    centro: tuple[float, float],
    radios: tuple[float, float],
    hacia: tuple[float, float],
) -> tuple[float, float]:
    """Punto del borde de la elipse en dirección al punto `hacia`."""
    cx, cy = centro
    rx, ry = radios
    angulo = math.atan2((hacia[1] - cy) / ry, (hacia[0] - cx) / rx)
    return cx + rx * math.cos(angulo), cy + ry * math.sin(angulo)


def _elipse(
    canv: Canvas,
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    titulo: str,
    sub: str = "",
    sub2: str = "",
) -> None:
    canv.setFillColor(colors.white)
    canv.setStrokeColor(colors.black)
    canv.setLineWidth(1.0)
    canv.ellipse(cx - rx, cy - ry, cx + rx, cy + ry, stroke=1, fill=1)
    if sub2:
        _texto(canv, cx, cy + 6, titulo, 8.6, True)
        _texto(canv, cx, cy - 4, sub, 7.0)
        _texto(canv, cx, cy - 12, sub2, 7.0)
    elif sub:
        _texto(canv, cx, cy + 3.2, titulo, 8.6, True)
        _texto(canv, cx, cy - 7.5, sub, 7.0)
    else:
        _texto(canv, cx, cy - 3, titulo, 8.6, True)


class DiagramaArquitectura(Flowable):
    """Navegador → app Streamlit (con driver y `.env`) → Neo4j AuraDB."""

    def __init__(self) -> None:
        super().__init__()
        self.width = ANCHO
        self.height = 213

    def draw(self) -> None:
        canv = self.canv
        canv.setLineWidth(1.0)
        canv.setStrokeColor(colors.black)

        # Navegador
        _caja(canv, 0, 68, 80, 78, "Navegador", ["usuario", "en la laptop"])
        # Aplicación en Python: contenedor y cuatro piezas
        _caja(canv, 162, 8, 148, 197, "Aplicación Python", ["en la laptop"], relleno=False)
        _caja(canv, 170, 146, 132, 31, "app.py", ["interfaz Streamlit"])
        _caja(canv, 170, 110, 132, 31, "src/", ["CRUD y consultas"])
        _caja(canv, 170, 74, 132, 31, "src/conexion.py", ["driver · pool"])
        _caja(canv, 170, 38, 132, 31, ".env", ["credenciales"])
        # Neo4j AuraDB
        _caja(
            canv,
            376,
            52,
            77,
            108,
            "Neo4j AuraDB",
            ["DaaS en la nube", "Cypher · grafo", "TLS obligatorio"],
        )

        # HTTP local: navegador → app
        _flecha(canv, (80, 107), (162, 107), "HTTP", "localhost:8501")
        # Bolt cifrado: app → base
        _flecha(canv, (310, 107), (376, 107), "Bolt + TLS", "neo4j+s://")
        # Qué hace el driver en cada consulta
        canv.setFont("Arial-Italic", 6.8)
        canv.setFillColor(GRIS)
        canv.drawCentredString(236, 22, "execute_query · reintentos · READ/WRITE")


def _caja(
    canv: Canvas,
    x: float,
    y: float,
    ancho: float,
    alto: float,
    titulo: str,
    lineas: list[str],
    relleno: bool = True,
) -> None:
    """Caja redondeada con título y hasta tres líneas de detalle."""
    canv.setLineWidth(0.9)
    canv.setStrokeColor(colors.black)
    canv.setFillColor(GRIS_CAJA if relleno else colors.white)
    canv.roundRect(x, y, ancho, alto, 5, stroke=1, fill=1)
    centro = x + ancho / 2
    alto_total = 9 + 10 * len(lineas)
    arriba = y + alto / 2 + alto_total / 2 - 7
    _texto(canv, centro, arriba, titulo, 9.0, True)
    for indice, linea in enumerate(lineas):
        _texto(canv, centro, arriba - 12 - indice * 10, linea, 7.4)


class DiagramaModelo(Flowable):
    """Cuatro etiquetas del grafo con sus relaciones y direcciones."""

    def __init__(self) -> None:
        super().__init__()
        self.width = ANCHO
        self.height = 252

    def draw(self) -> None:
        canv = self.canv
        # Nodos
        usuario1 = (80.0, 225.0)
        usuario2 = (355.0, 225.0)
        pelicula = (216.0, 136.0)
        genero = (392.0, 136.0)
        actor = (80.0, 56.0)
        director = (216.0, 36.0)

        radios_usuario = (52.0, 17.0)
        radios_pelicula = (70.0, 27.0)
        radios_genero = (42.0, 17.0)
        radios_persona = (52.0, 17.0)

        # Flechas primero, nodos encima: así ningún borde tapa una flecha.
        _flecha(
            canv,
            _borde_elipse(usuario1, radios_usuario, usuario2),
            _borde_elipse(usuario2, radios_usuario, usuario1),
            "SIGUE",
            "",
            (0, 7),
        )
        _flecha(
            canv,
            _borde_elipse(usuario1, radios_usuario, pelicula),
            _borde_elipse(pelicula, radios_pelicula, usuario1),
            "CALIFICO",
            "{estrellas, fecha}",
            (-16, 5),
        )
        _flecha(
            canv,
            _borde_elipse(actor, radios_persona, pelicula),
            _borde_elipse(pelicula, radios_pelicula, actor),
            "ACTUO_EN",
            "",
            (2, 7),
        )
        _flecha(
            canv,
            _borde_elipse(director, radios_persona, pelicula),
            _borde_elipse(pelicula, radios_pelicula, director),
            "DIRIGIO",
            "",
            (30, 0),
        )
        _flecha(
            canv,
            _borde_elipse(pelicula, radios_pelicula, genero),
            _borde_elipse(genero, radios_genero, pelicula),
            "DE_GENERO",
            "",
            (0, 7),
        )

        _elipse(canv, *usuario1, *radios_usuario, "Usuario", "id, nombre")
        _elipse(canv, *usuario2, *radios_usuario, "Usuario", "id, nombre")
        _elipse(canv, *pelicula, *radios_pelicula, "Pelicula", "id, titulo, anio, duracion")
        _elipse(canv, *genero, *radios_genero, "Genero", "nombre")
        _elipse(canv, *actor, *radios_persona, "Persona", "nombre")
        _elipse(canv, *director, *radios_persona, "Persona", "nombre")

        canv.setFont("Arial-Italic", 7.2)
        canv.setFillColor(GRIS)
        canv.drawCentredString(216, 6, "misma etiqueta Persona para actores y directores")


# --------------------------------------------------------------------------- #
# Portada y pie de página
# --------------------------------------------------------------------------- #


class LienzoNumerado(Canvas):
    """Canvas que guarda cada página y escribe «Página X de Y» al final."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._paginas: list[dict[str, object]] = []

    def showPage(self) -> None:  # noqa: N802 (API de reportlab)
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._paginas) - 1  # la portada no se numera
        for numero, estado in enumerate(self._paginas, start=1):
            self.__dict__.update(estado)
            if numero > 1:
                self._pie(numero - 1, total)
            super().showPage()
        super().save()

    def _pie(self, numero: int, total: int) -> None:
        self.setFont("Arial", 7.6)
        self.setFillColor(GRIS)
        self.drawCentredString(ANCHO_PAGINA / 2, 1.35 * cm, f"Página {numero} de {total}")


class Documento(BaseDocTemplate):
    """Plantilla con portada sin encabezado y páginas de cuerpo numeradas."""

    def __init__(self, ruta: Path) -> None:
        kwargs = {
            "pagesize": A4,
            "leftMargin": MARGEN,
            "rightMargin": MARGEN,
            "topMargin": MARGEN,
            "bottomMargin": MARGEN,
            "title": f"{TITULO} — {SUBTITULO}",
            "author": ALUMNO or MATERIA,
            "subject": PARCIAL,
            "creator": "docs/reporte/build_pdf.py",
        }
        super().__init__(str(ruta), **kwargs)
        marco = Frame(
            MARGEN,
            MARGEN,
            ANCHO,
            ALTO_PAGINA - 2 * MARGEN,
            id="cuerpo",
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        )
        self.addPageTemplates(
            [
                PageTemplate(id="portada", frames=[marco], onPage=self._portada),
                PageTemplate(id="cuerpo", frames=[marco], onPage=self._encabezado),
            ]
        )

    def _portada(self, canv: Canvas, doc: Documento) -> None:
        """La portada no lleva encabezado ni número: solo los bloques de texto."""

    def _encabezado(self, canv: Canvas, doc: Documento) -> None:
        canv.saveState()
        canv.setStrokeColor(GRIS_BORDE)
        canv.setLineWidth(0.4)
        canv.line(MARGEN, ALTO_PAGINA - MARGEN + 7, ANCHO_PAGINA - MARGEN, ALTO_PAGINA - MARGEN + 7)
        canv.setFont("Arial", 7.6)
        canv.setFillColor(GRIS)
        canv.drawString(MARGEN, ALTO_PAGINA - MARGEN + 11, f"{TITULO} · Neo4j AuraDB")
        canv.drawRightString(ANCHO_PAGINA - MARGEN, ALTO_PAGINA - MARGEN + 11, MATERIA)
        canv.restoreState()


def portada() -> list[Flowable]:
    """Portada tipográfica: materia, título, parcial, alumno y fecha."""
    datos = []
    if ALUMNO.strip():
        datos.append(parrafo(f"Alumno: {ALUMNO}", PORTADA_DATO))
    datos.append(parrafo(FECHA, PORTADA_DATO))
    return [
        Spacer(1, 3.1 * cm),
        parrafo(MATERIA.upper(), PORTADA_KICKER),
        Spacer(1, 0.55 * cm),
        parrafo(TITULO, PORTADA_TITULO),
        Spacer(1, 0.18 * cm),
        parrafo(SUBTITULO, PORTADA_SUBTITULO),
        Spacer(1, 0.5 * cm),
        HRFlowable(width="100%", thickness=0.7, color=colors.black, spaceBefore=4, spaceAfter=14),
        parrafo(PARCIAL, PORTADA_DATO),
        Spacer(1, 11.6 * cm),
        HRFlowable(width=4.2 * cm, thickness=0.6, color=colors.black, hAlign="LEFT", spaceAfter=10),
        parrafo(REPO, PORTADA_DATO),
        Spacer(1, 0.25 * cm),
        *datos,
    ]


# --------------------------------------------------------------------------- #
# Contenido
# --------------------------------------------------------------------------- #


def seccion_introduccion() -> list[Flowable]:
    return [
        titulo_seccion("1. Introducción y dominio"),
        parrafo(
            "Esta aplicación es una plataforma pequeña de reseñas de películas, parecida a "
            "Letterboxd: cada usuario califica lo que vio con una a cinco estrellas, sigue a "
            "otros usuarios y descubre qué ver después. La base de datos guarda las películas "
            "con su año y su duración, a las personas que actuaron y dirigieron, los géneros y "
            "las relaciones entre usuarios. Todo eso vive en un grafo, no en tablas."
        ),
        parrafo(
            "El dominio se puede describir con cuatro etiquetas de nodo. <b>Pelicula</b> tiene "
            "<i>id</i>, <i>titulo</i>, <i>anio</i> y <i>duracion</i>. <b>Persona</b> guarda el "
            "<i>nombre</i> y se usa tanto para actores como para directores. <b>Genero</b> "
            "guarda el <i>nombre</i> del género. <b>Usuario</b> tiene <i>id</i> y <i>nombre</i>. "
            "Las relaciones son cinco: <b>CALIFICO</b> (con <i>estrellas</i> y <i>fecha</i>), "
            "<b>SIGUE</b>, <b>ACTUO_EN</b>, <b>DIRIGIO</b> y <b>DE_GENERO</b>. Cada una tiene "
            "una dirección y un significado propio."
        ),
        parrafo("Con ese modelo, el usuario espera cuatro cosas de la plataforma:"),
        vineta(
            "<b>Recomendaciones.</b> Qué ver según lo que les gustó a personas con gustos "
            "parecidos, sin repetir lo que ya calificó."
        ),
        vineta(
            "<b>Películas parecidas.</b> Al ver una película, otras con el mismo director, "
            "actores o géneros."
        ),
        vineta("<b>A quién seguir.</b> Usuarios que siguen a la gente que él sigue."),
        vineta(
            "<b>Curiosidades del reparto.</b> Cuántos saltos hay entre dos actores, al estilo "
            "de los seis grados de Kevin Bacon."
        ),
        parrafo(
            "Ninguna de esas funciones se responde mirando una sola fila. Todas dependen de "
            "<i>cómo se conectan</i> los datos, y esa observación es el punto de partida de la "
            "justificación del paradigma (§2). El alcance del parcial es deliberadamente chico: "
            "35 películas reales, 74 personas, 10 géneros, 12 usuarios, 95 calificaciones y 36 "
            "relaciones <b>SIGUE</b>, o sea 131 nodos y 368 relaciones. Sobre esos datos corren "
            "el CRUD completo y las seis consultas de grafo del catálogo."
        ),
        parrafo(
            "El resto del documento sigue el orden del enunciado: la justificación del paradigma "
            "(§2), la arquitectura y la integración con la nube (§3), el diseño del modelo con "
            "sus restricciones (§4), el catálogo de las 13 consultas con resultados reales (§5) "
            "y las conclusiones con lo que falta para producción (§6)."
        ),
    ]


def seccion_justificacion() -> list[Flowable]:
    return [
        titulo_seccion("2. Justificación del paradigma"),
        parrafo(
            "Las cuatro funciones del §1 recorren conexiones. En una base relacional cada "
            "conexión es un JOIN más, y el número de JOINs queda escrito en la consulta: si "
            "mañana la recomendación necesita un salto adicional, hay que reescribirla. En un "
            "grafo la conexión es una relación de primera clase y el patrón se lee igual que el "
            "enunciado en español."
        ),
        parrafo(
            "<b>La recomendación son tres saltos.</b> Yo califiqué una película, otro usuario "
            "calificó esa misma película y también calificó otra que yo no vi. En SQL la tabla "
            "de calificaciones se une consigo misma tres veces y hace falta una subconsulta para "
            "excluir lo ya visto:"
        ),
        codigo(
            """
SELECT p2.titulo, COUNT(DISTINCT c2.usuario_id) AS votos
FROM calificaciones c1
JOIN calificaciones c2 ON c2.pelicula_id = c1.pelicula_id AND c2.usuario_id <> c1.usuario_id
JOIN calificaciones c3 ON c3.usuario_id = c2.usuario_id
JOIN peliculas p2      ON p2.id = c3.pelicula_id
WHERE c1.usuario_id = 'u01' AND c1.estrellas >= 4 AND c2.estrellas >= 4
  AND c3.estrellas >= 4
  AND c3.pelicula_id NOT IN (SELECT pelicula_id FROM calificaciones WHERE usuario_id = 'u01')
GROUP BY p2.titulo
ORDER BY votos DESC;
"""
        ),
        parrafo("En Cypher el mismo recorrido se escribe como el patrón que describe el problema:"),
        codigo(
            """
MATCH (yo:Usuario {id: $id})-[mia:CALIFICO]->(:Pelicula)<-[suya:CALIFICO]-(otro:Usuario)
WHERE otro <> yo AND mia.estrellas >= 4 AND suya.estrellas >= 4
MATCH (otro)-[otra:CALIFICO]->(recomendada:Pelicula)
WHERE otra.estrellas >= 4 AND NOT (yo)-[:CALIFICO]->(recomendada)
RETURN recomendada.titulo, count(otro) AS usuarios_parecidos
"""
        ),
        parrafo(
            "<b>El camino más corto es el caso extremo.</b> Entre dos actores no se sabe cuántos "
            "saltos hay, así que en SQL hace falta una CTE recursiva (<i>WITH RECURSIVE</i>) que "
            "alterne persona y película, lleve un arreglo de nodos visitados para no ciclarse y "
            "crezca nivel por nivel. La forma de esa consulta es así:"
        ),
        codigo(
            """
-- esquema de la CTE: alterna persona y película, guarda visitados y corta a 12 saltos
WITH RECURSIVE paso (origen, tipo, id, largo, visitados) AS ( ... )
SELECT * FROM paso WHERE tipo = 'persona' AND id = :destino ORDER BY largo LIMIT 1;
"""
        ),
        parrafo(
            "Además de larga, esa consulta no puede buscar desde los dos extremos a la vez. "
            "Neo4j lo resuelve con una primitiva del motor:"
        ),
        codigo(
            """
MATCH (a:Persona {nombre: $origen}), (b:Persona {nombre: $destino})
MATCH camino = shortestPath((a)-[:ACTUO_EN|DIRIGIO*..12]-(b))
RETURN [n IN nodes(camino) | coalesce(n.nombre, n.titulo)] AS camino,
       length(camino) AS saltos
"""
        ),
        parrafo(
            "<b>Index-free adjacency.</b> En un motor relacional, cada JOIN busca en el índice "
            "de toda la tabla las filas que coinciden; el costo depende del tamaño de la tabla y "
            "se repite en cada salto. En Neo4j cada nodo guarda apuntadores directos a sus "
            "relaciones, así que pasar de un nodo a su vecino no consulta ninguna estructura "
            "global: el costo depende de cuántos nodos se visitan, no de cuántos hay en total. "
            "Los índices sirven para encontrar el nodo de partida (el usuario, la película) y "
            "después el recorrido avanza por los apuntadores."
        ),
        parrafo(
            "<b>Las relaciones son datos.</b> La calificación no es una fila intermedia sin "
            "significado: es la relación entre un usuario y una película, y sus estrellas y su "
            "fecha viven en ella. En SQL eso obliga a una tabla puente; en el grafo es la "
            "relación misma, y por eso se puede escribir una propiedad sin tocar el resto del "
            "esquema."
        ),
        parrafo(
            "<b>¿Y una base clave-valor?</b> Redis o DynamoDB son excelentes para leer o "
            "escribir un dato por su llave: una sesión, un carrito, una caché. Aquí casi nada se "
            "consulta por llave; casi todo es recorrer. En clave-valor habría que guardar listas "
            "de vecinos a mano (por ejemplo un conjunto <i>pelicula:123:actores</i>) y hacer los "
            "recorridos en el código de la aplicación, con un viaje de red por salto. El grafo "
            "hace ese trabajo en el motor, en una sola consulta."
        ),
        parrafo("La comparación, en una tabla:"),
        tabla(
            ["Criterio", "SQL", "Clave-valor", "Grafo (Neo4j)"],
            [
                [
                    "Recomendación (3 saltos)",
                    "3 JOINs + subconsulta",
                    "Varios viajes de red y lógica en la app",
                    "Un patrón <i>MATCH</i>",
                ],
                [
                    "Camino más corto",
                    "<i>WITH RECURSIVE</i> complejo",
                    "No aplica",
                    "<i>shortestPath</i>",
                ],
                [
                    "Costo por salto",
                    "Crece con el tamaño de la tabla",
                    "Un viaje de red por salto",
                    "Constante por vecino",
                ],
                [
                    "Agregar un tipo de relación",
                    "Nueva tabla y migración",
                    "Nuevas llaves a mano",
                    "Nueva relación, sin migrar",
                ],
                ["Reportes agregados", "Muy bueno", "Malo", "Aceptable"],
            ],
            [3.4 * cm, 3.9 * cm, 4.6 * cm, 4.1 * cm],
        ),
        parrafo(
            "<b>Dónde SQL sería mejor.</b> Para reportes con sumas y agrupaciones sobre toda la "
            "base, o para datos muy tabulares con transacciones entre muchas tablas, un motor "
            "relacional es la herramienta correcta. Tampoco hay que exagerar: con 35 películas "
            "una base relacional responde perfecto y hasta sería más simple de operar. La "
            "decisión no se apoya en el volumen de hoy sino en la forma de las consultas y en "
            "cómo crecen: los recorridos son el corazón del producto, y en un grafo se expresan "
            "sin reescribir JOINs ni mantener tablas de caminos precalculados."
        ),
    ]


def seccion_arquitectura() -> list[Flowable]:
    return [
        titulo_seccion("3. Arquitectura"),
        parrafo(
            "La aplicación corre en la laptop y la base de datos corre en la nube. El navegador "
            "habla con la interfaz Streamlit por HTTP local; la interfaz llama a los módulos de "
            "<i>src/</i>, que usan un único driver oficial de Neo4j; el driver abre conexiones "
            "cifradas por Bolt contra la instancia de AuraDB. El siguiente diagrama muestra los "
            "bloques y los dos protocolos."
        ),
        DiagramaArquitectura(),
        leyenda(
            "Figura 1. Arquitectura por bloques. La app y la base no comparten máquina: lo único "
            "que viaja entre ellas es Bolt sobre TLS, con las credenciales del archivo .env."
        ),
        parrafo(
            "<b>Capas.</b> La presentación es <i>app.py</i>, un solo archivo Streamlit con cuatro "
            "secciones (películas, usuarios, recomendaciones y caminos). La lógica de dominio "
            "está en <i>src/peliculas.py</i>, <i>src/usuarios.py</i>, <i>src/consultas.py</i> y "
            "<i>src/validacion.py</i>; ahí viven las validaciones y las consultas, no en la "
            "interfaz. El acceso a datos está concentrado en <i>src/conexion.py</i>, que expone "
            "<i>leer</i>, <i>escribir</i>, <i>en_transaccion</i> y <i>verificar_conexion</i>. "
            "Nadie más crea un driver ni arma una sesión. El almacenamiento es Neo4j AuraDB Free."
        ),
        parrafo(
            "<b>Un driver, un pool.</b> El driver se crea la primera vez que se usa y se "
            "reutiliza durante toda la vida del proceso; un candado evita que dos hilos de "
            "Streamlit creen dos drivers a la vez. Cada consulta pasa por "
            "<i>driver.execute_query()</i>, que la ejecuta en una transacción administrada, "
            "reintenta ante errores transitorios y reutiliza conexiones del pool. Las lecturas se "
            "marcan con <i>routing_=READ</i> y las escrituras con <i>routing_=WRITE</i>, para que "
            "el enrutamiento del clúster elija el servidor correcto."
        ),
        parrafo(
            "<b>Por qué la base no corre en localhost.</b> El enunciado pide una base NoSQL "
            "administrada en la nube, y la rúbrica evalúa esa integración. Tenerla en AuraDB "
            "implica que el respaldo, el parcheo y el cifrado en reposo los maneja el proveedor, "
            "que la conexión va cifrada con <i>neo4j+s://</i> y que la instancia es la misma que "
            "ve el profesor desde la consola de Neo4j. Un Neo4j en Docker solo se usa en las "
            "pruebas de integración del CI, contra una base desechable, nunca en la app."
        ),
        parrafo(
            "<b>Credenciales y TLS.</b> La URI, el usuario y la contraseña se leen de variables "
            "de entorno cargadas desde <i>.env</i> con <i>python-dotenv</i>. El archivo está en "
            "<i>.gitignore</i>, el repo trae un <i>.env.example</i> sin valores y el código no "
            "imprime ni registra la contraseña ni la URI. Si falta una variable, la app falla al "
            "iniciar con un mensaje que nombra la que falta en vez de intentar conectarse. En "
            "macOS, cuando el intérprete no tiene certificados raíz, <i>src/conexion.py</i> "
            "apunta <i>SSL_CERT_FILE</i> al bundle de <i>certifi</i>; solo lo hace si la variable "
            "no está definida y el contexto TLS del sistema no trae ninguna CA, para no romper "
            "una red con proxy corporativo."
        ),
        tabla(
            ["Pieza", "Tecnología", "Dónde corre", "ADR"],
            [
                ["Base de datos", "Neo4j AuraDB Free (grafo, Cypher)", "Nube de Neo4j", "0001"],
                ["Aplicación", "Python 3.12+ y driver oficial neo4j 5.x", "Laptop", "0002"],
                ["Interfaz", "Streamlit", "Laptop (navegador)", "0003"],
                ["Credenciales", "Variables de entorno en .env", "Laptop, fuera del repo", "0004"],
            ],
            [3.0 * cm, 6.8 * cm, 4.4 * cm, 1.8 * cm],
        ),
    ]


def seccion_modelo() -> list[Flowable]:
    return [
        titulo_seccion("4. Diseño del modelo"),
        parrafo(
            "El grafo tiene cuatro etiquetas y cinco tipos de relación. La figura 2 muestra las "
            "etiquetas con sus propiedades, las relaciones con su dirección y las propiedades que "
            "viven en la relación de calificación."
        ),
        DiagramaModelo(),
        leyenda(
            "Figura 2. Modelo del grafo. Cada flecha va del nodo que «hace» al nodo que «recibe»; "
            "las consultas de caminos y vecindad recorren esas relaciones en los dos sentidos."
        ),
        tabla(
            ["Etiqueta", "Propiedades", "Llave única", "Notas"],
            [
                [
                    "Pelicula",
                    "id, titulo, anio, duracion (min)",
                    "id",
                    "id = título y año en minúsculas, ej. inception-2010",
                ],
                [
                    "Persona",
                    "nombre",
                    "nombre",
                    "Actores y directores en la misma etiqueta",
                ],
                [
                    "Genero",
                    "nombre",
                    "nombre",
                    "Nodo y no propiedad, para poder recorrer por género",
                ],
                ["Usuario", "id, nombre", "id", "id = u01, u02…"],
            ],
            [2.3 * cm, 4.5 * cm, 2.0 * cm, 7.2 * cm],
        ),
        KeepTogether(
            tabla(
                ["Relación", "Dirección", "Propiedades", "Significado"],
                [
                    [
                        "CALIFICO",
                        "Usuario → Pelicula",
                        "estrellas (1–5), fecha",
                        "La calificación le pertenece a la pareja usuario-película",
                    ],
                    ["SIGUE", "Usuario → Usuario", "—", "Red social"],
                    ["ACTUO_EN", "Persona → Pelicula", "—", "Papel de actor"],
                    ["DIRIGIO", "Persona → Pelicula", "—", "Papel de director"],
                    ["DE_GENERO", "Pelicula → Genero", "—", "Clasificación por género"],
                ],
                [2.4 * cm, 4.0 * cm, 3.8 * cm, 5.8 * cm],
            )
        ),
        parrafo(
            "Las restricciones de unicidad hacen dos cosas: impiden duplicados y crean el índice "
            "que usa cada <i>MATCH</i> para encontrar el nodo de partida. El índice sobre el "
            "título sirve para listar y buscar sin recorrer todas las películas. Todas las "
            "sentencias llevan <i>IF NOT EXISTS</i>, así que el esquema se puede aplicar dos "
            "veces sin error."
        ),
        codigo(
            """
CREATE CONSTRAINT pelicula_id    IF NOT EXISTS FOR (p:Pelicula) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT usuario_id     IF NOT EXISTS FOR (u:Usuario)  REQUIRE u.id IS UNIQUE;
CREATE CONSTRAINT persona_nombre IF NOT EXISTS FOR (p:Persona)  REQUIRE p.nombre IS UNIQUE;
CREATE CONSTRAINT genero_nombre  IF NOT EXISTS FOR (g:Genero)   REQUIRE g.nombre IS UNIQUE;
CREATE INDEX pelicula_titulo     IF NOT EXISTS FOR (p:Pelicula) ON (p.titulo);
"""
        ),
        parrafo(
            "<b>La calificación vive en la relación.</b> Una calificación no existe sin un "
            "usuario y una película: es la pareja. Ponerla en la relación permite guardar "
            "propiedades (<i>estrellas</i>, <i>fecha</i>) y actualizarla con "
            "<i>MERGE … SET</i> sin crear una fila puente ni duplicar nada. Además, el patrón "
            "<i>(u)-[c:CALIFICO]->(p)</i> se lee como la frase «u calificó p», y las consultas "
            "de recomendación pueden filtrar por las estrellas de la relación en cada salto."
        ),
        parrafo(
            "<b>El género es un nodo.</b> Si el género fuera una propiedad de la película (o una "
            "lista de textos) no se podría recorrer hacia él: «las mejores de Drama» exigiría "
            "buscar en listas y no habría un nodo por el que entrar. Como nodo compartido, "
            "<i>DE_GENERO</i> conecta muchas películas con un género y la consulta empieza por "
            "<i>(:Genero {nombre: $genero})</i>, que además tiene índice único. Lo mismo vale para "
            "los géneros nuevos: crearlos es un <i>MERGE</i>, no una migración."
        ),
        parrafo(
            "<b>Persona es una sola etiqueta.</b> Una persona puede actuar y dirigir (Clint "
            "Eastwood, por ejemplo), así que separar <i>Actor</i> y <i>Director</i> duplicaría el "
            "nodo y rompería el camino entre personas: el recorrido <i>ACTUO_EN|DIRIGIO</i> "
            "funciona justamente porque ambos papeles llegan al mismo tipo de nodo. La diferencia "
            "está en la relación, no en la etiqueta."
        ),
        parrafo(
            "<b>Ids slug y dirección explícita.</b> El id de una película se deriva del título y "
            "el año («Batman Begins», 2005 → <i>batman-begins-2005</i>): es legible en la consola, "
            "estable y determinista, y no cambia cuando se edita la película, porque las "
            "calificaciones lo referencian. Los usuarios usan <i>u01</i>, <i>u02</i>… Todas las "
            "relaciones tienen dirección; las consultas de camino las recorren sin dirección "
            "porque el patrón va de persona a película y de película a persona."
        ),
        parrafo(
            "<b>La llave de Persona es el nombre, y en producción no lo sería.</b> En este "
            "parcial alcanza: 74 personas, nombres únicos, y la restricción de unicidad lo "
            "garantiza. Pero dos actores pueden llamarse igual y un nombre puede cambiar (o "
            "escribirse distinto según la fuente), así que en producción la llave sería un id "
            "externo de TMDB o IMDb y <i>nombre</i> quedaría como propiedad. Es una limitación "
            "consciente, no un olvido, y se retoma en §6."
        ),
    ]


def seccion_catalogo() -> list[Flowable]:
    return [
        KeepTogether(
            [
                titulo_seccion("5. Catálogo de consultas"),
                parrafo(
                    "El catálogo tiene 13 consultas: el esquema, las siete operaciones de CRUD y "
                    "las seis consultas propias del grafo. Todas usan parámetros (<i>$id</i>, "
                    "<i>$nombre</i>, <i>$limite</i>); el texto que llega desde la interfaz nunca "
                    "se pega en el Cypher. Esta sección reproduce el Cypher exacto que corre la "
                    "app y los resultados reales contra AuraDB después de "
                    "<i>python seed/seed.py --reset</i>."
                ),
                tabla(
                    ["#", "Consulta", "Tipo", "Dónde"],
                    [
                        ["1", "Restricciones e índices", "Esquema", "seed/esquema.cypher"],
                        [
                            "2",
                            "Crear película con géneros, director y actores",
                            "CRUD (C)",
                            "src/peliculas.py",
                        ],
                        ["3", "Listar y ver detalle de película", "CRUD (R)", "src/peliculas.py"],
                        ["4", "Actualizar película y sus géneros", "CRUD (U)", "src/peliculas.py"],
                        ["5", "Eliminar película (DETACH DELETE)", "CRUD (D)", "src/peliculas.py"],
                        [
                            "6",
                            "Crear, listar, renombrar y eliminar usuario",
                            "CRUD",
                            "src/usuarios.py",
                        ],
                        ["7", "Calificar y quitar calificación", "CRUD", "src/usuarios.py"],
                        [
                            "8",
                            "Recomendación colaborativa",
                            "Recorrido (3 saltos)",
                            "src/consultas.py",
                        ],
                        ["9", "Películas parecidas", "Vecindad + puntaje", "src/consultas.py"],
                        ["10", "Top por género", "Agregación", "src/consultas.py"],
                        ["11", "Camino más corto entre personas", "Camino", "src/consultas.py"],
                        [
                            "12",
                            "Vecindad de una persona a N grados",
                            "Vecindad",
                            "src/consultas.py",
                        ],
                        ["13", "A quién seguir", "Recorrido", "src/consultas.py"],
                    ],
                    [0.9 * cm, 8.6 * cm, 3.1 * cm, 3.4 * cm],
                ),
            ]
        ),
        parrafo(
            "Los tiempos de la tabla siguiente se midieron con <i>time.perf_counter</i> en la "
            "app, contra AuraDB. Incluyen el viaje por red desde la laptop, por eso el rango es "
            "de cientos de milisegundos y no de milisegundos: en el servidor cada consulta tarda "
            "una fracción de eso."
        ),
        tabla(
            ["Consulta", "Tiempo típico"],
            [
                ["8. Recomendación colaborativa", "340 ms"],
                ["9. Películas parecidas", "410 ms"],
                ["10. Top por género", "310 ms"],
                ["11. Camino más corto", "560 ms"],
                ["12. Vecindad a 2 grados", "300 ms"],
                ["13. A quién seguir", "280 ms"],
            ],
            [10.0 * cm, 3.0 * cm],
        ),
        parrafo(
            "<b>5.1 Esquema y CRUD.</b> Las consultas 1 a 7 están documentadas con su Cypher en "
            "<i>docs/catalogo-consultas.md</i>. Dos decisiones se ven en el código: crear una "
            "película escribe en una sola transacción (película, géneros, director y actores), y "
            "calificar usa <i>MERGE</i>, así que la segunda llamada actualiza en vez de duplicar."
        ),
        codigo(
            """
MATCH (u:Usuario {id: $usuario})
MATCH (p:Pelicula {id: $pelicula})
MERGE (u)-[c:CALIFICO]->(p)
SET c.estrellas = $estrellas, c.fecha = $fecha
RETURN p.id AS pelicula_id, p.titulo AS titulo, c.estrellas AS estrellas, c.fecha AS fecha
"""
        ),
        parrafo(
            "Las escrituras que van juntas usan <i>en_transaccion</i>, que corre la función en "
            "una transacción administrada: si una sentencia falla, el commit no ocurre y no queda "
            "una película a medias. Las lecturas van con <i>routing_=READ</i>. De ahí en adelante "
            "vienen las seis consultas que justifican el paradigma."
        ),
        parrafo(
            "<b>5.2 Recomendación colaborativa.</b> Gustos parecidos son los usuarios que "
            "calificaron con 4 o 5 estrellas una película que al usuario también le gustó. El "
            "<i>WITH DISTINCT yo, otro</i> deja un solo registro por usuario parecido, así "
            "<i>count(otro)</i> no se pondera por las películas en común; el <i>NOT</i> excluye "
            "todo lo que el usuario ya calificó, con cualquier puntaje. Se agrupa por nodo y no "
            "por título para que dos películas homónimas no se mezclen."
        ),
        codigo(
            """
MATCH (yo:Usuario {id: $id})-[mia:CALIFICO]->(:Pelicula)<-[suya:CALIFICO]-(otro:Usuario)
WHERE otro <> yo AND mia.estrellas >= 4 AND suya.estrellas >= 4
WITH DISTINCT yo, otro
MATCH (otro)-[otra:CALIFICO]->(recomendada:Pelicula)
WHERE otra.estrellas >= 4 AND NOT (yo)-[:CALIFICO]->(recomendada)
RETURN recomendada.id AS pelicula_id,
       recomendada.titulo AS pelicula,
       count(otro) AS usuarios_parecidos,
       round(avg(otra.estrellas), 2) AS promedio
ORDER BY usuarios_parecidos DESC, promedio DESC, pelicula, pelicula_id
LIMIT $limite
"""
        ),
        tabla(
            ["Película", "Usuarios parecidos", "Promedio"],
            [
                ["Oppenheimer", "3", "4.33"],
                ["Toy Story", "2", "5.0"],
                ["Eternal Sunshine of the Spotless Mind", "2", "4.5"],
                ["Iron Man", "2", "4.5"],
                ["La La Land", "2", "4.0"],
            ],
            [8.4 * cm, 4.0 * cm, 2.6 * cm],
        ),
        leyenda(
            "Resultado real para u01 (las cinco primeras de diez), 340 ms. Un usuario válido sin "
            "coincidencias devuelve una lista vacía, no un error."
        ),
        parrafo(
            "<b>5.3 Películas parecidas.</b> Compara la película base con todas las demás usando "
            "tres subconsultas <i>COUNT { }</i>, que cuentan sin multiplicar filas como harían "
            "tres <i>MATCH</i> encadenados. El puntaje es actores en común + 2 × mismo director + "
            "géneros en común; compartir director pesa el doble. Las películas con puntaje 0 se "
            "descartan, y el resultado trae el desglose para que la app explique el porqué."
        ),
        codigo(
            """
MATCH (base:Pelicula {id: $id})
MATCH (otra:Pelicula)
WHERE otra <> base
WITH base, otra,
     COUNT { (base)-[:DE_GENERO]->(:Genero)<-[:DE_GENERO]-(otra) } AS generos_comunes,
     COUNT { (base)<-[:ACTUO_EN]-(:Persona)-[:ACTUO_EN]->(otra) } AS actores_comunes,
     COUNT { (base)<-[:DIRIGIO]-(:Persona)-[:DIRIGIO]->(otra) } AS mismo_director
WITH otra, generos_comunes, actores_comunes, mismo_director,
     actores_comunes + 2 * mismo_director + generos_comunes AS puntos
WHERE puntos > 0
RETURN otra.id AS pelicula_id, otra.titulo AS titulo, puntos,
       actores_comunes, mismo_director, generos_comunes
ORDER BY puntos DESC, titulo
LIMIT $limite
"""
        ),
        tabla(
            ["Película", "Puntos", "Actores", "Director", "Géneros"],
            [
                ["The Dark Knight Rises", "6", "2", "1", "2"],
                ["The Dark Knight", "5", "1", "1", "2"],
                ["Batman Begins", "4", "1", "1", "1"],
                ["Captain America: The Winter Soldier", "3", "0", "0", "3"],
                ["Interstellar", "3", "0", "1", "1"],
            ],
            [7.6 * cm, 1.7 * cm, 1.8 * cm, 1.9 * cm, 1.7 * cm],
        ),
        leyenda("Resultado real para inception-2010, 410 ms."),
        parrafo(
            "<b>5.4 Top por género.</b> Ordena por promedio descendente y desempata por votos y "
            "después por título, para que dos corridas den lo mismo. Solo entran películas con al "
            "menos una calificación: sin votos no hay promedio. El promedio va redondeado a dos "
            "decimales y se devuelve el conteo para que la app muestre «4.67 (3 votos)»."
        ),
        codigo(
            """
MATCH (p:Pelicula)-[:DE_GENERO]->(:Genero {nombre: $genero})
MATCH (p)<-[c:CALIFICO]-(:Usuario)
RETURN p.id AS pelicula_id,
       p.titulo AS titulo,
       round(avg(c.estrellas), 2) AS promedio,
       count(c) AS votos
ORDER BY promedio DESC, votos DESC, titulo, pelicula_id
LIMIT $limite
"""
        ),
        tabla(
            ["pelicula_id", "Película", "Promedio", "Votos"],
            [
                ["pulp-fiction-1994", "Pulp Fiction", "4.67", "3"],
                ["the-green-mile-1999", "The Green Mile", "4.67", "3"],
                ["titanic-1997", "Titanic", "4.67", "3"],
            ],
            [5.4 * cm, 5.2 * cm, 2.6 * cm, 2.0 * cm],
        ),
        leyenda("Resultado real para Drama con límite 3, 310 ms."),
        parrafo(
            "<b>5.5 Camino más corto entre personas.</b> El patrón está restringido a "
            "<i>ACTUO_EN</i> y <i>DIRIGIO</i>, así que no puede escaparse por los géneros, y el "
            "tope <i>*..12</i> solo acota la búsqueda. Doce saltos son seis películas y cinco "
            "personas intermedias; si origen y destino son la misma persona se devuelve 0 saltos "
            "sin consultar, porque <i>shortestPath</i> no admite extremos iguales. Si no hay "
            "camino, la respuesta es <i>encontrado: false</i>, no una excepción."
        ),
        codigo(
            """
MATCH (a:Persona {nombre: $origen}), (b:Persona {nombre: $destino})
MATCH camino = shortestPath((a)-[:ACTUO_EN|DIRIGIO*..12]-(b))
RETURN [n IN nodes(camino) | coalesce(n.nombre, n.titulo)] AS camino,
       length(camino) AS saltos
"""
        ),
        parrafo("Resultado real para Tom Hanks → Scarlett Johansson, 4 saltos y 560 ms:"),
        recuadro("Tom Hanks → The Green Mile → Sam Rockwell → Jojo Rabbit → Scarlett Johansson"),
        parrafo(
            "<b>5.6 Vecindad de una persona a N grados.</b> En este grafo las personas solo se "
            "tocan a través de una película, así que un grado de separación son dos saltos. Hay "
            "una variante por grado (<i>*2..2</i>, <i>*2..4</i>, <i>*2..6</i>) para no enumerar "
            "caminos más largos de lo pedido; <i>min(length(ruta))</i> se queda con la distancia "
            "más corta cuando una persona se alcanza por varios caminos. <i>grados</i> se valida "
            "como entero de 1 a 3."
        ),
        codigo(
            """
MATCH (a:Persona {nombre: $nombre})
MATCH ruta = (a)-[:ACTUO_EN|DIRIGIO*2..4]-(otra:Persona)
WHERE otra <> a
WITH otra, min(length(ruta)) AS saltos
RETURN otra.nombre AS persona, saltos / 2 AS distancia
ORDER BY distancia, persona
LIMIT $limite
"""
        ),
        tabla(
            ["Persona", "Distancia"],
            [
                ["Don Rickles", "1"],
                ["Frank Darabont", "1"],
                ["John Lasseter", "1"],
                ["Lee Unkrich", "1"],
                ["Michael Clarke Duncan", "1"],
                ["Sam Rockwell", "1"],
                ["Tim Allen", "1"],
                ["Scarlett Johansson", "2"],
                ["Taika Waititi", "2"],
            ],
            [8.0 * cm, 2.4 * cm],
        ),
        leyenda(
            "Resultado real para Tom Hanks con grados = 2, 300 ms. Con grados = 1 salen solo las "
            "siete personas de distancia 1."
        ),
        parrafo(
            "<b>5.7 A quién seguir.</b> Busca amigos de mis amigos, excluye al propio usuario y a "
            "quien ya sigue, y cuenta los amigos en común con <i>count(DISTINCT amigo)</i>. Es la "
            "misma forma de recorrido de tres nodos que la recomendación, pero sobre usuarios en "
            "lugar de películas."
        ),
        codigo(
            """
MATCH (yo:Usuario {id: $id})-[:SIGUE]->(amigo:Usuario)-[:SIGUE]->(sugerido:Usuario)
WHERE sugerido <> yo AND NOT (yo)-[:SIGUE]->(sugerido)
WITH sugerido, count(DISTINCT amigo) AS amigos_en_comun
RETURN sugerido.id AS usuario_id,
       sugerido.nombre AS nombre,
       amigos_en_comun
ORDER BY amigos_en_comun DESC, nombre, usuario_id
LIMIT $limite
"""
        ),
        tabla(
            ["usuario_id", "Nombre", "Amigos en común"],
            [
                ["u05", "Elena", "2"],
                ["u06", "Fabián", "2"],
                ["u08", "Hugo", "2"],
                ["u09", "Irene", "2"],
                ["u10", "Javier", "2"],
            ],
            [4.0 * cm, 5.0 * cm, 4.0 * cm],
        ),
        leyenda(
            "Resultado real para u01, 280 ms. u01 sigue a u02, u03, u04 y u07; ninguno de esos "
            "cuatro aparece en la lista, y tampoco él mismo."
        ),
    ]


def seccion_conclusiones() -> list[Flowable]:
    return [
        titulo_seccion("6. Conclusiones y limitaciones"),
        parrafo(
            "El proyecto confirmó dos ideas que en clase suenan teóricas. La primera es que en un "
            "grafo el costo de una consulta depende de cuánto del grafo se recorre, no de cuántas "
            "filas hay: con 131 nodos las consultas se sienten instantáneas, y el tiempo que se "
            "mide en la app es casi todo viaje de red. La segunda es que el modelo importa más "
            "que el motor: la calificación en la relación y el género como nodo hicieron que las "
            "seis consultas salieran cortas y legibles."
        ),
        parrafo(
            "También quedó claro qué resuelve el driver. Un solo objeto con pool evita pagar el "
            "handshake TLS en cada clic; <i>execute_query</i> da transacciones administradas y "
            "reintentos ante fallos transitorios; <i>en_transaccion</i> agrupa varias escrituras "
            "(crear película con sus géneros, director y actores) y un fallo a mitad de camino no "
            "deja datos a medias. Como las escrituras usan <i>MERGE</i>, un reintento no duplica "
            "nada."
        ),
        parrafo("Para llevar esto a producción faltaría:"),
        vineta(
            "<b>Identidad externa.</b> Cambiar <i>Persona.nombre</i> por un id de TMDB o IMDb y "
            "dejar el nombre como propiedad; lo mismo para las películas, con control de "
            "homónimos y de títulos que cambian según la región."
        ),
        vineta(
            "<b>Paginación.</b> El catálogo ya limita con <i>$limite</i>, pero la app carga todas "
            "las películas para los selectores; con miles de títulos habría que paginar."
        ),
        vineta(
            "<b>Caché y réplicas.</b> Las recomendaciones y el top por género se pueden cachear "
            "unos minutos y las lecturas repartirse en réplicas; Aura Free no las ofrece."
        ),
        vineta(
            "<b>Autenticación y despliegue.</b> Hoy no hay login: cualquiera que abra la app puede "
            "escribir. En producción haría falta autenticar usuarios, separar permisos de lectura "
            "y escritura y desplegar la interfaz fuera de la laptop."
        ),
        vineta(
            "<b>Operación.</b> La instancia Free se pausa tras tres días sin uso y limita a 200 "
            "mil nodos y 400 mil relaciones; para un curso sobra, para un producto no."
        ),
        parrafo(
            "Nada de esto invalida el parcial: el paradigma, el diseño y la integración con la "
            "nube están cubiertos y probados contra la instancia real."
        ),
    ]


def construir() -> Path:
    """Arma el documento completo y devuelve la ruta del PDF."""
    registrar_fuentes()
    doc = Documento(SALIDA)
    historia: list[Flowable] = []
    historia += portada()
    historia.append(NextPageTemplate("cuerpo"))
    historia.append(PageBreak())
    historia += seccion_introduccion()
    historia += seccion_justificacion()
    historia += seccion_arquitectura()
    historia += seccion_modelo()
    historia += seccion_catalogo()
    historia += seccion_conclusiones()
    doc.build(historia, canvasmaker=LienzoNumerado)
    return SALIDA


def main() -> int:
    if not FUENTES.exists():
        print("Este script necesita macOS: no encuentro /System/Library/Fonts/Supplemental")
        return 1
    ruta = construir()
    print(f"Listo: {ruta} ({ruta.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
