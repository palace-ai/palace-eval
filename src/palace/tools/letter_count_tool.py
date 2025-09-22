import re
from typing import Dict

from palace.tools import Tool


class LetterCountTool(Tool):
    def execute(self, *args, **kwargs) -> str:
        """Execute the tool functionality."""
        # Check parameter compliance
        for parameter in self.required_parameters:
            if parameter not in kwargs:
                return f"""Tool `{self.name}` encountered the following error: parameter `{parameter}` was not found in the tool call but it is required. Make sure to comply with the required parameters name and type. For this tool, the required parameters are the following:
{self.required_parameters}"""

        return str(len(re.findall(kwargs["letter"], kwargs["word"], re.DOTALL)))

    @property
    def name(self) -> str:
        """Return the name of the tool."""
        return "Letter Count Tool"

    @property
    def description(self) -> str:
        """Return the description of the tool."""
        return "Count the number of occurrences of a given letter within a given word. This search is case-sensitive."

    @property
    def parameters(self) -> Dict[str, str]:
        """Return the parameters required by the tool along with their description."""
        return {
            "letter": "The letter to find the number of occurrences of.",
            "word": "The word in which to look for the given letter.",
        }
