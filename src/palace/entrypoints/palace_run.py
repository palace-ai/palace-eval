import argparse
import os
from pathlib import Path
from typing import Callable

from palace.agents.mcp_agent import MCPAgent
from palace.agents.openai_api_agent import OpenAIAPIAgent
from palace.evaluation import Evaluation
from palace.models.api_model import APIModel
from palace.utils.paths import RESULTS_PATH
from palace.utils.printing import print


def evaluate(
    run_name: str,
    output_folder: str | None,
    url: str,
    token: str | None,
    name: str,
    tasklist: str | list[str],
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
        tasklist: The tasklist(s) to evaluate the model/agent on.
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
    tasklists = [tasklist] if isinstance(tasklist, str) else tasklist
    evaluation.evaluate_all([agent], tasklists=tasklists)


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
        default=os.environ.get("OPENAI_LIKE_API_KEY"),
        help="The token to use for authentication. Falls back to OPENAI_LIKE_API_KEY environment variable.",
    )
    argparser.add_argument(
        "-m", "--name", type=str, default=None, help="The name of the model/agent. If omitted, lists available models."
    )
    argparser.add_argument(
        "-t",
        "--tasklist",
        type=str,
        required=True,
        action="append",
        help="The tasklist(s) to evaluate on. Can be specified multiple times: -t T1 -t T2",
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

    # If no model specified, list available models and exit
    if args.name is None:
        try:
            models = sorted(APIModel.list_models(args.url, args.token))
            if models:
                print("[cyan]Available models at this endpoint:[/cyan]")
                for model in models:
                    print(f"  - {model}")
                print(f"\n[yellow]Run again with: -m <model_name>[/yellow]")
            else:
                print("[yellow]No models found at this endpoint.[/yellow]")
        except Exception as e:
            print(f"[red]Error: {e}[/red]")
        exit(0)

    try:
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
    except FileNotFoundError as e:
        print(f"[red]Error: {e}[/red]")
        exit(1)
    except KeyboardInterrupt:
        exit(130)
    except Exception as e:
        print(f"[red]Error: {e}[/red]")
        exit(1)
