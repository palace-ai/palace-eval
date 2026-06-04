import json
import sys

import emoji
import questionary

from palace.agents import MCPAgent, OpenAIAPIAgent, VivariumAgent
from palace.evaluation import Evaluation
from palace.mcp_utils.mcp_client import list_tools
from palace.models import APIModel
from palace.utils.constants import (
    ABW_SERVE_STAGING_URL,
    ALOHA_STAGING_URL,
    OPENAI_LIKE_API_BASE_URL,
    TS_STAGING_URL,
)
from palace.utils.paths import TASKLISTS_PATH
from palace.utils.printing import loading, print
from palace.utils.secrets import (
    ALOHA_STAGING_TOKEN,
    OPENAI_LIKE_API_KEY,
    TS_STAGING_TOKEN,
)

_DEFAULT_MCP_SERVERS = [
    {"name": "Default local Palace", "url": "http://localhost:8080/mcp/"},
    {"name": "Default local agentpoc", "url": "http://localhost:8000/mcp/"},
    {"name": "Default local abw-serve", "url": "http://localhost:8090/mcp/sse"},
    {"name": "ABW-serve Staging", "url": ABW_SERVE_STAGING_URL},
    {"name": "ALOHA Staging", "url": ALOHA_STAGING_URL, "token": ALOHA_STAGING_TOKEN},
    {
        "name": "ThematicSpaces Staging",
        "url": TS_STAGING_URL,
        "token": TS_STAGING_TOKEN,
        "params": {
            "main": "query",
            "custom": {"thematic_space": "cb305107-63f4-479d-962c-27496e35aa99"},
        },
    },
]
_DEFAULT_URL = OPENAI_LIKE_API_BASE_URL or ""
_DEFAULT_TOKEN = OPENAI_LIKE_API_KEY


def main():
    print("""[bright_yellow]
                                ╔══════════ ≪  ◆  ≫ ══════════╗[bright_magenta]
━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━     ┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃     ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━[bright_yellow]
━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━     ┃┃┃┏━━━┓┃┃┃┃┓┃┃┃┃┃┃┃┃┃┃┃┃┃┃     ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━[bright_magenta]
━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━     ┃┃┃┃┏━┓┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃     ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━[bright_yellow]
━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━     ┃┃┃┃┗━┛┃━━┓┃┃┃━━┓┃━━┓━━┓┃┃┃     ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━[bright_magenta]
━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━     ┃┃┃┃┏━━┛┃┓┃┃┃┃┃┓┃┃┏━┛┏┓┃┃┃┃     ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━[bright_yellow]
━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━     ┃┃┃┃┃┃┃┃┗┛┗┓┗┓┗┛┗┓┗━┓┃━┫┃┃┃     ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━[bright_magenta]
━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━     ┃┃┃┗┛┃┃┃━━━┛━┛━━━┛━━┛━━┛┃┃┃     ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━[bright_yellow]
━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━     ┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃     ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━[bright_magenta]
━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━     ┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃     ━━━━━ ◆ ━━━━━ ◆ ━━━━━ ◆ ━━━━━[bright_yellow]
                                ╚══════════ ≪  ◆  ≫ ══════════╝
""")
    print(
        """This is the main user interface for the [bold]Palace[/] evaluation framework.
Documentation: [blue]https://gitlab.jrc.ec.europa.eu/jrc-projects/jrc-gpt/evaluation/palace-lib[/]
Contact: [blue]massimiliano.altieri@ec.europa.eu[/]""",
        box=True,
        box_title=":waving_hand: Welcome to Palace",
        wrap_width=108,
    )
    print()

    if not OPENAI_LIKE_API_BASE_URL or not OPENAI_LIKE_API_KEY:
        print(
            "[red]Error: OPENAI_LIKE_API_BASE_URL and OPENAI_LIKE_API_KEY must be set (in .env or environment).[/red]"
        )
        sys.exit(1)

    # --- Endpoint ---
    endpoint_type = questionary.select(
        "Endpoint type:",
        choices=[
            questionary.Choice("OpenAI-compatible API", value="openai"),
            questionary.Choice("MCP server", value="mcp"),
        ],
    ).ask()
    if endpoint_type is None:
        return

    # --- Agentic mode ---
    agentic = questionary.confirm(
        "Force agentic execution via Vivarium for all tasklists?",
        default=False,
    ).ask()
    if agentic is None:
        return

    # --- Configure endpoint and select models/agents ---
    agents = []

    if endpoint_type == "mcp":
        url, token, mcp_server = _select_mcp_server()
        available_mcp_agents = [tool.name for tool in list_tools(url, token).tools]
        if not available_mcp_agents:
            raise ValueError("No agents found at the provided MCP server URL.")
        selected = questionary.checkbox(
            "Select agents:",
            choices=available_mcp_agents,
            validate=lambda c: True if c else "Select at least one",
        ).ask()
        if not selected:
            return
        agents = [
            MCPAgent(
                url=url,
                token=token,
                name=a,
                params=mcp_server.get("params"),
                output_processor=mcp_server.get("output_processor"),
            )
            for a in selected
        ]
    else:
        url = questionary.text("API URL:", default=_DEFAULT_URL).ask()
        if not url:
            return
        token = questionary.password("API Token (Enter to use env var):").ask()
        if not token:
            token = _DEFAULT_TOKEN
        available_models = APIModel.list_models(url=url, token=token)
        if not available_models:
            raise ValueError("No models found at the provided URL.")
        selected = questionary.checkbox(
            "Select models:",
            choices=sorted(available_models),
            validate=lambda c: True if c else "Select at least one",
        ).ask()
        if not selected:
            return
        if agentic:
            agents = [VivariumAgent(name=m, url=url, token=token) for m in selected]
        else:
            agents = [
                OpenAIAPIAgent(
                    url=url,
                    token=token,
                    name=m,
                )
                for m in selected
            ]

    # --- Tasklists ---
    available_tasklists = sorted(
        [
            {
                "name": t.name,
                **(info := json.loads((t / "info.json").read_text())),
                "category": info["category"],
                "input_modalities": info.get(
                    "input_modalities", info.get("modalities", ["text"])
                ),
                "output_modalities": info.get("output_modalities", ["text"]),
            }
            for t in TASKLISTS_PATH.iterdir()
            if t.is_dir() and (t / "tasks.json").exists()
        ],
        key=lambda x: (x["category"], x["name"]),
    )

    custom_style = questionary.Style([("blue", "fg:blue"), ("bold", "bold")])
    tasklists = questionary.checkbox(
        "Select tasklists:",
        choices=[
            questionary.Choice(
                title=[
                    ("class:blue", f"[{tl['category']}] "),
                    (
                        "",
                        f"[{', '.join(tl['input_modalities'])}→{', '.join(tl['output_modalities'])}] ",
                    ),
                    ("class:bold", tl["name"]),
                ],
                value=tl["name"],
            )
            for tl in available_tasklists
        ],
        style=custom_style,
        validate=lambda c: True if c else "Select at least one",
    ).ask()
    if not tasklists:
        return

    # --- Options ---
    task_limit = questionary.select(
        "Task limit per tasklist:",
        choices=["1", "5", "20", "50", "100", "500", "Unlimited"],
        default="1",
    ).ask()
    if not task_limit:
        return
    task_limit = int(task_limit) if task_limit != "Unlimited" else sys.maxsize

    runs = questionary.select(
        "Runs per configuration:", choices=["1", "3", "5", "10"], default="1"
    ).ask()
    if not runs:
        return
    runs = int(runs)
    name = questionary.text("Run name:", default="eval").ask()
    if not name:
        return

    # --- Execute ---
    evaluation = Evaluation(
        name=name, task_amount_limit=task_limit, runs_per_configuration=runs
    )
    try:
        evaluation.evaluate_all(agents, tasklists=tasklists)
    except KeyboardInterrupt:
        pass


def _select_mcp_server():
    """Interactive MCP server selection. Returns (url, token, server_dict)."""
    with loading() as ld:
        for server in _DEFAULT_MCP_SERVERS:
            ld.status(f"Checking MCP servers... [dim]({server['url']})")
            try:
                list_tools(server["url"], server.get("token"))
                server["available"] = True
            except Exception:
                server["available"] = False

    url = questionary.select(
        "MCP server:",
        choices=[
            questionary.Choice(
                title=[
                    (
                        "",
                        f"{emoji.emojize(':green_circle:')} "
                        if s.get("available")
                        else f"{emoji.emojize(':red_circle:')} ",
                    ),
                    ("class:blue", f"[{s['name']}] "),
                    ("class:bold", s["url"]),
                ],
                value=s["url"],
            )
            for s in _DEFAULT_MCP_SERVERS
        ]
        + [
            questionary.Choice(
                title=[
                    ("", "○ "),
                    ("class:blue", "[Custom] "),
                    ("class:bold", "http://..."),
                ],
                value="custom",
            )
        ],
    ).ask()

    if url == "custom":
        url = questionary.text("URL:").ask()
        token = questionary.text("Token (leave empty if none):").ask() or None
        return url, token, {"url": url}

    server = next(s for s in _DEFAULT_MCP_SERVERS if s["url"] == url)
    return url, server.get("token"), server


if __name__ == "__main__":
    main()
