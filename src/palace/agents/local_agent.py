import json
import re
from typing import Dict, List

from palace.agents import Agent
from palace.environments import Environment
from palace.models import Model
from palace.paradigms import Paradigm
from palace.tools import Tool
from palace.utils.exceptions import ToolHallucinationException
from palace.utils.printing import print


class LocalAgent(Agent):
    """Standard implementation of the agentic loop."""

    def __init__(
        self,
        model: Model,
        paradigm: Paradigm,
        environment: Environment,
        _temperature: float = 0.0,
        _native_function_calling: bool = False,
    ):
        self.model: Model = model
        self.paradigm: Paradigm = paradigm
        self.environment: Environment = environment
        self._temperature: float = _temperature

        self.tools: List[Tool] = []
        self.conversation: List[Dict[str, str]] = []

        self._native_function_calling = _native_function_calling

    def _call_tool(self, name: str, **parameters: Dict[str, any]) -> str:
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

    def step(self, verbose: bool = False) -> str:
        # if self._native_function_calling:
        #     generated_text, generated_tool_calls = self.model.generate_with_tools(
        #         messages=self.conversation,
        #         tools=self.tools,
        #         temperature=self._temperature,
        #     )
        #     print(
        #         "*** DEBUG *** The model generated these direct tool calls:",
        #         generated_tool_calls,
        #     )
        # else:
        generated_text = self.model.generate(
            messages=self.conversation, temperature=self._temperature
        )
        if verbose:
            print(f"[bold]Generated text: [/] \n{generated_text}\n")

        tool_calls = self._extract_tool_calls(generated_text)
        for tool_call in tool_calls:
            response = self._call_tool(tool_call["name"], **tool_call["parameters"])
            tool_call["response"] = response

        return generated_text, tool_calls

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
    def environment_name(self) -> str:
        return self.environment.name

    def run(self, task: str, max_steps: int = 15, verbose: bool = False) -> str:
        self.tools = self.environment.tools
        self.conversation: List[Dict[str, str]] = []

        system_prompt = (
            self.paradigm.paradigm_prompt
            if not self._native_function_calling
            else self.paradigm._paradigm_prompt_without_tools
        ) + (
            self.environment.environment_prompt
            if not self._native_function_calling
            else self.environment._environment_prompt_without_tools
        )
        self.conversation.append(
            {
                "role": "system",
                "content": system_prompt,
            }
        )
        self.conversation.append({"role": "user", "content": task})
        final_answer = None

        if verbose:
            print(f"[bold]System prompt: [/] \n{system_prompt}\n")
            print(f"[bold]Task: [/] \n{task}\n")

        self.n_toolcalls = 0
        self.n_tool_hallucinations = 0

        for i in range(max_steps):
            if verbose:
                print("-" * 40)
                print(f"[bold]\nSTEP {i + 1}: [/]")

            # run the agent step
            generated_text, tool_calls = self.step(verbose=verbose)

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
            # print([tool_call["response"] for tool_call in tool_calls])

            self.conversation.append({"role": "user", "content": tool_responses})
            if verbose:
                print(f"[bold]Tool calls and responses: [/] \n{tool_responses}\n")

            # break if model has called the final answer tool
            for tool_call in tool_calls:
                if tool_call["name"] == "Final Answer Tool":
                    final_answer = tool_call["response"]
            if final_answer is not None:
                break

        return final_answer, {
            "n_steps": i + 1,
            "n_toolcalls": self.n_toolcalls,
            "n_tool_hallucinations": self.n_tool_hallucinations,
        }

    def _extract_tool_calls(self, text: str) -> List[Dict]:
        tool_calls = []

        # Pattern to match blocks starting with ```tool-call and ending with ```
        pattern = r"```tool-call\n(.*?)```"

        # Use re.DOTALL to make '.' match newlines as well
        try:
            matches = re.findall(pattern, text, re.DOTALL)
        except TypeError:
            print(
                f"[bold yellow]Error while using the regex to extract tool calls from this text:\n{text}[/]"
            )
            return []

        # Process each match to extract valid JSON content
        for match in matches:
            try:
                # Parse the JSON content
                tool_call = json.loads(match)
            except json.JSONDecodeError:
                # Skip invalid JSON
                print(f"[bold yellow]Found a malformed tool call:\n{match}[/]")
                continue

            if (
                "name" in tool_call
                and "parameters" in tool_call
                and isinstance(tool_call["parameters"], dict)
            ):
                tool_calls.append(tool_call)
            else:
                # Skip invalid tool call
                print(f"[bold yellow]Found an invalid tool call:\n{match}[/]")
                continue

        return tool_calls
