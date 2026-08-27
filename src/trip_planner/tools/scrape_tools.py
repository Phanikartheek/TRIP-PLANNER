"""
Page-scraping tool for agents.
"""

from crewai_tools import ScrapeWebsiteTool


class ConciseScrapeWebsiteTool(ScrapeWebsiteTool):
    def _run(self, *args, **kwargs) -> str:
        res = super()._run(*args, **kwargs)
        if isinstance(res, str) and len(res) > 800:
            return res[:800] + "... [truncated]"
        return res


def build_scrape_tool() -> ScrapeWebsiteTool:
    return ConciseScrapeWebsiteTool()
