"""Caso de uso: Crear Deck y listar decks del jugador."""

from ..domain.deck_model import (
    MAX_DECK_SIZE,
    Deck,
    DeckCartasRepetidas,
    DeckResumen,
    DeckTamanoInvalido,
)
from ..ports.deck_ports import RepositorioDecks




class DecksService:

    def __init__(self, repo: RepositorioDecks) -> None:
        self._repo = repo

    async def crear_deck(
        self,
        user_id: str,
        name: str,
        card_ids: list[str],
        idempotency_key: str,
    ) -> Deck:
        """Valida tamaño y unicidad antes de delegar al repositorio."""
        if len(card_ids) != MAX_DECK_SIZE:
            raise DeckTamanoInvalido(recibidas=len(card_ids))

        repetidas = [cid for cid in card_ids if card_ids.count(cid) > 1]
        if repetidas:
            raise DeckCartasRepetidas(repetidas=list(set(repetidas)))

        return await self._repo.crear_deck(user_id, name, card_ids, idempotency_key)

    async def listar_decks(self, user_id: str) -> list[DeckResumen]:
        return await self._repo.listar_decks(user_id)

    async def contar_decks(self, user_id: str) -> int:
        return await self._repo.contar_decks(user_id)

    async def obtener_deck(self, user_id: str, deck_id: str) -> Deck:
        return await self._repo.obtener_deck(user_id, deck_id)

    async def actualizar_deck(
        self, user_id: str, deck_id: str, name: str, card_ids: list[str]
    ) -> Deck:
        if len(card_ids) != MAX_DECK_SIZE:
            raise DeckTamanoInvalido(recibidas=len(card_ids))
        repetidas = [cid for cid in card_ids if card_ids.count(cid) > 1]
        if repetidas:
            raise DeckCartasRepetidas(repetidas=list(set(repetidas)))
        return await self._repo.actualizar_deck(user_id, deck_id, name, card_ids)

    async def eliminar_deck(self, user_id: str, deck_id: str) -> None:
        await self._repo.eliminar_deck(user_id, deck_id)
