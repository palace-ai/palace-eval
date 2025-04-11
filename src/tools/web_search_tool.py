from typing import Dict, List
import requests
from bs4 import BeautifulSoup

from . import Tool


class WebSearchTool(Tool):

    def _duckduckgo_html_search(query: str) -> List[Dict[str, str]]:
        url = "https://html.duckduckgo.com/html/"
        params = {"q": query, "kl": "wt-wt"}
        headers = {"User-Agent": "Mozilla/5.0"}
        
        response = requests.post(url, data=params, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        results = []
        for result in soup.select('.result'):
            title = result.select_one('.result__title a').text
            link = result.select_one('.result__url')['href']
            snippet = result.select_one('.result__snippet').text if result.select_one('.result__snippet') else ""
            
            # DuckDuckGo links are redirects (e.g., //duckduckgo.com/l/?uddg=...)
            # Extract the real URL:
            if link.startswith('//duckduckgo.com/l/?uddg='):
                link = link.split('uddg=')[1].split('&')[0]
                link = requests.utils.unquote(link)  # Decode URL-encoded characters
            
            results.append({"title": title, "link": link, "snippet": snippet})
        
        return results


    def execute(self, *args, **kwargs) -> str:
        """Execute the tool functionality."""
        # Check parameter compliance
        for parameter in self.required_parameters:
            if parameter not in kwargs:
                return f"""Tool `{self.name}` encountered the following error: parameter `{parameter}` was not found in the tool call but it is required. Make sure to comply with the required parameters name and type. For this tool, the required parameters are the following:
{self.required_parameters}"""

        results = __class__._duckduckgo_html_search(kwargs["query"])

        formatted_results = ""
        for idx, result in enumerate(results, 1):
            formatted_results += f"{idx}. {result['title']}\n   {result['link']}\n   {result['snippet']}\n"
        return formatted_results

    @property
    def name(self) -> str:
        """Return the name of the tool."""
        return "Web Search Tool"

    @property
    def description(self) -> str:
        """Return the description of the tool."""
        return """Search the web using the input query, and retrieve a list of relevant results, each with a title, a URL, and a snippet of its content."""

    @property
    def parameters(self) -> Dict[str, str]:
        """Return the parameters required by the tool along with their description."""
        return {
            "query": "The search query.",
        }
