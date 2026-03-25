"""LLM-based judge for evaluating task outputs.

The Judge class extracts structured data from LLM responses using XML tags.
It supports both flat and nested tag structures with automatic retry on parse failures.

Usage Examples
--------------

Flat tags (simple):
    judge = Judge(
        judge_model="minimax-m2",
        judge_prompt="Evaluate and respond with <reasoning>...</reasoning><judgement>...</judgement>",
        output_keywords=["reasoning", "judgement"]
    )
    result = judge.judge("Is the sky blue?")
    # Returns: {"reasoning": "The sky appears blue due to...", "judgement": "Correct"}

Nested tags (for complex structured output):
    judge = Judge(
        judge_model="minimax-m2", 
        judge_prompt="...",
        output_keywords={
            "clarity": ["discussion", "best", "gap"],
            "accuracy": ["discussion", "best", "gap"]
        }
    )
    result = judge.judge(prompt)
    # Returns: {
    #     "clarity": {"discussion": "...", "best": "A", "gap": "3"},
    #     "accuracy": {"discussion": "...", "best": "B", "gap": "2"}
    # }

Leaf tags (nested structure with some tags having no children):
    output_keywords = {
        "summary": [],  # Empty list = leaf tag, extracts content directly
        "details": ["pros", "cons"]  # List = extract these children
    }
    # Returns: {"summary": "text content", "details": {"pros": "...", "cons": "..."}}

Deep nesting (arbitrary depth):
    output_keywords = {
        "evaluation": {
            "technical": ["accuracy", "completeness"],
            "style": ["clarity", "tone"]
        }
    }
    # Returns nested dict mirroring the structure
"""

import re
from typing import Any

from palace.models.api_model import APIModel
from palace.utils.constants import OPENAI_LIKE_API_BASE_URL
from palace.utils.printing import print
from palace.utils.secrets import OPENAI_LIKE_API_KEY


class Judge:
    """LLM-based judge that extracts structured XML data from responses.

    The judge sends a prompt to an LLM and parses the response according to
    a specified tag structure. It automatically retries on parse failures.

    Args:
        judge_model: Model identifier (e.g., "minimax-m2", "openai/gpt-oss-120b").
        judge_prompt: System prompt instructing the LLM how to format its response.
            Must specify the XML tag structure matching output_keywords.
        output_keywords: Specifies which XML tags to extract.
            As a list of strings: flat tags at root level, returns dict[str, str].
            As a dict: nested structure where values can be [] (leaf tag),
            ["a", "b"] (extract child tags), or {...} (recurse).
            Returns nested dict mirroring the input structure.

    Examples:
        >>> judge = Judge("minimax-m2", prompt, ["reasoning", "judgement"])
        >>> result = judge.judge("Evaluate this answer")
        >>> result["judgement"]
        'Correct'

        >>> judge = Judge("minimax-m2", prompt, {"quality": ["score", "explanation"]})
        >>> result = judge.judge("Rate this text")
        >>> result["quality"]["score"]
        '8'
    """

    def __init__(
        self,
        judge_model: str,
        judge_prompt: str,
        output_keywords: list[str] | dict[str, Any] = ["reasoning", "judgement"],
    ) -> None:
        self.judge_prompt = judge_prompt
        self.output_keywords = output_keywords
        
        assert OPENAI_LIKE_API_BASE_URL is not None, (
            "OPENAI_LIKE_API_BASE_URL is not set in the environment variables."
        )
        self.judge_model = APIModel(
            judge_model,
            OPENAI_LIKE_API_BASE_URL,
            OPENAI_LIKE_API_KEY,
        )

    def _parse_tag(self, content: str, tag: str) -> str:
        """Extract content of a single XML tag. Raises ValueError if not found."""
        match = re.search(rf"<{tag}>(.*?)</{tag}>", content, re.S)
        if not match:
            raise ValueError(f"Missing tag: <{tag}>")
        return match.group(1).strip()

    def _parse_recursive(self, content: str, spec: list | dict) -> dict:
        """Parse nested XML according to spec. Returns nested dict."""
        if isinstance(spec, list):
            if not spec:
                raise ValueError("Empty list spec should be handled by caller")
            result = {}
            for tag in spec:
                result[tag] = self._parse_tag(content, tag)
            return result
        
        result = {}
        for tag, children in spec.items():
            tag_content = self._parse_tag(content, tag)
            if children == []:
                result[tag] = tag_content
            elif isinstance(children, list):
                result[tag] = {}
                for child in children:
                    result[tag][child] = self._parse_tag(tag_content, child)
            else:
                result[tag] = self._parse_recursive(tag_content, children)
        return result

    def _parse_flat(self, content: str, keywords: list[str]) -> dict[str, str]:
        """Parse flat XML tags at root level."""
        result = {}
        for keyword in keywords:
            result[keyword] = self._parse_tag(content, keyword)
        return result

    def judge(self, prompt: str) -> dict:
        """Send prompt to judge LLM and extract structured response.

        Args:
            prompt: The user prompt to evaluate.

        Returns:
            Extracted values. Structure matches output_keywords:
            flat dict[str, str] for list input, nested dict for dict input.

        Raises:
            ValueError: If parsing fails after max retries (5 attempts).
        """
        conversation = []
        if self.judge_prompt is not None:
            conversation.append({"role": "system", "content": self.judge_prompt})
        conversation.append({"role": "user", "content": prompt})

        max_attempts = 5
        for attempt in range(1, max_attempts + 1):
            judge_output = self.judge_model.generate(conversation)
            try:
                if isinstance(self.output_keywords, list):
                    return self._parse_flat(judge_output, self.output_keywords)
                else:
                    return self._parse_recursive(judge_output, self.output_keywords)
            except ValueError as e:
                print(f"[bold yellow]{e}. Retrying ({attempt}/{max_attempts})...")

        raise ValueError(
            f"[bold red]Max attempts ({max_attempts}) exceeded. Could not parse judge output."
        )
