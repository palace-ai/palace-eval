# Copyright (C) 2025 European Union
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the European Union Public Licence (EUPL) v. 1.2
# as published by the European Union.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# European Union Public Licence for more details.
#
# You should have received a copy of the European Union Public Licence
# along with this program. If not, see <https://joinup.ec.europa.eu/collection/eupl/eupl-text-eupl-12>.

import asyncio
import concurrent.futures
import os
import threading
from typing import Any, Coroutine, Optional

import psutil

from palace.utils.exceptions import TimeoutException
from palace.utils.printing import print


class AsyncThread:
    """Handles all async/threading operations"""

    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.check_file_descriptors()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._main_task = None
        self._stop_event = threading.Event()
        self._disconnect_done = threading.Event()
        self._ready_event = threading.Event()
        self._started = True  # Track if thread is running
        self._thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_forever()
        finally:
            # Clean up all remaining tasks
            pending = asyncio.all_tasks(self.loop)
            for task in pending:
                task.cancel()

            # Run final iteration to complete cancellations
            if pending:
                self.loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )

            self.loop.close()
            self._started = False

    def reset(self):
        """Only reset events, don't recreate thread/loop"""
        self._stop_event.clear()
        self._disconnect_done.clear()
        self._ready_event.clear()
        self._main_task = None

    def stop(self):
        """Properly stop the thread and event loop"""
        if not self._started:
            return

        # Signal stop and stop the event loop
        self.signal_stop()
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)

        # Wait for thread to finish with timeout
        if self._thread.is_alive():
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                print("Warning: AsyncThread did not stop gracefully")

        self._started = False

    def run_async(self, coro: Coroutine) -> Any:
        async def wrap_with_timeout(
            coro: Coroutine, timeout: int
        ) -> Optional[Coroutine]:
            try:
                return await asyncio.wait_for(coro, timeout)
            except asyncio.TimeoutError:
                print("Timeout occurred")
                return None
            except Exception as e:
                print(f"Internal error occurred: {e}")
                return None

        # Check if loop is closed before running
        if self.loop.is_closed():
            raise RuntimeError("Event loop is closed")

        return asyncio.run_coroutine_threadsafe(
            wrap_with_timeout(coro, timeout=600), self.loop
        ).result()

    def start_main_task(self, coro: Coroutine):
        if self.loop.is_closed():
            raise RuntimeError("Cannot start task on closed event loop")

        async def wrapped_coro():
            try:
                await coro
            except Exception as e:
                print(f"Error in main task: {e}")
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
        except Exception as e:
            print(f"Error in main task: {e}")

    def wait_until_ready(self, timeout: float = 5):
        if not self._ready_event.wait(timeout):
            raise TimeoutException("AsyncThread not ready within timeout")

    def wait_for_disconnect(self, timeout: float = 5):
        self._disconnect_done.wait(timeout)

    def is_running(self):
        return self._started and not self.loop.is_closed()

    @staticmethod
    def check_file_descriptors():
        process = psutil.Process(os.getpid())
        fd_count = process.num_fds()
        if fd_count > 1000:  # Adjust threshold as needed
            print(
                f"[bold on_yellow][WARN][/] High file descriptor usage detected: {fd_count}."
            )
