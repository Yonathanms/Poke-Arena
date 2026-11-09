"""Consulta y confirmación del paquete sobre la misma unidad de trabajo de Jugadores."""

from ..domain.entrega_inicial_model import (
    EstadoPaquete,
    EstadoPaqueteInicial,
    EstadoProvisionInconsistente,
    JugadorNoElegible,
    PaquetePendiente,
)
from ..ports.entrega_inicial_ports import TransaccionEntregaInicial, UnidadEntregaInicial
from .entrega_inicial_service import validar_premio_sin_abrir


class PaqueteInicial:
    """Consulta el paquete y registra su apertura sin provisionar beneficios."""

    def __init__(self, unidad: UnidadEntregaInicial) -> None:
        self._unidad = unidad

    async def consultar(self, token: str) -> EstadoPaqueteInicial:
        """Lee el estado coherente del paquete y sus cartas asignadas."""
        async with self._unidad.transaccion() as tx:
            usuario = await self._jugador(tx, token)
            return await self._estado(tx, usuario, abrir=False)

    async def abrir(self, token: str) -> EstadoPaqueteInicial:
        """Confirma la apertura una vez y devuelve el timestamp original en reintentos."""
        async with self._unidad.transaccion() as tx:
            usuario = await self._jugador(tx, token)
            estado = await self._estado(tx, usuario, abrir=True)
            if estado.estado is EstadoPaquete.PENDING_CATALOG:
                raise PaquetePendiente()
            if estado.estado is EstadoPaquete.COMPLETED:
                return estado
            abierto_en = await tx.registrar_apertura(usuario)
            return EstadoPaqueteInicial(EstadoPaquete.COMPLETED, abierto_en)

    @staticmethod
    async def _jugador(tx: TransaccionEntregaInicial, token: str) -> str:
        usuario = await tx.jugador_elegible(token)
        if usuario is None:
            raise JugadorNoElegible()
        return usuario

    @staticmethod
    async def _estado(
        tx: TransaccionEntregaInicial, usuario: str, *, abrir: bool
    ) -> EstadoPaqueteInicial:
        perfil = await (tx.bloquear_perfil(usuario) if abrir else tx.leer_perfil(usuario))
        if perfil is None:
            raise EstadoProvisionInconsistente("Falta el perfil de jugador.")
        if not perfil.recibido:
            if (
                perfil.abierto_en is not None or perfil.cubes != 0
                or await tx.tiene_inventario_o_historial(usuario)
            ):
                raise EstadoProvisionInconsistente("Hay datos de juego sin provisión.")
            return EstadoPaqueteInicial(EstadoPaquete.PENDING_CATALOG)

        # La apertura confirma el premio inicial antes de habilitar recursos mutables.
        if perfil.abierto_en is not None:
            return EstadoPaqueteInicial(EstadoPaquete.COMPLETED, perfil.abierto_en)
        cartas = await validar_premio_sin_abrir(tx, usuario, perfil.cubes)
        return EstadoPaqueteInicial(EstadoPaquete.READY_TO_OPEN, cartas=cartas)
