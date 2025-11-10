from pydantic import BaseModel, Field

from palace.tools import Tool


class HumanTool(Tool):
    def execute(self, **kwargs) -> str:
        """Execute the tool functionality."""
        # Check parameter compliance
        for parameter in self.required_parameters:
            if parameter not in kwargs:
                return f"""Tool `{self.name}` encountered the following error: parameter `{parameter}` was not found in the tool call but it is required. Make sure to comply with the required parameters name and type. For this tool, the required parameters are the following:
{self.required_parameters}"""

        response = input(kwargs["query"])
        return response

    @property
    def name(self) -> str:
        """Return the name of the tool."""
        return "Human-Feedback Tool"

    @property
    def description(self) -> str:
        """Return the description of the tool."""
        return "A tool that allows interaction with a human. Use it when you want some clarifications or feedback on the task that you are performing, to ensure that you are doing the right thing."

    @property
    def parameters(self) -> dict[str, str]:
        """Return the parameters required by the tool along with their description."""
        return {"query": "The query to ask the human."}

    class Parameters(BaseModel):
        query: str = Field(..., description="The query to ask the human.")

        class Config:
            # Disable validation on assignment
            validate_assignment = False

    def mcp_execute(
        self,
        params: Parameters,
    ) -> str:
        if isinstance(params, dict):
            params = __class__.Parameters(**params)

        return self.execute(params)
