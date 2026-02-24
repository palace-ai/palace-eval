import itertools
import json
import sys

import emoji
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
from palace.models import APIModel
from palace.paradigms import (
    ActParadigm,
    NonAgenticParadigm,
    PlanAndExecuteParadigm,
    ReActParadigm,
    ReflectionParadigm,
)
from palace.utils.constants import (
    ABW_SERVE_STAGING_URL,
    ALOHA_STAGING_URL,
    GPTJRC_PROD_API_URL,
    TS_STAGING_URL,
)
from palace.utils.paths import TASKLISTS_PATH
from palace.utils.printing import loading, print
from palace.utils.secrets import (
    ALOHA_STAGING_TOKEN,
    GPTJRC_PROD_TOKEN,
    TS_STAGING_TOKEN,
)

_DEFAULT_MCP_SERVERS = [
    {
        "name": "Default local Palace",
        "url": "http://localhost:8080/sse",
    },
    {
        "name": "Default local agentpoc",
        "url": "http://localhost:8000/sse",
    },
    {
        "name": "Default local abw-serve",
        "url": "http://localhost:8090/mcp/sse",
    },
    {
        "name": "ABW-serve Staging",
        "url": ABW_SERVE_STAGING_URL,
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
        """This is the main user interface for the [bold]Palace[/] agents evaluation framework.
Please make sure you have the required dependencies installed.
You can find the documentation at [blue]https://gitlab.jrc.ec.europa.eu/jrc-projects/jrc-gpt/evaluation/palace-lib[/].
If you have any questions, please contact us at [blue]massimiliano.altieri@ec.europa.eu[/].""",
        box=True,
        box_title=":waving_hand: Welcome to the Palace CLI!",
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
        [
            {"name": t.name, "category": json.load(open(t / "info.json"))["category"]}
            for t in (TASKLISTS_PATH).iterdir()
            if t.is_dir()
        ],
        key=lambda x: (x["category"], x["name"]),
    )

    local_or_remote = questionary.checkbox(
        "What agent types would you like to test?",
        choices=[
            questionary.Choice("Remote (via MCP)"),
            questionary.Choice("Remote (via OpenAI-compatible API)"),
            questionary.Choice("Local"),
        ],
        validate=lambda choices: (
            True if len(choices) > 0 else "You must select at least one!"
        ),
    ).ask()
    if len(local_or_remote) == 0:
        print("You have selected nothing to test. Have a nice day :)")
        return

    agents = []

    custom_style = questionary.Style(
        [
            ("blue", "fg:blue"),
            ("bold", "bold"),
        ]
    )

    if "Local" in local_or_remote:
        # set paradigms
        paradigm = questionary.checkbox(
            "Select Reasoning Paradigms to test for local agents:",
            choices=[questionary.Choice(p.name) for p in _PARADIGMS],
            validate=lambda choices: (
                True if len(choices) > 0 else "You must select at least one!"
            ),
        ).ask()
        paradigms = [p for p in _PARADIGMS if p.name in paradigm]
        if len(paradigms) == 0:
            raise ValueError("No paradigms selected")

        # set models
        models = questionary.checkbox(
            "Select Models to test for local agents:",
            choices=_MODELS,
            validate=lambda choices: (
                True if len(choices) > 0 else "You must select at least one!"
            ),
        ).ask()
        if len(models) == 0:
            raise ValueError("No models selected")

        # set local or remote llm
        local_llm = questionary.select(
            "Where do you want to run the LLMs for local agents?",
            choices=[
                questionary.Choice(
                    "Locally (make sure you have enough GPU memory)",
                    disabled="NO LONGER SUPPORTED",
                ),
                questionary.Choice("GPT@JRC", checked=True),
            ],
            default="GPT@JRC",
        ).ask()
        local_llm: bool = local_llm != "GPT@JRC"

        # set environments
        environments = questionary.checkbox(
            "Select Environments to test for local agents:",
            choices=[e.name for e in _ENVIRONMENTS],
            validate=lambda choices: (
                True if len(choices) > 0 else "You must select at least one!"
            ),
        ).ask()
        environments = [e for e in _ENVIRONMENTS if e.name in environments]
        if len(environments) == 0:
            raise ValueError("No environments selected")

        # add local agents
        if GPTJRC_PROD_API_URL is None and not local_llm:
            raise ValueError(
                "GPTJRC_PROD_API_URL is not set in the environment variables."
            )
        agents += [
            LocalAgent(
                # model=HuggingfaceModel(model)
                # if local_llm
                # else
                APIModel(
                    model,
                    GPTJRC_PROD_API_URL,  # type: ignore
                    GPTJRC_PROD_TOKEN,
                    api_type="openai" if "claude-" not in model else "anthropic",
                ),
                paradigm=paradigm,
                environment=environment,
            )
            for model, paradigm, environment in itertools.product(
                models, paradigms, environments
            )
        ]

    if "Remote (via MCP)" in local_or_remote:
        # check actually available mcp servers
        with loading() as ld:
            for server in _DEFAULT_MCP_SERVERS:
                ld.status(
                    f"Checking availability of MCP servers... [dim]({server['url']})"
                )
                try:
                    with MCPClientPool.get_connection(
                        server["url"], server.get("token")
                    ) as mcp_client:
                        mcp_client.list_tools()
                except Exception:
                    server["available"] = False
                else:
                    server["available"] = True

        # set url
        url = questionary.select(
            "MCP Agents URL:",
            choices=[
                questionary.Choice(
                    title=[
                        (
                            "",
                            f"{emoji.emojize(':green_circle:')} "
                            if server.get("available")
                            else f"{emoji.emojize(':red_circle:')} ",
                        ),
                        (
                            "class:blue",
                            f"[{server.get('name')}] " if "name" in server else "",
                        ),
                        ("class:bold", f"{server['url']}"),
                    ],
                    value=server["url"],
                )
                for server in _DEFAULT_MCP_SERVERS
            ]
            + [
                questionary.Choice(
                    title=[
                        ("", f"{emoji.emojize(':white_circle:')} "),
                        ("class:blue", "[Custom URL] "),
                        ("class:bold", "http://..."),
                    ],
                    value="Custom URL",
                )
            ],
        ).ask()
        if url == "Custom URL":  # custom mcp server can't require a token
            url = questionary.text("Custom URL:").ask()
            if not url.startswith("http"):
                raise ValueError("Invalid URL provided.")
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
            "Select MCP Agents:",
            choices=available_mcp_agents,
            validate=lambda choices: (
                True if len(choices) > 0 else "You must select at least one!"
            ),
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
            questionary.password("OpenAI-compatible Agents Token:").ask()
            if openai_agents_url != _DEFAULT_OPENAI_AGENTS_URL
            else _DEFAULT_OPENAI_AGENTS_TOKEN
        )
        available_openai_agents = APIModel.list_models(
            url=openai_agents_url, token=token
        )
        if len(available_openai_agents) == 0:
            raise ValueError(
                "No agents found in the provided OpenAI-compatible server URL."
            )

        openai_agents = questionary.checkbox(
            "Select OpenAI-compatible Agents:",
            choices=available_openai_agents,
            validate=lambda choices: (
                True if len(choices) > 0 else "You must select at least one!"
            ),
        ).ask()

        # add OpenAI-compatible agents
        agents += [
            OpenAIAPIAgent(
                url=openai_agents_url,
                token=token,
                name=agent,
                api_type="openai" if "claude-" not in agent else "anthropic",
            )
            for agent in openai_agents
        ]

    # set tasklists
    tasklists = questionary.checkbox(
        "Select Tasklists to use as benchmarks:",
        choices=[
            questionary.Choice(
                title=[
                    (
                        "class:blue",
                        f"[{tasklist['category']}] ",
                    ),
                    ("class:bold", tasklist["name"]),
                ],
                value=tasklist["name"],
            )
            for tasklist in available_tasklists
        ],
        style=custom_style,
        validate=lambda choices: (
            True if len(choices) > 0 else "You must select at least one!"
        ),
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
