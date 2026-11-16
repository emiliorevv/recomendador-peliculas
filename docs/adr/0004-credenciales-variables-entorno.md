# ADR-0004: Credenciales en variables de entorno

- Estado: Aceptado
- Fecha: 2026-11-16

## Contexto
La rúbrica evalúa el manejo de credenciales mediante variables de entorno. La contraseña de AuraDB no puede quedar en el código ni en el repositorio.

## Decisión
URI, usuario y contraseña se leen de variables de entorno, cargadas desde un archivo `.env` con `python-dotenv`. El `.env` está en `.gitignore` y el repo trae un `.env.example` sin valores.

## Alternativas consideradas
| Opción | A favor | En contra |
|---|---|---|
| **`.env` + `python-dotenv`** | Simple, estándar, el código no cambia entre máquinas | Hay que cuidar no subir el `.env` |
| `.streamlit/secrets.toml` | Integrado a Streamlit | Ata la configuración a Streamlit; el seed no lo usa |
| Gestor de secretos (Vault, AWS Secrets Manager) | Lo más seguro | Excesivo para un parcial |

## Consecuencias
- Si falta una variable, la app falla al iniciar con un mensaje claro en lugar de intentar conectarse.
- El CI usa sus propias variables apuntando a un Neo4j de pruebas, sin tocar AuraDB.
