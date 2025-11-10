from palace.paradigms import Paradigm


class ReActParadigm(Paradigm):
    """Simple implementation of the ReAct paradigm."""

    @property
    def name(self):
        """The name of the paradigm."""
        return "ReAct Paradigm"

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
            + """
Now let me explain exactly how you are going to behave in order to reach the goal. You have to work in a cycle of "Thoughts" and "Actions". In "Thoughts" you have to reason on what you aim to do to achieve your goal, what are the exact steps, what you have done so far, and what is left to do. You can freely express yourself and reason about your strategy. In "Actions" you have to explicitly call *tools* (described later), that can help you in achieving your goal. You can call as many tools as you like in the "Actions" section. The results of the tools that you call will be then available to you to continue with your plan. Make sure to use the correct tool definition and to pass compatible parameters to each tool. Let me be clear: your response MUST have the following format:
```
Thoughts:
<insert your thoughts here>

Actions:
<insert your tool calls here>
```

Nothing else can be in your response. Just one and only one "Thoughts:" section, and one and only one "Actions:" section.
"""
        )


#     @property
#     def _paradigm_prompt_without_tools(self) -> str:
#         return (
#             super()._paradigm_prompt_without_tools
#             + """
# Now let me explain how you have to operate in practice, in order to complete the tasks. After the user gives you a task, you have to work in an *iterative* way. What this means is that you don't just provide a single response, you have to keep in mind a long-term plan of how to complete the task, and perform your plan step by step, getting closer and closer to your objective. Don't worry about doing everything in a single step; you just have to get a little bit closer to the solution, because at each step you will continue from where you left last time.
# You have to work in a cycle of "Thoughts" and "Actions". In "Thoughts" you have to reason on what you aim to do to achieve your goal, what are the exact steps, what you have done so far, and what is left to do. You can freely express yourself and reason about your strategy. In "Actions" you have to state your actions about how to achieve your goal, i.e. what tools you want to call. You can call as many tools as you like in the "Actions" section. The results of the tools that you call will be then available to you to continue with your plan. Make sure to use the correct tool definition and to pass compatible parameters to each tool. Let me be clear: your response MUST have the following format:
# ```
# Thoughts:
# <insert your thoughts here>

# Actions:
# <insert your tool calls here>
# ```
# Nothing else can be in your response. Just one and only one "Thoughts:" section, and one and only one "Actions:" section.
# """
#         )
