from palace.tools import Tool


class FinalAnswerTool(Tool):
    def execute(self, **kwargs) -> str:
        """Execute the tool functionality."""
        # Check parameter compliance
        for parameter in self.required_parameters:
            if parameter not in kwargs:
                return f"""Tool `{self.name}` encountered the following error: parameter `{parameter}` was not found in the tool call but it is required. Make sure to comply with the required parameters name and type. For this tool, the required parameters are the following:
{self.required_parameters}"""

        final_answer = kwargs["final_answer"]
        return final_answer

    @property
    def name(self) -> str:
        """Return the name of the tool."""
        return "Final Answer Tool"

    @property
    def description(self) -> str:
        """Return the description of the tool."""
        return "This tool is required to complete your assigned task. When you are ready to provide a final answer to the user, make sure to call this tool to complete your task, passing your final answer as a parameter. Make sure to only call this tool once you are absolutely sure of the final result you want to submit; after calling this tool, you won't be able to continue and the process will be interrupted. You will be evaluated according to the answer you pass to this tool, checking if it is the correct answer for the given task."

    @property
    def parameters(self) -> dict[str, str]:
        """Return the parameters required by the tool along with their description."""
        return {
            "final_answer": "Your final answer for the given task. You can call this tool only once, so make sure to be absolutely sure of your final answer before calling it.",
        }
