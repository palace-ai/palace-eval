"""Instruction Following task type — deterministic constraint verification."""

import json
import re
from typing import Any

from palace.task_types.base import Task, TaskVerificationResult


class InstructionFollowingTask(Task):
    """Verifies responses against syntactic constraints. No LLM judge needed."""

    task_type_name = "Instruction Following"

    def adapt_prompt(self) -> str:
        return self.objective

    async def verify(self, answer: str, env=None) -> TaskVerificationResult:
        constraints = self.custom_fields.get("task_type_fields", {}).get("constraints", [])
        if not constraints:
            return TaskVerificationResult(is_correct=False, reasoning="No constraints defined")

        results = []
        for c in constraints:
            passed = _check_constraint(c["type"], answer, c.get("params", {}), self.objective)
            results.append((c["type"], passed))

        score = sum(1 for _, p in results if p) / len(results)
        reasoning = "\n".join(f"{'✓' if p else '✗'} {t}" for t, p in results)
        return TaskVerificationResult(
            is_correct=score >= 0.5,
            reasoning=reasoning,
            metrics={"score": round(score, 4), "satisfied": sum(p for _, p in results), "total": len(results)},
        )

    @classmethod
    def aggregate(cls, results: list[TaskVerificationResult], penalize_unsupported: bool = False) -> dict[str, Any]:
        evaluated = [r for r in results if not r.is_skipped]
        if not evaluated:
            return {"accuracy": 0, "avg_score": 0}
        scores = [r.metrics.get("score", 0) for r in evaluated]
        correct = sum(1 for r in evaluated if r.is_correct)
        return {
            "accuracy": round(correct / len(evaluated), 4),
            "avg_score": round(sum(scores) / len(scores), 4),
        }


# --- Constraint checkers ---

def _compare(value: float, target: float, relation: str) -> bool:
    """Compare value against target using the specified relation."""
    if relation == "at least":
        return value >= target
    elif relation == "at most":
        return value <= target
    elif relation == "less than":
        return value < target
    elif relation == "more than":
        return value > target
    elif relation == "exactly":
        return value == target
    return value >= target


def _check_constraint(ctype: str, answer: str, params: dict, prompt: str = "") -> bool:
    checker = _CHECKERS.get(ctype)
    if checker is None:
        import logging
        logging.getLogger("palace.instruction_following").warning(f"Unknown constraint type: {ctype}")
        return False
    try:
        return checker(answer, params, prompt)
    except Exception:
        return False


def _check_no_comma(answer: str, params: dict, prompt: str) -> bool:
    return "," not in answer


def _check_number_words(answer: str, params: dict, prompt: str) -> bool:
    count = len(answer.split())
    return _compare(count, params.get("num_words", 0), params.get("relation", "at least"))


def _check_number_sentences(answer: str, params: dict, prompt: str) -> bool:
    count = len([s for s in re.split(r'[.!?]+', answer) if s.strip()])
    return _compare(count, params.get("num_sentences", 0), params.get("relation", "at least"))


def _check_number_paragraphs(answer: str, params: dict, prompt: str) -> bool:
    count = len([p for p in answer.split("\n\n") if p.strip()])
    return _compare(count, params.get("num_paragraphs", 0), params.get("relation", "at least"))


def _check_nth_paragraph_first_word(answer: str, params: dict, prompt: str) -> bool:
    paragraphs = [p for p in answer.split("\n\n") if p.strip()]
    nth = params.get("nth_paragraph", 1)
    if nth > len(paragraphs):
        return False
    first_word = paragraphs[nth - 1].strip().split()[0].lower() if paragraphs[nth - 1].strip() else ""
    return first_word == params.get("first_word", "").lower()


def _check_keywords_existence(answer: str, params: dict, prompt: str) -> bool:
    keywords = params.get("keywords", [])
    lower = answer.lower()
    return all(k.lower() in lower for k in keywords)


def _check_forbidden_words(answer: str, params: dict, prompt: str) -> bool:
    forbidden = params.get("forbidden_words", [])
    lower = answer.lower()
    return all(w.lower() not in lower for w in forbidden)


def _check_keyword_frequency(answer: str, params: dict, prompt: str) -> bool:
    keyword = params.get("keyword", "")
    count = answer.lower().count(keyword.lower())
    return _compare(count, params.get("frequency", 0), params.get("relation", "at least"))


def _check_letter_frequency(answer: str, params: dict, prompt: str) -> bool:
    letter = params.get("letter", "")
    count = answer.count(letter)
    return _compare(count, params.get("let_frequency", 0), params.get("let_relation", "at least"))


def _check_english_capital(answer: str, params: dict, prompt: str) -> bool:
    return answer == answer.upper()


def _check_english_lowercase(answer: str, params: dict, prompt: str) -> bool:
    return answer == answer.lower()


def _check_capital_word_frequency(answer: str, params: dict, prompt: str) -> bool:
    words = answer.split()
    if not words:
        return False
    cap_count = sum(1 for w in words if w[0].isupper())
    freq = cap_count * 100 / len(words)
    return _compare(freq, params.get("capital_frequency", 0), params.get("capital_relation", "at least"))


def _check_json_format(answer: str, params: dict, prompt: str) -> bool:
    # Extract JSON from markdown code blocks if present
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", answer)
    text = match.group(1).strip() if match else answer.strip()
    try:
        json.loads(text)
        return True
    except (json.JSONDecodeError, ValueError):
        return False


def _check_number_bullet_lists(answer: str, params: dict, prompt: str) -> bool:
    bullets = len(re.findall(r"^\s*[\*\-•]\s", answer, re.MULTILINE))
    return _compare(bullets, params.get("num_bullets", 0), params.get("relation", "at least"))


def _check_number_highlighted_sections(answer: str, params: dict, prompt: str) -> bool:
    highlights = len(re.findall(r"\*[^*\n]+\*", answer))
    return _compare(highlights, params.get("num_highlights", 0), params.get("relation", "at least"))


def _check_multiple_sections(answer: str, params: dict, prompt: str) -> bool:
    splitter = params.get("section_spliter", "SECTION")
    sections = [s for s in re.split(re.escape(splitter), answer, flags=re.IGNORECASE) if s.strip()]
    return _compare(len(sections), params.get("num_sections", 0), params.get("relation", "at least"))


def _check_title(answer: str, params: dict, prompt: str) -> bool:
    # Title = first line wrapped in # or all caps or short first line
    first_line = answer.strip().split("\n")[0] if answer.strip() else ""
    return bool(re.match(r"^#{1,6}\s", first_line) or (first_line.isupper() and len(first_line) < 100))


def _check_constrained_response(answer: str, params: dict, prompt: str) -> bool:
    # Response should be very short (one of a few allowed options)
    return len(answer.strip().split()) <= 5


def _check_number_placeholders(answer: str, params: dict, prompt: str) -> bool:
    placeholders = len(re.findall(r"\[.*?\]", answer))
    return _compare(placeholders, params.get("num_placeholders", 0), params.get("relation", "at least"))


def _check_postscript(answer: str, params: dict, prompt: str) -> bool:
    marker = params.get("postscript_marker", "P.S.")
    return marker.lower() in answer.lower()


def _check_response_language(answer: str, params: dict, prompt: str) -> bool:
    # Simple heuristic: check if answer contains characters from the target script
    # For a robust check, would need langdetect — but keep dependency-free
    lang = params.get("language", "en")
    if lang == "en":
        return bool(re.search(r"[a-zA-Z]", answer))
    # For non-English, just check it's not purely ASCII (heuristic)
    non_ascii = sum(1 for c in answer if ord(c) > 127)
    return non_ascii > len(answer) * 0.1


def _check_end_checker(answer: str, params: dict, prompt: str) -> bool:
    end_phrase = params.get("end_phrase", "")
    return answer.rstrip().endswith(end_phrase)


def _check_quotation(answer: str, params: dict, prompt: str) -> bool:
    stripped = answer.strip()
    return (stripped.startswith('"') and stripped.endswith('"')) or \
           (stripped.startswith("'") and stripped.endswith("'"))


def _check_repeat_prompt(answer: str, params: dict, prompt: str) -> bool:
    to_repeat = params.get("prompt_to_repeat", prompt)
    return to_repeat.strip() in answer


def _check_two_responses(answer: str, params: dict, prompt: str) -> bool:
    # Check for two distinct response sections (separated by *** or similar)
    separators = re.findall(r"\n\s*\*{3,}\s*\n|\n\s*-{3,}\s*\n|\n\s*={3,}\s*\n", answer)
    return len(separators) >= 1


# --- Registry ---

_CHECKERS = {
    "punctuation:no_comma": _check_no_comma,
    "length_constraints:number_words": _check_number_words,
    "length_constraints:number_sentences": _check_number_sentences,
    "length_constraints:number_paragraphs": _check_number_paragraphs,
    "length_constraints:nth_paragraph_first_word": _check_nth_paragraph_first_word,
    "keywords:existence": _check_keywords_existence,
    "keywords:forbidden_words": _check_forbidden_words,
    "keywords:frequency": _check_keyword_frequency,
    "keywords:letter_frequency": _check_letter_frequency,
    "change_case:english_capital": _check_english_capital,
    "change_case:english_lowercase": _check_english_lowercase,
    "change_case:capital_word_frequency": _check_capital_word_frequency,
    "detectable_format:json_format": _check_json_format,
    "detectable_format:number_bullet_lists": _check_number_bullet_lists,
    "detectable_format:number_highlighted_sections": _check_number_highlighted_sections,
    "detectable_format:multiple_sections": _check_multiple_sections,
    "detectable_format:title": _check_title,
    "detectable_format:constrained_response": _check_constrained_response,
    "detectable_content:number_placeholders": _check_number_placeholders,
    "detectable_content:postscript": _check_postscript,
    "language:response_language": _check_response_language,
    "startend:end_checker": _check_end_checker,
    "startend:quotation": _check_quotation,
    "combination:repeat_prompt": _check_repeat_prompt,
    "combination:two_responses": _check_two_responses,
}
