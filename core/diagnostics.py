"""Temporary opt-in tracing through the existing log callback."""
import json
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, is_dataclass

_logger = ContextVar("website_diagnostic_logger", default=None)


def enabled():
    return _logger.get() is not None


@contextmanager
def diagnostic_logging(log):
    token = _logger.set(log)
    try:
        yield
    finally:
        _logger.reset(token)


def trace(stage, **values):
    callback = _logger.get()
    if callback is None:
        return
    try:
        callback("[DIAG " + stage + "] " + json.dumps(
            values, ensure_ascii=False,
            default=lambda value: asdict(value) if is_dataclass(value) else str(value),
        ))
    except Exception:
        pass  # Diagnostics must never interrupt collection/qualification.
