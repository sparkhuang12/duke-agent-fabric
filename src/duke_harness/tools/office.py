from __future__ import annotations

import builtins
import difflib
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from backend.data_store import list_documents
from duke_harness.domain import Principal
from duke_harness.resilience.errors import ToolExecutionError


class SearchKnowledgeArgs(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    category: str = Field(default="all", max_length=80)
    limit: int = Field(default=5, ge=1, le=20)


class GetDocumentArgs(BaseModel):
    document_id: str = Field(min_length=1, max_length=128)


class CompareTextsArgs(BaseModel):
    left: str = Field(max_length=50_000)
    right: str = Field(max_length=50_000)
    context_lines: int = Field(default=3, ge=0, le=10)


class ScanSensitiveTextArgs(BaseModel):
    text: str = Field(max_length=100_000)


@dataclass(frozen=True)
class ToolExecutionContext:
    principal: Principal
    run_id: str
    agent_id: str


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    args_schema: type[BaseModel]
    handler: Callable[[BaseModel, ToolExecutionContext], dict[str, Any]]

    def as_langchain_tool(self) -> BaseTool:
        def schema_only(**_: Any) -> dict[str, Any]:
            raise RuntimeError("tools must be executed by the policy-mediated harness tool node")

        return StructuredTool.from_function(
            func=schema_only,
            name=self.name,
            description=self.description,
            args_schema=self.args_schema,
        )


class ToolRegistry:
    def __init__(self, tools: list[ToolDefinition] | None = None):
        definitions = tools or default_tools()
        self._tools = {tool.name: tool for tool in definitions}
        if len(self._tools) != len(definitions):
            raise ValueError("tool names must be unique")

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def langchain_tools(self, allowed_names: builtins.list[str]) -> builtins.list[BaseTool]:
        return [self._tools[name].as_langchain_tool() for name in allowed_names if name in self._tools]

    def invoke(self, name: str, arguments: dict[str, Any], context: ToolExecutionContext) -> dict[str, Any]:
        tool = self.get(name)
        if tool is None:
            raise ToolExecutionError(f"unknown tool: {name}")
        try:
            parsed = tool.args_schema.model_validate(arguments)
            return tool.handler(parsed, context)
        except ToolExecutionError:
            raise
        except Exception as exc:
            raise ToolExecutionError(f"tool {name} failed: {type(exc).__name__}") from exc


def _clearance_rank(clearance: str) -> int:
    return {"public": 0, "internal": 1, "confidential": 2, "secret": 3}.get(clearance.lower(), 1)


def _document_rank(level: str) -> int:
    mapping = {"公开": 0, "内部": 1, "机密": 2, "秘密": 3, "public": 0, "internal": 1, "confidential": 2, "secret": 3}
    return mapping.get(level.lower(), 1)


def _search_knowledge(args: BaseModel, context: ToolExecutionContext) -> dict[str, Any]:
    parsed = SearchKnowledgeArgs.model_validate(args)
    matches = []
    for document in list_documents():
        if _document_rank(str(document.get("security_level", "内部"))) > _clearance_rank(context.principal.clearance):
            continue
        if parsed.category != "all" and document.get("category") != parsed.category:
            continue
        haystack = " ".join(str(document.get(field, "")) for field in ("title", "summary", "content", "department"))
        if parsed.query not in haystack:
            continue
        matches.append(
            {
                "id": document["id"],
                "title": document["title"],
                "summary": document.get("summary", ""),
                "department": document.get("department", ""),
                "security_level": document.get("security_level", "内部"),
            }
        )
    return {"query": parsed.query, "total": len(matches), "items": matches[: parsed.limit]}


def _get_document(args: BaseModel, context: ToolExecutionContext) -> dict[str, Any]:
    parsed = GetDocumentArgs.model_validate(args)
    document = next((item for item in list_documents() if item.get("id") == parsed.document_id), None)
    if document is None:
        return {"found": False, "document_id": parsed.document_id}
    if _document_rank(str(document.get("security_level", "内部"))) > _clearance_rank(context.principal.clearance):
        raise ToolExecutionError("document access denied by clearance filter")
    return {"found": True, "document": document}


def _compare_texts(args: BaseModel, _: ToolExecutionContext) -> dict[str, Any]:
    parsed = CompareTextsArgs.model_validate(args)
    diff = list(
        difflib.unified_diff(
            parsed.left.splitlines(),
            parsed.right.splitlines(),
            fromfile="left",
            tofile="right",
            lineterm="",
            n=parsed.context_lines,
        )
    )
    return {"changed": bool(diff), "diff": "\n".join(diff[:2000]), "truncated": len(diff) > 2000}


def _scan_sensitive_text(args: BaseModel, _: ToolExecutionContext) -> dict[str, Any]:
    parsed = ScanSensitiveTextArgs.model_validate(args)
    patterns = {
        "phone": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
        "id_card": re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
        "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    }
    findings = [
        {"type": name, "count": len(pattern.findall(parsed.text))}
        for name, pattern in patterns.items()
        if pattern.search(parsed.text)
    ]
    return {
        "contains_sensitive_data": bool(findings),
        "findings": findings,
        "security_level": "confidential" if findings else "internal",
    }


def default_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition("search_knowledge", "检索当前用户有权访问的组织知识。", SearchKnowledgeArgs, _search_knowledge),
        ToolDefinition("get_document", "按文件 ID 读取有权访问的文件。", GetDocumentArgs, _get_document),
        ToolDefinition("compare_texts", "生成两段文本的统一差异。", CompareTextsArgs, _compare_texts),
        ToolDefinition(
            "scan_sensitive_text", "扫描手机号、身份证号和邮箱等敏感信息。", ScanSensitiveTextArgs, _scan_sensitive_text
        ),
    ]
