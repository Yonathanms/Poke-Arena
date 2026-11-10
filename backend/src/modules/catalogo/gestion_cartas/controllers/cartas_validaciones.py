"""Validaciones descriptivas para los endpoints de cartas (RFC 7807)."""

from src.shared.http_module import problema

from .cartas_dtos import RarezaCarta, TipoCarta


def validar_parametros_busqueda(
    pagina: int | None = 1,
    limite: int | None = 15,
    tipo: str | None = None,
    costo: int | None = None,
    rareza: str | None = None,
) -> tuple[int, int, TipoCarta | None, RarezaCarta | None]:
    """Valida los filtros de búsqueda según US 3.1.2 devolviendo 422 descriptivo ante errores."""
    if pagina is not None and pagina < 1:
        raise problema(
            422,
            "paginacion_invalida",
            "El parámetro 'pagina' debe ser un número entero mayor o igual a 1.",
        )
    limite_efectivo = limite if limite is not None else 15
    if limite_efectivo < 1 or limite_efectivo > 100:
        raise problema(
            422,
            "paginacion_invalida",
            "El parámetro 'limite' debe ser un número entero entre 1 y 100.",
        )

    tipo_dto: TipoCarta | None = None
    if tipo is not None and tipo.strip() != "":
        tipo_limpio = tipo.strip().upper()
        try:
            tipo_dto = TipoCarta(tipo_limpio)
        except ValueError:
            valores_permitidos = ", ".join(t.value for t in TipoCarta if t.value != "INC")
            raise problema(
                422,
                "tipo_invalido",
                f"Tipo elemental inválido '{tipo}'. Valores permitidos: {valores_permitidos}.",
            )

    if costo is not None and (costo < 0 or costo > 10):
        raise problema(
            422,
            "costo_invalido",
            f"Costo de energía '{costo}' fuera de rango. Valores permitidos: entre 0 y 10.",
        )

    rareza_dto: RarezaCarta | None = None
    if rareza is not None and rareza.strip() != "":
        rareza_limpia = rareza.strip().upper()
        try:
            rareza_dto = RarezaCarta(rareza_limpia)
        except ValueError:
            valores_permitidos = ", ".join(r.value for r in RarezaCarta)
            raise problema(
                422,
                "rareza_invalida",
                f"Rareza inválida '{rareza}'. Valores permitidos: {valores_permitidos}.",
            )

    pagina_efectiva = pagina if pagina is not None else 1
    return limite_efectivo, pagina_efectiva, tipo_dto, rareza_dto

