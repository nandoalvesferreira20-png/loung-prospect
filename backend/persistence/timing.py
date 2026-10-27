"""Request-local timings with fixed labels only; never record SQL or identities."""
from contextvars import ContextVar
from contextlib import contextmanager
from functools import wraps
from time import perf_counter

current = ContextVar('request_timings', default=None)


@contextmanager
def measure(name):
    started = perf_counter()
    try:
        yield
    finally:
        values = current.get()
        if values is not None:
            values[name] = values.get(name, 0) + (perf_counter() - started) * 1000


def timed(name):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            with measure(name):
                return function(*args, **kwargs)
        return wrapped
    return decorate
