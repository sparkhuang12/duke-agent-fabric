from __future__ import annotations

from duke_harness.domain import Principal
from duke_harness.tools.office import ToolExecutionContext, ToolRegistry


def test_local_tools_are_bounded_and_do_not_return_sensitive_matches() -> None:
    registry = ToolRegistry()
    context = ToolExecutionContext(
        principal=Principal(tenant_id="t", user_id="u", clearance="internal"),
        run_id="run",
        agent_id="review",
    )
    result = registry.invoke("scan_sensitive_text", {"text": "电话 13800138000，邮箱 a@example.com"}, context)
    assert result["contains_sensitive_data"] is True
    assert result["findings"] == [{"type": "phone", "count": 1}, {"type": "email", "count": 1}]
    assert "13800138000" not in str(result)


def test_compare_tool_truncates_large_diff() -> None:
    registry = ToolRegistry()
    context = ToolExecutionContext(principal=Principal(tenant_id="t", user_id="u"), run_id="r", agent_id="compare")
    result = registry.invoke("compare_texts", {"left": "a\nb", "right": "a\nc"}, context)
    assert result["changed"] is True
    assert "-b" in result["diff"]
    assert "+c" in result["diff"]
