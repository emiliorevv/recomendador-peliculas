# Recomendador de películas con Neo4j

[![CI](https://github.com/emiliorevv/recomendador-peliculas/actions/workflows/ci.yml/badge.svg)](https://github.com/emiliorevv/recomendador-peliculas/actions/workflows/ci.yml)

Parcial de Bases de Datos Avanzadas: "Desarrollo e Integración de Aplicaciones con Bases de Datos NoSQL en la Nube".

Aplicación en Python conectada a una base de datos de **grafos** (Neo4j AuraDB, en la nube) que guarda películas, actores, directores, géneros, usuarios y sus calificaciones. Con eso recomienda películas, encuentra películas parecidas, busca el camino más corto entre dos actores y sugiere a quién seguir.

## El problema en una frase

Recomendar una película es seguir conexiones (yo califiqué esta, alguien con gustos parecidos calificó esa misma, y también le gustó otra que yo no he visto). En una base relacional cada conexión es un JOIN más, y en un grafo es solo seguir una relación. El detalle está en [docs/01-problema.md](docs/01-problema.md) y la comparación contra SQL en [docs/02-justificacion.md](docs/02-justificacion.md).

## Arquitectura

```
┌──────────────┐  HTTP  ┌─────────────────────────────────────┐  Bolt + TLS  ┌──────────────────┐
│  Navegador   │───────▶│ App en Python                       │─────────────▶│  Neo4j AuraDB    │
│  (usuario)   │        │  app.py        interfaz Streamlit   │ neo4j+s://   │  (DaaS, nube)    │
└──────────────┘        │  src/          CRUD y consultas     │              └──────────────────┘
                        │  driver oficial neo4j (pool)        │
                        │  .env          credenciales         │
                        └─────────────────────────────────────┘
```

| Pieza | Tecnología | Dónde corre | ADR |
|---|---|---|---|
| Base de datos | Neo4j AuraDB Free (grafo, Cypher) | Nube administrada por Neo4j | [0001](docs/adr/0001-grafo-neo4j-auradb.md) |
| Código de la aplicación | Python 3.12+ con el driver oficial `neo4j` | Laptop | [0002](docs/adr/0002-python-driver-oficial.md) |
| Interfaz para la demo | Streamlit | Laptop (navegador) | [0003](docs/adr/0003-interfaz-streamlit.md) |
| Credenciales | Variables de entorno en `.env` | Laptop, fuera del repo | [0004](docs/adr/0004-credenciales-variables-entorno.md) |

La base nunca corre en localhost: el enunciado lo prohíbe en la evaluación, y la app siempre se conecta a AuraDB.

## Modelo del grafo (resumen)

```
(:Usuario)-[:CALIFICO {estrellas, fecha}]->(:Pelicula)
(:Usuario)-[:SIGUE]->(:Usuario)
(:Persona)-[:ACTUO_EN]->(:Pelicula)
(:Persona)-[:DIRIGIO]->(:Pelicula)
(:Pelicula)-[:DE_GENERO]->(:Genero)
```

Propiedades, restricciones e índices en [docs/modelo-grafo.md](docs/modelo-grafo.md).

## Qué hace la aplicación

**CRUD**
- Películas: crear (con géneros, director y actores), consultar, actualizar y eliminar.
- Usuarios: crear, consultar, renombrar y eliminar.
- Calificaciones: calificar (crea o actualiza), ver las de un usuario y quitar una.
- Seguidores: seguir, dejar de seguir y ver a quién sigue cada usuario y quiénes lo siguen.

**Consultas propias del grafo** (catálogo completo en [docs/catalogo-consultas.md](docs/catalogo-consultas.md))
- Recomendación colaborativa: lo que les gustó a usuarios con gustos parecidos (recorrido de 3 saltos).
- Películas parecidas a otra por actores, director y género en común.
- Mejores películas de un género.
- Camino más corto entre dos personas (`shortestPath`, estilo "seis grados de Kevin Bacon").
- Vecindad de una persona a 1, 2 o 3 grados de separación.
- A quién seguir: amigos de mis amigos.

## Estructura del repo

```
.
├── app.py                 # interfaz Streamlit de la demo
├── pyproject.toml         # configuración de Ruff y pytest
├── requirements.txt       # dependencias de la app
├── requirements-dev.txt   # dependencias de desarrollo (pytest, Ruff)
├── src/
│   ├── conexion.py        # driver, credenciales, leer/escribir, transacciones
│   ├── peliculas.py       # CRUD de películas
│   ├── usuarios.py        # CRUD de usuarios y calificaciones
│   ├── validacion.py      # validaciones compartidas del CRUD
│   └── consultas.py       # recomendaciones, caminos y vecindad
├── seed/
│   ├── esquema.cypher     # restricciones e índices
│   ├── esquema.py         # aplica el esquema al grafo
│   └── seed.py            # carga de datos iniciales
├── data/                  # películas y usuarios en JSON
├── tests/
│   ├── conftest.py        # fixtures y guardas para no tocar la base real
│   ├── test_app.py        # compila app.py y revisa sus secciones
│   └── ...                # pytest contra un Neo4j de pruebas
├── docs/
│   ├── 01-problema.md
│   ├── 02-justificacion.md
│   ├── modelo-grafo.md
│   ├── catalogo-consultas.md
│   ├── demo-y-defensa.md
│   └── adr/
└── .github/
    ├── pull_request_template.md
    └── workflows/ci.yml   # CI con Ruff y pytest
```

## Cómo correrlo

### Requisitos

- Python 3.12 o superior.
- Una instancia de Neo4j AuraDB Free (https://console.neo4j.io).

### Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env      # y llena las credenciales que te dio Aura
```

`.env` está en `.gitignore`: las credenciales nunca se suben al repo.

### Esquema de la base

```bash
python seed/esquema.py    # restricciones e índices; se puede correr varias veces
```

### Datos iniciales

```bash
python seed/seed.py            # carga los datos de data/ sin borrar (idempotente)
python seed/seed.py --reset    # primero borra el grafo y después carga desde cero
```

Lee `data/peliculas.json` y `data/usuarios.json` y crea los nodos y relaciones con `MERGE`
(35 películas, 74 personas, 10 géneros, 12 usuarios, 95 calificaciones y 36 relaciones `SIGUE`),
así que correrlo dos veces no duplica nada. Aplica el esquema al empezar (es idempotente), así que
una instancia nueva queda lista con una sola corrida.

Al final imprime los conteos del grafo y valida según el modo:

- con `--reset` exige que los conteos coincidan **exactamente** con los JSON, porque se acaba de
  borrar todo;
- sin `--reset` solo exige que **todo lo del seed siga presente**, porque el CRUD puede haber
  agregado usuarios, calificaciones o seguidores. Sale con 0 si el seed está aplicado.

> Con `--reset` el borrado va antes del esquema: así las restricciones se crean aunque el grafo
> anterior tuviera datos que las violaran.

### Interfaz de la demo

```bash
streamlit run app.py
```

Streamlit abre la app en el navegador (http://localhost:8501) y lo primero que muestra es el
resultado real de `verificar_conexion()`: servidor, versión, base y cantidad de nodos de AuraDB. Si
la instancia no responde, la app explica el problema en pantalla en vez de romperse con un
traceback.

El recorrido de la demo, en orden, es este:

1. **Películas**: la tabla trae las 35 del seed; se busca por título (sin importar acentos ni
   mayúsculas), se abre el detalle con géneros, director y reparto, y se crea, edita o borra una
   película (el borrado pide confirmación escribiendo el id).
2. **Usuarios**: se crea un usuario, se renombra, se califica una película de 1 a 5, se quitan
   calificaciones y se sigue o deja de seguir a otro usuario, viendo siempre a quién sigue y quién
   lo sigue.
3. **Recomendaciones**: con `u01` salen las películas que le gustaron a gente con gustos parecidos;
   con `inception-2010`, las parecidas con el desglose de puntos (actores + 2 × director +
   géneros); y por género, el top de promedio y votos.
4. **Caminos**: el camino más corto entre `Tom Hanks` y `Scarlett Johansson` se muestra como cadena
   legible (`Tom Hanks → The Green Mile → Sam Rockwell → …`), la vecindad de una persona a 1, 2 o 3
   grados y a quién seguir.

Los selectores se llenan con lo que hay en el grafo y ya vienen con esos valores por defecto, así
que cada consulta muestra un resultado sin escribir nada. Cada consulta del catálogo lleva su
Cypher (tomado de `src.consultas.catalogo()`, nunca escrito en la interfaz) y los milisegundos que
tardó (`time.perf_counter`) dentro de un desplegable. Las escrituras refrescan la vista al
instante: la app no cachea datos.

> Si al conectar aparece `SSL: CERTIFICATE_VERIFY_FAILED` o `Unable to retrieve routing information`
> en macOS, al intérprete le faltan los certificados raíz. `src/conexion.py` ya apunta
> `SSL_CERT_FILE` al bundle de `certifi` cuando la variable no está definida **y** el contexto TLS
> del sistema no tiene ninguna CA, así que no hay que exportar nada; si el sistema sí tiene CAs
> (por ejemplo la de un proxy corporativo) o se define `SSL_CERT_FILE` a mano, no se toca nada.

### Demo en la nube (opcional)

La app se publica en **Streamlit Community Cloud**, que es gratis y corre Streamlit de forma nativa.
Vercel no sirve para esto (es serverless y Streamlit necesita un proceso Python con WebSockets) y
Render puede correrla, pero el plan free duerme la instancia y el arranque en frío tarda cerca de un
minuto, justo cuando se está exponiendo.

1. Entra a https://share.streamlit.io con la cuenta de GitHub del repo.
2. **New app** → repositorio `emiliorevv/recomendador-peliculas`, rama `main`, archivo `app.py`.
3. En **Advanced settings → Secrets**, pega las credenciales en formato TOML (la plantilla está en
   `.streamlit/secrets.toml.example`). Ahí no va el `.env`: la app lee `st.secrets` y lo pasa al
   driver.
4. **Deploy**.

La app puede escribir en la base, así que si queda pública cualquiera con el enlace puede crear o
borrar datos de la demo. Para la presentación conviene dejarla privada (se comparte por correo) o
correr `python seed/seed.py --reset` antes de exponer.

### Pruebas y estilo

```bash
ruff check .        # lint
ruff format --check .
pytest              # unitarias; las de integración se omiten sin base de pruebas
```

Las pruebas marcadas como `integration` necesitan un Neo4j desechable, no la instancia de AuraDB:

```bash
docker run -d --name neo4j-test -p 7687:7687 -e NEO4J_AUTH=neo4j/testpassword neo4j:5.26
until docker exec neo4j-test cypher-shell -u neo4j -p testpassword "RETURN 1" >/dev/null 2>&1; do sleep 2; done
NEO4J_TEST_URI=bolt://localhost:7687 pytest
```
