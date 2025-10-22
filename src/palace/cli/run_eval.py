import itertools
import sys

import questionary

from palace.agents import LocalAgent, RemoteAgent
from palace.environments import (
    AssistantEnvironment,
    IsolatedEnvironment,
    IsolatedEnvironmentWithInterpreter,
    IsolatedEnvironmentWithLetterCount,
    MCPEnvironment,
)
from palace.evaluation import Evaluation
from palace.mcp_utils.mcp_client import MCPClient
from palace.models import HuggingfaceModel, OpenAICompatibleModel
from palace.paradigms import (
    ActParadigm,
    PlanAndExecuteParadigm,
    ReActParadigm,
    ReflectionParadigm,
)
from palace.utils.printing import print
from palace.utils.secrets import ALOHA_TOKEN

_DEFAULT_REMOTE_AGENTS_URL = (
    "https://aloha-main-jrc-gpt.apps.ocpg.jrc.ec.europa.eu/api/mcp/react-agent/sse"
)


def main():
    print("""
[bright_yellow]
                                        ╔══════════ ≪  ◆  ≫ ══════════╗[bright_magenta]
━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━     ┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃     ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━[bright_yellow]
━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━     ┃┃┃┏━━━┓┃┃┃┃┓┃┃┃┃┃┃┃┃┃┃┃┃┃┃     ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━[bright_magenta]
━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━     ┃┃┃┃┏━┓┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃     ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━[bright_yellow]
━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━     ┃┃┃┃┗━┛┃━━┓┃┃┃━━┓┃━━┓━━┓┃┃┃     ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━[bright_magenta]
━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━     ┃┃┃┃┏━━┛┃┓┃┃┃┃┃┓┃┃┏━┛┏┓┃┃┃┃     ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━[bright_yellow]
━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━     ┃┃┃┃┃┃┃┃┗┛┗┓┗┓┗┛┗┓┗━┓┃━┫┃┃┃     ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━[bright_magenta]
━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━     ┃┃┃┗┛┃┃┃━━━┛━┛━━━┛━━┛━━┛┃┃┃     ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━[bright_yellow]
━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━     ┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃     ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━[bright_magenta]
━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━     ┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃     ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━[bright_yellow]
                                        ╚══════════ ≪  ◆  ≫ ══════════╝
          
""")
    print(
        """This is a simple evaluation script for the [bold]Palace[/] agents evaluation framework.
It will evaluate the performance of different models and paradigms on various environments.
Please make sure you have the required dependencies installed.
You can find the documentation at [blue]https://gitlab.jrc.ec.europa.eu/jrc-projects/jrc-gpt/agents/agents-eval[/].
If you have any questions, please contact us at [blue]massimiliano.altieri@ec.europa.eu[/].""",
        box=True,
        box_title="Welcome to the Palace CLI!",
        wrap_width=108,
    )
    print()

    _PARADIGMS = [
        ActParadigm(),
        ReActParadigm(),
        PlanAndExecuteParadigm(),
        ReflectionParadigm(),
    ]
    _MODELS = [
        "meta-llama/Llama-3.3-70B-Instruct",
        "mistralai/Mistral-Small-3.1-24B-Instruct-2503",
        "Qwen/Qwen3-32B",
        "gpt-4o",
        "Qwen/Qwen2.5-Coder-32B-Instruct",
    ]
    _ENVIRONMENTS = [
        AssistantEnvironment(),
        IsolatedEnvironment(),
        IsolatedEnvironmentWithInterpreter(),
        IsolatedEnvironmentWithLetterCount(),
        MCPEnvironment(mcp_server="local"),
        MCPEnvironment(mcp_server="aloha"),
    ]
    _TASKLISTS = [
        "AssistantBench",
        "CURIE-protein",
        "Fever",
        "GAIA",
        "HLE",
        "HotpotQA",
        "Scopus",
        "SimpleQA",
    ]

    local_or_remote = questionary.checkbox(
        "What agent types would you like to test?",
        choices=[
            questionary.Choice("Remote", checked=True),
            questionary.Choice("Local", checked=True),
        ],
    ).ask()
    if len(local_or_remote) == 0:
        print("You have selected nothing to test. Have a nice day :)")
        return

    if "Remote" in local_or_remote:
        remote_agents_url = questionary.text(
            "Remote Agents URL:", default=_DEFAULT_REMOTE_AGENTS_URL
        ).ask()
        with MCPClient().connection(remote_agents_url, ALOHA_TOKEN) as mcp_client:
            available_remote_agents = [
                tool.name for tool in mcp_client.list_tools().tools
            ]
        if len(available_remote_agents) == 0:
            raise ValueError("No agents found in the provided MCP server URL.")
        remote_agents = questionary.checkbox(
            "Select Remote Agents:", choices=available_remote_agents
        ).ask()
    else:
        remote_agents = []

    if "Local" in local_or_remote:
        default_paradigms = [ReActParadigm().name]
        paradigm = questionary.checkbox(
            "Select Reasoning Paradigms to test for local agents:",
            choices=[
                questionary.Choice(p.name, checked=p.name in default_paradigms)
                for p in _PARADIGMS
            ],
        ).ask()
        paradigms = [p for p in _PARADIGMS if p.name in paradigm]
        if len(paradigms) == 0:
            raise ValueError("No paradigms selected")

        models = questionary.checkbox(
            "Select Models to test for local agents:",
            choices=_MODELS,
        ).ask()
        if len(models) == 0:
            raise ValueError("No models selected")

        local_mode = questionary.select(
            "Where do you want to run the LLMs for local agents?",
            choices=["Locally (make sure you have enough GPU memory)", "GPT@JRC"],
            default="GPT@JRC",
        ).ask()
        local_mode = local_mode != "GPT@JRC"

        environments = questionary.checkbox(
            "Select Environments to test for local agents:",
            choices=[e.name for e in _ENVIRONMENTS],
        ).ask()
        environments = [e for e in _ENVIRONMENTS if e.name in environments]
        if len(environments) == 0:
            raise ValueError("No environments selected")
    else:
        models = []
        paradigms = []
        environments = []

    tasklists = questionary.checkbox(
        "Select Tasklists to use as benchmarks:",
        choices=_TASKLISTS,
    ).ask()
    if len(tasklists) == 0:
        raise ValueError("No tasklists selected")

    verbose = questionary.select(
        "Verbose Mode?",
        choices=["True", "False"],
        default="False",
    ).ask()
    verbose = True if verbose == "True" else False

    task_amount_limit = questionary.select(
        "Limit the number of tasks:",
        choices=["1", "5", "20", "50", "100", "Unlimited"],
        default="1",
    ).ask()
    task_amount_limit = (
        int(task_amount_limit) if task_amount_limit != "Unlimited" else sys.maxsize
    )

    runs_per_configuration = questionary.select(
        "Runs Per Configuration:",
        choices=["1", "3", "5", "10"],
        default="1",
    ).ask()
    runs_per_configuration = int(runs_per_configuration)

    name = questionary.text(
        "Name of the evaluation run:",
        default="eval",
    ).ask()

    evaluation = Evaluation(
        name=name,
        verbose=verbose,
        task_amount_limit=task_amount_limit,
        runs_per_configuration=runs_per_configuration,
    )

    evaluation.evaluate_all(
        # TODO BUG Currently it assumes all remote agents are located at the same URL (not possible to define multiple URLs)
        agents=[
            LocalAgent(
                model=HuggingfaceModel(model)
                if local_mode
                else OpenAICompatibleModel(model),
                paradigm=paradigm,
                environment=environment,
            )
            for model, paradigm, environment in itertools.product(
                models, paradigms, environments
            )
        ]
        + [
            RemoteAgent(
                url=remote_agents_url,
                token=ALOHA_TOKEN,
                name=agent,
            )
            for agent in remote_agents
        ],
        tasklists=tasklists,
    )


if __name__ == "__main__":
    main()
