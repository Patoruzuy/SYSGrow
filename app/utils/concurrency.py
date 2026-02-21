"""
Concurrency utilities.

Provides a `synchronized` decorator that acquires an instance `_lock` if present.
Supports both sync and async functions (note: acquiring a threading lock in async
functions will block the event loop; project currently uses this decorator
for synchronous methods).
"""

from __future__ import annotations

import inspect
from functools import wraps
from typing import Callable


def synchronized(func: Callable) -> Callable:
    """Decorator that acquires `self._lock` if present on the instance.

    Works for normal functions and async coroutines. If no `_lock` attribute
    exists on `self`, the function is executed without locking.
    """
    if inspect.iscoroutinefunction(func):

        @wraps(func)
        async def _async_wrapped(*args, **kwargs):
            self = args[0] if args else None
            lock = getattr(self, "_lock", None)
            if lock is None:
                return await func(*args, **kwargs)
            with lock:
                return await func(*args, **kwargs)

        return _async_wrapped

    @wraps(func)
    def _wrapped(*args, **kwargs):
        self = args[0] if args else None
        lock = getattr(self, "_lock", None)
        if lock is None:
            return func(*args, **kwargs)
        with lock:
            return func(*args, **kwargs)

    return _wrapped
