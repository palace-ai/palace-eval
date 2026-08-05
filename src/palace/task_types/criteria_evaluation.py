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

"""Criteria Evaluation task type — pairwise comparison or absolute rubric scoring."""

import re
from typing import Any

from palace.judge import Judge
from palace.task_types.base import ExecutionEnvironment, Task, TaskVerificationResult
from palace.utils.constants import get_judge_model
from palace.utils.printing import print

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


class CriteriaEvaluationTask(Task):
    """Criteria-based evaluation with pairwise comparison or absolute rubric scoring.

    Modes:
    - "pairwise" (default): Compares model output vs reference using criteria.
    - "absolute": Evaluates each criterion independently (met/not met) without reference.
    """

    @classmethod
    def aggregate(cls, results: list["TaskVerificationResult"], penalize_unsupported: bool = False) -> dict[str, Any]:
        """Compute avg_normalized_score and per-dimension/criteria averages."""
        results = [r for r in results if not r.is_skipped]
        base = super().aggregate(results, penalize_unsupported=penalize_unsupported)
        if not results:
            return base

        # avg_normalized_score
        scores = [r.metrics["normalized_score"] for r in results if "normalized_score" in r.metrics]
        if scores:
            base["avg_normalized_score"] = round(sum(scores) / len(scores), 4)

        # per-dimension averages
        dim_totals: dict[str, list[float]] = {}
        for r in results:
            for dim, score in r.metrics.get("dimension_scores", {}).items():
                dim_totals.setdefault(dim, []).append(score)
        if dim_totals:
            base["per_dimension_avg"] = {d: round(sum(v) / len(v), 4) for d, v in dim_totals.items()}

        # per-criteria averages (handle both flat and nested formats)
        crit_totals: dict[tuple[str | None, str], list[float]] = {}
        for r in results:
            for key, val in r.metrics.get("criteria_scores", {}).items():
                if isinstance(val, dict):
                    for crit, score in val.items():
                        crit_totals.setdefault((key, crit), []).append(score)
                else:
                    crit_totals.setdefault((None, key), []).append(val)
        if crit_totals:
            grouped: dict[str, dict[str, float]] = {}
            flat: dict[str, float] = {}
            for (dim, crit), vals in crit_totals.items():
                avg = round(sum(vals) / len(vals), 4)
                if dim:
                    grouped.setdefault(dim, {})[crit] = avg
                else:
                    flat[crit] = avg
            base["per_criteria_avg"] = grouped if grouped else flat

        return base

    def adapt_prompt(self) -> str:
        return self.objective

    def _get_criteria(self) -> tuple[list[dict], dict[str, list[str]] | None]:
        """Get criteria from task_type_fields or use defaults.

        Returns:
            (criteria_list, dimension_map) - dimension_map is None for flat format
        """
        task_type_fields = self.custom_fields.get("task_type_fields", {})

        # Hierarchical format: dimensions with nested criteria
        if "dimensions" in task_type_fields:
            base_dims = task_type_fields["dimensions"]
            if task_type_fields.get("per_task_criteria", False):
                task_dims = self.custom_fields.get("dimensions", [])
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
        task_criteria = self.custom_fields.get("criteria", [])
        merged_criteria = {c["name"]: c for c in tasklist_criteria}
        for c in task_criteria:
            merged_criteria[c["name"]] = c
        return list(merged_criteria.values()), None

    def _build_judge_prompt(self, criteria: list[dict]) -> str:
        """Generate judge prompt dynamically from criteria list."""
        criteria_list = "\n".join(f"{i + 1}. *{c['name']}*: {c['description']}" for i, c in enumerate(criteria))

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

    async def _judge_batch(self, batch: list[dict], prompt_AB: str, prompt_BA: str) -> tuple[dict, dict]:
        """Run judge on a batch of criteria, return keyword values for AB and BA."""
        judge_prompt = self._build_judge_prompt(batch)
        # Nested format: {criterion_name: [inner_tags]}
        output_keywords = {c["name"]: ["discussion", "best", "gap"] for c in batch}
        verifier = Judge(
            judge_model=get_judge_model(),
            judge_prompt=judge_prompt,
            output_keywords=output_keywords,
        )
        return await verifier.judge(prompt_AB), await verifier.judge(prompt_BA)

    async def verify(self, answer: str, env: ExecutionEnvironment | None = None) -> TaskVerificationResult:
        """Verify using criteria — dispatches to pairwise or absolute mode."""
        if not answer or not answer.strip():
            return TaskVerificationResult(
                is_correct=False,
                reasoning="Agent did not provide a response.",
                metrics={"normalized_score": 0.0},
            )

        mode = self.custom_fields.get("task_type_fields", {}).get("mode", "pairwise")
        if mode == "absolute":
            return await self._verify_absolute(answer)
        return await self._verify_pairwise(answer)

    async def _verify_absolute(self, answer: str) -> TaskVerificationResult:
        """Absolute mode: evaluate each criterion independently (met/not met)."""
        try:
            criteria = self.custom_fields.get("task_type_fields", {}).get("criteria", [])
            if not criteria:
                criteria = self.custom_fields.get("criteria", [])
            if not criteria:
                return TaskVerificationResult(
                    is_correct=False, reasoning="No criteria defined", metrics={"normalized_score": 0.0}
                )

            task_type_fields = self.custom_fields.get("task_type_fields", {})
            max_per_batch = task_type_fields.get("max_criteria_per_batch", DEFAULT_MAX_CRITERIA_PER_BATCH)

            # Evaluate criteria in batches
            all_results: dict[str, bool] = {}
            batches = [criteria[i : i + max_per_batch] for i in range(0, len(criteria), max_per_batch)]
            for i, batch in enumerate(batches):
                if len(batches) > 1:
                    print(f"  Judging criteria batch {i + 1}/{len(batches)} ({len(batch)} criteria)...")
                batch_results = await self._judge_absolute_batch(batch, answer)
                all_results.update(batch_results)

            # Score: earned points / max possible points
            earned = 0.0
            max_positive = 0.0
            criteria_met: dict[str, dict] = {}
            for c in criteria:
                name = c["name"]
                points = c.get("points", 1.0)
                met = all_results.get(name, False)
                criteria_met[name] = {"met": met, "points": points}
                if points > 0:
                    max_positive += points
                    if met:
                        earned += points
                else:
                    # Negative points: penalty if criterion IS met (bad behavior detected)
                    if met:
                        earned += points  # subtracts

            score = max(0.0, min(1.0, earned / max_positive)) if max_positive > 0 else 0.0

            # Build reasoning
            reasoning_parts = []
            for c in criteria:
                name = c["name"]
                info = criteria_met[name]
                icon = "✓" if info["met"] else "✗"
                sign = "+" if info["points"] > 0 else ""
                reasoning_parts.append(f"{icon} {name} ({sign}{info['points']}pts): {c.get('description', '')[:100]}")
            reasoning = "\n".join(reasoning_parts)
            reasoning += f"\n\nScore: {earned:.1f}/{max_positive:.1f} = {score:.2f}"

            # Build metrics with dimension grouping
            metrics: dict[str, Any] = {
                "normalized_score": round(score, 4),
                "earned_points": earned,
                "max_points": max_positive,
            }
            dimension_scores: dict[str, list[float]] = {}
            for c in criteria:
                dim = c.get("dimension")
                if dim:
                    met = all_results.get(c["name"], False)
                    dimension_scores.setdefault(dim, []).append(1.0 if met else 0.0)
            if dimension_scores:
                metrics["dimension_scores"] = {d: round(sum(v) / len(v), 4) for d, v in dimension_scores.items()}

            return TaskVerificationResult(
                is_correct=score >= 0.5,
                reasoning=reasoning,
                metrics=metrics,
            )
        except Exception as e:
            return TaskVerificationResult(
                is_correct=False,
                reasoning=f"Verification failed: {e}",
                metrics={"normalized_score": 0.0},
            )

    async def _judge_absolute_batch(self, batch: list[dict], answer: str) -> dict[str, bool]:
        """Judge a batch of criteria in absolute mode. Returns {name: met}."""
        criteria_list = "\n".join(f"{i + 1}. *{c['name']}*: {c['description']}" for i, c in enumerate(batch))
        output_template = "\n\n".join(f"<{c['name']}>\n<met>YES or NO</met>\n</{c['name']}>" for c in batch)

        judge_prompt = f"""You are an expert evaluator. Given a response to a question, evaluate whether each criterion is satisfied.

For each criterion, answer YES if the response satisfies it, or NO if it does not.

Criteria:
{criteria_list}

Structure your output exactly as follows:
-----
{output_template}
-----"""

        content = f"QUESTION\n{self.objective}\n\nRESPONSE\n{answer}"
        output_keywords = {c["name"]: ["met"] for c in batch}
        verifier = Judge(
            judge_model=get_judge_model(),
            judge_prompt=judge_prompt,
            output_keywords=output_keywords,
        )
        result = await verifier.judge(content)
        return {c["name"]: result.get(c["name"], {}).get("met", "").strip().upper().startswith("Y") for c in batch}

    async def _verify_pairwise(self, answer: str) -> TaskVerificationResult:
        """Pairwise mode: compare model output vs reference using criteria."""

        try:
            criteria, dimension_map = self._get_criteria()
            task_type_fields = self.custom_fields.get("task_type_fields", {})
            max_per_batch = task_type_fields.get("max_criteria_per_batch", DEFAULT_MAX_CRITERIA_PER_BATCH)

            prompt_AB = f"""
    QUESTION
    {self.objective}

    REPORT A
    {self.expected}

    REPORT B
    {answer}
    """
            prompt_BA = f"""
    QUESTION
    {self.objective}

    REPORT A
    {answer}

    REPORT B
    {self.expected}
    """

            # Evaluate in batches
            batches = _create_batches(criteria, max_per_batch)
            keyword_values_AB = {}
            keyword_values_BA = {}
            for i, batch in enumerate(batches):
                if len(batches) > 1:
                    print(f"  Judging criteria batch {i + 1}/{len(batches)} ({len(batch)} criteria)...")
                ab, ba = await self._judge_batch(batch, prompt_AB, prompt_BA)
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

                ab_best = ab["best"].strip().upper()[:1]
                ba_best = ba["best"].strip().upper()[:1]

                if ab_best not in ("A", "B") or ba_best not in ("A", "B"):
                    return TaskVerificationResult(
                        is_correct=False,
                        reasoning=f"Judge returned invalid comparison for '{name}': AB={ab['best']}, BA={ba['best']}. Skipping task.",
                        metrics={"normalized_score": 0.0, "skipped": True},
                    )

                # AB comparison
                if ab_best == "A":
                    score_expected += int(ab["gap"]) * weight
                else:
                    score_provided += int(ab["gap"]) * weight

                # BA comparison (swapped)
                if ba_best == "A":
                    score_provided += int(ba["gap"]) * weight
                else:
                    score_expected += int(ba["gap"]) * weight

                # Per-criterion score for metrics
                coef_AB = 1 if ab_best == "B" else -1
                coef_BA = 1 if ba_best == "A" else -1
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
                disc_ab = replace_report_names(keyword_values_AB[name]["discussion"], provided_is_a=False)
                disc_ba = replace_report_names(keyword_values_BA[name]["discussion"], provided_is_a=True)

                reasoning_parts.append(f"## {name} ({sign}{score})\n{disc_ab}\n\n{disc_ba}")

            reasoning = "\n\n".join(reasoning_parts)

            # Summary section
            overall_gap = score_provided - score_expected
            max_score = sum(c.get("weight", 1.0) for c in criteria) * 10
            normalized_score = (overall_gap + max_score) / (2 * max_score) if max_score > 0 else 0.5

            reasoning += "\n\n## Summary\n"
            reasoning += "Scores per criterion (positive = provided better, range -10 to +10):\n"
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

            # Add dimension scores and nest criteria if hierarchical
            if dimension_map:
                dimension_scores = {}
                for dim_name, crit_names in dimension_map.items():
                    if crit_names:
                        dim_vals = [criteria_scores.get(cn, 0) for cn in crit_names]
                        dimension_scores[dim_name] = sum(dim_vals) / len(dim_vals)
                metrics["dimension_scores"] = dimension_scores
                metrics["criteria_scores"] = {
                    dim: {cn: criteria_scores[cn] for cn in cns} for dim, cns in dimension_map.items() if cns
                }

            return TaskVerificationResult(
                is_correct=score_provided > score_expected,
                reasoning=reasoning,
                metrics=metrics,
            )

        except Exception as e:
            return TaskVerificationResult(
                is_correct=False,
                reasoning=f"Verification failed: {e}",
                metrics={"normalized_score": 0.0},
            )
