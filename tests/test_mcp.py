from __future__ import annotations

from duke_harness.mcp.office_server import mcp


async def test_mcp_server_registers_and_executes_local_tools() -> None:
    tools = await mcp.list_tools()
    assert {tool.name for tool in tools} == {
        "search_knowledge",
        "get_document",
        "compare_texts",
        "scan_sensitive_text",
    }
    result = await mcp.call_tool("compare_texts", {"left": "a", "right": "b"})
    assert result[0][0].type == "text"
    assert result[1]["changed"] is True
