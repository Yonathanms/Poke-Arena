"""Servicios de aplicación de paquete inicial y consulta de colección."""

from src.shared.maquina_estados import TransicionInvalida

from ..domain.entrega_inicial_model import (
    MAQUINA_ESTADOS_PAQUETE,
    CartaColeccion,
    EstadoPaquete,
    EstadoPaqueteInicial,
    EstadoProvisionInconsistente,
    EventoPaquete,
    JugadorNoElegible,
    PaquetePendiente,
)
from ..ports.entrega_inicial_ports import (
    ColeccionJugadorPort,
    TransaccionEntregaInicial,
    UnidadEntregaInicial,
)
from .entrega_inicial_service import validar_premio_sin_abrir


class PaqueteInicial:
    """Consulta el paquete y aplica transiciones mediante la máquina de estados."""

    def __init__(self, unidad: UnidadEntregaInicial) -> None:
        self._unidad = unidad

    async def consultar(self, token: str) -> EstadoPaqueteInicial:
        """Lee el estado coherente del paquete y sus cartas asignadas."""
        async with self._unidad.transaccion() as tx:
            usuario = await self._jugador(tx, token)
            return await self._estado(tx, usuario, abrir=False)

    async def abrir(self, token: str) -> EstadoPaqueteInicial:
        """Aplica la transición ABRIR y devuelve el timestamp original en reintentos."""
        async with self._unidad.transaccion() as tx:
            usuario = await self._jugador(tx, token)
            estado = await self._estado(tx, usuario, abrir=True)
            try:
                siguiente = MAQUINA_ESTADOS_PAQUETE.transicionar(
                    estado.estado, EventoPaquete.ABRIR
                )
            except TransicionInvalida:
                raise PaquetePendiente() from None
            if estado.estado is EstadoPaquete.COMPLETED:
                return estado
            abierto_en = await tx.registrar_apertura(usuario)
            return EstadoPaqueteInicial(siguiente, abierto_en, cartas=estado.cartas)

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
                perfil.abierto_en is not None
                or perfil.cubes != 0
                or await tx.tiene_inventario_o_historial(usuario)
            ):
                raise EstadoProvisionInconsistente("Hay datos de juego sin provisión.")
            return EstadoPaqueteInicial(EstadoPaquete.PENDING_CATALOG)

        # La apertura confirma el premio inicial antes de habilitar recursos mutables.
        if perfil.abierto_en is not None:
            return EstadoPaqueteInicial(EstadoPaquete.COMPLETED, perfil.abierto_en)
        cartas = await validar_premio_sin_abrir(tx, usuario, perfil.cubes)
        return EstadoPaqueteInicial(EstadoPaquete.READY_TO_OPEN, cartas=cartas)


class ColeccionJugadorService:
    """Caso de uso para consultar la colección personal del jugador."""

    def __init__(self, repositorio: ColeccionJugadorPort) -> None:
        self._repositorio = repositorio

    async def listar_cartas(self, usuario_id: str) -> list[CartaColeccion]:
        """Obtiene las cartas en posesión del jugador mediante su puerto."""
        return await self._repositorio.listar_cartas(usuario_id)
