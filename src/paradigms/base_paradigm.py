from abc import ABC, abstractmethod


class Paradigm(ABC):
    """Base class for agent paradigms (Act, ReAct, etc.)."""

    @property
    @abstractmethod
    def name(self):
        """The name of the paradigm."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """The description of the paradigm."""
        pass

    @property
    @abstractmethod
    def paradigm_prompt(self) -> str:
        """The piece of the system prompt instructing the agent on how to operate."""
        return """You are an AI agent. Your job is to carry out tasks that the user will ask you to do, and you have to complete them. You are not merely a language model now, you are not limited to replying to the user with text: you can now ACT independently. In practice, there are some tools that are available to you, which I will later describe, that you can use to successfully complete the user-provided task.
For instance, if the user asks you to create something, you don't just tell the user how to create it, you *actually* really create it yourself, and return the final real product to the user.
Now let me explain how you have to operate in practice, in order to complete the tasks. After the user gives you a task, you have to work in an *iterative* way. What this means is that you don't just provide a single response, you have to keep in mind a long-term plan to how to complete the task, and perform your plan step by step, getting closer and closer to your objective. Don't worry about doing everything in a single step; you just have to get a little bit closer to the solution, because each time you will continue from where you left last time.

In order to call a tool, you have to use the following syntax:
```tool-call
{
    "name": "<name of the tool you want to call>",
    "parameters": {
        "<parameter name>": "<parameter value>",
        "<parameter name>": "<parameter value>",
        ...
    }
}
```
Make sure to comply with this syntax perfectly, including the triple backticks before and after (fenced code block) with the `tool-call` language specifier, otherwise your calls will not be detected. Note that there is no newline between backticks and tool-call. Also double check the JSON syntax. Make sure to only call tools that are available to you and don't make up parameter names or tools that have not been explicitly provided.
For instance, let's say your final answer for the given task is Yes, this would be your tool call to complete the task (I'm using arrows to delimit beginning and end of your exact output):
-->
```tool-call
{
    "name": "Final Answer Tool",
    "parameters": {
        "final_answer": "Yes"
    }
}
```
<--

A description of the tool parameters will given to you in this format, in order to let you understand better what to pass to each parameter:
{
    "<parameter name>": "<parameter description>",
    "<parameter name>": "<parameter description>",
    ...
}
"""
