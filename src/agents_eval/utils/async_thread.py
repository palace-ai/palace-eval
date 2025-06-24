import asyncio
import concurrent.futures
import threading
from typing import Any, Coroutine


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
            wrap_with_timeout(coro, timeout=180), self.loop
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
        # if self._main_task:
        #     self._main_task.result()

    def wait_until_ready(self, timeout: float = 5):
        self._ready_event.wait(timeout)

    def wait_for_disconnect(self, timeout: float = 5):
        self._disconnect_done.wait(timeout)
