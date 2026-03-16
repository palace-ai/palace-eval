"""Configurable Report Generation task type."""

import os
import re
from typing import TYPE_CHECKING

from palace.judge import Judge
from palace.task_types.base import TaskType, TaskVerificationResult
from palace.utils.printing import print

JUDGE_MODEL = os.getenv("JUDGE_MODEL", "minimax-m2")

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

DEFAULT_MAX_CRITERIA_PER_BATCH = 10


def _flatten_dimensions(
    dimensions: list[dict],
) -> tuple[list[dict], dict[str, list[str]]]:
    """Flatten hierarchical dimensions to flat criteria list.

    Returns:
        (flat_criteria, dimension_map) where dimension_map tracks criteria per dimension
    """
    flat = []
    dimension_map: dict[str, list[str]] = {}
    for dim in dimensions:
        dim_name = dim["name"]
        dim_weight = dim.get("weight", 1.0)
        dimension_map[dim_name] = []
        for c in dim.get("criteria", []):
            flat.append(
                {
                    "name": c["name"],
                    "description": c["description"],
                    "weight": dim_weight * c.get("weight", 1.0),
                    "_dimension": dim_name,
                }
            )
            dimension_map[dim_name].append(c["name"])
    return flat, dimension_map


def _create_batches(criteria: list[dict], max_per_batch: int) -> list[list[dict]]:
    """Create batches of criteria, grouping by dimension when possible."""
    by_dim: dict[str, list[dict]] = {}
    no_dim: list[dict] = []
    for c in criteria:
        dim = c.get("_dimension")
        if dim:
            by_dim.setdefault(dim, []).append(c)
        else:
            no_dim.append(c)

    batches = []
    for dim_criteria in by_dim.values():
        for i in range(0, len(dim_criteria), max_per_batch):
            batches.append(dim_criteria[i : i + max_per_batch])
    for i in range(0, len(no_dim), max_per_batch):
        batches.append(no_dim[i : i + max_per_batch])

    return batches if batches else [criteria]


class ReportGenerationTaskType(TaskType):
    """Configurable report generation evaluation using pairwise comparison.

    Supports flat criteria or hierarchical dimensions with nested criteria.
    Evaluates in batches to handle large numbers of criteria.
    """

    def adapt_prompt(self, task: "Task") -> str:
        return f"Generate a detailed report based on the following prompt:\n\n{task.objective}"

    def _get_criteria(
        self, task: "Task"
    ) -> tuple[list[dict], dict[str, list[str]] | None]:
        """Get criteria from task_type_fields or use defaults.

        Returns:
            (criteria_list, dimension_map) - dimension_map is None for flat format
        """
        task_type_fields = task.custom_fields.get("task_type_fields", {})

        # Hierarchical format: dimensions with nested criteria
        if "dimensions" in task_type_fields:
            base_dims = task_type_fields["dimensions"]
            if task_type_fields.get("per_task_criteria", False):
                task_dims = task.custom_fields.get("dimensions", [])
                # Merge: task dimensions override by name, add new ones
                merged = {d["name"]: d for d in base_dims}
                for d in task_dims:
                    merged[d["name"]] = d
                base_dims = list(merged.values())
            return _flatten_dimensions(base_dims)

        # Flat format: simple criteria list
        tasklist_criteria = task_type_fields.get("criteria", DEFAULT_CRITERIA)
        if not task_type_fields.get("per_task_criteria", False):
            return tasklist_criteria, None

        # Merge: task criteria override by name, add new ones
        task_criteria = task.custom_fields.get("criteria", [])
        merged_criteria = {c["name"]: c for c in tasklist_criteria}
        for c in task_criteria:
            merged_criteria[c["name"]] = c
        return list(merged_criteria.values()), None

    def _build_judge_prompt(self, criteria: list[dict]) -> str:
        """Generate judge prompt dynamically from criteria list."""
        criteria_list = "\n".join(
            f"{i + 1}. *{c['name']}*: {c['description']}"
            for i, c in enumerate(criteria)
        )

        output_template = "\n\n".join(
            f"""<{c["name"]}>
<discussion>
Discussion on advantages and disadvantages, explaining why you prefer one report over the other.
</discussion>
<best>
Either "A" or "B".
</best>
<gap>
An integer on a scale 0 to 5, where 0 indicates that both reports have similar quality and 5 is the maximum difference in quality.
</gap>
</{c["name"]}>"""
            for c in criteria
        )

        return f"""You are an expert evaluator for reports to a research question.

You'll be comparing two reports: report_a and report_b, evaluating them on the following criteria:
{criteria_list}

For each criterion, you will provide:
1. A discussion comparing advantages and disadvantages of each report
2. Your decision on which report is better ("A" or "B")
3. A gap score (0-5) indicating the difference in quality

Structure your output exactly as follows:
-----
{output_template}
-----

Be fair and objective in your evaluation. Do not be biased towards either report A or B.
The length of a report is not necessarily an indicator of quality - focus on the substance and how well it meets the user's needs."""

    def _judge_batch(
        self, batch: list[dict], prompt_AB: str, prompt_BA: str
    ) -> tuple[dict, dict]:
        """Run judge on a batch of criteria, return keyword values for AB and BA."""
        judge_prompt = self._build_judge_prompt(batch)
        # Nested format: {criterion_name: [inner_tags]}
        output_keywords = {c["name"]: ["discussion", "best", "gap"] for c in batch}
        verifier = Judge(
            judge_model=JUDGE_MODEL,
            judge_prompt=judge_prompt,
            output_keywords=output_keywords,
        )
        return verifier.judge(prompt_AB), verifier.judge(prompt_BA)

    def verify(self, task: "Task", answer: str) -> TaskVerificationResult:
        """Verify using configurable criteria with pairwise comparison."""
        criteria, dimension_map = self._get_criteria(task)
        task_type_fields = task.custom_fields.get("task_type_fields", {})
        max_per_batch = task_type_fields.get(
            "max_criteria_per_batch", DEFAULT_MAX_CRITERIA_PER_BATCH
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

        # Evaluate in batches
        batches = _create_batches(criteria, max_per_batch)
        keyword_values_AB = {}
        keyword_values_BA = {}
        for i, batch in enumerate(batches):
            if len(batches) > 1:
                print(
                    f"  Judging criteria batch {i + 1}/{len(batches)} ({len(batch)} criteria)..."
                )
            ab, ba = self._judge_batch(batch, prompt_AB, prompt_BA)
            keyword_values_AB.update(ab)
            keyword_values_BA.update(ba)

        # Calculate weighted scores
        score_expected, score_provided = 0.0, 0.0
        criteria_scores = {}

        for c in criteria:
            name = c["name"]
            weight = c.get("weight", 1.0)
            ab = keyword_values_AB[name]
            ba = keyword_values_BA[name]

            # AB comparison
            if ab["best"] == "A":
                score_expected += int(ab["gap"]) * weight
            elif ab["best"] == "B":
                score_provided += int(ab["gap"]) * weight
            else:
                raise ValueError(
                    f"Invalid best report value for criterion '{name}': {ab['best']}. Must be 'A' or 'B'."
                )

            # BA comparison (swapped)
            if ba["best"] == "A":
                score_provided += int(ba["gap"]) * weight
            elif ba["best"] == "B":
                score_expected += int(ba["gap"]) * weight
            else:
                raise ValueError(
                    f"Invalid best report value for criterion '{name}': {ba['best']}. Must be 'A' or 'B'."
                )

            # Per-criterion score for metrics
            coef_AB = 1 if ab["best"] == "B" else -1
            coef_BA = 1 if ba["best"] == "A" else -1
            criteria_scores[name] = coef_AB * int(ab["gap"]) + coef_BA * int(ba["gap"])

        # Build reasoning string with per-criterion sections
        def replace_report_names(text: str, provided_is_a: bool) -> str:
            """Replace 'Report A/B' with 'Provided/Expected'."""
            if provided_is_a:
                text = re.sub(r"[Rr]eport\s*A", "Provided", text)
                text = re.sub(r"[Rr]eport\s*B", "Expected", text)
            else:
                text = re.sub(r"[Rr]eport\s*A", "Expected", text)
                text = re.sub(r"[Rr]eport\s*B", "Provided", text)
            return text

        reasoning_parts = []
        for c in criteria:
            name = c["name"]
            score = criteria_scores[name]
            sign = "+" if score > 0 else ""

            # Combine discussions from both comparisons
            disc_ab = replace_report_names(
                keyword_values_AB[name]["discussion"], provided_is_a=False
            )
            disc_ba = replace_report_names(
                keyword_values_BA[name]["discussion"], provided_is_a=True
            )

            reasoning_parts.append(f"## {name} ({sign}{score})\n{disc_ab}\n\n{disc_ba}")

        reasoning = "\n\n".join(reasoning_parts)

        # Summary section
        overall_gap = score_provided - score_expected
        max_score = sum(c.get("weight", 1.0) for c in criteria) * 10
        normalized_score = (
            (overall_gap + max_score) / (2 * max_score) if max_score > 0 else 0.5
        )

        reasoning += "\n\n## Summary\n"
        reasoning += (
            "Scores per criterion (positive = provided better, range -10 to +10):\n"
        )
        for name, score in criteria_scores.items():
            sign = "+" if score > 0 else ""
            reasoning += f"  {name}: {sign}{score}\n"
        reasoning += f"\nOverall: {overall_gap:+.1f} (range {-max_score:.0f} to +{max_score:.0f})"
        reasoning += f"\nNormalized: {normalized_score:.2f} (0=worst, 0.5=tie, 1=best)"

        # Build metrics
        metrics: dict = {
            "criteria_scores": criteria_scores,
            "overall_gap": overall_gap,
            "score_provided": score_provided,
            "score_expected": score_expected,
            "normalized_score": normalized_score,
        }

        # Add dimension scores if hierarchical
        if dimension_map:
            dimension_scores = {}
            for dim_name, crit_names in dimension_map.items():
                dim_total = sum(criteria_scores.get(cn, 0) for cn in crit_names)
                dimension_scores[dim_name] = dim_total
            metrics["dimension_scores"] = dimension_scores

        return TaskVerificationResult(
            is_correct=score_provided > score_expected,
            reasoning=reasoning,
            metrics=metrics,
        )
