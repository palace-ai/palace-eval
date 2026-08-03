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

"""Citation Verification Analyzer.

Verifies that claims in generated reports are supported by their cited sources.

Overview
--------
The CitationVerifier extracts claims with citations from LLM-generated reports,
fetches the cited URLs, and uses an LLM judge to determine whether each source
actually supports the claim made.

This is useful for evaluating the factual grounding of report generation tasks,
particularly for detecting hallucinated citations (URLs that don't exist or
don't support the claims attributed to them).

Pipeline
--------
1. **Extract**: Parse the report to find (claim, URL) pairs using an LLM
2. **Deduplicate**: Group claims by URL, merge semantically similar claims
3. **Fetch**: Retrieve content from each unique URL
4. **Validate**: For each claim, ask LLM if the source content supports it
5. **Compute**: Aggregate results into accuracy metrics

Usage
-----
The analyzer is enabled via environment variable:

    ENABLE_CITATION_VERIFIER=true palace-cli

Or programmatically:

    from palace.evaluation import Evaluation
    eval = Evaluation(name="test", enable_citation_verifier=True)

It automatically runs on Criteria Evaluation tasks after the main evaluation.

Configuration
-------------
Environment variables:
- ENABLE_CITATION_VERIFIER: Set to "true" to enable (default: disabled)
- JUDGE_MODEL: Model for extraction/validation (required, no default)
- USE_ALOHA: Set to "true" to use ALOHA MCP for URL fetching (for DMZ clusters)

Output Metrics
--------------
The analyzer produces these metrics under `metrics.analyzers.citation_verifier`:

| Metric | Type | Description |
|--------|------|-------------|
| claims_extracted | int | Total claims with citations found in report |
| claims_checked | int | Claims where the URL was successfully fetched |
| claims_supported | int | Claims verified as supported by source |
| claims_unsupported | int | Claims not supported by source content |
| claims_failed | int | Claims where URL fetch or validation failed |
| urls_unique | int | Number of distinct URLs cited |
| urls_fetched | list[str] | URLs successfully retrieved |
| urls_failed | list[str] | URLs that could not be fetched |
| accuracy | float | claims_supported / claims_checked (0.0-1.0) |
| extraction_failed | bool | True if claim extraction itself failed |

Example output:
```json
{
  "claims_extracted": 12,
  "claims_checked": 8,
  "claims_supported": 6,
  "claims_unsupported": 2,
  "claims_failed": 4,
  "urls_unique": 10,
  "urls_fetched": ["https://example.com/report1", ...],
  "urls_failed": ["https://broken.link/404", ...],
  "accuracy": 0.75
}
```

Limitations
-----------
- Only processes markdown-style citations: [text](url)
- URL fetch may fail due to paywalls, bot blocking, or network restrictions
- Validation depends on LLM judgment, which may have false positives/negatives
- Maximum 100 citations processed per report (configurable)
"""

import json
import re
import time
from typing import Any, Callable, Optional

from palace.analyzers.base import Analyzer
from palace.models.api_model import APIModel, create_api_model
from palace.prompts.fact_prompts import (
    DEDUPLICATE_PROMPT,
    EXTRACT_PROMPT,
    VALIDATE_PROMPT,
)
from palace.task_types import Task, TaskVerificationResult
from palace.task_types.criteria_evaluation import CriteriaEvaluationTask
from palace.utils.constants import JUDGE_MODEL, OPENAI_LIKE_API_BASE_URL
from palace.utils.printing import print
from palace.utils.secrets import OPENAI_LIKE_API_KEY

MAX_RETRIES = 3


def _get_model() -> APIModel:
    """Get the model for LLM calls."""
    if OPENAI_LIKE_API_BASE_URL is None:
        raise ValueError("Missing required env var: OPENAI_LIKE_API_BASE_URL")
    if OPENAI_LIKE_API_KEY is None:
        raise ValueError("Missing required env var: OPENAI_LIKE_API_KEY")
    return create_api_model(
        JUDGE_MODEL,
        OPENAI_LIKE_API_BASE_URL,
        OPENAI_LIKE_API_KEY,
    )


def _parse_json_list(text: str) -> Optional[list]:
    """Parse a JSON list from LLM output, stripping markdown fences if present."""
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        result = json.loads(text)
        return result if isinstance(result, list) else None
    except json.JSONDecodeError:
        return None


def _remove_urls_from_text(text: str) -> str:
    """Remove markdown link URLs, keeping only the title."""
    return re.sub(r"\[([^\]]+)\]\([^)]+\)", r"[\1]", text)


class CitationVerifier(Analyzer):
    """Verifies that claims in generated reports are supported by cited sources.

    Implements the FACT pipeline: extract → deduplicate → fetch → validate → compute.

    Attributes:
        name: "citation_verifier" (used as metrics key)
        supported_task_types: [CriteriaEvaluationTask]

    Example:
        >>> from palace.analyzers.fetch import get_fetch_fn
        >>> verifier = CitationVerifier(fetch_fn=get_fetch_fn())
        >>> metrics = verifier.analyze(task, answer, verification_result)
        >>> print(f"Accuracy: {metrics['accuracy']:.0%}")
    """

    @property
    def name(self) -> str:
        return "citation_verifier"

    @property
    def supported_task_types(self) -> list[type[Task]]:
        return [CriteriaEvaluationTask]

    def __init__(
        self,
        fetch_fn: Callable[[str], Optional[str]],
        max_citations: int = 100,
    ):
        """Initialize CitationVerifier.

        Args:
            fetch_fn: Function that takes a URL and returns page content as string,
                or None if fetch fails. Use get_fetch_fn() for default implementation.
            max_citations: Maximum claims to process per report (default: 100).
        """
        self.fetch_fn = fetch_fn
        self.max_citations = max_citations

    def format_summary(self, metrics: dict[str, Any]) -> str:
        """Format metrics as human-readable summary for console output."""
        extracted = metrics.get("claims_extracted", 0)
        checked = metrics.get("claims_checked", 0)
        supported = metrics.get("claims_supported", 0)
        failed = metrics.get("claims_failed", 0)
        accuracy = metrics.get("accuracy", 0)

        if extracted == 0:
            return "No claims with citations found in the generated report."

        lines = [
            f"Claims: {extracted} extracted, {checked} checked, {failed} failed",
            f"Supported: {supported}/{checked} ({accuracy:.0%} accuracy)",
        ]
        if failed > 0:
            urls_failed = metrics.get("urls_failed", [])
            lines.append(f"[dim]({len(urls_failed)} URLs could not be fetched)[/]")
        return "\n".join(lines)

    async def analyze(
        self,
        task: Task,
        answer: str,
        verification_result: TaskVerificationResult,
    ) -> dict[str, Any]:
        """Run citation verification on the answer and return metrics."""
        extraction_failed = False
        try:
            model = _get_model()

            # Step 1: Extract citations
            citations, extraction_failed = await self._extract_citations(answer, model)
            if not citations:
                return {
                    "claims_extracted": 0,
                    "claims_checked": 0,
                    "claims_supported": 0,
                    "claims_unsupported": 0,
                    "claims_failed": 0,
                    "urls_unique": 0,
                    "urls_fetched": [],
                    "urls_failed": [],
                    "accuracy": 0.0,
                    "extraction_failed": extraction_failed,
                }

            # Limit citations
            if len(citations) > self.max_citations:
                citations = citations[: self.max_citations]

            # Step 2: Deduplicate
            deduped = await self._deduplicate_citations(citations, model)

            # Step 3: Scrape
            deduped = self._scrape_all(deduped)

            # Step 4: Validate
            deduped = await self._validate_citations(deduped, model)

            # Step 5: Compute stats
            return self._compute_stats(deduped, len(citations))

        except Exception as e:
            print(f"[bold red]Citation verification failed: {e}[/]")
            raise

    async def _extract_citations(self, article: str, model: APIModel) -> tuple[list[dict], bool]:
        """Extract (fact, ref_idx, url) triplets from the article using LLM.

        Returns:
            Tuple of (citations list, extraction_failed flag)
        """
        prompt = EXTRACT_PROMPT.format(report_text=article)

        try:
            response = await model.generate([{"role": "user", "content": prompt}])
        except Exception as e:
            print(f"[bold yellow]Extract LLM call failed: {e}[/]")
            return [], True

        for attempt in range(MAX_RETRIES):
            try:
                if response:
                    citations = _parse_json_list(response)
                    if citations is not None:
                        for c in citations:
                            c["fact"] = _remove_urls_from_text(c.get("fact", ""))
                        return citations, False
            except Exception as e:
                print(f"[bold yellow]Extract parse attempt {attempt + 1} failed: {e}[/]")
                continue

        return [], True

    async def _deduplicate_citations(self, citations: list[dict], model: APIModel) -> dict[str, dict]:
        """Group citations by URL and deduplicate facts within each group."""
        if not citations:
            return {}

        # Group by URL
        groups: dict[str, list[dict]] = {}
        for c in citations:
            url = c.get("url", "")
            groups.setdefault(url, []).append(c)

        deduped: dict[str, dict] = {}
        for url, group in groups.items():
            if len(group) == 1:
                deduped[url] = {"facts": [group[0]["fact"]], "url_content": None}
                continue

            statements = "\n".join(f"{i + 1}. {c['fact']}" for i, c in enumerate(group))
            prompt = DEDUPLICATE_PROMPT.format(statements=statements)

            kept_indices: list[int] = []
            for attempt in range(MAX_RETRIES):
                try:
                    response = await model.generate([{"role": "user", "content": prompt}])
                    parsed = _parse_json_list(response)
                    if parsed and all(isinstance(x, int) for x in parsed):
                        kept_indices = parsed
                        break
                except Exception as e:
                    print(f"[bold yellow]Dedup attempt {attempt + 1} failed: {e}[/]")
                    time.sleep(1)

            # Fallback: keep all
            if not kept_indices or 0 in kept_indices or len(kept_indices) > len(group):
                print(f"[bold yellow]Deduplication failed for {url}, keeping all {len(group)} citations[/]")
                kept_indices = list(range(1, len(group) + 1))

            deduped[url] = {
                "facts": [group[i - 1]["fact"] for i in kept_indices if 1 <= i <= len(group)],
                "url_content": None,
            }

        return deduped

    def _scrape_all(self, deduped: dict[str, dict]) -> dict[str, dict]:
        """Scrape webpage content for every URL using injected fetch_fn."""
        for url in deduped:
            if deduped[url].get("url_content") is None:
                content = self.fetch_fn(url)
                if content:
                    deduped[url]["url_content"] = content
                else:
                    deduped[url]["url_content"] = None
                    deduped[url]["scrape_failed"] = True
        return deduped

    async def _validate_citations(self, deduped: dict[str, dict], model: APIModel) -> dict[str, dict]:
        """For each URL group, ask LLM whether each fact is supported."""
        for url, group in deduped.items():
            # Skip if scrape failed
            if group.get("scrape_failed"):
                group["validate_res"] = []
                group["validate_error"] = "scrape failed"
                continue

            ref = group.get("url_content")
            facts = group.get("facts", [])
            if not ref or not facts:
                group["validate_res"] = []
                group["validate_error"] = "no reference" if not ref else "no facts"
                continue

            facts_str = "\n".join(f"{i + 1}. {fact}" for i, fact in enumerate(facts))
            prompt = VALIDATE_PROMPT.format(reference=ref, statements=facts_str)

            error = None
            for attempt in range(MAX_RETRIES):
                try:
                    response = await model.generate([{"role": "user", "content": prompt}])
                    validate_res = _parse_json_list(response)
                    if validate_res is not None:
                        # Adjust 1-based idx to 0-based
                        for v in validate_res:
                            if "idx" in v:
                                v["idx"] -= 1
                        if len(validate_res) == len(facts):
                            group["validate_res"] = validate_res
                            group["validate_error"] = None
                            break
                except Exception as e:
                    error = str(e)
                    print(f"[bold yellow]Validate attempt {attempt + 1} for {url}: {e}[/]")
                    time.sleep(2)
            else:
                group["validate_res"] = []
                group["validate_error"] = error

        return deduped

    def _compute_stats(self, deduped: dict[str, dict], total_extracted: int) -> dict[str, Any]:
        """Compute claim verification stats."""
        supported = 0
        unsupported = 0
        failed = 0
        urls_failed = []
        urls_fetched = []
        details = []  # For debugging

        for url, group in deduped.items():
            if group.get("scrape_failed") or group.get("validate_error"):
                failed += len(group.get("facts", []))
                urls_failed.append(url)
                continue
            urls_fetched.append(url)
            for i, v in enumerate(group.get("validate_res", [])):
                result = v.get("result", "unknown")
                fact = group.get("facts", [])[i] if i < len(group.get("facts", [])) else ""
                details.append({"url": url, "claim": fact[:200], "result": result})
                if result == "supported":
                    supported += 1
                elif result == "unsupported":
                    unsupported += 1
                else:
                    failed += 1

        checked = supported + unsupported
        accuracy = supported / checked if checked > 0 else 0.0

        return {
            "claims_extracted": total_extracted,
            "claims_checked": checked,
            "claims_supported": supported,
            "claims_unsupported": unsupported,
            "claims_failed": failed,
            "urls_unique": len(deduped),
            "urls_fetched": urls_fetched,
            "urls_failed": urls_failed,
            "accuracy": round(accuracy, 4),
            "details": details,
        }
