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

"""Interactive wizard for palace run command."""

import json
import sys

import questionary

from palace.utils.config import get_config_value
from palace.utils.paths import TASKLISTS_PATH
from palace.utils.printing import print


def run_wizard() -> None:
    """Interactive wizard for configuring and running an evaluation.

    Called by `palace run` when invoked with no arguments.
    """
    # --- Banner ---
    print("""[bright_cyan]
    ╔══════════════════════════════════════════════════════╗
    ║                                                      ║
    ║   ██████╗  █████╗ ██╗      █████╗  ██████╗███████╗   ║
    ║   ██╔══██╗██╔══██╗██║     ██╔══██╗██╔════╝██╔════╝   ║
    ║   ██████╔╝███████║██║     ███████║██║     █████╗     ║
    ║   ██╔═══╝ ██╔══██║██║     ██╔══██║██║     ██╔══╝     ║
    ║   ██║     ██║  ██║███████╗██║  ██║╚██████╗███████╗   ║
    ║   ╚═╝     ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝ ╚═════╝╚══════╝   ║
    ║                                                      ║
    ║           Interactive Command-Line Wizard            ║
    ╚══════════════════════════════════════════════════════╝
[/bright_cyan]""")

    # --- Defaults from config ---
    default_url = get_config_value("url") or ""
    default_token = get_config_value("key") or ""
    default_vivarium_url = get_config_value("vivarium_url") or ""

    if not default_url:
        print("[yellow]Tip:[/yellow] Run [cyan]palace config set url <url>[/cyan] to avoid typing it each time.")

    # --- API URL ---
    url = questionary.text("API URL:", default=default_url).ask()
    if url is None:
        sys.exit(130)
    if not url:
        print("[red]Error:[/red] API URL is required.")
        sys.exit(1)

    # --- Token ---
    token_answer = questionary.password("API token (Enter to use configured value):").ask()
    if token_answer is None:
        sys.exit(130)
    token = token_answer or default_token or None

    # --- Model selection ---
    try:
        from palace.models.api_model import APIModel

        with _spinner("Fetching models from endpoint..."):
            available_models = sorted(APIModel.list_models(url=url, token=token))
    except Exception:
        available_models = []

    if available_models:
        models = questionary.checkbox(
            "Select model(s):",
            choices=available_models,
            validate=lambda c: True if c else "Select at least one model.",
        ).ask()
        if not models:
            sys.exit(130)
    else:
        print("[dim]Could not fetch model list — enter model name manually.[/dim]")
        model_name = questionary.text("Model name:").ask()
        if not model_name:
            sys.exit(130)
        models = [model_name]

    # --- Agentic mode ---
    agentic = questionary.confirm(
        "Use agentic mode via Vivarium?",
        default=False,
    ).ask()
    if agentic is None:
        sys.exit(130)

    vivarium_url = None
    if agentic:
        viv = questionary.text(
            "Vivarium URL:",
            default=default_vivarium_url,
        ).ask()
        if viv is None:
            sys.exit(130)
        vivarium_url = viv or None

    # --- Tasklist selection ---
    available_tasklists = _load_local_tasklists()
    if not available_tasklists:
        print("[red]No tasklists found.[/red] Run [cyan]palace download <name>[/cyan] first.")
        sys.exit(1)

    custom_style = questionary.Style([("blue", "fg:blue"), ("bold", "bold")])
    tasklists = questionary.checkbox(
        "Select tasklist(s):",
        choices=[
            questionary.Choice(
                title=[
                    ("class:blue", f"[{tl['category']}] "),
                    ("", f"[{', '.join(tl['input_modalities'])}→{', '.join(tl['output_modalities'])}] "),
                    ("class:bold", tl["name"]),
                ],
                value=tl["name"],
            )
            for tl in available_tasklists
        ],
        style=custom_style,
        validate=lambda c: True if c else "Select at least one tasklist.",
    ).ask()
    if not tasklists:
        sys.exit(130)

    # --- Options ---
    task_limit_str = questionary.select(
        "Task limit per tasklist:",
        choices=["1", "5", "20", "50", "100", "300", "1000", "5000", "Unlimited"],
        default="Unlimited",
    ).ask()
    if task_limit_str is None:
        sys.exit(130)
    task_limit = None if task_limit_str == "Unlimited" else int(task_limit_str)

    runs_str = questionary.select(
        "Runs per configuration:",
        choices=["1", "3", "5", "10"],
        default="1",
    ).ask()
    if runs_str is None:
        sys.exit(130)
    runs = int(runs_str)

    concurrency_str = questionary.select(
        "Concurrency (1 = detailed output, higher = faster):",
        choices=["1", "5", "10", "25", "50"],
        default="1",
    ).ask()
    if concurrency_str is None:
        sys.exit(130)
    concurrency = int(concurrency_str)

    run_name = questionary.text("Run name:", default="eval").ask()
    if run_name is None:
        sys.exit(130)
    run_name = run_name or "eval"

    # --- Summary ---
    print(f"""
[bold]Ready to run:[/bold]
  Models:      {", ".join(models)}
  Tasklists:   {", ".join(tasklists)}
  Agentic:     {"yes" if agentic else "no"}{f" ({vivarium_url})" if vivarium_url else ""}
  Limit:       {task_limit if task_limit is not None else "unlimited"} tasks
  Concurrency: {concurrency}
  Runs:        {runs}
  Run name:    {run_name}
""")

    confirm = questionary.confirm("Start evaluation?", default=True).ask()
    if not confirm:
        print("[dim]Cancelled.[/dim]")
        sys.exit(0)

    # --- Execute ---
    from palace.agents import ModelNotFoundError
    from palace.evaluation import Evaluation
    from palace.utils.exceptions import JudgeConfigurationError

    try:
        evaluation = Evaluation(
            name=run_name,
            url=url,
            token=token,
            agentic=True if agentic else None,
            vivarium_url=vivarium_url,
            task_amount_limit=task_limit,
            runs_per_configuration=runs,
            concurrency=concurrency,
        )
        evaluation.evaluate_all(models, tasklists=tasklists)

    except ModelNotFoundError as e:
        print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except JudgeConfigurationError as e:
        print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        print(f"[red]Error:[/red] {e}")
        sys.exit(1)


def _load_local_tasklists() -> list[dict]:
    """Load metadata for all locally downloaded tasklists."""
    tasklists = []
    if not TASKLISTS_PATH.exists():
        return tasklists
    for t in TASKLISTS_PATH.iterdir():
        info_file = t / "info.json"
        if not t.is_dir() or not info_file.exists():
            continue
        try:
            info = json.loads(info_file.read_text())
            tasklists.append(
                {
                    "name": t.name,
                    "category": info.get("category", "Unknown"),
                    "input_modalities": info.get("input_modalities", info.get("modalities", ["text"])),
                    "output_modalities": info.get("output_modalities", ["text"]),
                }
            )
        except Exception:
            continue
    return sorted(tasklists, key=lambda x: (x["category"], x["name"]))


class _spinner:
    """Simple context manager for a loading message."""

    def __init__(self, message: str):
        self._message = message

    def __enter__(self):
        print(f"[dim]{self._message}[/dim]")
        return self

    def __exit__(self, *_):
        pass
