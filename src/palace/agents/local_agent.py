import json
import re
from typing import Any, Optional, cast

from palace.agents import Agent
from palace.environments import Environment
from palace.models import Model
from palace.paradigms import Paradigm
from palace.paradigms.non_agentic_paradigm import NonAgenticParadigm
from palace.tools import Tool
from palace.utils.config import VERBOSE_MODE
from palace.utils.exceptions import ConvergenceError, ToolHallucinationException
from palace.utils.printing import print


class LocalAgent(Agent):
    """Standard implementation of the agentic loop."""

    MAX_STEPS_DEFAULT_VALUE = 15

    def __init__(
        self,
        model: Model,
        paradigm: Paradigm,
        environment: Environment,
        max_steps: Optional[int] = None,
    ):
        self.model: Model = model
        self.paradigm: Paradigm = paradigm
        self._environment: Environment = environment
        self.max_steps: int = max_steps or self.MAX_STEPS_DEFAULT_VALUE

        self.tools: list[Tool] = []
        self.conversation: list[dict[str, str]] = []

    @property
    def name(self) -> str:
        return f"( {self.model_name} x {self.paradigm_name} )"

    @property
    def model_name(self) -> str:
        return self.model.name

    @property
    def paradigm_name(self) -> str:
        return self.paradigm.name

    @property
    def environment(self) -> Environment:
        return self._environment

    def run(self, task: str) -> tuple[str, dict[str, Any] | None]:
        self.tools = self.environment.tools
        self.conversation = []

        system_prompt: str = (
            self.paradigm.paradigm_prompt + self.environment.environment_prompt
        )

        self.conversation.append(
            {
                "role": "system",
                "content": system_prompt,
            }
        )
        self.conversation.append({"role": "user", "content": task})
        final_answer = None

        if VERBOSE_MODE:
            print(f"[bold]System prompt: [/] \n{system_prompt}\n")
            print(f"[bold]Task: [/] \n{task}\n")

        self.n_toolcalls: int = 0
        self.n_tool_hallucinations: int = 0

        steps = 0
        for i in range(self.max_steps):
            steps += 1
            if VERBOSE_MODE:
                print("-" * 40)
                print(f"[bold]\nSTEP {i + 1}: [/]")

            # run the agent step
            generated_text, tool_calls = self.step()

            # increment tool calls counter
            self.n_toolcalls += len(tool_calls)

            # append the last generated text
            self.conversation.append({"role": "assistant", "content": generated_text})

            # append the last tool responses
            tool_responses = "\n".join(
                [
                    f"Your call to {tool_call['name']} returned the following response:\n{tool_call['response']}"
                    for tool_call in tool_calls
                ]
                + [
                    f"(If you expected additional tool responses, double check that your tool call syntax is correct.{' Also I remind you that when you are ready to give your definitive answer, you have to call the Final Answer Tool.' if len(tool_calls) == 0 else ''})"
                ]
            )

            self.conversation.append({"role": "user", "content": tool_responses})
            if VERBOSE_MODE:
                print(f"[bold]Tool calls and responses: [/] \n{tool_responses}\n")

            # break if model has provided a final answer
            if type(self.paradigm) is NonAgenticParadigm:
                final_answer = generated_text
                break
            else:
                for tool_call in tool_calls:
                    if tool_call["name"] == "Final Answer Tool":
                        final_answer = tool_call["response"]
                        break

        if final_answer is None:
            raise ConvergenceError()

        metrics: dict[str, Any] = {
            "n_steps": steps,
            "n_toolcalls": self.n_toolcalls,
            "n_tool_hallucinations": self.n_tool_hallucinations,
        }
        return final_answer, metrics

    def step(self) -> tuple[str, list[dict[str, Any]]]:
        generated_text = self.model.generate(messages=self.conversation)
        if VERBOSE_MODE:
            print(f"[bold]Generated text: [/] \n{generated_text}\n")

        tool_calls = self._extract_tool_calls(generated_text)
        for tool_call in tool_calls:
            response = self._call_tool(
                tool_call["name"], cast(dict[str, str], tool_call["parameters"])
            )
            tool_call["response"] = response

        return generated_text, tool_calls

    def _extract_tool_calls(self, text: str) -> list[dict[str, Any]]:
        tool_calls = []

        try:
            matches = re.findall(r"```tool_call\n(.*?)```", text, re.DOTALL)
        except TypeError:
            print(
                f"[bold yellow]Error while using the regex to extract tool calls from this text:\n{text}[/]"
            )
            return []

        for match in matches:
            try:
                tool_call = json.loads(match)
            except json.JSONDecodeError:
                print(f"[bold yellow]Found a malformed tool call:\n{match}[/]")
                continue

            if (
                "name" in tool_call
                and "parameters" in tool_call
                and isinstance(tool_call["parameters"], dict)
            ):
                tool_calls.append(tool_call)
            else:
                print(f"[bold yellow]Found an invalid tool call:\n{match}[/]")
                continue

        return tool_calls

    def _call_tool(self, name: str, parameters: dict[str, str]) -> str:
        try:
            matching_tools = [tool for tool in self.tools if tool.name == name]

            if len(matching_tools) == 0:
                raise ToolHallucinationException(
                    f"The tool `{name}` that you have tried to call does not exist. Make sure to only use explicitly provided tools."
                )
            elif len(matching_tools) > 1:
                print(f"""[bold bright_white on_red] The tool `{name}` that you have tried to call is ambiguous because there are multiple tools with the same name.
    This should never happen. [/]""")
                import sys

                sys.exit(1)
            else:
                tool = matching_tools[0]
                return tool.execute(**parameters)
        except ToolHallucinationException as e:
            self.n_tool_hallucinations += 1
            return str(e)
        except Exception as e:
            print(f"[red]Exception while calling tool `{name}`:\n{e} [/]")
            return f"""An exception was raised while calling tool `{name}`.
I'm not sure what was the cause, but you can try moving forward with the task anyway.
Maybe something was wrong with your syntax or maybe that tool is unavailable for now."""
