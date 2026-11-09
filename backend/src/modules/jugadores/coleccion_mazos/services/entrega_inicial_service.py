"""Orquesta la entrega de beneficios sin dependencias de HTTP o SQL."""

from ..domain.entrega_inicial_model import (
    INITIAL_CARD_COUNT,
    INITIAL_CUBES,
    CartaPaquete,
    EstadoProvisionInconsistente,
    ResultadoProvision,
)
from ..ports.entrega_inicial_ports import TransaccionEntregaInicial, UnidadEntregaInicial


async def validar_premio_sin_abrir(
    tx: TransaccionEntregaInicial, usuario_id: str, cubos: int,
) -> tuple[CartaPaquete, ...]:
    """Valida el premio previo al juego bajo el bloqueo del perfil del llamador."""
    cartas = await tx.cartas_del_paquete(usuario_id)
    if (
        len(cartas) != INITIAL_CARD_COUNT
        or any(carta.quantity != 1 for carta in cartas)
        or cubos != INITIAL_CUBES
        or not await tx.movimiento_inicial_integro(usuario_id)
    ):
        raise EstadoProvisionInconsistente("El paquete provisionado no es íntegro.")
    return cartas


class EntregaInicial:
    """Provisiona una vez a partir de una sesión de plataforma."""

    def __init__(self, unidad: UnidadEntregaInicial) -> None:
        self._unidad = unidad

    async def asegurar(self, token_sesion: str) -> ResultadoProvision:
        """Resuelve al jugador y confirma sus beneficios en una transacción independiente."""
        async with self._unidad.transaccion() as tx:
            usuario_id = await tx.jugador_elegible(token_sesion)
            if usuario_id is None:
                return ResultadoProvision.NOT_ELIGIBLE
            perfil = await tx.bloquear_perfil(usuario_id)
            if perfil is None:
                raise EstadoProvisionInconsistente("Falta el perfil de jugador.")
            if perfil.recibido:
                if perfil.abierto_en is None:
                    await validar_premio_sin_abrir(tx, usuario_id, perfil.cubes)
                return ResultadoProvision.ALREADY_GRANTED
            if (
                perfil.abierto_en is not None
                or perfil.cubes != 0
                or await tx.tiene_inventario_o_historial(usuario_id)
            ):
                raise EstadoProvisionInconsistente("El perfil ya contiene beneficios o apertura.")

            cartas = await tx.seleccionar_cartas()
            if len(cartas) < INITIAL_CARD_COUNT:
                return ResultadoProvision.INSUFFICIENT_CATALOG
            await tx.registrar_entrega(usuario_id, cartas)
            return ResultadoProvision.GRANTED
