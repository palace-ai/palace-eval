import asyncio
from contextlib import contextmanager
from typing import Dict, Optional

import nest_asyncio
from anyio import BrokenResourceError
from mcp import ClientSession
from mcp.client.sse import sse_client

from palace.utils.metaclasses import SingletonMetaclass
from palace.utils.threading import AsyncThread

# enable nested asyncio if running in jupyter notebook
try:
    from IPython import get_ipython

    if "IPKernelApp" in get_ipython().config:
        nest_asyncio.apply()
except Exception:
    pass  # not running in jupyter notebook


class MCPClient(metaclass=SingletonMetaclass):
    """Single class interface with simplified API"""

    def __init__(self):
        self.session: Optional[ClientSession] = None
        self._async = AsyncThread()
        self._streams_context = None
        self._session_context = None
        self._connected = False

    @contextmanager
    def connection(self, url: str, token: Optional[str] = None):
        """
        Context manager for connection lifecycle.

        Usage:
            with MCPClient().connection("http://localhost:8080/sse") as mcp_client:
                mcp_client.list_tools()
        """
        try:
            self.connect(url, token)
            yield self
        finally:
            self.disconnect()

    def connect(self, url: str, token: Optional[str] = None):
        if self._connected:
            raise RuntimeError("Already connected")

        if self._async.loop.is_closed():
            self._async = AsyncThread()

        async def _main():
            headers = {"Authorization": f"Bearer {token}"} if token else {}

            try:
                self._streams_context = sse_client(url=url, headers=headers)
                streams = await self._streams_context.__aenter__()

                self._session_context = ClientSession(*streams)
                self.session = await self._session_context.__aenter__()
                await self.session.initialize()

                self._async.signal_ready()

                while not self._async.should_stop():
                    await asyncio.sleep(0.1)

            finally:
                await self._cleanup_resources()

        self._async.start_main_task(_main())
        self._async.wait_until_ready(5)
        self._connected = True

    async def _cleanup_resources(self):
        """Safely clean up all resources, ignoring expected errors"""
        # Clean up session first
        if self._session_context is not None:
            try:
                # safety timeout on whatever the library might hang on
                await asyncio.wait_for(
                    self._session_context.__aexit__(None, None, None), timeout=10.0
                )
            except asyncio.TimeoutError:
                print("Timeout during session cleanup, skipping")
            except BrokenResourceError:
                pass
            except Exception as e:
                print(f"Unexpected error during cleanup: {e!r}")
            finally:
                self._session_context = None
                self.session = None

        # Then clean up streams
        if self._streams_context is not None:
            try:
                await asyncio.wait_for(
                    self._streams_context.__aexit__(None, None, None), timeout=10.0
                )
            except asyncio.TimeoutError:
                print("Timeout during streams cleanup, skipping")
            except BrokenResourceError:
                pass
            except Exception as e:
                print(f"Unexpected error during cleanup: {e!r}")
            finally:
                self._streams_context = None

    def list_tools(self):
        if not self._connected:
            raise RuntimeError("Not connected")
        return self._async.run_async(self.session.list_tools())

    def call_tool(self, tool_name: str, parameters: Dict[str, str]):
        if not self._connected:
            raise RuntimeError("Not connected")
        return self._async.run_async(self.session.call_tool(tool_name, parameters))

    def disconnect(self):
        if not self._connected:
            return

        self._async.signal_stop()
        try:
            # give the cleanup event up to 5s...
            self._async.wait_for_disconnect(timeout=10)
            # ...and the task itself up to another 5s
            self._async.wait_for_task(timeout=10)
        except Exception as e:
            print(f"Warning during disconnect: {e!r}")
        finally:
            self._force_reset_state()

    def _force_reset_state(self):
        """Completely reset the state regardless of previous errors"""
        self.session = None
        self._streams_context = None
        self._session_context = None
        self._connected = False
        self._async.reset()
