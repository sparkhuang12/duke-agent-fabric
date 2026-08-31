from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from duke_harness.domain import Principal, new_id
from duke_harness.tools.office import ToolExecutionContext, ToolRegistry

mcp = FastMCP(
    "duke-office-tools",
    instructions=(
        "Local, read-only office tools. Identity and clearance are injected by the server process; "
        "tool arguments cannot elevate access."
    ),
)
registry = ToolRegistry()


def _execution_context() -> ToolExecutionContext:
    principal = Principal(
        tenant_id=os.environ.get("DUKE_MCP_TENANT_ID", "local"),
        user_id=os.environ.get("DUKE_MCP_USER_ID", "local-user"),
        roles=[item for item in os.environ.get("DUKE_MCP_ROLES", "user").split(",") if item],
        department=os.environ.get("DUKE_MCP_DEPARTMENT", "local"),
        clearance=os.environ.get("DUKE_MCP_CLEARANCE", "internal"),
    )
    return ToolExecutionContext(principal=principal, run_id=new_id("mcp"), agent_id="mcp-local")


@mcp.tool()
def search_knowledge(query: str, category: str = "all", limit: int = 5) -> dict[str, Any]:
    """Search documents visible to the process-bound MCP principal."""
    return registry.invoke(
        "search_knowledge",
        {"query": query, "category": category, "limit": limit},
        _execution_context(),
    )


@mcp.tool()
def get_document(document_id: str) -> dict[str, Any]:
    """Read one document if the process-bound principal has sufficient clearance."""
    return registry.invoke("get_document", {"document_id": document_id}, _execution_context())


@mcp.tool()
def compare_texts(left: str, right: str, context_lines: int = 3) -> dict[str, Any]:
    """Return a bounded unified diff for two text values."""
    return registry.invoke(
        "compare_texts",
        {"left": left, "right": right, "context_lines": context_lines},
        _execution_context(),
    )


@mcp.tool()
def scan_sensitive_text(text: str) -> dict[str, Any]:
    """Detect common Chinese phone, ID card and email patterns without returning matched values."""
    return registry.invoke("scan_sensitive_text", {"text": text}, _execution_context())


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
