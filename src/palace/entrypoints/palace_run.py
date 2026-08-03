# Copyright (C) 2025 European Union
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the European Union Public Licence (EUPL) v. 1.2
# as published by the European Union.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# European Union Public Licence for more details.
#
# You should have received a copy of the European Union Public Licence
# along with this program. If not, see <https://joinup.ec.europa.eu/collection/eupl/eupl-text-eupl-12>.

import argparse
import json
import os

from palace.evaluation import Evaluation
from palace.models.api_model import APIModel
from palace.utils.printing import print


def _parse_param_value(value: str):
    """Parse a param value: try JSON literal (number, bool, object), fallback to string."""
    try:
        return json.loads(value)
    except (json.JSONDecodeError, ValueError):
        return value


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
        default="auto",
        choices=["auto", "openai", "anthropic", "azure", "mcp"],
        help="The type of endpoint. Default 'auto' detects from model name.",
    )
    argparser.add_argument(
        "--report-detail",
        type=str,
        default="default",
        choices=["none", "default", "full"],
        help="Level of detail in per-task report: none (omit report), default (slimmed), full (includes task text).",
    )
    argparser.add_argument(
        "--agentic",
        action="store_true",
        default=False,
        help="Force agentic execution via Vivarium for all tasklists (sandboxed environment with tools).",
    )
    argparser.add_argument(
        "-c",
        "--concurrency",
        type=int,
        default=None,
        help="Number of tasks to run concurrently (default: PALACE_CONCURRENCY env var, or 25).",
    )
    argparser.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Extra model parameter (e.g., --param reasoning_effort=high --param temperature=0.5). Can be specified multiple times.",
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
        from pathlib import Path
        from palace.utils.paths import RESULTS_PATH
        output_path = Path(args.output_folder) if args.output_folder else RESULTS_PATH

        # Parse --param flags into dict
        model_extra_params = None
        if args.param:
            model_extra_params = {}
            for item in args.param:
                if "=" not in item:
                    print(f"[red]Error: --param must be KEY=VALUE, got: {item}[/red]")
                    exit(1)
                key, value = item.split("=", 1)
                model_extra_params[key] = _parse_param_value(value)

        endpoint_type = args.endpoint_type if args.endpoint_type != "auto" else None

        evaluation = Evaluation(
            name=args.run_name,
            url=args.url,
            token=args.token,
            endpoint_type=endpoint_type,
            agentic=True if args.agentic else None,
            task_amount_limit=args.limit,
            runs_per_configuration=args.runs_per_configuration,
            output_path=output_path,
            report_detail=args.report_detail,
            concurrency=args.concurrency,
            model_extra_params=model_extra_params,
        )
        evaluation.evaluate_all([args.name], tasklists=args.tasklist)
    except FileNotFoundError as e:
        print(f"[red]Error: {e}[/red]")
        exit(1)
    except KeyboardInterrupt:
        exit(130)
    except Exception as e:
        print(f"[red]Error: {e}[/red]")
        exit(1)
