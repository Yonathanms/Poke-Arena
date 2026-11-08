"""Hash local scrypt con sal aleatoria y parámetros fijos de costo acotado."""

from hashlib import scrypt
from hmac import compare_digest
from secrets import token_bytes

_FORMATO = "scrypt-17-8-1"


def _derivar(password: str, sal: bytes) -> bytes:
    return scrypt(password.encode(), salt=sal, n=2**17, r=8, p=1, maxmem=256 * 1024**2)


def crear_hash(password: str) -> str:
    """Valida la longitud de aprovisionamiento y devuelve un hash con sal única."""
    if not 16 <= len(password) <= 256 or not password.strip():
        raise ValueError("La contraseña requiere de 16 a 256 caracteres")
    sal = token_bytes(16)
    return f"{_FORMATO}${sal.hex()}${_derivar(password, sal).hex()}"


def verificar_hash(password: str, guardado: str) -> bool:
    """Verifica en tiempo constante con parámetros internos, nunca del cliente."""
    try:
        formato, sal, digest = guardado.split("$")
        sal_bin, digest_bin = bytes.fromhex(sal), bytes.fromhex(digest)
        return (
            formato == _FORMATO
            and len(sal_bin) == 16
            and len(digest_bin) == 64
            and 1 <= len(password) <= 256
            and compare_digest(_derivar(password, sal_bin), digest_bin)
        )
    except ValueError:
        return False
