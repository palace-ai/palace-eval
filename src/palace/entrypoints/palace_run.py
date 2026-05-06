import argparse
import os
from pathlib import Path
from typing import Callable

import httpx

from palace.agents.mcp_agent import MCPAgent
from palace.agents.openai_api_agent import OpenAIAPIAgent
from palace.evaluation import Evaluation
from palace.utils.paths import RESULTS_PATH
from palace.utils.printing import print


class EndpointError(Exception):
    """Raised when there's an issue with the API endpoint."""
    pass


class ModelNotFoundError(EndpointError):
    """Raised when the specified model is not available."""
    def __init__(self, message: str, available_models: list[str] | None = None):
        super().__init__(message)
        self.available_models = available_models


def _check_endpoint(url: str, token: str | None, model: str) -> None:
    """Verify the endpoint is reachable and the model is available.
    
    Args:
        url: The base URL of the OpenAI-compatible API.
        token: Optional authentication token.
        model: The model name to verify.
        
    Raises:
        EndpointError: If the endpoint is not reachable.
        ModelNotFoundError: If the model is not available.
    """
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    # Check endpoint is reachable and get available models
    try:
        response = httpx.get(f"{url}/models", headers=headers, timeout=30)
    except httpx.ConnectError:
        raise EndpointError(f"Cannot connect to endpoint: {url}")
    except httpx.TimeoutException:
        raise EndpointError(f"Connection to endpoint timed out: {url}")
    except Exception as e:
        raise EndpointError(f"Error connecting to endpoint: {e}")
    
    if response.status_code == 401:
        raise EndpointError("Authentication failed. Please check your API token.")
    if response.status_code == 403:
        raise EndpointError("Access forbidden. Please check your API token permissions.")
    if response.status_code != 200:
        raise EndpointError(f"Endpoint returned status {response.status_code}: {response.text[:200]}")
    
    # Parse available models
    try:
        data = response.json()
        available_models = [m["id"] for m in data.get("data", [])]
    except Exception:
        # If we can't parse models, skip model validation
        return
    
    # Check if model exists
    if available_models and model not in available_models:
        raise ModelNotFoundError(
            f"Model '{model}' not found at endpoint.",
            available_models=available_models
        )
    
    # Quick sanity check: try a minimal completion
    try:
        test_response = httpx.post(
            f"{url}/chat/completions",
            headers={**headers, "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 5,
            },
            timeout=30,
        )
        if test_response.status_code != 200:
            error_detail = test_response.json().get("detail", test_response.text[:200])
            if "not available" in str(error_detail).lower() or "not found" in str(error_detail).lower():
                raise ModelNotFoundError(
                    f"Model '{model}' is not available: {error_detail}",
                    available_models=available_models if available_models else None
                )
            raise EndpointError(f"Model test failed: {error_detail}")
    except ModelNotFoundError:
        raise
    except EndpointError:
        raise
    except Exception as e:
        raise EndpointError(f"Failed to verify model: {e}")


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
        # Verify endpoint and model before starting evaluation
        _check_endpoint(url, token, name)
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
        default=os.environ.get("OPENAI_API_KEY") or os.environ.get("API_KEY"),
        help="The token to use for authentication. Falls back to OPENAI_API_KEY or API_KEY environment variables.",
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
            headers = {"Authorization": f"Bearer {args.token}"} if args.token else {}
            response = httpx.get(f"{args.url}/models", headers=headers, timeout=30)
            if response.status_code == 401:
                print("[red]Error: Authentication failed. Please provide a token with -k or set OPENAI_API_KEY.[/red]")
                exit(1)
            if response.status_code != 200:
                print(f"[red]Error: Failed to fetch models (status {response.status_code})[/red]")
                exit(1)
            data = response.json()
            # Check for error in response body (some APIs return 200 with error)
            if "error" in data or (data.get("base_resp", {}).get("status_code", 0) != 0):
                error_msg = data.get("error", {}).get("message") or data.get("base_resp", {}).get("status_msg") or "Unknown error"
                print(f"[red]Error: {error_msg}[/red]")
                exit(1)
            models = sorted([m["id"] for m in data.get("data", [])])
            if models:
                print("[cyan]Available models at this endpoint:[/cyan]")
                for model in models:
                    print(f"  - {model}")
                print(f"\n[yellow]Run again with: -m <model_name>[/yellow]")
            else:
                print("[yellow]No models found at this endpoint.[/yellow]")
            exit(0)
        except httpx.ConnectError:
            print(f"[red]Error: Cannot connect to endpoint: {args.url}[/red]")
            exit(1)
        except Exception as e:
            print(f"[red]Error: {e}[/red]")
            exit(1)

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
    except ModelNotFoundError as e:
        print(f"[red]Error: {e}[/red]")
        if e.available_models:
            print("\n[yellow]Available models at this endpoint:[/yellow]")
            for model in sorted(e.available_models):
                print(f"  - {model}")
            print(f"\n[cyan]Run again with: -m <model_name>[/cyan]")
        exit(1)
    except EndpointError as e:
        print(f"[red]Error: {e}[/red]")
        exit(1)
