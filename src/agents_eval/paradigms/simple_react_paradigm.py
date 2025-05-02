from agents_eval.paradigms import Paradigm


class SimpleReActParadigm(Paradigm):
    """Simple implementation of the ReAct paradigm."""

    @property
    def name(self):
        """The name of the paradigm."""
        return "Simple ReAct Paradigm"

    @property
    def description(self) -> str:
        """The description of the paradigm."""
        return (
            "The agent works in three steps: (1) thought, (2) action, (3) observation."
        )

    @property
    def paradigm_prompt(self) -> str:
        return (
            super().paradigm_prompt
            + """Now let me explain exactly how you are going to behave in order to reach the goal. You have to work in a cycle of "Thoughts" and "Actions". In "Thoughts" you have to reason on what you aim to do to achieve your goal, what are the exact steps, what you have done so far, and what is left to do. You can freely express yourself and reason about your strategy. In "Actions" you have to explicitly call *tools* (described later), that can help you in achieving your goal. You can call as many tools as you like in the "Actions" section. The results of the tools that you call will be then available to you to continue with your plan. Make sure to use the correct tool definition and to pass compatible parameters to each tool. Let me be clear: your response MUST have the following format:
```
Thoughts:
<insert your thoughts here>

Actions:
<insert your tool calls here>
```
Nothing else can be in your response. Just one and only one "Thoughts:" section, and one and only one "Actions:" section.
"""
        )
