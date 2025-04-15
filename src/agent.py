import gc
import json
import re
from typing import Dict, List

import torch
from environments import Environment
from models import Model
from paradigms import Paradigm
from tools import Tool


class Agent:
    """Standard implementation of the agentic loop, based on ReAct."""

    def __init__(
        self,
        model: Model,
        paradigm: Paradigm,
        _temperature: float = 0.0,
        verbose: bool = True,
    ):
        self.model: Model = model
        self.paradigm: Paradigm = paradigm
        self._temperature: float = _temperature
        self.verbose = verbose

        self.tools: Dict[str, Tool] = {}
        self.conversation: List[Dict[str, str]] = []

    def _call_tool(self, name: str, **parameters: Dict[str, any]) -> str:
        if name not in self.tools:
            return f"""The tool `{name}` that you have tried to call does not exist.
Make sure to only use explicitly provided tools."""

        tool = self.tools[name]
        try:
            response = tool.execute(**parameters)
        except Exception as e:
            print(f"\033[31mException while calling tool `{name}`:\n{e}")
            # TODO handling tool exceptions should probably be done by the tool class or some other class
            return f"""An exception was raised while calling tool `{name}`.
I'm not sure what was the cause, but you can try moving forward with the task anyway.
Maybe something was wrong with your syntax or maybe that tool is unavailable for now."""

        return response

    # TODO add modules, such as the memory module
    def step(self) -> str:
        generated_text = self.model.generate(self.conversation, self._temperature)
        if self.verbose:
            print(f"\033[1mGenerated text:\033[0m\n{generated_text}\n")

        tool_calls = self._extract_tool_calls(generated_text)
        for tool_call in tool_calls:
            response = self._call_tool(tool_call["name"], **tool_call["parameters"])
            tool_call["response"] = response

        return generated_text, tool_calls

    def run(
        self,
        environment: Environment,
        task: str,
        max_steps: int = 10,
    ) -> str:
        self.tools: Dict[str, Tool] = {tool.name: tool for tool in environment.tools}
        self.conversation: List[Dict[str, str]] = []

        system_prompt = self.paradigm.paradigm_prompt + environment.environment_prompt
        self.conversation.append(
            {
                "role": "system",
                "content": system_prompt,
            }
        )
        self.conversation.append({"role": "user", "content": task})
        final_answer = None

        if self.verbose:
            print(f"\033[1mSystem prompt:\033[0m\n{system_prompt}\n")
            print(f"\033[1mTask:\033[0m\n{task}\n")

        for i in range(max_steps):
            if self.verbose:
                print("-" * 40)
                print(f"\033[1m\nSTEP {i + 1}:\033[0m")

            # run the agent step
            generated_text, tool_calls = self.step()

            # append the last generated text
            self.conversation.append({"role": "assistant", "content": generated_text})

            # append the last tool responses
            tool_responses = "\n".join(
                [
                    f"Your call to {tool_call['name']} returned the following response: {tool_call['response']}"
                    for tool_call in tool_calls
                ]
                + [
                    f"(If you expected additional tool responses, double check that your tool call syntax is correct.{' Also I remind you that when you are ready to give your definitive answer, you have to call the Final Answer Tool.' if len(tool_calls) == 0 else ''})"
                ]
            )
            self.conversation.append({"role": "user", "content": tool_responses})
            if self.verbose:
                print(f"\033[1mTool calls and responses:\033[0m\n{tool_responses}\n")

            # break if model has called the final answer tool
            for tool_call in tool_calls:
                if tool_call["name"] == "Final Answer Tool":
                    final_answer = tool_call["response"]
            if final_answer is not None:
                break

        return final_answer

    def _extract_tool_calls(self, text: str) -> List[Dict]:
        # Pattern to match blocks starting with ```tool-call and ending with ```
        pattern = r"```tool-call\n(.*?)```"

        # Use re.DOTALL to make '.' match newlines as well
        matches = re.findall(pattern, text, re.DOTALL)

        # Process each match to extract valid JSON content
        tool_calls = []
        for match in matches:
            try:
                # Parse the JSON content
                tool_call = json.loads(match)
            except json.JSONDecodeError:
                # Skip invalid JSON
                print(f"\033[1;33mFound a malformed tool call:\n{match}\033[0m")
                continue

            if (
                "name" in tool_call
                and "parameters" in tool_call
                and isinstance(tool_call["parameters"], dict)
            ):
                tool_calls.append(tool_call)
            else:
                # Skip invalid tool call
                print(f"\033[1;33mFound an invalid tool call:\n{match}\033[0m")
                continue

        return tool_calls

    # TODO not working
    def destroy(self):
        del self.model.model
        del self.model
        torch.cuda.empty_cache()
        gc.collect()

    """
    Paradigma dà al modello:
    - System prompt: include varie cose, fornite da provider diversi:
        - [Paradigm]: deve spiegare al modello come funziona l'agentic loop
        - [Tool-calling strategy]: deve o (i) dire quali tool sono disponibili, o (ii) spiegare come fare per pullare tool a runtime
        - [Environment]: deve spiegare il contesto in cui viene usato l'agente e come si deve comportare (research assistant, policy assistant, etc). possibilmente dovrebbe anche spiegare come il modello deve comportarsi quando viene chiamato da altri agenti
    - User prompt: task effettivo, anch'esso fornito da [Scenario]
    """
