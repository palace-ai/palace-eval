import asyncio
from contextlib import contextmanager
from threading import Lock
from typing import Any, Optional

import anyio
import nest_asyncio
from anyio import BrokenResourceError
from mcp import ClientSession
from mcp.client.sse import sse_client

from palace.utils.exceptions import TimeoutException
from palace.utils.threading import AsyncThread

# enable nested asyncio if running in jupyter notebook
try:
    from IPython.core.getipython import get_ipython

    ipython = get_ipython()
    if ipython is not None and "IPKernelApp" in ipython.config:
        nest_asyncio.apply()
except Exception:
    pass  # not running in jupyter notebook


class MCPClientPool:
    """Pool for reusing MCPClient connections"""

    _instances: dict[str, "MCPClient"] = {}
    _lock = Lock()
    _usage_count: dict[str, int] = {}

    @classmethod
    @contextmanager
    def get_connection(cls, url: str, token: Optional[str] = None):
        """
        Context manager that provides a client connection from the pool.

        Usage:
            with MCPClientPool.get_connection("http://localhost:8080/sse") as client:
                client.list_tools()
        """
        client = None
        try:
            client = cls._get_client(url)
            with client.connection(url, token):
                yield client
        finally:
            if client:
                cls._release_client(url)

    @classmethod
    def _get_client(cls, url: str) -> "MCPClient":
        """Get or create a client for the given URL"""
        with cls._lock:
            if url not in cls._instances:
                cls._instances[url] = MCPClient()
                cls._usage_count[url] = 0

            cls._usage_count[url] += 1
            return cls._instances[url]

    @classmethod
    def _release_client(cls, url: str):
        """Release a client after use"""
        with cls._lock:
            if url in cls._usage_count:
                cls._usage_count[url] -= 1

                # If no one is using this client, clean it up
                if cls._usage_count[url] <= 0:
                    client = cls._instances.pop(url, None)
                    if client:
                        client.disconnect()
                    cls._usage_count.pop(url, None)

    @classmethod
    def cleanup_all(cls):
        """Clean up all clients in the pool"""
        with cls._lock:
            for url, client in list(cls._instances.items()):
                client.disconnect()
            cls._instances.clear()
            cls._usage_count.clear()


class MCPClient:
    """Single class interface with simplified API"""

    def __init__(self):
        self.session: Optional[ClientSession] = None
        self._async: Optional[AsyncThread] = None
        self._streams_context = None
        self._session_context = None
        self._connected = False
        self._url: Optional[str] = None

    def __del__(self):
        """Ensure cleanup on garbage collection"""
        self.disconnect()

    @contextmanager
    def connection(self, url: str, token: Optional[str] = None):
        """
        Context manager for connection lifecycle.
        """
        try:
            self.connect(url, token)
            yield self
        finally:
            self.disconnect()

    def connect(self, url: str, token: Optional[str] = None):
        if self._connected:
            raise RuntimeError("Already connected")

        # Create new async thread if needed
        if self._async is None or not self._async.is_running():
            self._async = AsyncThread()

        self._url = url

        async def _main():
            assert self._url is not None
            assert self._async is not None

            try:
                async with sse_client(
                    url=self._url,
                    headers={"Authorization": f"Bearer {token}"} if token else {},
                ) as streams:
                    async with ClientSession(*streams) as session:
                        self.session = session
                        await session.initialize()

                        self._async.signal_ready()

                        # Keep the connection alive until stop signal
                        try:
                            while not self._async.should_stop():
                                await asyncio.sleep(0.1)
                        except anyio.get_cancelled_exc_class():
                            print(
                                "[red]Exception in MCPClient: Connection was cancelled"
                            )
                            raise

            except Exception as e:
                # print(f"[red]Exception in MCPClient: Error in connection: {e}")
                self._async.signal_ready()  # Always signal ready to avoid deadlock
            finally:
                # No manual cleanup needed - async with handles it
                self.session = None

        self._async.start_main_task(_main())

        try:
            self._async.wait_until_ready(15)  # Increased timeout
            self._connected = True
        except TimeoutException:
            # If we timeout, check if the async task failed
            if self._async._main_task and self._async._main_task.done():
                try:
                    self._async._main_task.result()  # This will raise the actual error
                except Exception as e:
                    raise ConnectionError(
                        f"[red]Exception in MCPClient: Failed to connect to {url}: {e}"
                    )
            raise TimeoutException(
                f"[red]Exception in MCPClient: Connection to {url} timed out after 15 seconds"
            )

    async def _cleanup_resources(self):
        """Safely clean up all resources, ignoring expected errors"""
        cleanup_tasks = []

        if self._session_context is not None:

            async def cleanup_session():
                try:
                    if self._session_context is None:
                        raise RuntimeError(
                            "Session context is already None during cleanup."
                        )
                    await asyncio.wait_for(
                        self._session_context.__aexit__(None, None, None), timeout=10.0
                    )
                except asyncio.TimeoutError:
                    print(
                        "[red]Exception in MCPClient: Timeout during session cleanup, skipping"
                    )
                except BrokenResourceError:
                    pass
                except Exception as e:
                    print(
                        f"[red]Exception in MCPClient: Unexpected error during session cleanup: {e!r}"
                    )
                finally:
                    self._session_context = None
                    self.session = None

            cleanup_tasks.append(cleanup_session())

        if self._streams_context is not None:

            async def cleanup_streams():
                try:
                    if self._streams_context is None:
                        raise RuntimeError(
                            "[red]Exception in MCPClient: Streams context is already None during cleanup."
                        )
                    await asyncio.wait_for(
                        self._streams_context.__aexit__(None, None, None), timeout=10.0
                    )
                except asyncio.TimeoutError:
                    print(
                        "[red]Exception in MCPClient: Timeout during streams cleanup, skipping"
                    )
                except BrokenResourceError:
                    pass
                except Exception as e:
                    print(
                        f"[red]Exception in MCPClient: Unexpected error during streams cleanup: {e!r}"
                    )
                finally:
                    self._streams_context = None

            cleanup_tasks.append(cleanup_streams())

        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)

    def list_tools(self):
        if not self._connected:
            raise RuntimeError("[red]Exception in MCPClient: Not connected")
        if self.session is None:
            raise RuntimeError(
                "[red]Exception in MCPClient: list_tools called on a None session"
            )
        if self._async is None:
            raise RuntimeError(
                "[red]Exception in MCPClient: MCPClient async thread is not initialized"
            )
        return self._async.run_async(self.session.list_tools())

    def call_tool(self, tool_name: str, parameters: dict[str, Any]):
        if not self._connected:
            raise RuntimeError("[red]Exception in MCPClient: Not connected")
        if self.session is None:
            raise RuntimeError(
                "[red]Exception in MCPClient: call_tool called on a None session"
            )
        if self._async is None:
            raise RuntimeError(
                "[red]Exception in MCPClient: MCPClient async thread is not initialized"
            )
        return self._async.run_async(self.session.call_tool(tool_name, parameters))

    def disconnect(self):
        if not self._connected:
            return

        try:
            # Signal stop and wait for cleanup
            if self._async:
                self._async.signal_stop()
                self._async.wait_for_disconnect(timeout=10)
                self._async.wait_for_task(timeout=10)
        except Exception as e:
            print(f"[red]Exception in MCPClient: Warning during disconnect: {e!r}")
        finally:
            self._force_reset_state()

    def _force_reset_state(self):
        """Completely reset the state regardless of previous errors"""
        self.session = None
        self._streams_context = None
        self._session_context = None
        self._connected = False
        self._url = None

        # Stop the async thread completely
        if self._async:
            self._async.stop()
            self._async = None
