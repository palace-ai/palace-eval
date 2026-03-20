from palace.models.api_model import APIModel
from palace.tools import Tool
from palace.utils.constants import OPENAI_LIKE_API_BASE_URL
from palace.utils.secrets import OPENAI_LIKE_API_KEY


class AIAssistantTool(Tool):
    def __init__(self):
        assert OPENAI_LIKE_API_BASE_URL is not None, (
            "OPENAI_LIKE_API_BASE_URL is not set in the environment variables."
        )
        self.model = APIModel("gpt-4o", OPENAI_LIKE_API_BASE_URL, OPENAI_LIKE_API_KEY)

    def execute(self, **kwargs) -> str:
        """Execute the tool functionality."""
        # Check parameter compliance
        for parameter in self.required_parameters:
            if parameter not in kwargs:
                return f"""Tool `{self.name}` encountered the following error: parameter `{parameter}` was not found in the tool call but it is required. Make sure to comply with the required parameters name and type. For this tool, the required parameters are the following:
{self.required_parameters}"""

        conversation = [
            {
                "role": "system",
                "content": """You are an AI assistant.
Your job is to help people who are executing some tasks. They will ask you some question, which may be general or may have additional context. You have to be very precise and concise, quickly providing the answer they need, without fumbling or stuttering.""",
            },
            {"role": "user", "content": kwargs["query"]},
        ]
        response = self.model.generate(conversation)
        return response

    @property
    def name(self) -> str:
        """Return the name of the tool."""
        return "AI Assistant Tool"

    @property
    def description(self) -> str:
        """Return the description of the tool."""
        return "A tool that allows interaction with an AI assistant. Use it when you want an external opinion or you need help during the execution of the task. The answers may not be perfect on the first try, so you may have to insist if you are not satisfied with the answer."

    @property
    def parameters(self) -> dict[str, str]:
        """Return the parameters required by the tool along with their description."""
        return {
            "query": "The query to ask the AI assistant.",
        }
