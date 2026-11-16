"""Small, flushed phase records for otherwise silent Cloud computations."""

from contextlib import contextmanager
import json
import sys
import time


@contextmanager
def daily_phase(stage: str):
    started = time.monotonic()
    cpu_started = time.process_time()

    def emit(event: str):
        print(json.dumps({
            "identity": "CLOUD_DAILY_PHASE_V1", "stage": stage,
            "event": event, "elapsed_seconds": round(time.monotonic() - started, 3),
            "cpu_seconds": round(time.process_time() - cpu_started, 3),
        }), file=sys.stderr, flush=True)

    emit("started")
    try:
        yield
    except BaseException:
        emit("failed")
        raise
    else:
        emit("finished")


def recorded_phase(stage):
    """Instrument a pure call without inspecting its arguments or return value."""
    from functools import wraps
    def decorate(function):
        @wraps(function)
        def traced(*args, **kwargs):
            with daily_phase(stage):
                return function(*args, **kwargs)
        return traced
    return decorate
