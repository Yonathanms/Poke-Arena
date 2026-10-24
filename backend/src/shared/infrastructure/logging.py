"""Configuración de observabilidad y registro estructurado en JSON (RNF-OBS-01, RNF-OBS-02)."""

import json
import logging
import sys
from datetime import UTC, datetime

from src.shared.domain.correlation import get_current_correlation_id


class JsonLogFormatter(logging.Formatter):
    """Formateador de logs en JSON estructurado con correlation_id."""

    def format(self, record: logging.LogRecord) -> str:
        log_payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", None)
            or get_current_correlation_id(),
        }
        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_payload, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    """Configura el manejador raíz para emitir logs en formato JSON."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
