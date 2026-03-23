"""Classification task type for categorical outputs with exact-match verification."""

import re
from typing import TYPE_CHECKING

from palace.task_types.base import TaskType, TaskVerificationResult

if TYPE_CHECKING:
    from palace.task_types.base import Task


class ClassificationTaskType(TaskType):
    """Classification task type for categorical outputs with exact-match verification."""

    def adapt_prompt(self, task: "Task") -> str:
        labels = task.custom_fields.get("task_type_fields", {}).get("labels", [])

        return f"""
You have to perform a classification task.
Consider the following text:
-----
{task.objective}
-----

And consider the following label(s) and relative description:
{"\n".join([f"- {label['name']}: {label['description']}" for label in labels])}

Your goal is to associate a class to the label(s), matching this format exactly:
-----
{"\n\n".join([f"<{label['name']}>\nEither {', or '.join(f'"{c["name"]}" ({c["condition"]})' for c in label['classes'])}\n</{label['name']}>" for label in labels])}
-----
        """.strip()

    def expected_display(self, task: "Task") -> str | None:
        """Return labels dict as formatted string for display."""
        labels = task.custom_fields.get("labels", {})
        if labels:
            return ", ".join(f"{k}: {v}" for k, v in labels.items())
        return None

    def verify(self, task: "Task", answer: str) -> TaskVerificationResult:
        labels = task.custom_fields.get("task_type_fields", {}).get("labels", [])
        correct_labels = {label["name"]: False for label in labels}
        for label in labels:
            matches = re.findall(
                f"<{label['name']}>((?:.|\n)*?)</{label['name']}>", answer
            )
            if matches is None or len(matches) != 1:
                continue
            pred = matches[0].strip()
            true = task.custom_fields.get("labels", {}).get(label["name"], [])
            if pred == true:
                correct_labels[label["name"]] = True

        is_correct = all(correct_labels.values())
        return TaskVerificationResult(
            is_correct=is_correct,
            reasoning=f"Label-wise correctness\n{'\n'.join([f'{':check_mark_button:' if v else ':cross_mark:'} {k}' for k, v in correct_labels.items()])}",
            metrics={"per_label_correct": correct_labels},
        )
