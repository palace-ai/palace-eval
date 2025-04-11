from typing import Dict, List
import requests
from bs4 import BeautifulSoup

from . import Tool


class FetchTool(Tool):

    def _fetch_url_content(url, limit_length: int = None):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()  # Raise HTTP errors
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove unwanted elements (scripts, styles, etc.)
            for element in soup(['script', 'style', 'nav', 'footer']):
                element.decompose()
            
            # Get clean text
            text = ' '.join(soup.stripped_strings)
            if limit_length is not None:
                text = text[:limit_length] + "..."
            return {
                "url": url,
                "title": soup.title.string if soup.title else "No title",
                "content": (text[:limit_length] + "...") if limit_length is not None else text  # Limit length
            }
        
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
            
        fetch_output = __class__._fetch_url_content(url, limit_length=limit_length)

        if "error" in fetch_output:
            return f"Fetching url {url} returned the following error: {fetch_output['error']}"
        else:
            return fetch_output["content"]
            
    @property
    def name(self) -> str:
        """Return the name of the tool."""
        return "Fetch Tool"

    @property
    def description(self) -> str:
        """Return the description of the tool."""
        return """Fetch the content of a URL in plain text format."""

    @property
    def parameters(self) -> Dict[str, str]:
        """Return the parameters required by the tool along with their description."""
        return {
            "url": "The search query.",
            "limit_length": "If set, limit the amount of output characters. Otherwise, get the whole content."
        }
    
    @property
    def required_parameters(self) -> List[str]:
        """Return the list of required parameters. By default, all of them are required. Override this method to define required ones."""
        return ["url"]