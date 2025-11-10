from palace.paradigms import Paradigm


class ActParadigm(Paradigm):
    """Simple implementation of the Act paradigm."""

    @property
    def name(self):
        """The name of the paradigm."""
        return "Act Paradigm"

    @property
    def description(self) -> str:
        """The description of the paradigm."""
        return "The agent works in an iterative way, stating its action at each step."

    @property
    def paradigm_prompt(self) -> str:
        return (
            super().paradigm_prompt
            + """
Now let me explain exactly how you are going to behave in order to reach the goal. You have to produce an "Action" section, where you explicitly call one (or more) *tools* (described later), that can help you in achieving your goal. The results of the tools that you call will be then available to you to continue with your plan, so don't worry of doing everything in one step, you just need to get a little closer to the solution, so you may call one tool at a time. Make sure to use the correct tool definition and to pass compatible and meaningful parameters to each tool. Let me be clear: your response MUST have the following format:
```
Action:
<insert your tool call(s) here>
```
Nothing else can be in your response. Just one and only one "Actions:" section.
"""
        )

    # @property
    # def _paradigm_prompt_without_tools(self) -> str:
    #     return super()._paradigm_prompt_without_tools
