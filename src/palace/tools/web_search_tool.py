import requests
from bs4 import BeautifulSoup

from palace.tools import Tool


class WebSearchTool(Tool):
    @staticmethod
    def _duckduckgo_html_search(query: str) -> list[dict[str, str]]:
        url = "https://html.duckduckgo.com/html/"
        params = {"q": query, "kl": "wt-wt"}
        headers = {"User-Agent": "Mozilla/5.0"}

        response = requests.post(url, data=params, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")

        results = []
        for result in soup.select(".result"):
            title = result.select_one(".result__title a")
            if title is not None:
                title = title.text
            else:
                title = ""

            link = result.select_one(".result__url")
            if link is not None:
                link = str(link["href"])
            else:
                link = ""

            snippet = result.select_one(".result__snippet")
            if snippet is not None:
                snippet = snippet.text
            else:
                snippet = ""

            # DuckDuckGo links are redirects (e.g., //duckduckgo.com/l/?uddg=...)
            # Extract the real URL:
            if link.startswith("//duckduckgo.com/l/?uddg="):
                link = link.split("uddg=")[1].split("&")[0]
                link = requests.utils.unquote(link)  # type: ignore # Decode URL-encoded characters

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
    def parameters(self) -> dict[str, str]:
        """Return the parameters required by the tool along with their description."""
        return {
            "query": "The search query.",
        }
