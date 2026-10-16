"""Opt-in timing without lead data; callback errors never include exception text."""
from contextlib import contextmanager
import logging
import os
from pathlib import Path
from time import perf_counter
import traceback

LOGGER = logging.getLogger("loung.sdr")


def event(stage, **measurements):
    if os.getenv("LOUNG_SDR_DEBUG") == "1":
        if not LOGGER.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
            LOGGER.addHandler(handler)
            LOGGER.propagate = False
        LOGGER.setLevel(logging.INFO)
        LOGGER.info("%s %s", stage, measurements)


@contextmanager
def timed(stage):
    start = perf_counter()
    try:
        yield
    finally:
        event(stage, seconds=round(perf_counter() - start, 4))


def callback_error(error_type, error, tb):
    frames = " > ".join(f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}"
                        for frame in traceback.extract_tb(tb))
    LOGGER.error("callback_error type=%s frames=%s", error_type.__name__, frames)


def log_current_error():
    import sys
    callback_error(*sys.exc_info())
