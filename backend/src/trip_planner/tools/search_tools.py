"""
Web search tool for agents with in-memory TTL caching.

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
3. In-memory TTL cache (default 24h) avoids repeating identical searches
   across multiple agent iterations or frequent user queries.
"""

import time

from crewai.tools import BaseTool
from ddgs import DDGS
from pydantic import BaseModel, Field

# In-memory search cache mapping normalized query -> (timestamp, formatted_results)
_SEARCH_CACHE: dict[str, tuple[float, str]] = {}
DEFAULT_CACHE_TTL_SECONDS: float = 86400.0  # 24 hours


def clear_search_cache() -> None:
    """Helper to reset search cache (useful in tests and maintenance)."""
    _SEARCH_CACHE.clear()


def get_cached_search(query: str, ttl_seconds: float = DEFAULT_CACHE_TTL_SECONDS) -> str | None:
    """Retrieve search result from cache if present and unexpired."""
    key = query.strip().lower()
    if key in _SEARCH_CACHE:
        cached_time, result = _SEARCH_CACHE[key]
        if time.time() - cached_time <= ttl_seconds:
            return result
        del _SEARCH_CACHE[key]
    return None


def set_cached_search(query: str, result: str) -> None:
    """Store search result in cache with current timestamp."""
    key = query.strip().lower()
    _SEARCH_CACHE[key] = (time.time(), result)


class SearchToolInput(BaseModel):
    query: str = Field(default="", description="The search query to look up on the web")

    model_config = {"extra": "allow"}


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
    cache_ttl_seconds: float = DEFAULT_CACHE_TTL_SECONDS

    def _run(self, query: str = "", topn: int | None = None, source: str | None = None, **kwargs) -> str:
        if not query:
            query = kwargs.get("search_query") or kwargs.get("q") or ""
        if not query:
            return "No search query provided."

        cached = get_cached_search(query, ttl_seconds=self.cache_ttl_seconds)
        if cached is not None:
            return cached

        try:
            limit = min(topn or self.max_results, 2)
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=limit))
        except Exception as exc:  # noqa: BLE001 - surface to the agent, don't crash the run
            return f"Search failed for query '{query}': {exc}"

        if not results:
            res = f"No results found for '{query}'."
            set_cached_search(query, res)
            return res

        formatted = []
        for r in results:
            title = (r.get("title") or "")[:80]
            body = (r.get("body") or "")[:180]
            href = r.get("href") or ""
            formatted.append(f"- {title}: {body} (Source: {href})")

        output = "\n".join(formatted)
        set_cached_search(query, output)
        return output
