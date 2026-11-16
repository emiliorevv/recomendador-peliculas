# 01 — El problema

## Caso de uso

Una plataforma pequeña de reseñas de películas, parecida a Letterboxd. Los usuarios califican películas del 1 al 5 y siguen a otros usuarios. La plataforma conoce el reparto, el director y los géneros de cada película.

Lo que el usuario espera de la plataforma:

- Que le recomiende qué ver con base en lo que les gustó a personas con gustos parecidos.
- Que al ver una película le muestre otras parecidas (mismo director, actores o género).
- Que le sugiera a quién seguir.
- Curiosidades del reparto, como cuántos "saltos" hay entre dos actores.

## Por qué es un problema de conexiones

Ninguna de esas funciones depende de los datos de una sola película o un solo usuario. Todas dependen de **cómo se conectan**:

| Función | Conexiones que recorre |
|---|---|
| Recomendación colaborativa | usuario → película → otro usuario → otra película |
| Películas parecidas | película → actor/director/género → otra película |
| A quién seguir | usuario → usuario → usuario |
| Camino entre actores | actor → película → actor → película → … (sin saber cuántos saltos) |

Además los datos crecen hacia los lados: mañana puede haber premios, plataformas de streaming o listas, y cada una es otra forma de conectar lo que ya existe.

## Alcance del parcial

- Datos de ejemplo: 35 películas reales, sus actores y directores, 10 géneros, 12 usuarios inventados con calificaciones y seguidores.
- CRUD completo de películas, usuarios y calificaciones.
- Las seis consultas de grafo listadas en el README.
- Interfaz sencilla para la demo. No hay login ni despliegue de la app: lo que va en la nube es la base de datos, que es lo que pide el enunciado.
