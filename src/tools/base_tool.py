from abc import ABC, abstractmethod
from typing import Dict


class Tool(ABC):
    """Base class for tools that agents can use.

    Attributes:
        ASYNC (bool): By default, tools are not asynchronous. If a tool is required to be asynchronous (e.g. to run external resources), override this class attribute and set it to True. Defaults to False."""

    # ASYNC: bool = False

    @abstractmethod
    def execute(self, *args, **kwargs) -> str:
        """Execute the tool functionality."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the tool."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Return the description of the tool."""
        pass

    @property
    @abstractmethod
    def parameters(self) -> Dict[str, str]:
        """Return the parameters required by the tool along with their description."""
        pass
