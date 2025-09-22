from typing import Dict

from palace.tools import Tool


class PythonInterpreterTool(Tool):
    def execute(self, *args, **kwargs) -> str:
        """Execute the tool functionality."""
        # Check parameter compliance
        for parameter in self.required_parameters:
            if parameter not in kwargs:
                return f"""Tool `{self.name}` encountered the following error: parameter `{parameter}` was not found in the tool call but it is required. Make sure to comply with the required parameters name and type. For this tool, the required parameters are the following:
{self.required_parameters}"""

        namespace = {"result": None}
        exec(kwargs["code"], namespace)

        if namespace["result"] is None:
            return "For some reason to me unknown, the provided code didn't produce any result. Remember that to return a result, you can't use the `return` keyword, but instead you have to assign it to the variable `result`. Also, make sure that the provided code is a valid Python code."
        else:
            return str(namespace["result"])

    @property
    def name(self) -> str:
        """Return the name of the tool."""
        return "Python Interpreter Tool"

    @property
    def description(self) -> str:
        """Return the description of the tool."""
        return """Execute an arbitrary Python code passed as input. 
Important: this does not evaluate the code as an expression! For instance, `return` statements won't work.
Instead, in order to return a final result, you have to assign whatever you want to return to the `result` variable."""

    @property
    def parameters(self) -> Dict[str, str]:
        """Return the parameters required by the tool along with their description."""
        return {
            "code": "The Python code to be executed.",
        }
