import argparse
from pathlib import Path
from typing import Callable

from palace.agents.mcp_agent import MCPAgent
from palace.agents.openai_api_agent import OpenAIAPIAgent
from palace.evaluation import Evaluation
from palace.utils.paths import RESULTS_PATH


def evaluate(
    run_name: str,
    output_folder: str | None,
    url: str,
    token: str | None,
    name: str,
    tasklist: str,
    limit: int | None = None,
    runs_per_configuration: int = 1,
    on_task_complete: Callable[[int, int], None] | None = None,
    endpoint_type: str = "openai",
    io_adapter: dict | None = None,
    report_detail: str = "default",
):
    """Evaluate a remote model/agent via OpenAI API on the specified tasklists and save results to a JSONL file.

    Args:
        run_name: The name of the run.
        output_folder: The path to the output folder (default: ~/.cache/palace/results/).
        url: The URL of the OpenAI API.
        token: The token to use for authentication, if required.
        name: The name of the model/agent.
        tasklist: The tasklist to evaluate the model/agent on.
        limit: The maximum number of tasks to evaluate per tasklist.
        runs_per_configuration: The number of evaluation runs to perform.
        on_task_complete: Optional callback invoked after each task with (current, total).
        endpoint_type: The type of endpoint ("openai" or "mcp").
        io_adapter: Optional model I/O adapter config dict for specialized models.
        report_detail: Level of detail in per-task report: "none" (omit report),
            "default" (slimmed), "full" (includes task text).
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
    
    output_path = Path(output_folder) if output_folder else RESULTS_PATH
    evaluation = Evaluation(
        name=run_name,
        task_amount_limit=limit,
        runs_per_configuration=runs_per_configuration,
        output_path=output_path,
        on_task_complete=on_task_complete,
        io_adapter=io_adapter,
        report_detail=report_detail,
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
        default=None,
        help="The path to the output folder (default: ~/.cache/palace/results/).",
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
    argparser.add_argument(
        "--report-detail",
        type=str,
        default="default",
        choices=["none", "default", "full"],
        help="Level of detail in per-task report: none (omit report), default (slimmed), full (includes task text).",
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
        report_detail=args.report_detail,
    )
