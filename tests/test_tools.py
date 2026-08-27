from unittest.mock import MagicMock, patch

from trip_planner.tools.search_tools import DuckDuckGoSearchTool


def test_search_tool_formats_results():
    fake_results = [
        {"title": "Lisbon Weather", "body": "Mild winters, warm summers.", "href": "https://example.com/1"},
        {"title": "Lisbon Prices", "body": "Budget-friendly for Western Europe.", "href": "https://example.com/2"},
    ]
    with patch("trip_planner.tools.search_tools.DDGS") as mock_ddgs_cls:
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__.return_value = mock_ddgs
        mock_ddgs.text.return_value = fake_results
        mock_ddgs_cls.return_value = mock_ddgs

        tool = DuckDuckGoSearchTool()
        output = tool._run("Lisbon weather in October")

    assert "Lisbon Weather" in output
    assert "https://example.com/1" in output
    assert "Lisbon Prices" in output


def test_search_tool_handles_no_results():
    with patch("trip_planner.tools.search_tools.DDGS") as mock_ddgs_cls:
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__.return_value = mock_ddgs
        mock_ddgs.text.return_value = []
        mock_ddgs_cls.return_value = mock_ddgs

        tool = DuckDuckGoSearchTool()
        output = tool._run("a query with no results")

    assert "No results found" in output


def test_search_tool_handles_exception_gracefully():
    with patch("trip_planner.tools.search_tools.DDGS") as mock_ddgs_cls:
        mock_ddgs_cls.side_effect = RuntimeError("network down")

        tool = DuckDuckGoSearchTool()
        output = tool._run("any query")

    assert "Search failed" in output
