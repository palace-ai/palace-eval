from palace.paradigms import Paradigm


class NonAgenticParadigm(Paradigm):
    """Paradigm (or lack thereof) for non-agentic behavior. The model will act as a normal LLM and will not use tools."""

    @property
    def name(self):
        """The name of the paradigm."""
        return "Non-Agentic Paradigm"

    @property
    def description(self) -> str:
        """The description of the paradigm."""
        return (
            "The model will act as a normal LLM (not an agent) and will not use tools."
        )

    @property
    def paradigm_prompt(self) -> str:
        return """You are a helpful AI assistant. Your job is to carry out tasks that the user will ask you to do. The tasks might be hard, but nevertheless try to provide a clear and concise answer to the best of your ability. Don't try to instruct the user on how to solve the task, it's just a test for you, to check whether you know the correct answer."""
