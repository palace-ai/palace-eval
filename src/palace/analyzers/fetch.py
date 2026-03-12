"""Fetch functions for URL content retrieval.

Supports direct HTTP (local dev) and ALOHA MCP (DMZ cluster).
"""

import asyncio
import json
import os
import re
from typing import Callable, Optional

import requests
from bs4 import BeautifulSoup
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from palace.utils.printing import print

# Environment variables
ALOHA_WEB_URL = os.getenv("ALOHA_WEB_URL", "")
ALOHA_WEB_TOKEN = os.getenv("ALOHA_WEB_TOKEN", "")
ALOHA_LITERATURE_URL = os.getenv("ALOHA_LITERATURE_URL", "")
ALOHA_LITERATURE_TOKEN = os.getenv("ALOHA_LITERATURE_TOKEN", "")

# DOI pattern
_DOI_PATTERN = re.compile(r"10\.\d{4,}/[^\s]+")


def extract_doi(url: str) -> Optional[str]:
    """Extract DOI from a URL if present."""
    if "doi.org/" in url:
        parts = url.split("doi.org/")
        if len(parts) > 1:
            return parts[1].split("?")[0].split("#")[0]
    if "dx.doi.org/" in url:
        match = _DOI_PATTERN.search(url)
        if match:
            return match.group(0)
    return None


def http_fetch(url: str, timeout: int = 30) -> Optional[str]:
    """Fetch URL content via direct HTTP.
    
    Returns extracted text content, or None on failure.
    """
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove unwanted elements
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        # Extract title
        title = soup.title.string.strip() if soup.title and soup.title.string else ""

        # Extract description
        description = ""
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            description = meta_desc["content"].strip()

        # Extract body text
        content = soup.get_text(separator="\n", strip=True)
        content = re.sub(r"\n{3,}", "\n\n", content)

        return f"{title}\n\n{description}\n\n{content}"

    except Exception as e:
        print(f"[bold yellow]HTTP fetch failed for {url}: {e}[/]")
        return None


def aloha_web_fetch(url: str) -> Optional[str]:
    """Fetch URL content via ALOHA Web MCP server's fetch_url tool."""
    if not ALOHA_WEB_URL:
        return None

    try:
        async def _fetch():
            headers = {"Authorization": f"Bearer {ALOHA_WEB_TOKEN}"} if ALOHA_WEB_TOKEN else None
            async with streamablehttp_client(ALOHA_WEB_URL, headers=headers) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool("fetch_url", {"url": url})
                    if result.content and result.content[0].text:
                        parsed = json.loads(result.content[0].text)
                        return parsed.get("text", "")
                    return None

        return asyncio.run(_fetch())
    except Exception as e:
        print(f"[bold yellow]ALOHA web fetch failed for {url}: {e}[/]")
        return None


def aloha_literature_fetch(doi: str) -> Optional[str]:
    """Fetch paper content via ALOHA Literature MCP server's scopus_search_doi tool."""
    if not ALOHA_LITERATURE_URL:
        return None

    try:
        async def _fetch():
            headers = {"Authorization": f"Bearer {ALOHA_LITERATURE_TOKEN}"} if ALOHA_LITERATURE_TOKEN else None
            async with streamablehttp_client(ALOHA_LITERATURE_URL, headers=headers) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(
                        "scopus_search_doi",
                        {"doi_codes": [doi], "return_fields": ["title", "abstract", "authors", "date"]},
                    )
                    if result.content and result.content[0].text:
                        parsed = json.loads(result.content[0].text)
                        if parsed and len(parsed) > 0:
                            paper = parsed[0]
                            return f"DOI: {doi}\n\nTitle: {paper.get('title', '')}\n\nAbstract: {paper.get('abstract', '')}"
                    return None

        return asyncio.run(_fetch())
    except Exception as e:
        print(f"[bold yellow]ALOHA literature fetch failed for DOI {doi}: {e}[/]")
        return None


def get_fetch_fn() -> Callable[[str], Optional[str]]:
    """Return composite fetch function that handles DOIs and regular URLs.
    
    - DOI URLs: Try literature search first, fall back to web fetch
    - Regular URLs: Use ALOHA web fetch (if USE_ALOHA) or direct HTTP
    """
    use_aloha = os.getenv("USE_ALOHA", "").lower() in ("true", "1", "yes")

    def composite_fetch(url: str) -> Optional[str]:
        # Try literature search for DOIs first
        doi = extract_doi(url)
        if doi and ALOHA_LITERATURE_URL:
            result = aloha_literature_fetch(doi)
            if result:
                return result

        # Fall back to regular fetch
        if use_aloha:
            return aloha_web_fetch(url)
        return http_fetch(url)

    return composite_fetch
