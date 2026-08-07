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

"""LLM-based judge for evaluating task outputs.

The Judge class extracts structured data from LLM responses using XML tags.
It supports both flat and nested tag structures with automatic retry on parse failures.

Usage Examples
--------------

Flat tags (simple):
    judge = Judge(
        judge_model="gpt-4o",
        judge_prompt="Evaluate and respond with <reasoning>...</reasoning><judgement>...</judgement>",
        output_keywords=["reasoning", "judgement"]
    )
    result = judge.judge("Is the sky blue?")
    # Returns: {"reasoning": "The sky appears blue due to...", "judgement": "Correct"}

Nested tags (for complex structured output):
    judge = Judge(
        judge_model="gpt-4o",
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

from palace.models.api_model import create_api_model
from palace.utils.constants import get_judge_key, get_judge_url
from palace.utils.exceptions import JudgeConfigurationError
from palace.utils.printing import print


class Judge:
    """LLM-based judge that extracts structured XML data from responses.

    The judge sends a prompt to an LLM and parses the response according to
    a specified tag structure. It automatically retries on parse failures.

    Args:
        judge_model: Model identifier (e.g., "gpt-4o", "claude-3-5-sonnet-latest").
        judge_prompt: System prompt instructing the LLM how to format its response.
            Must specify the XML tag structure matching output_keywords.
        output_keywords: Specifies which XML tags to extract.
            As a list of strings: flat tags at root level, returns dict[str, str].
            As a dict: nested structure where values can be [] (leaf tag),
            ["a", "b"] (extract child tags), or {...} (recurse).
            Returns nested dict mirroring the input structure.
        url: API endpoint URL. Defaults to judge_url config, then falls back to url config.
        token: API token. Defaults to judge_key config, then falls back to key config.

    Examples:
        >>> judge = Judge("gpt-4o", prompt, ["reasoning", "judgement"])
        >>> result = judge.judge("Evaluate this answer")
        >>> result["judgement"]
        'Correct'

        >>> judge = Judge("gpt-4o", prompt, {"quality": ["score", "explanation"]})
        >>> result = judge.judge("Rate this text")
        >>> result["quality"]["score"]
        '8'
    """

    def __init__(
        self,
        judge_model: str,
        judge_prompt: str,
        output_keywords: list[str] | dict[str, Any] = ["reasoning", "judgement"],
        url: str | None = None,
        token: str | None = None,
    ) -> None:
        self.judge_prompt = judge_prompt
        self.output_keywords = output_keywords

        # Check judge_model is set
        if not judge_model:
            raise JudgeConfigurationError(
                "judge_model is required but not set. Set via:\n"
                "  - palace config set judge_model <model>\n"
                "  - JUDGE_MODEL env var"
            )

        # Resolve URL and token: explicit params > judge config > main config
        resolved_url = url or get_judge_url()
        resolved_token = token or get_judge_key()

        if not resolved_url:
            raise JudgeConfigurationError(
                "Judge API URL not configured. Set via:\n"
                "  - palace config set judge_url <url>  (judge-specific)\n"
                "  - palace config set url <url>  (fallback)\n"
                "  - JUDGE_API_URL or OPENAI_LIKE_API_BASE_URL env var"
            )
        self.judge_model = create_api_model(
            judge_model,
            resolved_url,
            resolved_token,
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

    async def judge(self, prompt: str) -> dict:
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
            judge_output = await self.judge_model.generate(conversation)
            try:
                if isinstance(self.output_keywords, list):
                    return self._parse_flat(judge_output, self.output_keywords)
                else:
                    return self._parse_recursive(judge_output, self.output_keywords)
            except ValueError as e:
                print(f"[bold yellow]{e}. Retrying ({attempt}/{max_attempts})...")

        raise ValueError(f"[bold red]Max attempts ({max_attempts}) exceeded. Could not parse judge output.")
