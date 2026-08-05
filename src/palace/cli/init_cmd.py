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

"""Init command: palace init."""

import json

import click
import questionary

from palace.utils.paths import TASKLISTS_PATH
from palace.utils.printing import print

# Task type templates
TASK_TYPES = ["QA", "Classification", "CriteriaEvaluation", "InstructionFollowing", "Agentic"]
CATEGORIES = ["Knowledge", "Reasoning", "Coding", "Safety", "Instruction Following", "Agentic", "Multimodal", "Other"]


@click.command()
@click.argument("name")
@click.option("--agentic", is_flag=True, help="Create an agentic benchmark scaffold.")
@click.option("--bare", is_flag=True, help="Skip wizard, create minimal scaffold.")
def init(name: str, agentic: bool, bare: bool) -> None:
    """Create a new benchmark scaffold.

    Creates a new benchmark directory with info.json and tasks.json templates.
    Runs an interactive wizard to configure the benchmark unless --bare is used.

    \b
    Examples:
        palace init my-benchmark
        palace init my-agent-test --agentic
        palace init quick-test --bare
    """
    dest = TASKLISTS_PATH / name

    if dest.exists():
        print(f"[red]Error:[/red] Benchmark already exists: {name}")
        print(f"[dim]Path: {dest}[/dim]")
        return

    if agentic:
        task_type = "Agentic"
    else:
        task_type = None

    if bare:
        # Create minimal scaffold without wizard
        _create_scaffold(dest, name, task_type=task_type or "QA", agentic=agentic)
        print(f"[green]Created benchmark scaffold:[/green] {name}")
        print(f"[dim]Path: {dest}[/dim]")
        print()
        print("[dim]Edit info.json and tasks.json to configure your benchmark.[/dim]")
        print("[dim]Run 'palace validate {name}' when ready.[/dim]")
        return

    # Interactive wizard
    print(f"[bold]Creating benchmark: {name}[/bold]\n")

    # Description
    description = questionary.text(
        "Description:",
        default="",
    ).ask()
    if description is None:
        return

    # Category
    category = questionary.select(
        "Category:",
        choices=CATEGORIES,
    ).ask()
    if category is None:
        return

    # Task type
    if not task_type:
        task_type = questionary.select(
            "Task type:",
            choices=TASK_TYPES,
        ).ask()
        if task_type is None:
            return

    # Agentic-specific options
    env_image = None
    if task_type == "Agentic" or agentic:
        agentic = True
        env_image = questionary.text(
            "Docker image for environment:",
            default="python:3.11-slim",
        ).ask()
        if env_image is None:
            return

    # Create scaffold
    _create_scaffold(
        dest,
        name,
        description=description,
        category=category,
        task_type=task_type,
        agentic=agentic,
        env_image=env_image,
    )

    print()
    print(f"[green]Created benchmark scaffold:[/green] {name}")
    print(f"[dim]Path: {dest}[/dim]")
    print()
    print("Next steps:")
    print(f"  1. Edit [bold]{dest}/tasks.json[/bold] to add your tasks")
    print(f"  2. Run [bold]palace validate {name}[/bold] to check for errors")
    print(f"  3. Run [bold]palace publish {name}[/bold] to publish to HuggingFace")


def _create_scaffold(
    dest,
    name: str,
    description: str = "",
    category: str = "Other",
    task_type: str = "QA",
    agentic: bool = False,
    env_image: str | None = None,
) -> None:
    """Create the benchmark scaffold files."""
    dest.mkdir(parents=True, exist_ok=True)

    # Build info.json
    info = {
        "name": name,
        "description": description,
        "category": category,
        "task_type": task_type,
        "input_modalities": ["text"],
        "output_modalities": ["text"],
    }

    # Add task_type_fields based on type
    if task_type == "QA":
        info["task_type_fields"] = {"# comment": "QA tasks require 'expected' field in each task"}
    elif task_type == "Classification":
        info["task_type_fields"] = {
            "labels": [
                {
                    "name": "Answer",
                    "description": "The classification label",
                    "classes": [
                        {"name": "A", "condition": "First option"},
                        {"name": "B", "condition": "Second option"},
                    ],
                }
            ]
        }
    elif task_type == "Agentic" or agentic:
        info["env"] = {
            "image": env_image or "python:3.11-slim",
            "# comment": "Specify Docker image and optional tools for agentic execution",
        }

    # Write info.json with comments
    info_content = json.dumps(info, indent=4, ensure_ascii=False)
    (dest / "info.json").write_text(info_content)

    # Build tasks.json template
    if task_type == "QA":
        tasks = [
            {
                "id": "task_001",
                "objective": "What is the capital of France?",
                "expected": "Paris",
                "# comment": "Add your QA tasks here. Each task needs id, objective, and expected.",
            }
        ]
    elif task_type == "Classification":
        tasks = [
            {
                "id": "task_001",
                "objective": "Classify the sentiment of: 'I love this product!'",
                "labels": {"Answer": "A"},
                "# comment": "Each task needs id, objective, and labels matching info.json task_type_fields",
            }
        ]
    elif task_type == "Agentic":
        tasks = [
            {
                "id": "task_001",
                "objective": "Create a file named 'hello.txt' containing 'Hello, World!'",
                "expected": "File hello.txt exists with content 'Hello, World!'",
                "# comment": "Agentic tasks are executed in a sandboxed environment with tools",
            }
        ]
    else:
        tasks = [
            {
                "id": "task_001",
                "objective": "Your task description here",
                "expected": "Expected outcome",
            }
        ]

    tasks_content = json.dumps(tasks, indent=4, ensure_ascii=False)
    (dest / "tasks.json").write_text(tasks_content)

    # Create task_files directory for attachments
    (dest / "task_files").mkdir(exist_ok=True)
    (dest / "task_files" / ".gitkeep").touch()
