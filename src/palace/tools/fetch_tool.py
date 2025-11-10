from urllib.parse import urlparse

import pymupdf
import requests
from bs4 import BeautifulSoup

from palace.tools import Tool


class FetchTool(Tool):
    def _fetch_page_content(url: str, limit_length: int = None):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()  # Raise HTTP errors

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove unwanted elements (scripts, styles, etc.)
            for element in soup(["script", "style", "nav", "footer"]):
                element.decompose()

            # Get clean text
            text = " ".join(soup.stripped_strings)
            if limit_length is not None and limit_length < len(text):
                text = text[:limit_length] + "..."
            return {
                "url": url,
                "title": soup.title.string if soup.title else "No title",
                "content": text,
            }

        except Exception as e:
            return {"url": url, "error": str(e)}

    def _is_pdf_url(url):
        """
        Check if a URL points to a PDF file by:
        1. Checking the file extension
        2. Checking the Content-Type header
        3. (Optionally) Checking the file magic number

        Args:
            url (str): The URL to check

        Returns:
            bool: True if URL points to PDF, False otherwise
        """
        try:
            # Parse URL and check path
            parsed = urlparse(url)
            if parsed.path.lower().endswith(".pdf"):
                return True

            # Make HEAD request to check Content-Type
            response = requests.head(url, allow_redirects=True, timeout=5)
            content_type = response.headers.get("Content-Type", "").lower()

            # Check for PDF content types
            if "pdf" in content_type:
                return True

            # If Content-Type is ambiguous, check the first bytes for PDF magic number
            if content_type in ["application/octet-stream", "binary/octet-stream"]:
                # Make a GET request for just the first few bytes
                headers = {"Range": "bytes=0-4"}
                response = requests.get(url, headers=headers, stream=True, timeout=5)
                return response.content.startswith(b"%PDF-")

            return False

        except (requests.RequestException, ValueError):
            return False

    def _fetch_pdf_content(url: str, limit_length: int = None):
        try:
            response = requests.get(url)
            response.raise_for_status()

            with pymupdf.open(stream=response.content, filetype="pdf") as pdf:
                # retrieve pdf title from metadata
                title = pdf.metadata.get("title", "No title").strip()

                # retrieve full pdf text
                content = ""
                for page in pdf:
                    content += page.get_text()

                # trim content length to `limit_length` if set
                if limit_length is not None and limit_length < len(content):
                    content = content[:limit_length] + "..."

                return {"url": url, "title": title, "content": content}

        except Exception as e:
            return {"url": url, "error": str(e)}

    def execute(self, *args, **kwargs) -> str:
        """Execute the tool functionality."""
        # Check parameter compliance
        for parameter in self.required_parameters:
            if parameter not in kwargs:
                return f"""Tool `{self.name}` encountered the following error: parameter `{parameter}` was not found in the tool call but it is required. Make sure to comply with the required parameters name and type. For this tool, the required parameters are the following:
{self.required_parameters}"""

        url = kwargs["url"]
        limit_length = kwargs.get("limit_length", None)
        if limit_length is not None:
            limit_length = int(limit_length)

        if __class__._is_pdf_url(url):  # adding direct pdf extraction capability
            fetch_output = __class__._fetch_pdf_content(url, limit_length=limit_length)
        else:
            fetch_output = __class__._fetch_page_content(url, limit_length=limit_length)

        if "error" in fetch_output:
            return f"Fetching url {url} returned the following error: {fetch_output['error']}"
        else:
            return f"{fetch_output['url']}\n{fetch_output['title']}\n{fetch_output['content']}"

    @property
    def name(self) -> str:
        """Return the name of the tool."""
        return "Fetch Tool"

    @property
    def description(self) -> str:
        """Return the description of the tool."""
        return """Fetch the content of a URL in plain text format."""

    @property
    def parameters(self) -> dict[str, str]:
        """Return the parameters required by the tool along with their description."""
        return {
            "url": "The search query.",
            "limit_length": "If set, limit the amount of output characters. Otherwise, get the whole content.",
        }

    @property
    def required_parameters(self) -> list[str]:
        """Return the list of required parameters. By default, all of them are required. Override this method to define required ones."""
        return ["url"]
