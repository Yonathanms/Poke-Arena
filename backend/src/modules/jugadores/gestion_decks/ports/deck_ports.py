"""Contratos que necesita el servicio de decks, independientes de la infraestructura."""

from typing import Protocol

from ..domain.deck_model import Deck, DeckResumen


class RepositorioDecks(Protocol):
    async def crear_deck(
        self,
        user_id: str,
        name: str,
        card_ids: list[str],
        idempotency_key: str,
    ) -> Deck:
        """
        Crea el deck de forma atómica. Lanza:
        - DeckCartasNoPertenecen si alguna carta no está en player_cards del jugador.
        - DeckNombreOcupado si ya existe un deck con ese nombre para el jugador.
        - DeckEnCurso si otra solicitud con la misma clave está en progreso.
        Retorna el deck existente si la idempotency_key ya fue procesada.
        """
        ...

    async def listar_decks(self, user_id: str) -> list[DeckResumen]:
        """Retorna los decks del jugador ordenados por created_at DESC."""
        ...

    async def contar_decks(self, user_id: str) -> int:
        """Retorna la cantidad de decks del jugador."""
        ...

    async def obtener_deck(self, user_id: str, deck_id: str) -> Deck:
        """Retorna el deck completo. Lanza DeckNoEncontrado si no existe o no pertenece."""
        ...

    async def actualizar_deck(
        self, user_id: str, deck_id: str, name: str, card_ids: list[str]
    ) -> Deck:
        """Actualiza nombre y cartas del deck. Lanza DeckCartasNoPertenecen, DeckNombreOcupado, DeckNoEncontrado."""
        ...

    async def eliminar_deck(self, user_id: str, deck_id: str) -> None:
        """Elimina el deck. Lanza DeckNoEncontrado si no existe o no pertenece."""
        ...
