import argparse
from pathlib import Path
from typing import Callable

from palace.agents.mcp_agent import MCPAgent
from palace.agents.openai_api_agent import OpenAIAPIAgent
from palace.evaluation import Evaluation


def evaluate(
    run_name: str,
    output_folder: str,
    url: str,
    token: str | None,
    name: str,
    tasklist: str,
    limit: int | None = None,
    runs_per_configuration: int = 1,
    on_task_complete: Callable[[int, int], None] | None = None,
    endpoint_type: str = "openai",
):
    """Evaluate a remote model/agent via OpenAI API on the specified tasklists and save results to a JSONL file.

    :param run_name: The name of the run.
    :param output_folder: The path to the output folder.
    :param url: The URL of the OpenAI API.
    :param token: The token to use for authentication, if required.
    :param name: The name of the model/agent.
    :param tasklist: The tasklist to evaluate the model/agent on.
    :param limit: The maximum number of tasks to evaluate per tasklist.
    :param runs_per_configuration: The number of evaluation runs to perform.
    :param endpoint_type: The type of endpoint ("openai" or "mcp").
    """
    if endpoint_type == "mcp":
        agent = MCPAgent(url=url, token=token, name=name)
    elif endpoint_type == "openai":
        agent = OpenAIAPIAgent(
            url=url,
            token=token,
            name=name,
            api_type="openai" if "claude" not in name.lower() else "anthropic",
        )
    else:
        raise ValueError(f"Unsupported endpoint type: {endpoint_type}")
    evaluation = Evaluation(
        name=run_name,
        task_amount_limit=limit,
        runs_per_configuration=runs_per_configuration,
        output_path=Path(output_folder),
        on_task_complete=on_task_complete,
    )
    evaluation.evaluate_all([agent], tasklists=[tasklist])


def run():
    argparser = argparse.ArgumentParser(
        description="Run evaluation of a model/agent on PALACE tasklists."
    )
    argparser.add_argument(
        "--run-name", type=str, default="eval", help="The name of the run."
    )
    argparser.add_argument(
        "--output-folder",
        type=str,
        default="./palace_results",
        help="The path to the output folder.",
    )
    argparser.add_argument(
        "-u", "--url", type=str, required=True, help="The URL of the OpenAI API."
    )
    argparser.add_argument(
        "-k",
        "--token",
        type=str,
        default=None,
        help="The token to use for authentication, if required.",
    )
    argparser.add_argument(
        "-m", "--name", type=str, required=True, help="The name of the model/agent."
    )
    argparser.add_argument(
        "-t",
        "--tasklist",
        type=str,
        required=True,
        help="The tasklist to evaluate the model/agent on.",
    )
    argparser.add_argument(
        "-l",
        "--limit",
        type=int,
        default=None,
        help="The maximum number of tasks to evaluate per tasklist.",
    )
    argparser.add_argument(
        "--runs-per-configuration",
        type=int,
        default=1,
        help="The number of evaluation runs to perform.",
    )
    argparser.add_argument(
        "--endpoint-type",
        type=str,
        default="openai",
        choices=["openai", "mcp"],
        help="The type of endpoint (openai or mcp).",
    )
    args = argparser.parse_args()

    evaluate(
        run_name=args.run_name,
        output_folder=args.output_folder,
        url=args.url,
        token=args.token,
        name=args.name,
        tasklist=args.tasklist,
        limit=args.limit,
        runs_per_configuration=args.runs_per_configuration,
        endpoint_type=args.endpoint_type,
    )
