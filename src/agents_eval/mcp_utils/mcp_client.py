import asyncio
from contextlib import contextmanager
from typing import Dict, Optional

import nest_asyncio
from anyio import BrokenResourceError
from mcp import ClientSession
from mcp.client.sse import sse_client

from agents_eval.utils.async_thread import AsyncThread
from agents_eval.utils.metaclasses import SingletonMetaclass

# enable nested asyncio if running in jupyter notebook
try:
    from IPython import get_ipython

    if "IPKernelApp" in get_ipython().config:
        nest_asyncio.apply()
except Exception:
    pass  # not running in jupyter notebook


# class MCPClientV1(metaclass=SingletonMetaclass):
#     def __init__(self):
#         self.session: Optional[ClientSession] = None
#         self._streams_context = None
#         self._session_context = None
#         self._connected = False

#     def _run_async(self, coro):
#         """Run an async coroutine in a way that preserves context"""
#         try:
#             # Get the current event loop if one exists
#             loop = asyncio.get_event_loop()
#         except RuntimeError:
#             # If no event loop exists in this thread, create one
#             loop = asyncio.new_event_loop()
#             asyncio.set_event_loop(loop)

#         return loop.run_until_complete(coro)

#     def connect(
#         self, url: str = "http://localhost:8080/sse", token: Optional[str] = None
#     ):
#         """Connect to the MCP server"""
#         if not self._connected:
#             # Prepare headers if token is provided
#             headers = {}
#             if token:
#                 headers["Authorization"] = f"Bearer {token}"

#             # Create streams
#             self._streams_context = sse_client(url=url, headers=headers)
#             streams = self._run_async(self._streams_context.__aenter__())

#             # Create and initialize session
#             self._session_context = ClientSession(*streams)
#             self.session = self._run_async(self._session_context.__aenter__())
#             self._run_async(self.session.initialize())
#             self._connected = True

#     def list_tools(self):
#         """Get available tools"""
#         if not self._connected:
#             raise RuntimeError("Client not initialized. Call connect first.")

#         return self._run_async(self.session.list_tools())

#     def call_tool(self, tool_name: str, parameters: Dict[str, str]):
#         """Call a tool with parameters"""
#         if not self._connected:
#             raise RuntimeError("Client not initialized. Call connect first.")

#         return self._run_async(self.session.call_tool(tool_name, parameters))

#     def disconnect(self):
#         """Clean up resources."""
#         if not self._connected:
#             return

#         try:
#             if self._session_context:
#                 self._run_async(self._session_context.__aexit__(None, None, None))
#                 self._session_context = None

#             if self._streams_context:
#                 self._run_async(self._streams_context.__aexit__(None, None, None))
#                 self._streams_context = None
#         finally:
#             self._connected = False


# class MCPClientV2(metaclass=SingletonMetaclass):
#     def __init__(self):
#         self.session: Optional[ClientSession] = None
#         self._loop: Optional[asyncio.AbstractEventLoop] = None
#         self._thread: Optional[threading.Thread] = None
#         self._connected = False
#         self._main_task = None
#         self._connect_event = threading.Event()
#         self._disconnect_event = threading.Event()
#         self._start_background_loop()

#     def _start_background_loop(self):
#         """Start a dedicated event loop thread."""
#         if self._loop is None or not self._loop.is_running():
#             self._loop = asyncio.new_event_loop()
#             self._thread = threading.Thread(
#                 target=self._run_background_loop, args=(self._loop,), daemon=True
#             )
#             self._thread.start()

#     @staticmethod
#     def _run_background_loop(loop: asyncio.AbstractEventLoop):
#         """Run the event loop indefinitely."""
#         asyncio.set_event_loop(loop)
#         try:
#             loop.run_forever()
#         finally:
#             loop.close()

#     def _run_async(self, coro):
#         """Run a coroutine in the background loop and wait for its result."""
#         return asyncio.run_coroutine_threadsafe(coro, self._loop).result()

#     def connect(
#         self, url: str = "http://localhost:8080/sse", token: Optional[str] = None
#     ):
#         """Connect to the MCP server."""
#         if self._connected:
#             return

#         async def _main():
#             """Main async context manager routine."""
#             headers = {"Authorization": f"Bearer {token}"} if token else {}

#             # Enter SSE client context
#             streams_ctx = sse_client(url=url, headers=headers)
#             streams = await streams_ctx.__aenter__()

#             # Enter ClientSession context
#             session_ctx = ClientSession(*streams)
#             session = await session_ctx.__aenter__()
#             await session.initialize()

#             # Update state
#             self.session = session
#             self._connected = True
#             self._connect_event.set()

#             # Wait for disconnect signal
#             await self._wait_for_disconnect()

#             # Exit contexts
#             await session_ctx.__aexit__(None, None, None)
#             await streams_ctx.__aexit__(None, None, None)
#             self._connected = False
#             self._disconnect_event.clear()

#         # Schedule the main coroutine in the background loop
#         self._main_task = asyncio.run_coroutine_threadsafe(_main(), self._loop)
#         # Wait for connection to complete
#         self._connect_event.wait()

#     async def _wait_for_disconnect(self):
#         """Wait for disconnect signal in an async-friendly way."""
#         while not self._disconnect_event.is_set():
#             await asyncio.sleep(0.1)

#     def list_tools(self):
#         """Get available tools."""
#         if not self._connected:
#             raise RuntimeError("Client not initialized. Call connect first.")
#         return self._run_async(self.session.list_tools())

#     def call_tool(self, tool_name: str, parameters: Dict[str, str]):
#         """Call a tool with parameters."""
#         if not self._connected:
#             raise RuntimeError("Client not initialized. Call connect first.")
#         return self._run_async(self.session.call_tool(tool_name, parameters))

#     def disconnect(self):
#         """Clean up resources."""
#         if not self._connected:
#             return

#         # Signal the async task to exit
#         self._disconnect_event.set()

#         # Wait for disconnect to complete
#         self._main_task.result()  # Wait for the async task to finish
#         self._main_task = None
#         self._connect_event.clear()


# class MCPClientV3(metaclass=SingletonMetaclass):
#     """Single class interface with simplified API"""

#     def __init__(self):
#         self.session: Optional[ClientSession] = None
#         self._async = AsyncThread()
#         self._streams_context = None
#         self._session_context = None
#         self._connected = False

#     @contextmanager
#     def connection(self, url: str, token: Optional[str] = None):
#         """
#         Context manager for connection lifecycle.

#         Usage:
#             with MCPClientV3().connection("http://localhost:8080/sse") as mcp_client:
#                 mcp_client.list_tools()
#         """
#         try:
#             self.connect(url, token)
#             yield self
#         finally:
#             self.disconnect()

#     def connect(self, url: str, token: Optional[str] = None):
#         if self._connected:
#             raise RuntimeError("Already connected")

#         if self._async.loop.is_closed():
#             self._async = AsyncThread()

#         async def _main():
#             headers = {"Authorization": f"Bearer {token}"} if token else {}

#             self._streams_context = sse_client(url=url, headers=headers)
#             streams = await self._streams_context.__aenter__()

#             self._session_context = ClientSession(*streams)
#             self.session = await self._session_context.__aenter__()
#             await self.session.initialize()

#             self._async.signal_ready()

#             while not self._async.should_stop():
#                 await asyncio.sleep(0.1)

#             await self._session_context.__aexit__(None, None, None)
#             await self._streams_context.__aexit__(None, None, None)

#         self._async.start_main_task(_main())
#         self._async.wait_until_ready(5)
#         self._connected = True

#     def list_tools(self):
#         if not self._connected:
#             raise RuntimeError("Not connected")
#         return self._async.run_async(self.session.list_tools())

#     def call_tool(self, tool_name: str, parameters: Dict[str, str]):
#         if not self._connected:
#             raise RuntimeError("Not connected")
#         return self._async.run_async(self.session.call_tool(tool_name, parameters))

#     def disconnect(self):
#         if not self._connected:
#             return

#         self._async.signal_stop()
#         self._async.wait_for_disconnect(5)
#         self._async.wait_for_task()

#         # Reset state without stopping loop
#         self._async.reset()
#         self.session = None
#         self._streams_context = None
#         self._session_context = None
#         self._connected = False


# class MCPClientV4(metaclass=SingletonMetaclass):
#     """Single class interface with simplified API"""

#     def __init__(self):
#         self.session: Optional[ClientSession] = None
#         self._async = AsyncThread()
#         self._streams_context = None
#         self._session_context = None
#         self._connected = False

#     @contextmanager
#     def connection(self, url: str, token: Optional[str] = None):
#         """
#         Context manager for connection lifecycle.

#         Usage:
#             with MCPClient().connection("http://localhost:8080/sse") as mcp_client:
#                 mcp_client.list_tools()
#         """
#         try:
#             self.connect(url, token)
#             yield self
#         finally:
#             self.disconnect()

#     def connect(self, url: str, token: Optional[str] = None):
#         if self._connected:
#             raise RuntimeError("Already connected")

#         if self._async.loop.is_closed():
#             self._async = AsyncThread()

#         async def _main():
#             headers = {"Authorization": f"Bearer {token}"} if token else {}

#             try:
#                 self._streams_context = sse_client(url=url, headers=headers)
#                 streams = await self._streams_context.__aenter__()

#                 self._session_context = ClientSession(*streams)
#                 self.session = await self._session_context.__aenter__()
#                 await self.session.initialize()

#                 self._async.signal_ready()

#                 while not self._async.should_stop():
#                     await asyncio.sleep(0.1)

#             finally:
#                 await self._cleanup_resources()

#             # await self._session_context.__aexit__(None, None, None)
#             # await self._streams_context.__aexit__(None, None, None)

#         self._async.start_main_task(_main())
#         self._async.wait_until_ready(5)
#         self._connected = True

#     async def _cleanup_resources(self):
#         """Safely clean up all resources, ignoring expected errors"""
#         # Clean up session first
#         if self._session_context is not None:
#             try:
#                 await self._session_context.__aexit__(None, None, None)
#             except BrokenResourceError:
#                 pass
#             except Exception as e:
#                 print(f"Unexpected error during cleanup: {repr(e)}")
#             finally:
#                 self._session_context = None
#                 self.session = None

#         # Then clean up streams
#         if self._streams_context is not None:
#             try:
#                 await self._streams_context.__aexit__(None, None, None)
#             except BrokenResourceError:
#                 pass
#             except Exception as e:
#                 print(f"Unexpected error during cleanup: {repr(e)}")
#             finally:
#                 self._streams_context = None

#     def list_tools(self):
#         if not self._connected:
#             raise RuntimeError("Not connected")
#         return self._async.run_async(self.session.list_tools())

#     def call_tool(self, tool_name: str, parameters: Dict[str, str]):
#         if not self._connected:
#             raise RuntimeError("Not connected")
#         return self._async.run_async(self.session.call_tool(tool_name, parameters))

#     def disconnect(self):
#         if not self._connected:
#             return

#         self._async.signal_stop()
#         try:
#             self._async.wait_for_disconnect(5)
#             self._async.wait_for_task()
#         except Exception as e:
#             print(f"Warning during disconnect: {repr(e)}")
#         finally:
#             self._force_reset_state()

#     def _force_reset_state(self):
#         """Completely reset the state regardless of previous errors"""
#         self.session = None
#         self._streams_context = None
#         self._session_context = None
#         self._connected = False
#         self._async.reset()


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

            # await self._session_context.__aexit__(None, None, None)
            # await self._streams_context.__aexit__(None, None, None)

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
