from palace.paradigms import Paradigm


class ReflectionParadigm(Paradigm):
    """Simple implementation of the Reflection (Reflexion) paradigm."""

    @property
    def name(self):
        """The name of the paradigm."""
        return "Reflection Paradigm"

    @property
    def description(self) -> str:
        """The description of the paradigm."""
        return "The agent works in a self-critique loop, where it reflects on its mistakes at the previous step. Based on https://arxiv.org/pdf/2303.11366."

    @property
    def paradigm_prompt(self) -> str:
        return (
            super().paradigm_prompt
            + """
Now let me explain exactly how you are going to behave in order to reach the goal.
You have to follow an iterative reflection loop.
Your messages must be divided in three sections:
```
Attempt:
<Propose an initial solution. This might be a guess or a partial solution, and it may not be correct initially.>

Critique:
<Analyze your attempt for errors, inefficiencies, or missing information. Be specific.>

Refinement:
<Revise your solution based on the critique. In this section, use can call the provided tools to gather additional data or to provide the final answer.>
```

Nothing else can be in your response. Just exactly one "Attempt:" section, one "Critique:" section, and one "Refinement:" section.

You don't have to reach a final solution in a single message. You will continue later until the solution meets all criteria or no further improvements can be made. Prioritize accuracy over speed; multiple iterations are encouraged.
"""
        )

    # @property
    # def _paradigm_prompt_without_tools(self) -> str:
    #     return super()._paradigm_prompt_without_tools
