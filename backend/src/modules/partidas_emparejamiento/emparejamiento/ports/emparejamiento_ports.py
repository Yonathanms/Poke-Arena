"""Puertos hexagonales del módulo de Emparejamiento."""

from contextlib import AbstractAsyncContextManager
from typing import Any, Protocol

from ..domain.emparejamiento_model import BusquedaPartida, PerfilBusqueda


class RepositorioEmparejamientoPort(Protocol):
    """Puerto de persistencia ACID para cola de emparejamiento, locks y heartbeats."""

    def abrir_transaccion(self) -> AbstractAsyncContextManager[Any]:
        """Abre una transacción ACID compartida para toda la operación."""
        ...

    def abrir_savepoint(self, sesion: Any) -> AbstractAsyncContextManager[Any]:
        """Abre un SAVEPOINT dentro de la transacción ya iniciada."""
        ...

    async def expirar_busquedas_vencidas_usuario(
        self, sesion: Any, user_id: str, heartbeat_timeout_seconds: int
    ) -> list[BusquedaPartida]:
        """Marca como EXPIRED las búsquedas SEARCHING vencidas del jugador."""
        ...

    async def expirar_busquedas_vencidas_contexto(
        self, sesion: Any, context: str, heartbeat_timeout_seconds: int
    ) -> list[BusquedaPartida]:
        """Marca como EXPIRED búsquedas abandonadas del contexto usando SKIP LOCKED."""
        ...

    async def obtener_partida_activa_en_sesion(self, sesion: Any, user_id: str) -> str | None:
        """Retorna el match_id si el jugador tiene una partida IN_PROGRESS."""
        ...

    async def obtener_busqueda_activa_usuario_for_update(
        self, sesion: Any, user_id: str
    ) -> BusquedaPartida | None:
        """Bloquea y devuelve la búsqueda SEARCHING activa del jugador si existe."""
        ...

    async def obtener_busqueda_por_id_for_update(
        self, sesion: Any, user_id: str, search_id: str
    ) -> BusquedaPartida | None:
        """Bloquea y devuelve una búsqueda de user_id por su identificador."""
        ...

    async def validar_y_leer_deck_para_busqueda(
        self, sesion: Any, user_id: str, deck_id: str
    ) -> tuple[str, ...]:
        """Valida existencia, propiedad, 12 cartas distintas y ownership actual."""
        ...

    async def leer_perfil_jugador(self, sesion: Any, user_id: str) -> PerfilBusqueda:
        """Lee Elo y cubos actuales directamente desde PostgreSQL primario."""
        ...

    async def insertar_busqueda(
        self,
        sesion: Any,
        *,
        search_id: str,
        user_id: str,
        deck_id: str,
        context: str,
        elo_snapshot: int,
    ) -> BusquedaPartida:
        """Inserta una nueva búsqueda SEARCHING protegida por índice único parcial."""
        ...

    async def refrescar_heartbeat(self, sesion: Any, search_id: str) -> BusquedaPartida:
        """Actualiza last_seen_at = clock_timestamp() en la búsqueda abierta."""
        ...

    async def listar_candidatos_skip_locked(
        self,
        sesion: Any,
        *,
        context: str,
        excluir_user_id: str,
        heartbeat_timeout_seconds: int,
        limite: int = 20,
    ) -> list[BusquedaPartida]:
        """Lista candidatos SEARCHING vigentes bloqueándolos con FOR UPDATE SKIP LOCKED."""
        ...

    async def bloquear_par_ordenado_por_usuario(
        self, sesion: Any, id_a: str, id_b: str
    ) -> list[BusquedaPartida]:
        """Bloquea ambas búsquedas en orden determinista user_id ASC FOR UPDATE."""
        ...

    async def actualizar_estado_busqueda(
        self,
        sesion: Any,
        *,
        search_id: str,
        nuevo_estado: str,
        match_id: str | None = None,
    ) -> BusquedaPartida:
        """Actualiza estado, match_id e incrementa state_version en match_searches."""
        ...
