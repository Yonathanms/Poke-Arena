"""Registro declarativo único, sin configurar motores ni ejecutar DDL."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Comparte metadata entre propietarios ORM; no sustituye las migraciones."""

