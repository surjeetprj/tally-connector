"""Bounded, payload-free diagnostics. HTTPX/Huey internals never log secrets."""
import logging
from logging.handlers import RotatingFileHandler
import re


class Redact(logging.Filter):
    def filter(self, record):
        message = record.getMessage()
        record.msg = re.sub(r"eb_live_[0-9a-fA-F]+|Bearer\s+\S+", "[REDACTED]", message)
        record.args = ()
        return True


def configure(directory):
    path = directory / "logs"
    path.mkdir(exist_ok=True)
    handler = RotatingFileHandler(path / "connector.log", maxBytes=1024 * 1024, backupCount=3, encoding="utf-8")
    handler.addFilter(Redact())
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    for name in ("httpx", "httpcore", "huey"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
    return handler
