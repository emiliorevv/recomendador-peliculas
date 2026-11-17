# Guion de demo y defensa

Demo de 4 minutos y defensa de 4 a 6 minutos del recomendador sobre Neo4j AuraDB.
Todo lo que se dice aquí está respaldado por el código de `src/`, por
[demo-resultados.md](demo-resultados.md) y por el reporte
[reporte/reporte.pdf](reporte/reporte.pdf).

## Antes de empezar (10 minutos antes)

- [ ] Abrir <https://console.neo4j.io> y confirmar que la instancia está **encendida**
      (Aura Free se pausa tras 3 días sin uso; despertarla tarda un minuto).
- [ ] `source .venv/bin/activate` y `streamlit run app.py`; dejar la pestaña abierta
      y la ventana del navegador en pantalla completa.
- [ ] Confirmar que la línea de estado dice «Conectado a Neo4j Kernel 5.27-aura · base
      79af95ef · 131 nodos en el grafo». Si dice otra cosa, revisar el `.env`.
- [ ] Tener a mano `docs/demo-resultados.md` por si falla la red (plan B).
- [ ] **No** correr `seed/seed.py --reset` durante la demo: borra lo que se cree en vivo.
- [ ] Tener escritos los datos de la película que se va a crear (abajo) para no improvisar.

## Guion de 4 minutos

| Tiempo | Qué se muestra | Qué se dice mientras se hace clic |
|---|---|---|
| 0:00–0:15 | App abierta, título y línea de estado | «Streamlit corre en la laptop; la base es Neo4j AuraDB, en la nube. No hay datos locales ni caché en medio.» |
| 0:15–0:35 | Línea «Conectado a … 131 nodos» | «Lo primero que hace la app es preguntarle al servidor versión, base y cantidad de nodos. Eso confirma que el driver está conectado a Aura, no a un Neo4j local.» |
| 0:35–1:20 | Películas → **Agregar** → alta de *The Prestige* | «Creo una película que no está en el seed: 2006, 130 minutos, Drama y Suspenso, director Christopher Nolan y cuatro actores. El id se deriva del título y el año: `the-prestige-2006`.» |
| 1:20–1:45 | Usuarios → **Calificaciones** → u01, *The Prestige*, 5 estrellas | «La calificación no es un nodo: es la relación `CALIFICO` con estrellas y fecha. Si la califico otra vez se actualiza, no se duplica: es un `MERGE`.» |
| 1:45–2:30 | Recomendaciones → **Recomendación colaborativa** → u01 | «Tres saltos: yo califiqué una película, otro usuario también, y a él le gustó otra que yo no vi. Oppenheimer encabeza con 3 usuarios parecidos y 4.33. En SQL serían tres JOINs y una subconsulta.» |
| 2:30–3:05 | Recomendaciones → **Películas parecidas** → Inception | «El puntaje suma actores, dos por director y uno por género. The Dark Knight Rises saca 6. Y miren: The Prestige, la que acabo de crear, ya aparece con 4 porque comparte a Michael Caine, a Nolan y Suspenso.» |
| 3:05–3:40 | Caminos → **Camino más corto** → Tom Hanks → Scarlett Johansson | «Cuatro saltos: Tom Hanks → The Green Mile → Sam Rockwell → Jojo Rabbit → Scarlett Johansson. Es `shortestPath` con tope de 12; en SQL sería una CTE recursiva con visitados.» |
| 3:40–4:00 | Caminos → **A quién seguir** → u01 | «Amigos de mis amigos: Elena, Fabián, Hugo, Irene y Javier, todos con 2 amigos en común, y ninguno de los que ya sigo. Todo esto se leyó del grafo en vivo.» |

### 0:00–0:35 · Abrir y comprobar la conexión

- Se abre el navegador en la app ya corriendo.
- La app llama a `verificar_conexion()`: `dbms.components()`, `db.info()` y
  `MATCH (n) RETURN count(n)`.
- **Qué se ve:** la línea de estado con el servidor, la versión, el id de la base y
  131 nodos.
- **Qué se dice:** «Si Aura estuviera caída o el `.env` estuviera mal, aquí saldría un
  error que nombra la variable que falta; la app no arranca a ciegas.»

### 0:35–1:20 · Crear una película

En **Películas → Agregar**:

| Campo | Valor |
|---|---|
| Título | `The Prestige` |
| Año | 2006 |
| Duración | 130 |
| Géneros | Drama, Suspenso |
| Director | Christopher Nolan |
| Actores | Christian Bale, Hugh Jackman, Michael Caine, Scarlett Johansson |

- **Qué se ve:** «Se agregó The Prestige (2006) en N ms» y la tabla ya la incluye.
- **Qué se dice:** «Son cuatro escrituras —película, géneros, director y actores— en
  una sola transacción. Si algo falla, no queda una película sin reparto. Los géneros
  y tres de los actores ya existían; el `MERGE` solo crea a Hugh Jackman, que es el
  único nuevo.»
- **Detalle para la defensa:** el grafo pasa de 131 nodos a 133 y las relaciones
  crecen con la película, sus 2 géneros, el director, 4 actores y la calificación.

### 1:20–1:45 · Calificarla

En **Usuarios → Calificaciones**, usuario `u01`, película *The Prestige*, 5 estrellas,
botón **Calificar o actualizar**.

- **Qué se ve:** la calificación en la tabla de u01 con la fecha de hoy.
- **Qué se dice:** «La relación `CALIFICO` guarda `estrellas` y `fecha`. Un nodo
  `Calificacion` sería una tabla puente disfrazada; en el grafo la relación ya es la
  pareja usuario-película.»
- **Truco si preguntan:** volver a calificar con 4 estrellas y mostrar que sigue
  habiendo **una** fila, con 4.

### 1:45–2:30 · Recomendación colaborativa de u01

**Recomendaciones → Recomendación colaborativa**, usuario `u01`, límite 10.

| Película | Usuarios parecidos | Promedio |
|---|---|---|
| Oppenheimer | 3 | 4.33 |
| Toy Story | 2 | 5.0 |
| Eternal Sunshine of the Spotless Mind | 2 | 4.5 |
| Iron Man | 2 | 4.5 |
| La La Land | 2 | 4.0 |

- Abrir el expander **«Ver el Cypher ejecutado · 340 ms»** y dejar el Cypher en
  pantalla mientras se habla.
- **Qué se dice:** «El `WITH DISTINCT yo, otro` deja un registro por usuario parecido,
  así no se pondera el que comparte más películas conmigo. El `NOT` excluye todo lo
  que ya califiqué, aunque le haya puesto una estrella. Y por eso The Prestige no
  aparece: ya la vi.»
- **Números:** 35 películas y 95 calificaciones; la consulta tarda cientos de
  milisegundos, casi todo viaje de red.

### 2:30–3:05 · Películas parecidas a Inception

**Recomendaciones → Películas parecidas**, película base *Inception* (2010).

| Película | Puntos | Actores | Director | Géneros |
|---|---|---|---|---|
| The Dark Knight Rises | 6 | 2 | 1 | 2 |
| The Dark Knight | 5 | 1 | 1 | 2 |
| Batman Begins | 4 | 1 | 1 | 1 |
| The Prestige | 4 | 1 | 1 | 1 |
| Captain America: The Winter Soldier | 3 | 0 | 0 | 3 |

- **Qué se dice:** «El puntaje es actores en común + 2 × director + géneros. Uso
  `COUNT { }`, que cuenta sin multiplicar filas como harían tres `MATCH` encadenados.
  The Prestige entra con 4 por Michael Caine, Nolan y Suspenso: la consulta no lee una
  lista fija, lee el grafo que acabo de modificar.»
- **Qué se ve:** el expander con el Cypher y **410 ms**.

### 3:05–3:40 · Camino Tom Hanks → Scarlett Johansson

**Caminos → Camino más corto entre personas**, origen *Tom Hanks*, destino *Scarlett
Johansson*.

- **Qué se ve:** `Tom Hanks → The Green Mile → Sam Rockwell → Jojo Rabbit → Scarlett
  Johansson`, **4 saltos**, y el expander con `shortestPath` y **560 ms**.
- **Qué se dice:** «El patrón solo permite `ACTUO_EN` y `DIRIGIO`, así que no se escapa
  por los géneros. El tope `*..12` son seis películas y cinco personas intermedias: la
  idea de los seis grados. `shortestPath` busca desde los dos extremos a la vez; una CTE
  recursiva tendría que llevar los visitados y crecer nivel por nivel.»

### 3:40–4:00 · A quién seguir desde u01

**Caminos → A quién seguir**, usuario `u01`.

| Usuario | Amigos en común |
|---|---|
| u05 Elena | 2 |
| u06 Fabián | 2 |
| u08 Hugo | 2 |
| u09 Irene | 2 |
| u10 Javier | 2 |

- **Qué se dice:** «Amigos de amigos, sin contarme a mí ni a los que ya sigo. Es el
  mismo recorrido de tres nodos que la recomendación, pero entre usuarios. 280 ms y
  cierro.»

### Plan B si algo falla

| Falla | Qué hacer |
|---|---|
| Aura pausada | Abrir la consola, despertar la instancia y esperar ~1 min. Mientras tanto, explicar el modelo con el PDF. |
| Sin red | Mostrar `docs/demo-resultados.md` y el reporte; decir que son las mismas consultas contra la misma base, con la salida real. |
| Credenciales malas | La app muestra el error y nombra la variable; revisar `.env` y reiniciar Streamlit. |
| Se creó una película mal | **Películas → Eliminar**, escribir el id para confirmar; `DETACH DELETE` se lleva sus relaciones. |

## Defensa (4–6 minutos)

### 1. ¿Por qué un solo driver y con pool?

Porque crear un driver abre el handshake TLS y el pool contra Aura, y eso cuesta
cientos de milisegundos. `src/conexion.py` lo crea una vez, con un candado para que dos
hilos de Streamlit no creen dos, y lo reutiliza. Además `driver.execute_query()` elige
una conexión libre del pool y la devuelve al terminar.

### 2. ¿Cómo evitan que crear una película quede a medias?

Con `en_transaccion`: las cuatro escrituras (película, géneros, director y actores)
corren en una sola transacción administrada con `execute_write`. Si la tercera falla,
no hay commit y el grafo queda como estaba. Lo mismo aplica a la actualización, que
borra las relaciones viejas y crea las nuevas.

### 3. ¿Qué pasa si se corta la red justo en el commit?

`execute_write` reintenta ante errores transitorios. El reintento es seguro porque las
escrituras son idempotentes: todo lo que no debe duplicarse se crea con `MERGE`, y las
películas nuevas usan un id fijo (`the-prestige-2006`), así que un segundo intento
actualiza en vez de duplicar. Si el cliente no sabe si el commit ocurrió, la app vuelve
a leer y lo verifica.

### 4. ¿Por qué la calificación vive en la relación y no en un nodo?

Porque una calificación no existe sin la pareja usuario-película: es la relación. Así
`MERGE (u)-[c:CALIFICO]->(p) SET c.estrellas = …` crea o actualiza en una sola
sentencia, sin tabla puente ni filas duplicadas, y el patrón se lee como la frase «u
calificó p». Un nodo `Calificacion` obligaría a un nodo extra por cada voto y a un
`MATCH` más en cada recomendación. El seed usa el mismo `MERGE`, por eso correrlo dos
veces deja los mismos 131 nodos y 368 relaciones.

### 5. ¿Por qué el género es un nodo y no una propiedad de la película?

Porque necesitamos entrar por el género: «las mejores de Drama» empieza en
`(:Genero {nombre: $genero})` y recorre `DE_GENERO` hacia las películas. Si el género
fuera una lista de textos, habría que escanear todas las películas y filtrar en memoria.
Como nodo compartido además se reutiliza: un género nuevo es un `MERGE`, no una
migración.

### 6. ¿Para qué sirven los índices si el grafo no los necesita para recorrer?

Para encontrar el nodo de partida. El recorrido es index-free: cada nodo apunta a sus
relaciones. Pero `MATCH (u:Usuario {id: $id})` necesita localizar ese usuario sin
recorrer los 12; para eso están las restricciones de unicidad, que crean un índice, y el
índice sobre `titulo` para listar y buscar. Una restricción hace dos cosas: prohíbe
duplicados y acelera la entrada.

### 7. ¿Por qué grafo y no SQL, si con 35 películas SQL también responde?

Con este volumen, SQL respondería bien y hasta sería más simple de operar; no voy a
decir que el grafo es más rápido por tener 131 nodos. La diferencia está en la forma de
las consultas y en cómo crecen: la recomendación son tres JOINs encadenados con una
subconsulta, el camino más corto es una CTE recursiva que lleva visitados y no puede
podar desde los dos extremos, y agregar un tipo de relación es una tabla y una migración
más. En el grafo esas tres cosas son un patrón, `shortestPath` y una relación nueva.

### 8. ¿Qué pasa si AuraDB se cae?

La app falla con un mensaje claro, no con datos falsos: `mostrar_estado()` atrapa la
excepción y dice qué revisar. No hay una copia local a propósito, porque la base de la
evaluación es la de la nube. El driver reintenta errores transitorios; si la instancia
está pausada hay que despertarla desde la consola. En producción iría un health check,
reintentos con backoff y una alerta.

### 9. ¿Por qué el tope `*..12` en el camino?

Para acotar la búsqueda. El patrón ya está restringido a `ACTUO_EN` y `DIRIGIO`, pero
sin tope un `shortestPath` podría recorrer todo el grafo. Doce saltos son seis
películas y cinco personas intermedias, que es la idea de los seis grados; si no hay
camino en ese radio, la respuesta correcta es «no encontrado», no una búsqueda infinita.

### 10. ¿Por qué `Persona.nombre` es la llave?

Porque en este parcial alcanza: 74 personas, nombres únicos, y la restricción de
unicidad lo garantiza. Es una limitación consciente: dos actores pueden llamarse igual o
un nombre puede cambiar. En producción la llave sería un id externo de TMDB o IMDb y
`nombre` quedaría como propiedad; las películas tendrían el mismo tratamiento.

### 11. ¿Qué hace el fallback de `certifi`?

Los Python instalados desde python.org en macOS no traen los certificados raíz, y el
TLS contra Aura falla con `CERTIFICATE_VERIFY_FAILED` o con un confuso «Unable to
retrieve routing information». `src/conexion.py` apunta `SSL_CERT_FILE` al bundle de
`certifi`, pero solo si la variable no está definida **y** el contexto TLS del sistema no
tiene ninguna CA. Si hay un proxy corporativo con su CA, no se toca nada: pisarla
rompería una conexión que hoy funciona.

### 12. ¿Por qué la base no corre en localhost?

Porque el enunciado pide una base NoSQL administrada en la nube y la rúbrica evalúa esa
integración. Aura se encarga del respaldo, el parcheo y el cifrado en reposo, y la
conexión va cifrada con `neo4j+s://`. El Neo4j en Docker solo se usa en las pruebas de
integración del CI, contra una base desechable; la app nunca se conecta a localhost.

## Trampas que no hay que pisar

- No decir «el grafo es más rápido siempre»: con 35 películas SQL también responde. La
  ventaja es la forma de la consulta y el costo por salto cuando el grafo crece.
- No correr `seed/seed.py --reset` en vivo: borra la película que se acaba de crear.
- No mostrar el `.env` ni la contraseña; si hace falta, decir que está en `.env` y fuera
  del repo.
- No prometer lo que no está: no hay login, no hay caché y la app no está desplegada.
  Eso es la sección de limitaciones del reporte.
