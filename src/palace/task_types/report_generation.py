"""Configurable Report Generation task type."""

import re
from typing import TYPE_CHECKING

from palace.judge import Judge
from palace.task_types.base import TaskType, TaskVerificationResult

if TYPE_CHECKING:
    from palace.task_types.base import Task

DEFAULT_CRITERIA = [
    {
        "name": "instruction_following",
        "description": "Evaluates response's fidelity to user specified instructions and constraints.",
        "weight": 1.0,
    },
    {
        "name": "comprehensiveness",
        "description": "Measures breadth and range of information covered in response, addressing the scope of user request.",
        "weight": 1.0,
    },
    {
        "name": "completeness",
        "description": "Measures the depth and thoroughness of information for topics addressed in the report.",
        "weight": 1.0,
    },
    {
        "name": "writing_quality",
        "description": "Evaluates clarity, conciseness, logical organization and overall readability of the report.",
        "weight": 1.0,
    },
]


class ReportGenerationTaskType(TaskType):
    """Configurable report generation evaluation using pairwise comparison."""

    def adapt_prompt(self, task: "Task") -> str:
        return f"Generate a detailed report based on the following prompt:\n\n{task.objective}"

    def _get_criteria(self, task: "Task") -> list[dict]:
        """Get criteria from task_type_fields or use defaults."""
        task_type_fields = task.custom_fields.get("task_type_fields", {})
        tasklist_criteria = task_type_fields.get("criteria", DEFAULT_CRITERIA)

        if not task_type_fields.get("per_task_criteria", False):
            return tasklist_criteria

        # Merge: task criteria override by name, add new ones
        task_criteria = task.custom_fields.get("criteria", [])
        merged_criteria = {c["name"]: c for c in tasklist_criteria}
        for c in task_criteria:
            merged_criteria[c["name"]] = c
        return list(merged_criteria.values())

    def _build_judge_prompt(self, criteria: list[dict]) -> str:
        """Generate judge prompt dynamically from criteria list."""
        criteria_list = "\n".join(
            f"{i + 1}. *{c['name']}*: {c['description']}"
            for i, c in enumerate(criteria)
        )

        output_template = "\n\n".join(
            f"""<{c["name"]}>
Discussion on advantages and disadvantages, explaining why you prefer one report over the other.
</{c["name"]}>

<{c["name"]}_best>
Either "A" or "B".
</{c["name"]}_best>

<{c["name"]}_gap_score>
An integer on a scale 0 to 5, where 0 indicates that both reports have similar quality and 5 is the maximum difference in quality.
</{c["name"]}_gap_score>"""
            for c in criteria
        )

        return f"""You are an expert evaluator for reports to a research question.

You'll be comparing two reports: report_a and report_b, evaluating them on the following dimensions:
{criteria_list}

For each dimension, you will indicate 3 things: a comparative discussion about advantages and disadvantages of each report, a decision on which report you prefer ("A" or "B"), and a gap score indicating the difference in quality between the two reports for that dimension.

You have to structure your output matching this template exactly:
-----
{output_template}
-----

Be fair and objective in your evaluation. Do not be biased towards either report A or B.
The length of a report is not necessarily an indicator of quality - focus on the substance and how well it meets the user's needs."""

    def verify(self, task: "Task", answer: str) -> TaskVerificationResult:
        """Verify using configurable criteria with pairwise comparison."""
        criteria = self._get_criteria(task)
        judge_prompt = self._build_judge_prompt(criteria)

        output_keywords = [
            item
            for c in criteria
            for item in [c["name"], f"{c['name']}_best", f"{c['name']}_gap_score"]
        ]
        verifier = Judge(
            judge_model="minimax-m2",
            judge_prompt=judge_prompt,
            output_keywords=output_keywords,
        )

        prompt_AB = f"""
QUESTION
{task.objective}

REPORT A
{task.expected}

REPORT B
{answer}
"""
        prompt_BA = f"""
QUESTION
{task.objective}

REPORT A
{answer}

REPORT B
{task.expected}
"""
        keyword_values_AB = verifier.judge(prompt_AB)
        keyword_values_BA = verifier.judge(prompt_BA)

        # Calculate weighted scores
        score_expected, score_provided = 0.0, 0.0
        criteria_scores = {}

        for c in criteria:
            name = c["name"]
            weight = c.get("weight", 1.0)

            # AB comparison
            if keyword_values_AB[f"{name}_best"] == "A":
                score_expected += int(keyword_values_AB[f"{name}_gap_score"]) * weight
            elif keyword_values_AB[f"{name}_best"] == "B":
                score_provided += int(keyword_values_AB[f"{name}_gap_score"]) * weight
            else:
                raise ValueError(
                    f"Invalid best report value for criterion '{name}': {keyword_values_AB[f'{name}_best']}. Must be 'A' or 'B'."
                )

            # BA comparison (swapped)
            if keyword_values_BA[f"{name}_best"] == "A":
                score_provided += int(keyword_values_BA[f"{name}_gap_score"]) * weight
            elif keyword_values_BA[f"{name}_best"] == "B":
                score_expected += int(keyword_values_BA[f"{name}_gap_score"]) * weight
            else:
                raise ValueError(
                    f"Invalid best report value for criterion '{name}': {keyword_values_BA[f'{name}_best']}. Must be 'A' or 'B'."
                )

            # Per-criterion score for metrics
            coef_AB = 1 if keyword_values_AB[f"{name}_best"] == "B" else -1
            coef_BA = 1 if keyword_values_BA[f"{name}_best"] == "A" else -1
            criteria_scores[name] = coef_AB * int(
                keyword_values_AB[f"{name}_gap_score"]
            ) + coef_BA * int(keyword_values_BA[f"{name}_gap_score"])

        # Build reasoning string
        reasoning_parts = []
        for c in criteria:
            name = c["name"]
            reasoning_parts.append(
                re.sub(
                    r"Report\sA",
                    "Report A (Expected)",
                    re.sub(
                        r"Report\sB",
                        "Report B (Provided)",
                        keyword_values_AB[name],
                    ),
                )
                + "\n"
                + re.sub(
                    r"Report\sB",
                    "Report B (Expected)",
                    re.sub(
                        r"Report\sA",
                        "Report A (Provided)",
                        keyword_values_BA[name],
                    ),
                )
            )

        reasoning = "\n".join(reasoning_parts)
        reasoning += "\n\nScore sheet for provided report (-10 to 10 per criterion):"
        for name, score in criteria_scores.items():
            reasoning += f"\n{name}: {score}"

        overall_gap = score_provided - score_expected
        max_score = sum(c.get("weight", 1.0) for c in criteria) * 10
        reasoning += (
            f"\noverall ({-max_score:.0f} to {max_score:.0f}): {overall_gap:.1f}"
        )

        return TaskVerificationResult(
            is_correct=score_provided > score_expected,
            reasoning=reasoning,
            metrics={
                "criteria_scores": criteria_scores,
                "overall_gap": overall_gap,
                "score_provided": score_provided,
                "score_expected": score_expected,
            },
        )
