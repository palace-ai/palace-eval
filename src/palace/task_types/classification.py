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

"""Classification task type for categorical outputs with exact-match verification."""

import re
from typing import Any

from palace.task_types.base import ExecutionEnvironment, Task, TaskVerificationResult


class ClassificationTask(Task):
    """Classification task type for categorical outputs with exact-match verification."""

    @classmethod
    def aggregate(cls, results: list["TaskVerificationResult"], penalize_unsupported: bool = False) -> dict[str, Any]:
        """Compute classification metrics: per-label P/R/F1/FPR/FNR + macro/micro."""
        results = [r for r in results if not r.is_skipped]
        base = super().aggregate(results, penalize_unsupported=penalize_unsupported)
        if not results:
            return base

        # Collect per-label predictions
        label_data: dict[str, list[dict]] = {}
        for r in results:
            per_label = r.metrics.get("per_label", {})
            for label_name, info in per_label.items():
                label_data.setdefault(label_name, []).append(info)

        if not label_data:
            return base

        per_label_metrics = {}
        total_tp = total_fp = total_tn = total_fn = 0

        for label_name, entries in label_data.items():
            positive = entries[0].get("positive_class") if entries else None
            tp = fp = tn = fn = 0
            for e in entries:
                pred, exp = e.get("predicted"), e.get("expected")
                if pred is None:
                    # Parse failure counts as negative prediction
                    if exp == positive:
                        fn += 1
                    else:
                        tn += 1
                    continue
                if exp == positive:
                    if pred == positive:
                        tp += 1
                    else:
                        fn += 1
                else:
                    if pred == positive:
                        fp += 1
                    else:
                        tn += 1

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
            fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
            fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0

            per_label_metrics[label_name] = {
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
                "fpr": round(fpr, 4),
                "fnr": round(fnr, 4),
                "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
            }
            total_tp += tp
            total_fp += fp
            total_tn += tn
            total_fn += fn

        # Macro averages
        n_labels = len(per_label_metrics)
        macro = {}
        for key in ("precision", "recall", "f1", "fpr", "fnr"):
            macro[key] = round(sum(m[key] for m in per_label_metrics.values()) / n_labels, 4)

        # Micro averages
        micro_p = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
        micro_r = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
        micro_f1 = 2 * micro_p * micro_r / (micro_p + micro_r) if (micro_p + micro_r) > 0 else 0.0
        micro_fpr = total_fp / (total_fp + total_tn) if (total_fp + total_tn) > 0 else 0.0
        micro_fnr = total_fn / (total_fn + total_tp) if (total_fn + total_tp) > 0 else 0.0
        micro = {
            "precision": round(micro_p, 4),
            "recall": round(micro_r, 4),
            "f1": round(micro_f1, 4),
            "fpr": round(micro_fpr, 4),
            "fnr": round(micro_fnr, 4),
        }

        base["per_label"] = per_label_metrics
        base["macro"] = macro
        base["micro"] = micro
        return base

    def adapt_prompt(self) -> str:
        labels = self.custom_fields.get("task_type_fields", {}).get("labels", [])

        return f"""
You have to perform a classification task.
Consider the following text:
-----
{self.objective}
-----

And consider the following label(s) and relative description:
{"\n".join([f"- {label['name']}: {label['description']}" for label in labels])}

Your goal is to associate a class to the label(s), matching this format exactly:
-----
{"\n\n".join([f"<{label['name']}>\nEither {', or '.join(f'"{c["name"]}" ({c["condition"]})' for c in label['classes'])}\n</{label['name']}>" for label in labels])}
-----
        """.strip()

    def expected_display(self) -> str | None:
        """Return labels dict as formatted string for display."""
        labels = self.custom_fields.get("labels", {})
        if labels:
            return ", ".join(f"{k}: {v}" for k, v in labels.items())
        return None

    async def verify(self, answer: str, env: ExecutionEnvironment | None = None, **kwargs) -> TaskVerificationResult:
        labels = self.custom_fields.get("task_type_fields", {}).get("labels", [])
        per_label = {}
        for label in labels:
            matches = re.findall(f"<{label['name']}>((?:.|\n)*?)</{label['name']}>", answer)
            pred = matches[0].strip() if matches and len(matches) == 1 else None
            expected = self.custom_fields.get("labels", {}).get(label["name"])
            per_label[label["name"]] = {
                "predicted": pred,
                "expected": expected,
                "correct": pred == expected,
                "positive_class": label["classes"][0]["name"] if label.get("classes") else None,
            }

        is_correct = all(v["correct"] for v in per_label.values())
        return TaskVerificationResult(
            is_correct=is_correct,
            reasoning=f"Label-wise correctness\n{'\n'.join([f'{":check_mark_button:" if v["correct"] else ":cross_mark:"} {k}' for k, v in per_label.items()])}",
            metrics={"per_label": per_label},
        )
