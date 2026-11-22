"""Caso de uso de búsqueda de partida, heartbeat, cancelación y oferta de Bot (US 2 y US 3)."""

import json
import math
from typing import Any
from uuid import uuid4

from src.modules.jugadores.partidas.domain.partida_model import (
    CatalogoPartidaInvalidoError,
    ParticipantePartidaInput,
    PartidaConflictoActivaError,
    PartidaCreada,
    PartidaNoDisponibleError,
)
from src.modules.jugadores.partidas.services.partidas_service import PartidasService
from src.modules.motor_juego.domain.maquina_estados import (
    MAQUINA_ESTADOS_BUSQUEDA,
    EstadoBusqueda,
    EventoBusqueda,
    TransicionInvalida,
)
from src.modules.motor_juego.domain.modelos_partida import UbicacionesInsuficientesError
from src.shared.cache import CachePort
from src.shared.http_etag import coincide_if_none_match, generar_etag

from ..domain.emparejamiento_model import (
    BusquedaActivaDuplicadaError,
    BusquedaNoEncontradaError,
    BusquedaPartida,
    BusquedaTerminalError,
    BusquedaVigenteOtroContextoError,
    BusquedaYaEmparejadaError,
    CubosInsuficientesError,
    DeckInvalidoBusquedaError,
    DeckNoEncontradoBusquedaError,
    EmparejamientoNoDisponibleError,
    OfertaBotNoDisponibleError,
    PartidaActivaError,
    ResultadoBusqueda,
    son_busquedas_compatibles,
)
from ..ports.emparejamiento_ports import RepositorioEmparejamientoPort
from .bot_service import ControladorBot

_TTL_BUSQUEDA_CACHE = 120


def _clave_cache_busqueda(search_id: str) -> str:
    return f"mm:v1:search:{search_id}:ver"


class EmparejamientoService:
    """Coordina la cola de emparejamiento con PostgreSQL ACID, FSM y caché ADR-003."""

    def __init__(
        self,
        repo: RepositorioEmparejamientoPort,
        partidas: PartidasService,
        bot: ControladorBot,
        cache: CachePort,
        *,
        heartbeat_timeout_seconds: int = 30,
        bot_offer_seconds: int = 60,
        max_elo_diff: int = 1000,
        ranked_min_cubes: int = 8,
    ) -> None:
        self._repo = repo
        self._partidas = partidas
        self._bot = bot
        self._cache = cache
        self._heartbeat_timeout = heartbeat_timeout_seconds
        self._bot_offer_seconds = bot_offer_seconds
        self._max_elo_diff = max_elo_diff
        self._ranked_min_cubes = ranked_min_cubes

    def _calcular_disponibilidad_bot(self, busqueda: BusquedaPartida) -> tuple[bool, int]:
        if busqueda.status != EstadoBusqueda.SEARCHING.value:
            return False, 0
        restante = max(0, math.ceil(self._bot_offer_seconds - busqueda.elapsed_seconds))
        return busqueda.elapsed_seconds >= self._bot_offer_seconds, restante

    def _construir_etag(self, busqueda: BusquedaPartida, bot_disponible: bool) -> str:
        return generar_etag(
            "mm",
            busqueda.id,
            f"{busqueda.state_version}-{busqueda.status}-b{int(bot_disponible)}",
        )

    def _a_resultado(
        self,
        busqueda: BusquedaPartida,
        *,
        created: bool = False,
        not_modified: bool = False,
        warning_code: str | None = None,
        warning_detail: str | None = None,
    ) -> ResultadoBusqueda:
        bot_disponible, bot_restante = self._calcular_disponibilidad_bot(busqueda)
        return ResultadoBusqueda(
            busqueda=busqueda,
            created=created,
            not_modified=not_modified,
            etag=self._construir_etag(busqueda, bot_disponible),
            bot_offer_available=bot_disponible,
            bot_offer_in_seconds=bot_restante,
            warning_code=warning_code,
            warning_detail=warning_detail,
        )

    def _serializar_busqueda(self, resultado: ResultadoBusqueda) -> dict[str, Any]:
        b = resultado.busqueda
        assert b is not None
        return {
            "search_id": b.id,
            "status": b.status,
            "context": b.context,
            "deck_id": b.deck_id,
            "elo_snapshot": b.elo_snapshot,
            "match_id": b.match_id,
            "elapsed_seconds": round(b.elapsed_seconds, 2),
            "bot_offer_available": resultado.bot_offer_available,
            "bot_offer_in_seconds": resultado.bot_offer_in_seconds,
            "state_version": b.state_version,
            "created_at": b.created_at.isoformat(),
            "last_seen_at": b.last_seen_at.isoformat(),
            "warning_code": resultado.warning_code,
            "warning_detail": resultado.warning_detail,
        }

    async def _publicar_cache_busqueda(self, resultado: ResultadoBusqueda) -> None:
        if resultado.busqueda is None:
            return
        payload = json.dumps({
            "u": resultado.busqueda.user_id,
            "s": resultado.busqueda.status,
            "etag": resultado.etag,
            "bot": resultado.bot_offer_available,
            "dto": self._serializar_busqueda(resultado),
        })
        await self._cache.set(
            _clave_cache_busqueda(resultado.busqueda.id),
            payload,
            _TTL_BUSQUEDA_CACHE,
        )

    async def _publicar_expiradas_cache(self, expiradas: list[BusquedaPartida]) -> None:
        for item in expiradas:
            await self._publicar_cache_busqueda(self._a_resultado(item))

    async def _intentar_emparejar(
        self,
        sesion: Any,
        mi_busqueda: BusquedaPartida,
    ) -> tuple[
        BusquedaPartida, PartidaCreada | None, list[BusquedaPartida], str | None, str | None
    ]:
        expiradas_ctx = await self._repo.expirar_busquedas_vencidas_contexto(
            sesion, mi_busqueda.context, self._heartbeat_timeout
        )
        candidatos = await self._repo.listar_candidatos_skip_locked(
            sesion,
            context=mi_busqueda.context,
            excluir_user_id=mi_busqueda.user_id,
            heartbeat_timeout_seconds=self._heartbeat_timeout,
        )

        for candidato in candidatos:
            if not son_busquedas_compatibles(
                mi_busqueda.elo_snapshot,
                mi_busqueda.elapsed_seconds,
                candidato.elo_snapshot,
                candidato.elapsed_seconds,
                self._max_elo_diff,
            ):
                continue

            bloqueadas = await self._repo.bloquear_par_ordenado_por_usuario(
                sesion, mi_busqueda.id, candidato.id
            )
            if len(bloqueadas) != 2:
                continue
            por_id = {b.id: b for b in bloqueadas}
            propia_locked = por_id.get(mi_busqueda.id)
            rival_locked = por_id.get(candidato.id)
            if (
                propia_locked is None
                or rival_locked is None
                or propia_locked.status != EstadoBusqueda.SEARCHING.value
                or rival_locked.status != EstadoBusqueda.SEARCHING.value
                or rival_locked.inactive_seconds > self._heartbeat_timeout
                or propia_locked.deck_id is None
                or rival_locked.deck_id is None
            ):
                continue

            try:
                async with self._repo.abrir_savepoint(sesion):
                    nuevo_estado = MAQUINA_ESTADOS_BUSQUEDA.transicionar(
                        EstadoBusqueda(propia_locked.status),
                        EventoBusqueda.EMPAREJAR,
                    ).value
                    MAQUINA_ESTADOS_BUSQUEDA.transicionar(
                        EstadoBusqueda(rival_locked.status),
                        EventoBusqueda.EMPAREJAR,
                    )

                    cards_propio = await self._repo.validar_y_leer_deck_para_busqueda(
                        sesion, propia_locked.user_id, propia_locked.deck_id
                    )
                    cards_rival = await self._repo.validar_y_leer_deck_para_busqueda(
                        sesion, rival_locked.user_id, rival_locked.deck_id
                    )

                    p1 = ParticipantePartidaInput(
                        seat=1,
                        user_id=propia_locked.user_id,
                        is_bot=False,
                        deck_id=propia_locked.deck_id,
                        card_ids=cards_propio,
                        elo=propia_locked.elo_snapshot,
                    )
                    p2 = ParticipantePartidaInput(
                        seat=2,
                        user_id=rival_locked.user_id,
                        is_bot=False,
                        deck_id=rival_locked.deck_id,
                        card_ids=cards_rival,
                        elo=rival_locked.elo_snapshot,
                    )

                    partida = await self._partidas.iniciar_partida_en_transaccion(
                        sesion,
                        context=propia_locked.context,
                        is_bot_match=False,
                        jugador_1=p1,
                        jugador_2=p2,
                    )
                    propia_actualizada = await self._repo.actualizar_estado_busqueda(
                        sesion,
                        search_id=propia_locked.id,
                        nuevo_estado=nuevo_estado,
                        match_id=partida.match_id,
                    )
                    rival_actualizada = await self._repo.actualizar_estado_busqueda(
                        sesion,
                        search_id=rival_locked.id,
                        nuevo_estado=nuevo_estado,
                        match_id=partida.match_id,
                    )
                    return (
                        propia_actualizada,
                        partida,
                        [*expiradas_ctx, rival_actualizada],
                        None,
                        None,
                    )
            except UbicacionesInsuficientesError as exc:
                return (
                    propia_locked,
                    None,
                    expiradas_ctx,
                    "ubicaciones_insuficientes",
                    str(exc),
                )
            except PartidaNoDisponibleError as exc:
                raise EmparejamientoNoDisponibleError(str(exc)) from None
            except (
                DeckNoEncontradoBusquedaError,
                DeckInvalidoBusquedaError,
                CatalogoPartidaInvalidoError,
                PartidaConflictoActivaError,
            ):
                continue

        return mi_busqueda, None, expiradas_ctx, None, None

    async def iniciar_busqueda(
        self,
        user_id: str,
        deck_id: str,
        context: str,
    ) -> ResultadoBusqueda:
        """Valida reglas ACID, garantiza 1 búsqueda global e intenta emparejar."""
        partida_creada: PartidaCreada | None = None
        expiradas_post: list[BusquedaPartida] = []
        busqueda_final: BusquedaPartida
        created = False
        warning_code: str | None = None
        warning_detail: str | None = None

        async with self._repo.abrir_transaccion() as sesion:
            expiradas_usr = await self._repo.expirar_busquedas_vencidas_usuario(
                sesion, user_id, self._heartbeat_timeout
            )
            expiradas_post.extend(expiradas_usr)

            partida_activa_id = await self._repo.obtener_partida_activa_en_sesion(sesion, user_id)
            if partida_activa_id is not None:
                raise PartidaActivaError(partida_activa_id)

            existente = await self._repo.obtener_busqueda_activa_usuario_for_update(
                sesion, user_id
            )
            if existente is not None:
                if existente.context != context:
                    raise BusquedaVigenteOtroContextoError(existente.id, existente.context)
                busqueda_refrescada = await self._repo.refrescar_heartbeat(sesion, existente.id)
                (
                    busqueda_final,
                    partida_creada,
                    extras,
                    warning_code,
                    warning_detail,
                ) = await self._intentar_emparejar(sesion, busqueda_refrescada)
                expiradas_post.extend(extras)
            else:
                await self._repo.validar_y_leer_deck_para_busqueda(sesion, user_id, deck_id)
                perfil = await self._repo.leer_perfil_jugador(sesion, user_id)
                if context == "RANKED" and perfil.cubes < self._ranked_min_cubes:
                    raise CubosInsuficientesError(perfil.cubes, self._ranked_min_cubes)

                try:
                    async with self._repo.abrir_savepoint(sesion):
                        nueva = await self._repo.insertar_busqueda(
                            sesion,
                            search_id=str(uuid4()),
                            user_id=user_id,
                            deck_id=deck_id,
                            context=context,
                            elo_snapshot=perfil.elo,
                        )
                    created = True
                except BusquedaActivaDuplicadaError:
                    colision = await self._repo.obtener_busqueda_activa_usuario_for_update(
                        sesion, user_id
                    )
                    if colision is None:
                        raise
                    if colision.context != context:
                        raise BusquedaVigenteOtroContextoError(
                            colision.id, colision.context
                        ) from None
                    nueva = await self._repo.refrescar_heartbeat(sesion, colision.id)

                (
                    busqueda_final,
                    partida_creada,
                    extras,
                    warning_code,
                    warning_detail,
                ) = await self._intentar_emparejar(sesion, nueva)
                expiradas_post.extend(extras)

        resultado = self._a_resultado(
            busqueda_final,
            created=created,
            warning_code=warning_code,
            warning_detail=warning_detail,
        )
        await self._publicar_expiradas_cache(expiradas_post)
        await self._publicar_cache_busqueda(resultado)
        if partida_creada is not None:
            await self._partidas.registrar_version_cache_post_commit(partida_creada)
        return resultado

    async def consultar_busqueda(
        self,
        user_id: str,
        search_id: str,
        if_none_match: str | None = None,
    ) -> ResultadoBusqueda:
        """Consulta estado de búsqueda; refresca heartbeat e intenta emparejar."""
        cached_raw = await self._cache.get(_clave_cache_busqueda(search_id))
        if cached_raw is not None:
            try:
                cached = json.loads(cached_raw)
                if cached.get("u") != user_id:
                    raise BusquedaNoEncontradaError("La búsqueda no existe.")
                if (
                    cached.get("s") != EstadoBusqueda.SEARCHING.value
                    and coincide_if_none_match(if_none_match, str(cached.get("etag", "")))
                ):
                    return ResultadoBusqueda(
                        busqueda=None,
                        created=False,
                        not_modified=True,
                        etag=str(cached["etag"]),
                        bot_offer_available=bool(cached.get("bot", False)),
                        bot_offer_in_seconds=0,
                    )
            except (ValueError, TypeError, KeyError):
                pass

        partida_creada: PartidaCreada | None = None
        expiradas_post: list[BusquedaPartida] = []
        warning_code: str | None = None
        warning_detail: str | None = None

        async with self._repo.abrir_transaccion() as sesion:
            busqueda = await self._repo.obtener_busqueda_por_id_for_update(
                sesion, user_id, search_id
            )
            if busqueda is None:
                raise BusquedaNoEncontradaError("La búsqueda no existe.")

            if busqueda.status == EstadoBusqueda.SEARCHING.value:
                if busqueda.inactive_seconds > self._heartbeat_timeout:
                    estado_exp = MAQUINA_ESTADOS_BUSQUEDA.transicionar(
                        EstadoBusqueda.SEARCHING,
                        EventoBusqueda.EXPIRAR,
                    ).value
                    busqueda_final = await self._repo.actualizar_estado_busqueda(
                        sesion, search_id=busqueda.id, nuevo_estado=estado_exp
                    )
                else:
                    refrescada = await self._repo.refrescar_heartbeat(sesion, busqueda.id)
                    (
                        busqueda_final,
                        partida_creada,
                        extras,
                        warning_code,
                        warning_detail,
                    ) = await self._intentar_emparejar(sesion, refrescada)
                    expiradas_post.extend(extras)
            else:
                busqueda_final = busqueda

        resultado = self._a_resultado(
            busqueda_final,
            warning_code=warning_code,
            warning_detail=warning_detail,
        )
        await self._publicar_expiradas_cache(expiradas_post)
        await self._publicar_cache_busqueda(resultado)
        if partida_creada is not None:
            await self._partidas.registrar_version_cache_post_commit(partida_creada)

        if warning_code is None and coincide_if_none_match(if_none_match, resultado.etag):
            return ResultadoBusqueda(
                busqueda=resultado.busqueda,
                created=False,
                not_modified=True,
                etag=resultado.etag,
                bot_offer_available=resultado.bot_offer_available,
                bot_offer_in_seconds=resultado.bot_offer_in_seconds,
            )
        return resultado

    async def consultar_busqueda_actual(
        self,
        user_id: str,
        if_none_match: str | None = None,
    ) -> ResultadoBusqueda | None:
        """Retorna la búsqueda SEARCHING activa del jugador, o None si no tiene ninguna."""
        partida_creada: PartidaCreada | None = None
        expiradas_post: list[BusquedaPartida] = []
        warning_code: str | None = None
        warning_detail: str | None = None

        async with self._repo.abrir_transaccion() as sesion:
            expiradas = await self._repo.expirar_busquedas_vencidas_usuario(
                sesion, user_id, self._heartbeat_timeout
            )
            expiradas_post.extend(expiradas)
            busqueda = await self._repo.obtener_busqueda_activa_usuario_for_update(
                sesion, user_id
            )
            if busqueda is None:
                busqueda_final = None
            else:
                refrescada = await self._repo.refrescar_heartbeat(sesion, busqueda.id)
                (
                    busqueda_final,
                    partida_creada,
                    extras,
                    warning_code,
                    warning_detail,
                ) = await self._intentar_emparejar(sesion, refrescada)
                expiradas_post.extend(extras)

        await self._publicar_expiradas_cache(expiradas_post)
        if busqueda_final is None:
            return None

        resultado = self._a_resultado(
            busqueda_final,
            warning_code=warning_code,
            warning_detail=warning_detail,
        )
        await self._publicar_cache_busqueda(resultado)
        if partida_creada is not None:
            await self._partidas.registrar_version_cache_post_commit(partida_creada)

        if warning_code is None and coincide_if_none_match(if_none_match, resultado.etag):
            return ResultadoBusqueda(
                busqueda=resultado.busqueda,
                created=False,
                not_modified=True,
                etag=resultado.etag,
                bot_offer_available=resultado.bot_offer_available,
                bot_offer_in_seconds=resultado.bot_offer_in_seconds,
            )
        return resultado

    async def cancelar_busqueda(self, user_id: str, search_id: str) -> ResultadoBusqueda:
        """Cancela atómicamente una búsqueda SEARCHING o rechaza si ya emparejó."""
        expirada_previa: BusquedaPartida | None = None
        busqueda_cancelada: BusquedaPartida | None = None

        async with self._repo.abrir_transaccion() as sesion:
            busqueda = await self._repo.obtener_busqueda_por_id_for_update(
                sesion, user_id, search_id
            )
            if busqueda is None:
                raise BusquedaNoEncontradaError("La búsqueda no existe.")

            if busqueda.status == EstadoBusqueda.MATCHED.value and busqueda.match_id is not None:
                raise BusquedaYaEmparejadaError(busqueda.match_id)

            if (
                busqueda.status == EstadoBusqueda.SEARCHING.value
                and busqueda.inactive_seconds > self._heartbeat_timeout
            ):
                estado_exp = MAQUINA_ESTADOS_BUSQUEDA.transicionar(
                    EstadoBusqueda.SEARCHING, EventoBusqueda.EXPIRAR
                ).value
                expirada_previa = await self._repo.actualizar_estado_busqueda(
                    sesion, search_id=busqueda.id, nuevo_estado=estado_exp
                )
            else:
                try:
                    nuevo_estado = MAQUINA_ESTADOS_BUSQUEDA.transicionar(
                        EstadoBusqueda(busqueda.status),
                        EventoBusqueda.CANCELAR,
                    ).value
                except TransicionInvalida:
                    raise BusquedaTerminalError(
                        busqueda.status,
                        f"La búsqueda ya finalizó en estado {busqueda.status}.",
                    ) from None

                busqueda_cancelada = await self._repo.actualizar_estado_busqueda(
                    sesion, search_id=busqueda.id, nuevo_estado=nuevo_estado
                )

        if expirada_previa is not None:
            await self._publicar_cache_busqueda(self._a_resultado(expirada_previa))
            raise BusquedaTerminalError("EXPIRED", "La búsqueda expiró por inactividad.")

        assert busqueda_cancelada is not None
        resultado = self._a_resultado(busqueda_cancelada)
        await self._publicar_cache_busqueda(resultado)
        return resultado

    async def aceptar_bot(self, user_id: str, search_id: str) -> ResultadoBusqueda:
        """Acepta enfrentar al Bot tras >= 60 s en SEARCHING y crea partida atómica."""
        partida_creada: PartidaCreada | None = None
        expirada_previa: BusquedaPartida | None = None
        busqueda_final: BusquedaPartida
        warning_code: str | None = None
        warning_detail: str | None = None

        async with self._repo.abrir_transaccion() as sesion:
            busqueda = await self._repo.obtener_busqueda_por_id_for_update(
                sesion, user_id, search_id
            )
            if busqueda is None:
                raise BusquedaNoEncontradaError("La búsqueda no existe.")

            if busqueda.status == EstadoBusqueda.MATCHED.value and busqueda.match_id is not None:
                raise BusquedaYaEmparejadaError(busqueda.match_id)

            if busqueda.status != EstadoBusqueda.SEARCHING.value:
                raise BusquedaTerminalError(busqueda.status)

            if busqueda.inactive_seconds > self._heartbeat_timeout:
                estado_exp = MAQUINA_ESTADOS_BUSQUEDA.transicionar(
                    EstadoBusqueda.SEARCHING, EventoBusqueda.EXPIRAR
                ).value
                expirada_previa = await self._repo.actualizar_estado_busqueda(
                    sesion, search_id=busqueda.id, nuevo_estado=estado_exp
                )
            else:
                if busqueda.elapsed_seconds < self._bot_offer_seconds:
                    restante = max(
                        1, math.ceil(self._bot_offer_seconds - busqueda.elapsed_seconds)
                    )
                    raise OfertaBotNoDisponibleError(restante)

                partida_activa = await self._repo.obtener_partida_activa_en_sesion(sesion, user_id)
                if partida_activa is not None:
                    raise PartidaActivaError(partida_activa)
                if busqueda.deck_id is None:
                    raise DeckInvalidoBusquedaError("La búsqueda no tiene un deck asociado.")

                try:
                    async with self._repo.abrir_savepoint(sesion):
                        cards_jugador = await self._repo.validar_y_leer_deck_para_busqueda(
                            sesion, user_id, busqueda.deck_id
                        )
                        nuevo_estado = MAQUINA_ESTADOS_BUSQUEDA.transicionar(
                            EstadoBusqueda(busqueda.status),
                            EventoBusqueda.ACEPTAR_BOT,
                        ).value
                        p1 = ParticipantePartidaInput(
                            seat=1,
                            user_id=user_id,
                            is_bot=False,
                            deck_id=busqueda.deck_id,
                            card_ids=cards_jugador,
                            elo=busqueda.elo_snapshot,
                        )
                        p2 = await self._bot.construir_participante_bot(
                            sesion,
                            elo_referencia=busqueda.elo_snapshot,
                            seat=2,
                        )
                        partida_creada = await self._partidas.iniciar_partida_en_transaccion(
                            sesion,
                            context=busqueda.context,
                            is_bot_match=True,
                            jugador_1=p1,
                            jugador_2=p2,
                        )
                        busqueda_final = await self._repo.actualizar_estado_busqueda(
                            sesion,
                            search_id=busqueda.id,
                            nuevo_estado=nuevo_estado,
                            match_id=partida_creada.match_id,
                        )
                except UbicacionesInsuficientesError as exc:
                    busqueda_final = await self._repo.refrescar_heartbeat(sesion, busqueda.id)
                    warning_code = "ubicaciones_insuficientes"
                    warning_detail = str(exc)
                except PartidaNoDisponibleError as exc:
                    raise EmparejamientoNoDisponibleError(str(exc)) from None

        if expirada_previa is not None:
            await self._publicar_cache_busqueda(self._a_resultado(expirada_previa))
            raise BusquedaTerminalError("EXPIRED", "La búsqueda expiró por inactividad.")

        resultado = self._a_resultado(
            busqueda_final,
            warning_code=warning_code,
            warning_detail=warning_detail,
        )
        await self._publicar_cache_busqueda(resultado)
        if partida_creada is not None:
            await self._partidas.registrar_version_cache_post_commit(partida_creada)
        return resultado
