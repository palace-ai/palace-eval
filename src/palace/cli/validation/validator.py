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

"""Full tasklist validation with errors/warnings separation."""

import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Severity(Enum):
    """Severity level for validation issues."""

    ERROR = "error"  # Blocking - must fix
    WARNING = "warning"  # Non-blocking - should fix


@dataclass
class ValidationIssue:
    """A single validation issue."""

    severity: Severity
    message: str
    path: str | None = None
    field: str | None = None

    def __str__(self) -> str:
        prefix = "ERROR" if self.severity == Severity.ERROR else "WARNING"
        location = ""
        if self.path:
            location = f" in {self.path}"
        if self.field:
            location = f"{location} ({self.field})"
        return f"[{prefix}]{location}: {self.message}"


# Required fields in info.json
REQUIRED_INFO_FIELDS = ["name", "category", "task_type"]

# Valid task types
VALID_TASK_TYPES = [
    "QA",
    "Classification",
    "CriteriaEvaluation",
    "InstructionFollowing",
    "Agentic",
]

# Valid categories and subcategories (aligned with vault taxonomy)
CATEGORY_TAXONOMY = {
    "Reasoning": [
        "Abstract Reasoning",
        "Common Sense Reasoning",
        "Expert Reasoning",
        "General Reasoning",
        "Mathematical Reasoning",
        "Multilingual Reasoning",
        "Video Reasoning",
        "Visual Reasoning",
    ],
    "Knowledge": [
        "Domain Knowledge",
        "General Knowledge",
        "Multilingual Knowledge",
    ],
    "Trust": [
        "Alignment",
        "Multilingual Safety",
        "Reliability",
        "Text Safety",
        "Visual Safety",
    ],
    "Skills": [
        "Cybersecurity",
        "Instruction Following",
        "Software Engineering",
        "Tool Use",
        "Visual Agents",
        "Web Research",
    ],
    "Literacy": [
        "Long Context",
        "Multilingual Comprehension",
        "Report Generation",
        "Translation",
    ],
}


class Validator:
    """Validates palace tasklists."""

    def validate(self, tasklist_path: Path) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
        """Validate a tasklist.

        Args:
            tasklist_path: Path to tasklist directory.

        Returns:
            Tuple of (errors, warnings).
        """
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []

        # Check directory exists
        if not tasklist_path.exists():
            errors.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    message=f"Tasklist directory does not exist: {tasklist_path}",
                )
            )
            return errors, warnings

        if not tasklist_path.is_dir():
            errors.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    message=f"Path is not a directory: {tasklist_path}",
                )
            )
            return errors, warnings

        # Validate info.json
        info_errors, info_warnings, info_data = self._validate_info(tasklist_path)
        errors.extend(info_errors)
        warnings.extend(info_warnings)

        # Validate tasks.json
        tasks_errors, tasks_warnings, tasks_data = self._validate_tasks(tasklist_path)
        errors.extend(tasks_errors)
        warnings.extend(tasks_warnings)

        # Cross-validation (if both files exist)
        if info_data and tasks_data:
            cross_errors, cross_warnings = self._validate_cross(tasklist_path, info_data, tasks_data)
            errors.extend(cross_errors)
            warnings.extend(cross_warnings)

        # Validate file references (attachments)
        if tasks_data:
            ref_errors, ref_warnings = self._validate_file_references(tasklist_path, tasks_data)
            errors.extend(ref_errors)
            warnings.extend(ref_warnings)

        return errors, warnings

    def _validate_info(self, tasklist_path: Path) -> tuple[list[ValidationIssue], list[ValidationIssue], dict | None]:
        """Validate info.json file.

        Returns:
            Tuple of (errors, warnings, parsed_data).
        """
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []
        info_file = tasklist_path / "info.json"

        if not info_file.exists():
            errors.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    message="Missing info.json",
                    path="info.json",
                )
            )
            return errors, warnings, None

        try:
            info_data = json.loads(info_file.read_text())
        except json.JSONDecodeError as e:
            errors.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    message=f"Invalid JSON: {e}",
                    path="info.json",
                )
            )
            return errors, warnings, None

        # Check required fields
        for field in REQUIRED_INFO_FIELDS:
            if field not in info_data:
                errors.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        message=f"Missing required field: {field}",
                        path="info.json",
                        field=field,
                    )
                )

        # Validate task_type
        task_type = info_data.get("task_type")
        if task_type and task_type not in VALID_TASK_TYPES:
            warnings.append(
                ValidationIssue(
                    severity=Severity.WARNING,
                    message=f"Unknown task_type: {task_type}. Valid types: {VALID_TASK_TYPES}",
                    path="info.json",
                    field="task_type",
                )
            )

        # Validate objective_template
        objective_template = info_data.get("objective_template")
        if objective_template is not None:
            if not isinstance(objective_template, str):
                errors.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        message=f"objective_template must be a string, got {type(objective_template).__name__}",
                        path="info.json",
                        field="objective_template",
                    )
                )
            elif not objective_template.strip():
                errors.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        message="objective_template cannot be empty",
                        path="info.json",
                        field="objective_template",
                    )
                )
            else:
                placeholders = re.findall(r"\{\{(\w+)\}\}", objective_template)
                if not placeholders:
                    warnings.append(
                        ValidationIssue(
                            severity=Severity.WARNING,
                            message="objective_template has no {{placeholders}} - template will be used literally",
                            path="info.json",
                            field="objective_template",
                        )
                    )

        # Validate category
        category = info_data.get("category")
        subcategory = info_data.get("subcategory")
        all_subcategories = [sub for subs in CATEGORY_TAXONOMY.values() for sub in subs]

        if category:
            if category not in CATEGORY_TAXONOMY:
                # Check if it's actually a subcategory (common mistake)
                if category in all_subcategories:
                    warnings.append(
                        ValidationIssue(
                            severity=Severity.WARNING,
                            message=f"'{category}' is a subcategory, not a category. Use 'category' + 'subcategory' fields. Valid categories: {list(CATEGORY_TAXONOMY.keys())}",
                            path="info.json",
                            field="category",
                        )
                    )
                else:
                    warnings.append(
                        ValidationIssue(
                            severity=Severity.WARNING,
                            message=f"Unknown category: {category}. Valid categories: {list(CATEGORY_TAXONOMY.keys())}",
                            path="info.json",
                            field="category",
                        )
                    )

        if subcategory:
            if subcategory not in all_subcategories:
                warnings.append(
                    ValidationIssue(
                        severity=Severity.WARNING,
                        message=f"Unknown subcategory: {subcategory}. Valid subcategories: {all_subcategories}",
                        path="info.json",
                        field="subcategory",
                    )
                )
            elif category and category in CATEGORY_TAXONOMY:
                # Check subcategory belongs to the category
                if subcategory not in CATEGORY_TAXONOMY[category]:
                    expected_cat = next((c for c, subs in CATEGORY_TAXONOMY.items() if subcategory in subs), None)
                    warnings.append(
                        ValidationIssue(
                            severity=Severity.WARNING,
                            message=f"Subcategory '{subcategory}' doesn't belong to category '{category}'. Expected category: '{expected_cat}'",
                            path="info.json",
                            field="subcategory",
                        )
                    )

        # Check for recommended fields
        recommended = ["description", "input_modalities", "output_modalities"]
        for field in recommended:
            if field not in info_data:
                warnings.append(
                    ValidationIssue(
                        severity=Severity.WARNING,
                        message=f"Missing recommended field: {field}",
                        path="info.json",
                        field=field,
                    )
                )

        # Agentic-specific validation
        if task_type == "Agentic":
            if "env" not in info_data:
                errors.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        message="Agentic tasklists require 'env' configuration",
                        path="info.json",
                        field="env",
                    )
                )
            else:
                env = info_data["env"]
                # Handle both single-env and multi-env formats:
                # Single-env: {"image": "...", "tools": [...]}
                # Multi-env: {"default": {"image": "...", "tools": [...]}, "other": {...}}
                if "image" in env:
                    # Single-env format - valid
                    pass
                elif isinstance(env, dict) and env:
                    # Multi-env format - check that all named envs have image
                    for env_name, env_config in env.items():
                        if not isinstance(env_config, dict):
                            errors.append(
                                ValidationIssue(
                                    severity=Severity.ERROR,
                                    message=f"Agentic env '{env_name}' must be a configuration object",
                                    path="info.json",
                                    field=f"env.{env_name}",
                                )
                            )
                        elif "image" not in env_config:
                            errors.append(
                                ValidationIssue(
                                    severity=Severity.ERROR,
                                    message=f"Agentic env '{env_name}' requires 'image' field",
                                    path="info.json",
                                    field=f"env.{env_name}.image",
                                )
                            )
                else:
                    errors.append(
                        ValidationIssue(
                            severity=Severity.ERROR,
                            message="Agentic env must specify 'image' or named environment configurations",
                            path="info.json",
                            field="env",
                        )
                    )

        return errors, warnings, info_data

    def _validate_tasks(self, tasklist_path: Path) -> tuple[list[ValidationIssue], list[ValidationIssue], list | None]:
        """Validate tasks.json file.

        Returns:
            Tuple of (errors, warnings, parsed_data).
        """
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []
        tasks_file = tasklist_path / "tasks.json"

        if not tasks_file.exists():
            errors.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    message="Missing tasks.json",
                    path="tasks.json",
                )
            )
            return errors, warnings, None

        try:
            tasks_data = json.loads(tasks_file.read_text())
        except json.JSONDecodeError as e:
            errors.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    message=f"Invalid JSON: {e}",
                    path="tasks.json",
                )
            )
            return errors, warnings, None

        if not isinstance(tasks_data, list):
            errors.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    message="tasks.json must be a JSON array",
                    path="tasks.json",
                )
            )
            return errors, warnings, None

        if len(tasks_data) == 0:
            warnings.append(
                ValidationIssue(
                    severity=Severity.WARNING,
                    message="tasks.json is empty",
                    path="tasks.json",
                )
            )

        # Validate each task
        seen_ids: set[str] = set()
        for i, task in enumerate(tasks_data):
            if not isinstance(task, dict):
                errors.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        message=f"Task {i} is not an object",
                        path="tasks.json",
                    )
                )
                continue

            # Check for id
            task_id = task.get("id")
            if not task_id:
                errors.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        message=f"Task {i} missing 'id' field",
                        path="tasks.json",
                    )
                )
            elif task_id in seen_ids:
                errors.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        message=f"Duplicate task id: {task_id}",
                        path="tasks.json",
                    )
                )
            else:
                seen_ids.add(task_id)

            # Check for objective
            if "objective" not in task:
                errors.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        message=f"Task {task_id or i} missing 'objective' field",
                        path="tasks.json",
                    )
                )
            else:
                # Check objective type
                objective = task.get("objective")
                if objective is not None and not isinstance(objective, (str, dict)):
                    errors.append(
                        ValidationIssue(
                            severity=Severity.ERROR,
                            message=f"Task {task_id or i} 'objective' must be string or dict, got {type(objective).__name__}",
                            path="tasks.json",
                        )
                    )

        return errors, warnings, tasks_data

    def _validate_cross(
        self,
        tasklist_path: Path,
        info_data: dict,
        tasks_data: list,
    ) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
        """Cross-validate info.json and tasks.json.

        Returns:
            Tuple of (errors, warnings).
        """
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []

        # Validate objective_template compatibility with task objectives
        objective_template = info_data.get("objective_template", "{{objective}}")
        # Skip if template is invalid type (already reported in _validate_info)
        if not isinstance(objective_template, str):
            objective_template = "{{objective}}"
        required_placeholders = set(re.findall(r"\{\{(\w+)\}\}", objective_template))

        for i, task in enumerate(tasks_data):
            task_id = task.get("id", str(i))
            objective = task.get("objective")
            if objective is None:
                continue  # Already reported in _validate_tasks

            # Determine available placeholders
            if isinstance(objective, str):
                available = {"objective"}
            elif isinstance(objective, dict):
                available = set(objective.keys())
            else:
                continue  # Invalid type already reported

            # Check for missing placeholders
            missing = required_placeholders - available
            if missing:
                errors.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        message=f"Task {task_id} objective missing required placeholder(s): {', '.join(sorted(missing))}",
                        path="tasks.json",
                        field=f"task[{task_id}].objective",
                    )
                )

        task_type = info_data.get("task_type")

        # Task-type specific validation
        if task_type == "QA":
            for i, task in enumerate(tasks_data):
                if "expected" not in task:
                    errors.append(
                        ValidationIssue(
                            severity=Severity.ERROR,
                            message=f"QA task {task.get('id', i)} missing 'expected' field",
                            path="tasks.json",
                        )
                    )

        elif task_type == "Classification":
            # Check for labels in info or tasks
            if "labels" not in info_data:
                has_labels_in_tasks = all("expected" in task for task in tasks_data)
                if not has_labels_in_tasks:
                    warnings.append(
                        ValidationIssue(
                            severity=Severity.WARNING,
                            message="Classification tasks should have 'labels' in info.json or 'expected' in each task",
                            path="info.json",
                            field="labels",
                        )
                    )

        return errors, warnings

    def _validate_file_references(
        self,
        tasklist_path: Path,
        tasks_data: list,
    ) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
        """Validate that file references (attachments) exist.

        Returns:
            Tuple of (errors, warnings).
        """
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []

        for task in tasks_data:
            attachments = task.get("attachment") or task.get("attachments")
            if not attachments:
                continue

            # Normalize to list
            if isinstance(attachments, str):
                attachments = [attachments]

            for attachment in attachments:
                if isinstance(attachment, dict):
                    # Handle structured attachments
                    path = attachment.get("path") or attachment.get("file")
                else:
                    path = attachment

                if not path:
                    continue

                # Skip URLs
                if path.startswith("http://") or path.startswith("https://"):
                    continue

                # Check file exists
                full_path = tasklist_path / path
                if not full_path.exists():
                    errors.append(
                        ValidationIssue(
                            severity=Severity.ERROR,
                            message=f"Referenced file does not exist: {path}",
                            path="tasks.json",
                            field=f"task[{task.get('id', '?')}].attachment",
                        )
                    )

        return errors, warnings
