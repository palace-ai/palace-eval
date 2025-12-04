import itertools
import sys

import questionary

from palace.agents import LocalAgent, MCPAgent, OpenAIAPIAgent
from palace.environments import (
    AssistantEnvironment,
    IsolatedEnvironment,
    IsolatedEnvironmentWithInterpreter,
    IsolatedEnvironmentWithLetterCount,
    MCPEnvironment,
)
from palace.environments.empty_environment import EmptyEnvironment
from palace.evaluation import Evaluation
from palace.mcp_utils.mcp_client import MCPClientPool
from palace.models import HuggingfaceModel, OpenAICompatibleModel
from palace.paradigms import (
    ActParadigm,
    NonAgenticParadigm,
    PlanAndExecuteParadigm,
    ReActParadigm,
    ReflectionParadigm,
)
from palace.utils.constants import (
    ALOHA_STAGING_URL,
    GPTJRC_PROD_API_URL,
    TS_STAGING_URL,
)
from palace.utils.paths import PROJECT_ROOT
from palace.utils.printing import print
from palace.utils.secrets import (
    ALOHA_STAGING_TOKEN,
    GPTJRC_PROD_TOKEN,
    TS_STAGING_TOKEN,
)

_DEFAULT_MCP_SERVERS = [
    {
        "url": "http://localhost:8090/mcp/sse",
    },
    {
        "url": "http://localhost:8000/sse",
    },
    {
        "name": "ALOHA Staging",
        "url": ALOHA_STAGING_URL,
        "token": ALOHA_STAGING_TOKEN,
    },
    {
        "name": "ThematicSpaces Staging",
        "url": TS_STAGING_URL,
        "token": TS_STAGING_TOKEN,
        "params": {
            "main": "query",
            "custom": {
                "thematic_space": "cb305107-63f4-479d-962c-27496e35aa99",
            },
        },
    },
]
_DEFAULT_OPENAI_AGENTS_URL = "https://api-gpt.jrc.ec.europa.eu/v1"
_DEFAULT_OPENAI_AGENTS_TOKEN = GPTJRC_PROD_TOKEN


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
        NonAgenticParadigm(),
        ActParadigm(),
        ReActParadigm(),
        PlanAndExecuteParadigm(),
        ReflectionParadigm(),
    ]
    _MODELS = [
        "meta-llama/Llama-3.3-70B-Instruct",
        "minimax-m2",
        "mistralai/Mistral-Small-3.1-24B-Instruct-2503",
        "Qwen/Qwen3-32B",
        "gpt-4o",
        "Qwen/Qwen2.5-Coder-32B-Instruct",
    ]
    _ENVIRONMENTS = [
        EmptyEnvironment(),
        AssistantEnvironment(),
        IsolatedEnvironment(),
        IsolatedEnvironmentWithInterpreter(),
        IsolatedEnvironmentWithLetterCount(),
        MCPEnvironment(mcp_server="local"),
        MCPEnvironment(mcp_server="aloha"),
    ]

    available_tasklists = sorted(
        [t.name for t in (PROJECT_ROOT / "tasklists" / "metadata").iterdir()]
    )

    local_or_remote = questionary.checkbox(
        "What agent types would you like to test?",
        choices=[
            questionary.Choice("Remote (via MCP)"),
            questionary.Choice("Remote (via OpenAI-compatible API)"),
            questionary.Choice("Local"),
        ],
    ).ask()
    if len(local_or_remote) == 0:
        print("You have selected nothing to test. Have a nice day :)")
        return

    agents = []

    if "Local" in local_or_remote:
        # set paradigms
        paradigm = questionary.checkbox(
            "Select Reasoning Paradigms to test for local agents:",
            choices=[questionary.Choice(p.name) for p in _PARADIGMS],
        ).ask()
        paradigms = [p for p in _PARADIGMS if p.name in paradigm]
        if len(paradigms) == 0:
            raise ValueError("No paradigms selected")

        # set models
        models = questionary.checkbox(
            "Select Models to test for local agents:",
            choices=_MODELS,
        ).ask()
        if len(models) == 0:
            raise ValueError("No models selected")

        # set local or remote llm
        local_llm = questionary.select(
            "Where do you want to run the LLMs for local agents?",
            choices=["Locally (make sure you have enough GPU memory)", "GPT@JRC"],
            default="GPT@JRC",
        ).ask()
        local_llm: bool = local_llm != "GPT@JRC"

        # set environments
        environments = questionary.checkbox(
            "Select Environments to test for local agents:",
            choices=[e.name for e in _ENVIRONMENTS],
        ).ask()
        environments = [e for e in _ENVIRONMENTS if e.name in environments]
        if len(environments) == 0:
            raise ValueError("No environments selected")

        # add local agents
        agents += [
            LocalAgent(
                model=HuggingfaceModel(model)
                if local_llm
                else OpenAICompatibleModel(
                    model, GPTJRC_PROD_API_URL, GPTJRC_PROD_TOKEN
                ),
                paradigm=paradigm,
                environment=environment,
            )
            for model, paradigm, environment in itertools.product(
                models, paradigms, environments
            )
        ]

    if "Remote (via MCP)" in local_or_remote:
        # set url
        url = questionary.select(
            "MCP Agents URL:",
            choices=[
                questionary.Choice(
                    title=f"{server['url']}{f' ({server.get("name")})' if 'name' in server else ''}",
                    value=server["url"],
                )
                for server in _DEFAULT_MCP_SERVERS
            ]
            + ["Custom URL"],
        ).ask()
        if url == "Custom URL":  # custom mcp server can't require a token
            url = questionary.text("MCP Agents URL:").ask()
        mcp_server = next(
            server for server in _DEFAULT_MCP_SERVERS if server["url"] == url
        )
        token = mcp_server.get("token")

        # retrieve remote agents from url
        with MCPClientPool.get_connection(url, token) as mcp_client:
            available_mcp_agents = [tool.name for tool in mcp_client.list_tools().tools]
        if len(available_mcp_agents) == 0:
            raise ValueError("No agents found in the provided MCP server URL.")
        mcp_agents = questionary.checkbox(
            "Select MCP Agents:", choices=available_mcp_agents
        ).ask()

        # add MCP agents
        agents += [
            MCPAgent(
                url=url,
                token=token,
                name=agent,
                params=mcp_server.get("params"),
                output_processor=mcp_server.get("output_processor"),
            )
            for agent in mcp_agents
        ]

    if "Remote (via OpenAI-compatible API)" in local_or_remote:
        openai_agents_url = questionary.text(
            "OpenAI-compatible Agents URL:", default=_DEFAULT_OPENAI_AGENTS_URL
        ).ask()
        token = (
            questionary.text("OpenAI-compatible Agents Token:").ask()
            if openai_agents_url != _DEFAULT_OPENAI_AGENTS_URL
            else _DEFAULT_OPENAI_AGENTS_TOKEN
        )
        available_openai_agents = OpenAICompatibleModel.list_models(
            url=openai_agents_url, token=token
        )
        if len(available_openai_agents) == 0:
            raise ValueError(
                "No agents found in the provided OpenAI-compatible server URL."
            )

        openai_agents = questionary.checkbox(
            "Select OpenAI-compatible Agents:", choices=available_openai_agents
        ).ask()

        # add OpenAI-compatible agents
        agents += [
            OpenAIAPIAgent(
                url=openai_agents_url,
                token=token,
                name=agent,
            )
            for agent in openai_agents
        ]

    # set tasklists
    tasklists = questionary.checkbox(
        "Select Tasklists to use as benchmarks:",
        choices=available_tasklists,
    ).ask()
    if len(tasklists) == 0:
        raise ValueError("No tasklists selected")

    # set task amount limit
    task_amount_limit = questionary.select(
        "Limit the number of tasks:",
        choices=["1", "5", "20", "50", "100", "Unlimited"],
        default="1",
    ).ask()
    task_amount_limit = (
        int(task_amount_limit) if task_amount_limit != "Unlimited" else sys.maxsize
    )

    # set runs per configuration
    runs_per_configuration = questionary.select(
        "Runs Per Configuration:",
        choices=["1", "3", "5", "10"],
        default="1",
    ).ask()
    runs_per_configuration = int(runs_per_configuration)

    # set run name
    name = questionary.text(
        "Name of the evaluation run:",
        default="eval",
    ).ask()

    evaluation = Evaluation(
        name=name,
        task_amount_limit=task_amount_limit,
        runs_per_configuration=runs_per_configuration,
    )

    evaluation.evaluate_all(
        # [agent for agent in local_agents + mcp_agents + openai_agents],
        agents,
        tasklists=tasklists,
    )


if __name__ == "__main__":
    main()
