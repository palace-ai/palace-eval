from palace.paradigms import Paradigm


class PlanAndExecuteParadigm(Paradigm):
    """Simple implementation of the Plan-and-Execute paradigm."""

    @property
    def name(self):
        """The name of the paradigm."""
        return "Plan-and-Execute Paradigm"

    @property
    def description(self) -> str:
        """The description of the paradigm."""
        return "Plan-and-Execute pattern adopts a 'plan first, execute later' strategy, dividing tasks into two distinct phases: a planning phase and an execution phase."

    @property
    def paradigm_prompt(self) -> str:
        return (
            super().paradigm_prompt
            + """
Now let me explain exactly how you are going to behave in order to reach the goal. You are a task planning assistant and a task executor. Given a task, first you have to create a detailed plan to achieve the goal, with this exact format:
```
Plan:
1. <the first step>
2. <the second step>
...
```

Then, you have to execute the plan step by step, calling the tools that you need to achieve your goal, one at a time. You have to use the following format:
```
Thought:
<think about the result of the previous step, if this is not the first one>
<think about the current step>

Action:
<the action to take to carry out the current step>
```

To recap, your first message in the conversation will contain a "Plan" section, a "Thought" section and an "Action" section. From the second message onwards, your messages will contain only a "Thought" and an "Action" section. Nothing else can be in your responses.
"""
        )

    @property
    def _paradigm_prompt_without_tools(self) -> str:
        return super()._paradigm_prompt_without_tools
