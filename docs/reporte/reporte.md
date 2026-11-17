# Recomendador de películas — diseño, justificación y catálogo

**Bases de Datos Avanzadas** · Parcial «Desarrollo e Integración de Aplicaciones con Bases
de Datos NoSQL en la Nube» · 18 de noviembre de 2026

> Versión Markdown del reporte. El PDF que se entrega es
> [`reporte.pdf`](reporte.pdf) y se genera con [`build_pdf.py`](build_pdf.py); las figuras 1
> y 2 se dibujan ahí con primitivas de reportlab (cajas, elipses y flechas), sin imágenes
> externas ni Graphviz. Este archivo es la fuente legible para revisar el texto y las
> tablas.

## 1. Introducción y dominio

Esta aplicación es una plataforma pequeña de reseñas de películas, parecida a Letterboxd:
cada usuario califica lo que vio con una a cinco estrellas, sigue a otros usuarios y
descubre qué ver después. La base de datos guarda las películas con su año y su duración,
a las personas que actuaron y dirigieron, los géneros y las relaciones entre usuarios. Todo
eso vive en un grafo, no en tablas.

El dominio se puede describir con cuatro etiquetas de nodo. **Pelicula** tiene `id`,
`titulo`, `anio` y `duracion`. **Persona** guarda el `nombre` y se usa tanto para actores
como para directores. **Genero** guarda el `nombre` del género. **Usuario** tiene `id` y
`nombre`. Las relaciones son cinco: **CALIFICO** (con `estrellas` y `fecha`), **SIGUE**,
**ACTUO_EN**, **DIRIGIO** y **DE_GENERO**. Cada una tiene una dirección y un significado
propio.

Con ese modelo, el usuario espera cuatro cosas de la plataforma:

- **Recomendaciones.** Qué ver según lo que les gustó a personas con gustos parecidos, sin
  repetir lo que ya calificó.
- **Películas parecidas.** Al ver una película, otras con el mismo director, actores o
  géneros.
- **A quién seguir.** Usuarios que siguen a la gente que él sigue.
- **Curiosidades del reparto.** Cuántos saltos hay entre dos actores, al estilo de los seis
  grados de Kevin Bacon.

Ninguna de esas funciones se responde mirando una sola fila. Todas dependen de *cómo se
conectan* los datos, y esa observación es el punto de partida de la justificación del
paradigma (§2). El alcance del parcial es deliberadamente chico: 35 películas reales, 74
personas, 10 géneros, 12 usuarios, 95 calificaciones y 36 relaciones **SIGUE**, o sea 131
nodos y 368 relaciones. Sobre esos datos corren el CRUD completo y las seis consultas de
grafo del catálogo.

El resto del documento sigue el orden del enunciado: la justificación del paradigma (§2),
la arquitectura y la integración con la nube (§3), el diseño del modelo con sus
restricciones (§4), el catálogo de las 13 consultas con resultados reales (§5) y las
conclusiones con lo que falta para producción (§6).

## 2. Justificación del paradigma

Las cuatro funciones del §1 recorren conexiones. En una base relacional cada conexión es un
JOIN más, y el número de JOINs queda escrito en la consulta: si mañana la recomendación
necesita un salto adicional, hay que reescribirla. En un grafo la conexión es una relación
de primera clase y el patrón se lee igual que el enunciado en español.

**La recomendación son tres saltos.** Yo califiqué una película, otro usuario calificó esa
misma película y también calificó otra que yo no vi. En SQL la tabla de calificaciones se
une consigo misma tres veces y hace falta una subconsulta para excluir lo ya visto:

```sql
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
```

En Cypher el mismo recorrido se escribe como el patrón que describe el problema:

```cypher
MATCH (yo:Usuario {id: $id})-[mia:CALIFICO]->(:Pelicula)<-[suya:CALIFICO]-(otro:Usuario)
WHERE otro <> yo AND mia.estrellas >= 4 AND suya.estrellas >= 4
MATCH (otro)-[otra:CALIFICO]->(recomendada:Pelicula)
WHERE otra.estrellas >= 4 AND NOT (yo)-[:CALIFICO]->(recomendada)
RETURN recomendada.titulo, count(otro) AS usuarios_parecidos
```

**El camino más corto es el caso extremo.** Entre dos actores no se sabe cuántos saltos hay,
así que en SQL hace falta una CTE recursiva (`WITH RECURSIVE`) que alterne persona y
película, lleve un arreglo de nodos visitados para no ciclarse y crezca nivel por nivel. La
forma de esa consulta es así:

```sql
-- esquema de la CTE: alterna persona y película, guarda visitados y corta a 12 saltos
WITH RECURSIVE paso (origen, tipo, id, largo, visitados) AS ( ... )
SELECT * FROM paso WHERE tipo = 'persona' AND id = :destino ORDER BY largo LIMIT 1;
```

Además de larga, esa consulta no puede buscar desde los dos extremos a la vez. Neo4j lo
resuelve con una primitiva del motor:

```cypher
MATCH (a:Persona {nombre: $origen}), (b:Persona {nombre: $destino})
MATCH camino = shortestPath((a)-[:ACTUO_EN|DIRIGIO*..12]-(b))
RETURN [n IN nodes(camino) | coalesce(n.nombre, n.titulo)] AS camino,
       length(camino) AS saltos
```

**Index-free adjacency.** En un motor relacional, cada JOIN busca en el índice de toda la
tabla las filas que coinciden; el costo depende del tamaño de la tabla y se repite en cada
salto. En Neo4j cada nodo guarda apuntadores directos a sus relaciones, así que pasar de un
nodo a su vecino no consulta ninguna estructura global: el costo depende de cuántos nodos se
visitan, no de cuántos hay en total. Los índices sirven para encontrar el nodo de partida (el
usuario, la película) y después el recorrido avanza por los apuntadores.

**Las relaciones son datos.** La calificación no es una fila intermedia sin significado: es
la relación entre un usuario y una película, y sus estrellas y su fecha viven en ella. En SQL
eso obliga a una tabla puente; en el grafo es la relación misma, y por eso se puede escribir
una propiedad sin tocar el resto del esquema.

**¿Y una base clave-valor?** Redis o DynamoDB son excelentes para leer o escribir un dato por
su llave: una sesión, un carrito, una caché. Aquí casi nada se consulta por llave; casi todo
es recorrer. En clave-valor habría que guardar listas de vecinos a mano (por ejemplo un
conjunto `pelicula:123:actores`) y hacer los recorridos en el código de la aplicación, con un
viaje de red por salto. El grafo hace ese trabajo en el motor, en una sola consulta.

| Criterio | SQL | Clave-valor | Grafo (Neo4j) |
|---|---|---|---|
| Recomendación (3 saltos) | 3 JOINs + subconsulta | Varios viajes de red y lógica en la app | Un patrón `MATCH` |
| Camino más corto | `WITH RECURSIVE` complejo | No aplica | `shortestPath` |
| Costo por salto | Crece con el tamaño de la tabla | Un viaje de red por salto | Constante por vecino |
| Agregar un tipo de relación | Nueva tabla y migración | Nuevas llaves a mano | Nueva relación, sin migrar |
| Reportes agregados | Muy bueno | Malo | Aceptable |

**Dónde SQL sería mejor.** Para reportes con sumas y agrupaciones sobre toda la base, o para
datos muy tabulares con transacciones entre muchas tablas, un motor relacional es la
herramienta correcta. Tampoco hay que exagerar: con 35 películas una base relacional responde
perfecto y hasta sería más simple de operar. La decisión no se apoya en el volumen de hoy sino
en la forma de las consultas y en cómo crecen: los recorridos son el corazón del producto, y
en un grafo se expresan sin reescribir JOINs ni mantener tablas de caminos precalculados.

## 3. Arquitectura

La aplicación corre en la laptop y la base de datos corre en la nube. El navegador habla con
la interfaz Streamlit por HTTP local; la interfaz llama a los módulos de `src/`, que usan un
único driver oficial de Neo4j; el driver abre conexiones cifradas por Bolt contra la instancia
de AuraDB.

```
┌────────────┐  HTTP   ┌──────────────────────────┐  Bolt + TLS  ┌─────────────────┐
│ Navegador  │────────▶│ Aplicación Python        │─────────────▶│ Neo4j AuraDB    │
│ (usuario)  │         │  app.py     Streamlit    │  neo4j+s://  │ DaaS en la nube │
└────────────┘         │  src/       CRUD y cons. │              │ Cypher · grafo  │
                       │  conexion   driver+pool  │              │ TLS obligatorio │
                       │  .env       credenciales │              └─────────────────┘
                       └──────────────────────────┘
```

**Figura 1.** Arquitectura por bloques. La app y la base no comparten máquina: lo único que
viaja entre ellas es Bolt sobre TLS, con las credenciales del archivo `.env`.

**Capas.** La presentación es `app.py`, un solo archivo Streamlit con cuatro secciones
(películas, usuarios, recomendaciones y caminos). La lógica de dominio está en
`src/peliculas.py`, `src/usuarios.py`, `src/consultas.py` y `src/validacion.py`; ahí viven las
validaciones y las consultas, no en la interfaz. El acceso a datos está concentrado en
`src/conexion.py`, que expone `leer`, `escribir`, `en_transaccion` y `verificar_conexion`.
Nadie más crea un driver ni arma una sesión. El almacenamiento es Neo4j AuraDB Free.

**Un driver, un pool.** El driver se crea la primera vez que se usa y se reutiliza durante
toda la vida del proceso; un candado evita que dos hilos de Streamlit creen dos drivers a la
vez. Cada consulta pasa por `driver.execute_query()`, que la ejecuta en una transacción
administrada, reintenta ante errores transitorios y reutiliza conexiones del pool. Las lecturas
se marcan con `routing_=READ` y las escrituras con `routing_=WRITE`, para que el enrutamiento
del clúster elija el servidor correcto.

**Por qué la base no corre en localhost.** El enunciado pide una base NoSQL administrada en la
nube, y la rúbrica evalúa esa integración. Tenerla en AuraDB implica que el respaldo, el
parcheo y el cifrado en reposo los maneja el proveedor, que la conexión va cifrada con
`neo4j+s://` y que la instancia es la misma que ve el profesor desde la consola de Neo4j. Un
Neo4j en Docker solo se usa en las pruebas de integración del CI, contra una base desechable,
nunca en la app.

**Credenciales y TLS.** La URI, el usuario y la contraseña se leen de variables de entorno
cargadas desde `.env` con `python-dotenv`. El archivo está en `.gitignore`, el repo trae un
`.env.example` sin valores y el código no imprime ni registra la contraseña ni la URI. Si falta
una variable, la app falla al iniciar con un mensaje que nombra la que falta en vez de intentar
conectarse. En macOS, cuando el intérprete no tiene certificados raíz, `src/conexion.py` apunta
`SSL_CERT_FILE` al bundle de `certifi`; solo lo hace si la variable no está definida y el
contexto TLS del sistema no trae ninguna CA, para no romper una red con proxy corporativo.

| Pieza | Tecnología | Dónde corre | ADR |
|---|---|---|---|
| Base de datos | Neo4j AuraDB Free (grafo, Cypher) | Nube de Neo4j | 0001 |
| Aplicación | Python 3.12+ y driver oficial neo4j 5.x | Laptop | 0002 |
| Interfaz | Streamlit | Laptop (navegador) | 0003 |
| Credenciales | Variables de entorno en `.env` | Laptop, fuera del repo | 0004 |

## 4. Diseño del modelo

El grafo tiene cuatro etiquetas y cinco tipos de relación. La figura 2 del PDF muestra las
etiquetas con sus propiedades, las relaciones con su dirección y las propiedades que viven en
la relación de calificación.

| Etiqueta | Propiedades | Llave única | Notas |
|---|---|---|---|
| Pelicula | id, titulo, anio, duracion (min) | id | id = título y año en minúsculas, ej. `inception-2010` |
| Persona | nombre | nombre | Actores y directores en la misma etiqueta |
| Genero | nombre | nombre | Nodo y no propiedad, para poder recorrer por género |
| Usuario | id, nombre | id | id = `u01`, `u02`… |

| Relación | Dirección | Propiedades | Significado |
|---|---|---|---|
| CALIFICO | Usuario → Pelicula | estrellas (1–5), fecha | La calificación le pertenece a la pareja usuario-película |
| SIGUE | Usuario → Usuario | — | Red social |
| ACTUO_EN | Persona → Pelicula | — | Papel de actor |
| DIRIGIO | Persona → Pelicula | — | Papel de director |
| DE_GENERO | Pelicula → Genero | — | Clasificación por género |

Las restricciones de unicidad hacen dos cosas: impiden duplicados y crean el índice que usa
cada `MATCH` para encontrar el nodo de partida. El índice sobre el título sirve para listar y
buscar sin recorrer todas las películas. Todas las sentencias llevan `IF NOT EXISTS`, así que
el esquema se puede aplicar dos veces sin error.

```cypher
CREATE CONSTRAINT pelicula_id    IF NOT EXISTS FOR (p:Pelicula) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT usuario_id     IF NOT EXISTS FOR (u:Usuario)  REQUIRE u.id IS UNIQUE;
CREATE CONSTRAINT persona_nombre IF NOT EXISTS FOR (p:Persona)  REQUIRE p.nombre IS UNIQUE;
CREATE CONSTRAINT genero_nombre  IF NOT EXISTS FOR (g:Genero)   REQUIRE g.nombre IS UNIQUE;
CREATE INDEX pelicula_titulo     IF NOT EXISTS FOR (p:Pelicula) ON (p.titulo);
```

**La calificación vive en la relación.** Una calificación no existe sin un usuario y una
película: es la pareja. Ponerla en la relación permite guardar propiedades (`estrellas`,
`fecha`) y actualizarla con `MERGE … SET` sin crear una fila puente ni duplicar nada. Además,
el patrón `(u)-[c:CALIFICO]->(p)` se lee como la frase «u calificó p», y las consultas de
recomendación pueden filtrar por las estrellas de la relación en cada salto.

**El género es un nodo.** Si el género fuera una propiedad de la película (o una lista de
textos) no se podría recorrer hacia él: «las mejores de Drama» exigiría buscar en listas y no
habría un nodo por el que entrar. Como nodo compartido, `DE_GENERO` conecta muchas películas
con un género y la consulta empieza por `(:Genero {nombre: $genero})`, que además tiene índice
único. Lo mismo vale para los géneros nuevos: crearlos es un `MERGE`, no una migración.

**Persona es una sola etiqueta.** Una persona puede actuar y dirigir (Clint Eastwood, por
ejemplo), así que separar `Actor` y `Director` duplicaría el nodo y rompería el camino entre
personas: el recorrido `ACTUO_EN|DIRIGIO` funciona justamente porque ambos papeles llegan al
mismo tipo de nodo. La diferencia está en la relación, no en la etiqueta.

**Ids slug y dirección explícita.** El id de una película se deriva del título y el año
(«Batman Begins», 2005 → `batman-begins-2005`): es legible en la consola, estable y
determinista, y no cambia cuando se edita la película, porque las calificaciones lo
referencian. Los usuarios usan `u01`, `u02`… Todas las relaciones tienen dirección; las
consultas de camino las recorren sin dirección porque el patrón va de persona a película y de
película a persona.

**La llave de Persona es el nombre, y en producción no lo sería.** En este parcial alcanza: 74
personas, nombres únicos, y la restricción de unicidad lo garantiza. Pero dos actores pueden
llamarse igual y un nombre puede cambiar (o escribirse distinto según la fuente), así que en
producción la llave sería un id externo de TMDB o IMDb y `nombre` quedaría como propiedad. Es
una limitación consciente, no un olvido, y se retoma en §6.

## 5. Catálogo de consultas

El catálogo tiene 13 consultas: el esquema, las siete operaciones de CRUD y las seis consultas
propias del grafo. Todas usan parámetros (`$id`, `$nombre`, `$limite`); el texto que llega
desde la interfaz nunca se pega en el Cypher. Esta sección reproduce el Cypher exacto que
corre la app y los resultados reales contra AuraDB después de `python seed/seed.py --reset`.

| # | Consulta | Tipo | Dónde |
|---|---|---|---|
| 1 | Restricciones e índices | Esquema | `seed/esquema.cypher` |
| 2 | Crear película con géneros, director y actores | CRUD (C) | `src/peliculas.py` |
| 3 | Listar y ver detalle de película | CRUD (R) | `src/peliculas.py` |
| 4 | Actualizar película y sus géneros | CRUD (U) | `src/peliculas.py` |
| 5 | Eliminar película (`DETACH DELETE`) | CRUD (D) | `src/peliculas.py` |
| 6 | Crear, listar, renombrar y eliminar usuario | CRUD | `src/usuarios.py` |
| 7 | Calificar y quitar calificación | CRUD | `src/usuarios.py` |
| 8 | Recomendación colaborativa | Recorrido (3 saltos) | `src/consultas.py` |
| 9 | Películas parecidas | Vecindad + puntaje | `src/consultas.py` |
| 10 | Top por género | Agregación | `src/consultas.py` |
| 11 | Camino más corto entre personas | Camino | `src/consultas.py` |
| 12 | Vecindad de una persona a N grados | Vecindad | `src/consultas.py` |
| 13 | A quién seguir | Recorrido | `src/consultas.py` |

Los tiempos se midieron con `time.perf_counter` en la app, contra AuraDB. Incluyen el viaje
por red desde la laptop, por eso el rango es de cientos de milisegundos y no de milisegundos:
en el servidor cada consulta tarda una fracción de eso.

| Consulta | Tiempo típico |
|---|---|
| 8. Recomendación colaborativa | 340 ms |
| 9. Películas parecidas | 410 ms |
| 10. Top por género | 310 ms |
| 11. Camino más corto | 560 ms |
| 12. Vecindad a 2 grados | 300 ms |
| 13. A quién seguir | 280 ms |

### 5.1 Esquema y CRUD

Las consultas 1 a 7 están documentadas con su Cypher en
[`catalogo-consultas.md`](../catalogo-consultas.md). Dos decisiones se ven en el código: crear
una película escribe en una sola transacción (película, géneros, director y actores), y
calificar usa `MERGE`, así que la segunda llamada actualiza en vez de duplicar.

```cypher
MATCH (u:Usuario {id: $usuario})
MATCH (p:Pelicula {id: $pelicula})
MERGE (u)-[c:CALIFICO]->(p)
SET c.estrellas = $estrellas, c.fecha = $fecha
RETURN p.id AS pelicula_id, p.titulo AS titulo, c.estrellas AS estrellas, c.fecha AS fecha
```

Las escrituras que van juntas usan `en_transaccion`, que corre la función en una transacción
administrada: si una sentencia falla, el commit no ocurre y no queda una película a medias. Las
lecturas van con `routing_=READ`.

### 5.2 Recomendación colaborativa

Gustos parecidos son los usuarios que calificaron con 4 o 5 estrellas una película que al
usuario también le gustó. El `WITH DISTINCT yo, otro` deja un solo registro por usuario
parecido, así `count(otro)` no se pondera por las películas en común; el `NOT` excluye todo lo
que el usuario ya calificó, con cualquier puntaje. Se agrupa por nodo y no por título para que
dos películas homónimas no se mezclen.

```cypher
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
```

| Película | Usuarios parecidos | Promedio |
|---|---|---|
| Oppenheimer | 3 | 4.33 |
| Toy Story | 2 | 5.0 |
| Eternal Sunshine of the Spotless Mind | 2 | 4.5 |
| Iron Man | 2 | 4.5 |
| La La Land | 2 | 4.0 |

Resultado real para `u01` (las cinco primeras de diez), 340 ms.

### 5.3 Películas parecidas

Compara la película base con todas las demás usando tres subconsultas `COUNT { }`, que cuentan
sin multiplicar filas como harían tres `MATCH` encadenados. El puntaje es actores en común +
2 × mismo director + géneros en común; compartir director pesa el doble. Las películas con
puntaje 0 se descartan, y el resultado trae el desglose para que la app explique el porqué.

```cypher
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
```

| Película | Puntos | Actores | Director | Géneros |
|---|---|---|---|---|
| The Dark Knight Rises | 6 | 2 | 1 | 2 |
| The Dark Knight | 5 | 1 | 1 | 2 |
| Batman Begins | 4 | 1 | 1 | 1 |
| Captain America: The Winter Soldier | 3 | 0 | 0 | 3 |
| Interstellar | 3 | 0 | 1 | 1 |

Resultado real para `inception-2010`, 410 ms.

### 5.4 Top por género

Ordena por promedio descendente y desempata por votos y después por título, para que dos
corridas den lo mismo. Solo entran películas con al menos una calificación: sin votos no hay
promedio. El promedio va redondeado a dos decimales y se devuelve el conteo para que la app
muestre «4.67 (3 votos)».

```cypher
MATCH (p:Pelicula)-[:DE_GENERO]->(:Genero {nombre: $genero})
MATCH (p)<-[c:CALIFICO]-(:Usuario)
RETURN p.id AS pelicula_id,
       p.titulo AS titulo,
       round(avg(c.estrellas), 2) AS promedio,
       count(c) AS votos
ORDER BY promedio DESC, votos DESC, titulo, pelicula_id
LIMIT $limite
```

| Película | Promedio | Votos |
|---|---|---|
| Pulp Fiction | 4.67 | 3 |
| The Green Mile | 4.67 | 3 |
| Titanic | 4.67 | 3 |

Resultado real para `Drama` con límite 3, 310 ms.

### 5.5 Camino más corto entre personas

El patrón está restringido a `ACTUO_EN` y `DIRIGIO`, así que no puede escaparse por los
géneros, y el tope `*..12` solo acota la búsqueda. Doce saltos son seis películas y cinco
personas intermedias; si origen y destino son la misma persona se devuelve 0 saltos sin
consultar, porque `shortestPath` no admite extremos iguales. Si no hay camino, la respuesta es
`encontrado: false`, no una excepción.

```cypher
MATCH (a:Persona {nombre: $origen}), (b:Persona {nombre: $destino})
MATCH camino = shortestPath((a)-[:ACTUO_EN|DIRIGIO*..12]-(b))
RETURN [n IN nodes(camino) | coalesce(n.nombre, n.titulo)] AS camino,
       length(camino) AS saltos
```

Resultado real para Tom Hanks → Scarlett Johansson, 4 saltos y 560 ms:

```text
Tom Hanks → The Green Mile → Sam Rockwell → Jojo Rabbit → Scarlett Johansson
```

### 5.6 Vecindad de una persona a N grados

En este grafo las personas solo se tocan a través de una película, así que un grado de
separación son dos saltos. Hay una variante por grado (`*2..2`, `*2..4`, `*2..6`) para no
enumerar caminos más largos de lo pedido; `min(length(ruta))` se queda con la distancia más
corta cuando una persona se alcanza por varios caminos. `grados` se valida como entero de 1 a
3.

```cypher
MATCH (a:Persona {nombre: $nombre})
MATCH ruta = (a)-[:ACTUO_EN|DIRIGIO*2..4]-(otra:Persona)
WHERE otra <> a
WITH otra, min(length(ruta)) AS saltos
RETURN otra.nombre AS persona, saltos / 2 AS distancia
ORDER BY distancia, persona
LIMIT $limite
```

| Persona | Distancia |
|---|---|
| Don Rickles | 1 |
| Frank Darabont | 1 |
| John Lasseter | 1 |
| Lee Unkrich | 1 |
| Michael Clarke Duncan | 1 |
| Sam Rockwell | 1 |
| Tim Allen | 1 |
| Scarlett Johansson | 2 |
| Taika Waititi | 2 |

Resultado real para Tom Hanks con `grados = 2`, 300 ms. Con `grados = 1` salen solo las siete
personas de distancia 1.

### 5.7 A quién seguir

Busca amigos de mis amigos, excluye al propio usuario y a quien ya sigue, y cuenta los amigos
en común con `count(DISTINCT amigo)`. Es la misma forma de recorrido de tres nodos que la
recomendación, pero sobre usuarios en lugar de películas.

```cypher
MATCH (yo:Usuario {id: $id})-[:SIGUE]->(amigo:Usuario)-[:SIGUE]->(sugerido:Usuario)
WHERE sugerido <> yo AND NOT (yo)-[:SIGUE]->(sugerido)
WITH sugerido, count(DISTINCT amigo) AS amigos_en_comun
RETURN sugerido.id AS usuario_id,
       sugerido.nombre AS nombre,
       amigos_en_comun
ORDER BY amigos_en_comun DESC, nombre, usuario_id
LIMIT $limite
```

| usuario_id | Nombre | Amigos en común |
|---|---|---|
| u05 | Elena | 2 |
| u06 | Fabián | 2 |
| u08 | Hugo | 2 |
| u09 | Irene | 2 |
| u10 | Javier | 2 |

Resultado real para `u01`, 280 ms. `u01` sigue a `u02`, `u03`, `u04` y `u07`; ninguno de esos
cuatro aparece en la lista, y tampoco él mismo.

## 6. Conclusiones y limitaciones

El proyecto confirmó dos ideas que en clase suenan teóricas. La primera es que en un grafo el
costo de una consulta depende de cuánto del grafo se recorre, no de cuántas filas hay: con 131
nodos las consultas se sienten instantáneas, y el tiempo que se mide en la app es casi todo
viaje de red. La segunda es que el modelo importa más que el motor: la calificación en la
relación y el género como nodo hicieron que las seis consultas salieran cortas y legibles.

También quedó claro qué resuelve el driver. Un solo objeto con pool evita pagar el handshake
TLS en cada clic; `execute_query` da transacciones administradas y reintentos ante fallos
transitorios; `en_transaccion` agrupa varias escrituras (crear película con sus géneros,
director y actores) y un fallo a mitad de camino no deja datos a medias. Como las escrituras
usan `MERGE`, un reintento no duplica nada.

Para llevar esto a producción faltaría:

- **Identidad externa.** Cambiar `Persona.nombre` por un id de TMDB o IMDb y dejar el nombre
  como propiedad; lo mismo para las películas, con control de homónimos y de títulos que
  cambian según la región.
- **Paginación.** El catálogo ya limita con `$limite`, pero la app carga todas las películas
  para los selectores; con miles de títulos habría que paginar.
- **Caché y réplicas.** Las recomendaciones y el top por género se pueden cachear unos minutos
  y las lecturas repartirse en réplicas; Aura Free no las ofrece.
- **Autenticación y despliegue.** Hoy no hay login: cualquiera que abra la app puede escribir.
  En producción haría falta autenticar usuarios, separar permisos de lectura y escritura y
  desplegar la interfaz fuera de la laptop.
- **Operación.** La instancia Free se pausa tras tres días sin uso y limita a 200 mil nodos y
  400 mil relaciones; para un curso sobra, para un producto no.

Nada de esto invalida el parcial: el paradigma, el diseño y la integración con la nube están
cubiertos y probados contra la instancia real.
