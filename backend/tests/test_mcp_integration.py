
from trip_planner.mcp_server import TOOLS_REGISTRY, handle_json_rpc
from trip_planner.tools.mcp_client import MCPClient, MCPToolAdapter


def test_mcp_server_initialize():
    """
    Verifies MCP server responds to 'initialize' with 2024-11-05 protocol version.
    """
    req = {"jsonrpc": "2.0", "id": 1, "method": "initialize"}
    res = handle_json_rpc(req)
    assert res["jsonrpc"] == "2.0"
    assert res["id"] == 1
    assert res["result"]["protocolVersion"] == "2024-11-05"
    assert res["result"]["serverInfo"]["name"] == "ai-trip-planner"


def test_mcp_server_tools_list():
    """
    Verifies MCP server lists all registered tools with schemas.
    """
    req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
    res = handle_json_rpc(req)
    tools = res["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "plan_trip" in tool_names
    assert "search_transit_links" in tool_names
    assert "emergency_radar" in tool_names
    assert "get_trip_status" in tool_names


def test_mcp_server_tools_call_transit_and_radar():
    """
    Verifies MCP server executes search_transit_links and emergency_radar tools.
    """
    # 1. search_transit_links
    call_req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "search_transit_links",
            "arguments": {"origin": "Hyderabad", "destination": "Goa"}
        }
    }
    call_res = handle_json_rpc(call_req)
    text = call_res["result"]["content"][0]["text"]
    assert "ConfirmTkt" in text
    assert "RedBus" in text
    assert "Google Flights" in text

    # 2. emergency_radar
    radar_req = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "emergency_radar",
            "arguments": {"city": "Visakhapatnam"}
        }
    }
    radar_res = handle_json_rpc(radar_req)
    radar_text = radar_res["result"]["content"][0]["text"]
    assert "112" in radar_text
    assert "Hospital" in radar_text
    assert "Police" in radar_text


def test_mcp_client_adapter_connects_to_mcp_server():
    """
    Verifies that MCPClient adapter can connect to our MCP server and expose tools as CrewAI BaseTool.
    """
    # Wire client transport directly to handle_json_rpc
    client = MCPClient(transport_fn=handle_json_rpc)
    tools = client.get_tools()

    assert len(tools) == len(TOOLS_REGISTRY)
    assert all(isinstance(t, MCPToolAdapter) for t in tools)

    # Test executing a tool through the CrewAI BaseTool adapter
    transit_tool = next(t for t in tools if t.name == "search_transit_links")
    output = transit_tool._run(origin="Delhi", destination="Manali")
    assert "ConfirmTkt" in output
    assert "RedBus" in output
