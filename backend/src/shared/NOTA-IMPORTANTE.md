# Capa Transversal (`shared`)

Esta carpeta representa la **Capa Transversal** que aparece en el diagrama de arquitectura del proyecto.

Aquí colocamos todo el código, utilidades y reglas técnicas que **no son exclusivas de un solo módulo**, sino que cualquier parte del sistema necesita usar. En lugar de copiar y pegar código en cada módulo, lo centralizamos aquí para que el proyecto sea ordenado y fácil de mantener.

---

### ¿Qué hay en cada carpeta?

* **`config.py`**: Lee el archivo `.env` y centraliza todas las configuraciones (puertos, credenciales de bases de datos, etc.).
* **`errores-rfc7807/`**: Asegura que todos los errores de la API se devuelvan siempre con el mismo formato limpio y estándar.
* **`idempotencia/`**: Evita que se creen cosas duplicadas si el usuario hace doble clic o si la conexión se corta y se reintenta una petición.
* **`observabilidad/`**: Agrega identificadores de seguimiento a cada petición para que podamos rastrear fácilmente qué pasó en la consola si algo falla.
* **`seguridad-roles/`**: Controla quién está autenticado y qué permisos tiene (por ejemplo, diferenciar entre un Administrador y un Jugador).
* **`validacion/`**: Esquemas y funciones de validación reutilizables en múltiples módulos.

---
> **Contrato para el equipo:**  
> Si una función o clase solo le sirve a las cartas, va en `modules/catalogo`.  
> Si le sirve a las cartas, a los torneos y a los jugadores por igual, va aquí en `shared`.

