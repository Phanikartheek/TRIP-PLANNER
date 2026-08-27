"""
Web search tool for agents.

Design note: CrewAI/crewai_tools ships a SerperDevTool but nothing free
out of the box, so this wraps `duckduckgo_search` behind CrewAI's
BaseTool interface. Two deliberate choices here:

1. The agent-facing interface (`_run(query: str) -> str`) is generic —
   it doesn't leak DuckDuckGo-specific details. Swapping to Serper or
   Tavily later means changing this one file, not touching agents.yaml
   or crew.py.
2. Results are deliberately compressed to title + snippet + url per
   result, not full page dumps — keeps token usage (and Groq free-tier
   rate limits) under control across a multi-agent run.
"""

from crewai.tools import BaseTool
from ddgs import DDGS
from pydantic import BaseModel, Field


class SearchToolInput(BaseModel):
    query: str = Field(description="The search query to look up on the web")


class DuckDuckGoSearchTool(BaseTool):
    name: str = "web_search"
    description: str = (
        "Searches the web for up-to-date information. Use this for current "
        "prices, weather patterns, events, attractions, or anything that "
        "may have changed since training data. Input should be a specific "
        "search query, not a full question."
    )
    args_schema: type[BaseModel] = SearchToolInput
    max_results: int = 2

    def _run(self, query: str, topn: int | None = None, source: str | None = None, **kwargs) -> str:
        try:
            limit = min(topn or self.max_results, 2)
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=limit))
        except Exception as exc:  # noqa: BLE001 - surface to the agent, don't crash the run
            return f"Search failed for query '{query}': {exc}"

        if not results:
            return f"No results found for '{query}'."

        formatted = []
        for r in results:
            title = (r.get("title") or "")[:80]
            body = (r.get("body") or "")[:180]
            href = r.get("href") or ""
            formatted.append(f"- {title}: {body} (Source: {href})")

        return "\n".join(formatted)
