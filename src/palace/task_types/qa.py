"""Configurable QA task type with LLM judge verification."""

from palace.judge import Judge
from palace.task_types.base import ExecutionEnvironment, Task, TaskVerificationResult
from palace.utils.constants import JUDGE_MODEL

DEFAULT_CORRECTNESS_CRITERION = {
    "name": "semantic equivalence",
    "description": "The answer conveys the same factual meaning as the reference.",
}
DEFAULT_REFERENCES = {"correct": ["expected"], "incorrect": []}


class QATask(Task):
    """Configurable QA task type with LLM judge verification."""

    def adapt_prompt(self) -> str:
        return f"Provide the direct answer, without any additional text:\n\n{self.objective}"

    def _get_config(self) -> tuple[dict, dict]:
        """Get correctness_criterion and references from config or defaults."""
        task_type_fields = self.custom_fields.get("task_type_fields", {})
        criterion = task_type_fields.get("correctness_criterion", DEFAULT_CORRECTNESS_CRITERION)
        references = task_type_fields.get("references", DEFAULT_REFERENCES)
        return criterion, references

    def _get_reference_value(self, field_name: str) -> str | None:
        """Get reference value from task by field name."""
        if field_name == "expected":
            return self.expected
        return self.custom_fields.get(field_name)

    def _build_judge_prompt(self, criterion: dict, references: dict, has_incorrect: bool) -> str:
        """Build judge prompt dynamically from configuration."""
        criterion_name = criterion["name"]
        criterion_desc = criterion["description"]

        if has_incorrect:
            return f"""You are evaluating an answer based on the criterion of "{criterion_name}".

Criterion definition: {criterion_desc}

You will be given:
- QUESTION: The original question or prompt
- CORRECT REFERENCE(S): Example(s) of answers that satisfy the criterion
- INCORRECT REFERENCE(S): Example(s) of answers that do NOT satisfy the criterion
- PROVIDED ANSWER: The answer to evaluate

Your job is to determine whether the provided answer aligns more with the CORRECT or INCORRECT references based on the criterion above.

Your output must follow this format:

<reasoning>
Your observations and reasoning about whether the provided answer satisfies the criterion of {criterion_name}. Compare it to both correct and incorrect references. Be detailed.
</reasoning>

<judgement>
Either Correct or Incorrect. No other text can be here.
</judgement>"""
        else:
            return f"""You are evaluating an answer based on the criterion of "{criterion_name}".

Criterion definition: {criterion_desc}

You will be given:
- QUESTION: The original question or prompt
- CORRECT REFERENCE(S): The reference answer(s) to compare against
- PROVIDED ANSWER: The answer to evaluate

Your job is to assess whether the provided answer satisfies the criterion when compared to the reference(s).

Your output must follow this format:

<reasoning>
Your observations and reasoning about why the provided answer might or might not satisfy the criterion. Be detailed.
</reasoning>

<judgement>
Either Correct or Incorrect. No other text can be here.
</judgement>"""

    def _build_judge_input(self, answer: str, references: dict) -> str:
        """Build the input for the judge from task and references."""
        parts = [f"QUESTION\n{self.objective}"]

        correct_fields = references.get("correct", ["expected"])
        correct_parts = []
        for field in correct_fields:
            value = self._get_reference_value(field)
            if value:
                correct_parts.append(f"{field}: {value}")
        if correct_parts:
            parts.append(f"CORRECT REFERENCE(S)\n" + "\n".join(correct_parts))

        incorrect_fields = references.get("incorrect", [])
        if incorrect_fields:
            incorrect_parts = []
            for field in incorrect_fields:
                value = self._get_reference_value(field)
                if value:
                    incorrect_parts.append(f"{field}: {value}")
            if incorrect_parts:
                parts.append(f"INCORRECT REFERENCE(S)\n" + "\n".join(incorrect_parts))

        parts.append(f"PROVIDED ANSWER\n{answer}")
        return "\n\n".join(parts)

    def expected_display(self) -> str | None:
        """Derive expected value from first correct reference field."""
        _, references = self._get_config()
        correct_fields = references.get("correct", ["expected"])
        if correct_fields:
            return self._get_reference_value(correct_fields[0])
        return self.expected

    async def verify(self, answer: str, env: ExecutionEnvironment | None = None) -> TaskVerificationResult:
        criterion, references = self._get_config()

        correct_fields = references.get("correct", ["expected"])
        has_correct = any(self._get_reference_value(f) for f in correct_fields)
        if not has_correct:
            raise ValueError(f"Cannot verify QA task without at least one correct reference. Fields checked: {correct_fields}")

        incorrect_fields = references.get("incorrect", [])
        has_incorrect = bool(incorrect_fields) and any(self._get_reference_value(f) for f in incorrect_fields)

        judge_prompt = self._build_judge_prompt(criterion, references, has_incorrect)
        judge_input = self._build_judge_input(answer, references)

        verifier = Judge(judge_model=JUDGE_MODEL, judge_prompt=judge_prompt)
        keyword_values = await verifier.judge(judge_input)

        judgement = keyword_values.get("judgement", "").strip()
        if judgement == "Correct":
            is_correct = True
        elif judgement == "Incorrect":
            is_correct = False
        else:
            raise ValueError(f"Judge returned invalid judgement: '{judgement}'. Expected 'Correct' or 'Incorrect'.")

        return TaskVerificationResult(
            is_correct=is_correct,
            reasoning=keyword_values.get("reasoning"),
            metrics={"criterion": criterion["name"]},
        )
