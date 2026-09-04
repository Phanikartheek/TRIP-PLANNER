"""
MCP (Model Context Protocol) Tools Client Adapter for CrewAI.

Enables CrewAI agents to dynamically discover and invoke tools exposed by
standard Model Context Protocol (MCP) servers (JSON-RPC 2.0).
"""

from __future__ import annotations

import json
from typing import Any, Callable, Type
from pydantic import BaseModel, Field, create_model
from crewai.tools import BaseTool


class MCPToolAdapter(BaseTool):
    """
    Adapts an MCP server tool definition into a CrewAI BaseTool.
    """

    name: str = ""
    description: str = ""
    mcp_call_fn: Callable[[str, dict[str, Any]], Any] = Field(default=None, exclude=True)

    def _run(self, **kwargs: Any) -> str:
        """
        Executes the MCP tool via the provided callable.
        """
        if not self.mcp_call_fn:
            return f"Error: MCP tool {self.name} has no execution handler configured."
        try:
            result = self.mcp_call_fn(self.name, kwargs)
            if isinstance(result, (dict, list)):
                return json.dumps(result, indent=2)
            return str(result)
        except Exception as e:
            return f"MCP Tool execution failed for {self.name}: {str(e)}"


class MCPClient:
    """
    Lightweight Client implementing standard MCP (JSON-RPC 2.0) protocol.
    Supports in-process, function-based, and stdio MCP server communication.
    """

    def __init__(self, transport_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None):
        self._transport_fn = transport_fn or self._default_transport

    def _default_transport(self, request: dict[str, Any]) -> dict[str, Any]:
        """Default fallback mock transport for standalone testing."""
        method = request.get("method")
        req_id = request.get("id", 1)

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "trip-planner-mcp", "version": "1.0.0"},
                    "capabilities": {"tools": {}}
                }
            }
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        {
                            "name": "mcp_weather_lookup",
                            "description": "Look up weather forecast via external MCP server",
                            "inputSchema": {
                                "type": "object",
                                "properties": {"city": {"type": "string"}},
                                "required": ["city"]
                            }
                        }
                    ]
                }
            }
        elif method == "tools/call":
            params = request.get("params", {})
            t_name = params.get("name")
            args = params.get("arguments", {})
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {"type": "text", "text": f"[MCP Result] Tool {t_name} executed with args {args}"}
                    ]
                }
            }
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}}

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Invokes tools/call on the MCP server."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments}
        }
        res = self._transport_fn(payload)
        if "error" in res:
            raise RuntimeError(f"MCP Error: {res['error'].get('message', 'Unknown')}")
        result = res.get("result", {})
        content = result.get("content", [])
        if content and isinstance(content, list) and "text" in content[0]:
            return content[0]["text"]
        return json.dumps(result)

    def get_tools(self) -> list[MCPToolAdapter]:
        """
        Discovers tools on the MCP server and wraps each into a CrewAI BaseTool.
        """
        list_req = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        res = self._transport_fn(list_req)
        tools_list = res.get("result", {}).get("tools", [])

        adapted_tools = []
        for t in tools_list:
            t_name = t.get("name", "unnamed_mcp_tool")
            t_desc = t.get("description", "MCP Tool")

            adapter = MCPToolAdapter(
                name=t_name,
                description=t_desc,
                mcp_call_fn=self.call_tool
            )
            adapted_tools.append(adapter)

        return adapted_tools
