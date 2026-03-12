"""Citation verification analyzer.

Extracts citations from generated reports, scrapes cited URLs,
and validates whether sources support the claimed facts.
"""

import json
import os
import re
import time
from typing import Any, Callable, Optional

from palace.analyzers.base import Analyzer
from palace.models.api_model import APIModel
from palace.prompts.fact_prompts import (
    DEDUPLICATE_PROMPT,
    EXTRACT_PROMPT,
    VALIDATE_PROMPT,
)
from palace.task_types import Task, TaskVerificationResult
from palace.utils.constants import GPTJRC_PROD_API_URL
from palace.utils.printing import print
from palace.utils.secrets import GPTJRC_PROD_TOKEN

MAX_RETRIES = 3
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "minimax-m2")


def _get_model() -> APIModel:
    """Get the model for LLM calls."""
    missing = []
    if not GPTJRC_PROD_API_URL:
        missing.append("GPTJRC_PROD_API_URL")
    if not GPTJRC_PROD_TOKEN:
        missing.append("GPTJRC_PROD_TOKEN")
    if missing:
        raise ValueError(f"Missing required env vars: {', '.join(missing)}")
    return APIModel(
        JUDGE_MODEL,
        GPTJRC_PROD_API_URL,
        GPTJRC_PROD_TOKEN,
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
    """Analyzer that verifies citations in generated reports.

    Pipeline: extract → deduplicate → scrape → validate → compute stats
    """

    @property
    def name(self) -> str:
        return "citation_verifier"

    @property
    def supported_task_types(self) -> list[str]:
        return ["Report Generation"]

    def __init__(
        self,
        fetch_fn: Callable[[str], Optional[str]],
        max_citations: int = 100,
    ):
        """Initialize CitationVerifier.

        Args:
            fetch_fn: Function to fetch URL content, returns text or None
            max_citations: Maximum citations to process
        """
        self.fetch_fn = fetch_fn
        self.max_citations = max_citations

    def analyze(
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
            citations, extraction_failed = self._extract_citations(answer, model)
            if not citations:
                return {
                    "citation_count": 0,
                    "unique_urls": 0,
                    "citations_supported": 0,
                    "citations_unsupported": 0,
                    "citations_failed": 0,
                    "citation_accuracy": 0.0,
                    "extraction_failed": extraction_failed,
                }

            # Limit citations
            if len(citations) > self.max_citations:
                citations = citations[: self.max_citations]

            # Step 2: Deduplicate
            deduped = self._deduplicate_citations(citations, model)

            # Step 3: Scrape
            deduped = self._scrape_all(deduped)

            # Step 4: Validate
            deduped = self._validate_citations(deduped, model)

            # Step 5: Compute stats
            return self._compute_stats(deduped, len(citations))

        except Exception as e:
            print(f"[bold red]Citation verification failed: {e}[/]")
            raise

    def _extract_citations(self, article: str, model: APIModel) -> tuple[list[dict], bool]:
        """Extract (fact, ref_idx, url) triplets from the article using LLM.
        
        Returns:
            Tuple of (citations list, extraction_failed flag)
        """
        prompt = EXTRACT_PROMPT.format(report_text=article)

        try:
            response = model.generate([{"role": "user", "content": prompt}])
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
                print(
                    f"[bold yellow]Extract parse attempt {attempt + 1} failed: {e}[/]"
                )
                continue

        return [], True

    def _deduplicate_citations(
        self, citations: list[dict], model: APIModel
    ) -> dict[str, dict]:
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
                    response = model.generate([{"role": "user", "content": prompt}])
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
                "facts": [
                    group[i - 1]["fact"] for i in kept_indices if 1 <= i <= len(group)
                ],
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

    def _validate_citations(
        self, deduped: dict[str, dict], model: APIModel
    ) -> dict[str, dict]:
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
                    response = model.generate([{"role": "user", "content": prompt}])
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
                    print(
                        f"[bold yellow]Validate attempt {attempt + 1} for {url}: {e}[/]"
                    )
                    time.sleep(2)
            else:
                group["validate_res"] = []
                group["validate_error"] = error

        return deduped

    def _compute_stats(
        self, deduped: dict[str, dict], total_extracted: int
    ) -> dict[str, Any]:
        """Compute citation accuracy and counts."""
        supported = 0
        unsupported = 0
        failed = 0

        for group in deduped.values():
            if group.get("validate_error") is not None:
                failed += len(group.get("facts", []))
                continue
            for v in group.get("validate_res", []):
                result = v.get("result", "unknown")
                if result == "supported":
                    supported += 1
                elif result == "unsupported":
                    unsupported += 1
                else:  # unknown
                    failed += 1

        total_verified = supported + unsupported
        accuracy = supported / total_verified if total_verified > 0 else 0.0

        return {
            "citation_count": total_extracted,
            "unique_urls": len(deduped),
            "citations_supported": supported,
            "citations_unsupported": unsupported,
            "citations_failed": failed,
            "citation_accuracy": round(accuracy, 4),
        }
