# Recomendador de películas con Neo4j

[![CI](https://github.com/emiliorevv/recomendador-peliculas/actions/workflows/ci.yml/badge.svg)](https://github.com/emiliorevv/recomendador-peliculas/actions/workflows/ci.yml)

Parcial de Bases de Datos Avanzadas: "Desarrollo e Integración de Aplicaciones con Bases de Datos NoSQL en la Nube". Entrega y exposición: miércoles 18 de noviembre.

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

**Consultas propias del grafo** (catálogo completo en [docs/catalogo-consultas.md](docs/catalogo-consultas.md))
- Recomendación colaborativa: lo que les gustó a usuarios con gustos parecidos (recorrido de 3 saltos).
- Películas parecidas a otra por actores, director y género en común.
- Mejores películas de un género.
- Camino más corto entre dos personas (`shortestPath`, estilo "seis grados de Kevin Bacon").
- Vecindad de una persona a 1, 2 o 3 grados de separación.
- A quién seguir: amigos de mis amigos.

## Plan de trabajo por PRs

Cada PR es una rama desde `main`, chica y revisable, y se mergea antes de empezar la siguiente si depende de ella. Las tareas se marcan aquí cuando el PR se mergea.

| # | Rama | Qué entrega | Criterio de la rúbrica |
|---|---|---|---|
| 1 | `docs/planeacion` | Este README, problema, justificación, modelo del grafo, ADRs, plantilla de PR | Justificación (15), Documentación (20) |
| 2 | `chore/ci` | `pyproject.toml` con Ruff y pytest, `requirements*.txt`, workflow de GitHub Actions con un Neo4j de pruebas y fixtures de pytest | Código (25) |
| 3 | `feat/conexion-esquema` | `src/conexion.py` (driver único, credenciales del `.env`, lectura/escritura), restricciones e índices, prueba de conexión a AuraDB | Código e integración cloud (25), Diseño (20) |
| 4 | `feat/seed` | Datos iniciales en `data/` y `seed/seed.py` (con `--reset`, sin duplicar con `MERGE`) | Entregable B (seeding script) |
| 5 | `feat/crud` | CRUD de películas, usuarios, calificaciones y seguidores + pruebas | CRUD obligatorio |
| 6 | `feat/consultas` | Recomendación colaborativa, películas parecidas, top por género, camino más corto, vecindad y a quién seguir + pruebas | Consultas del paradigma |
| 7 | `feat/app-streamlit` | Interfaz con secciones de CRUD, recomendaciones y caminos; muestra el Cypher y el tiempo de respuesta | Demo en vivo (20) |
| 8 | `docs/reporte` | PDF de diseño y justificación (5 secciones del enunciado) y guion de demo y defensa | Documentación (20), Exposición (20) |

## Entregables del enunciado

- [ ] **A. PDF** con: introducción y dominio, justificación del paradigma, arquitectura (diagrama de bloques), diseño del modelo (diagrama del grafo con etiquetas, propiedades y relaciones con dirección) y catálogo de consultas. Fuente en `docs/reporte/` (PR 8).
- [ ] **B. Código** en este repo: modular y documentado, README con requisitos, instalación y ejecución, y script de seed (PRs 2 a 7).
- [ ] **Demo** de 4 minutos conectada a AuraDB y **defensa** de 4 a 6 minutos ([docs/demo-y-defensa.md](docs/demo-y-defensa.md), PR 8).

## Estructura del repo

```
.
├── app.py                 # interfaz Streamlit (PR 7)
├── pyproject.toml         # configuración de Ruff y pytest
├── requirements.txt       # dependencias de la app
├── requirements-dev.txt   # dependencias de desarrollo (pytest, Ruff)
├── src/
│   ├── conexion.py        # driver, credenciales, leer/escribir (PR 3)
│   ├── peliculas.py       # CRUD de películas (PR 5)
│   ├── usuarios.py        # CRUD de usuarios y calificaciones (PR 5)
│   └── consultas.py       # recomendaciones, caminos y vecindad (PR 6)
├── seed/
│   ├── esquema.cypher     # restricciones e índices (PR 3)
│   ├── esquema.py         # aplica el esquema al grafo (PR 3)
│   └── seed.py            # carga de datos iniciales (PR 4)
├── data/                  # películas y usuarios en JSON (PR 4)
├── tests/
│   ├── conftest.py        # fixtures y guardas para no tocar la base real
│   └── ...                # pytest contra un Neo4j de pruebas
├── docs/
│   ├── 01-problema.md
│   ├── 02-justificacion.md
│   ├── modelo-grafo.md
│   ├── catalogo-consultas.md
│   ├── demo-y-defensa.md
│   ├── adr/
│   └── reporte/           # fuente y PDF final
└── .github/
    ├── pull_request_template.md
    └── workflows/ci.yml   # PR 2
```

## Cómo trabajamos

- `main` siempre funciona. No se hace push directo: todo entra por PR.
- Ramas con prefijo por tipo: `docs/`, `chore/`, `feat/`, `fix/`.
- Commits con [Conventional Commits](https://www.conventionalcommits.org/es/): `feat(consultas): camino más corto entre personas`.
- Cada PR llena la plantilla, pasa el CI (Ruff y pytest) y se revisa antes del merge.
- Las decisiones de diseño van en un ADR; un ADR aceptado no se edita, se reemplaza con uno nuevo.
- Todas las consultas usan parámetros (`$id`), nunca texto pegado en el Cypher.
- Las credenciales solo viven en `.env`. El repo trae `.env.example` sin valores.
- **Terminado** = mergeado en `main` y probado contra la instancia de AuraDB.

## Cómo correrlo

> La interfaz de la app se completa en el PR 7.

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
así que correrlo dos veces no duplica nada. Al final imprime los conteos del grafo y falla con un
mensaje claro si no coinciden con los esperados.

> Se aplica el esquema primero: las restricciones de unicidad son las que respaldan el `MERGE`.

> Si al conectar aparece `SSL: CERTIFICATE_VERIFY_FAILED` o `Unable to retrieve routing information`
> en macOS, al intérprete le faltan los certificados raíz: corre `Install Certificates.command` del
> instalador de Python o exporta `SSL_CERT_FILE=$(python -c "import certifi;print(certifi.where())")`.

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
