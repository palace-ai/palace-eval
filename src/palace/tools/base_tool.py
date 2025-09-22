from abc import ABC, abstractmethod
from typing import Dict, List


class Tool(ABC):
    """Base class for tools that agents can use.
    """

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
        """Return the parameters that can be passed to the tool along with their description."""
        pass

    @property
    def required_parameters(self) -> List[str]:
        """Return the list of required parameters. By default, all of them are required. Override this method to define required ones."""
        return [k for k in self.parameters]