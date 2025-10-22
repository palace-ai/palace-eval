import asyncio
import concurrent.futures
import threading
from functools import wraps
from typing import Any, Coroutine

from palace.utils.exceptions import TimeoutException
from palace.utils.printing import print


class AsyncThread:
    """Handles all async/threading operations"""

    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._main_task = None
        self._stop_event = threading.Event()
        self._disconnect_done = threading.Event()
        self._ready_event = threading.Event()
        self._thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_forever()
        finally:
            self.loop.close()

    def reset(self):
        self._stop_event.clear()
        self._disconnect_done.clear()
        self._ready_event.clear()
        self._main_task = None

    def run_async(self, coro: Coroutine) -> Any:
        async def wrap_with_timeout(coro: Coroutine, timeout: int) -> Coroutine:
            try:
                return await asyncio.wait_for(coro, timeout)
            except asyncio.TimeoutError:
                print("Timeout occurred")
                return None
            except Exception as e:
                print(f"Internal error occurred: {e}")
                return None

        return asyncio.run_coroutine_threadsafe(
            wrap_with_timeout(coro, timeout=600), self.loop
        ).result()

    def start_main_task(self, coro: Coroutine):
        async def wrapped_coro():
            try:
                await coro
            finally:
                self._disconnect_done.set()

        self._main_task = asyncio.run_coroutine_threadsafe(wrapped_coro(), self.loop)

    def signal_ready(self):
        self._ready_event.set()

    def signal_stop(self):
        self._stop_event.set()

    def should_stop(self) -> bool:
        return self._stop_event.is_set()

    def wait_for_task(self, timeout: float = 5):
        """Block until the main task finishes, or until timeout (seconds)."""
        if not self._main_task:
            return
        try:
            self._main_task.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            print("Warning: main task did not finish in time")

    def wait_until_ready(self, timeout: float = 5):
        self._ready_event.wait(timeout)

    def wait_for_disconnect(self, timeout: float = 5):
        self._disconnect_done.wait(timeout)


def with_timeout(seconds: int):
    """Decorator that adds timeout to a function"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result_container = [None]
            exception_container = [None]

            def worker():
                try:
                    result_container[0] = func(*args, **kwargs)
                except Exception as e:
                    exception_container[0] = e

            t = threading.Thread(target=worker, daemon=True)
            t.start()
            t.join(seconds)

            if t.is_alive():
                raise TimeoutException(f"Operation timed out after {seconds} seconds")
            if exception_container[0]:
                raise exception_container[0]

            return result_container[0]

        return wrapper

    return decorator
