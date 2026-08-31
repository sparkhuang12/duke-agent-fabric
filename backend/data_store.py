from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("DUKE_AGENT_DATA_DIR", str(ROOT / "data"))).resolve()
TASKS_FILE = DATA_DIR / "tasks.json"
AUDIT_FILE = DATA_DIR / "audit_logs.json"
DOCUMENTS_FILE = DATA_DIR / "documents.json"


AGENTS: list[dict[str, Any]] = [
    {
        "id": "document",
        "name": "公文生成智能体",
        "icon": "文",
        "tag": "核心场景",
        "color": "#167060",
        "score": 88,
        "summary": "模板匹配、依据推荐、初稿生成、格式辅助与本地导出。",
        "desc": "围绕通知、请示、报告、函、纪要、批复、意见等常见文种，结合历史范例、政策依据和模板规则生成可审校的公文草稿。",
        "sources": ["历史公文库", "政策法规库", "模板知识库", "单位行文规则"],
        "outputs": ["公文初稿", "依据引用清单", "格式审校提示", "本地导出文件"],
        "workflow": ["识别文种和主送对象", "检索历史范例和政策依据", "按模板生成结构化初稿", "执行格式与表述审校", "人工确认后导出留痕"],
        "checks": ["文种适配", "标题结构", "政策引用", "附件说明", "成文日期"],
    },
    {
        "id": "policy",
        "name": "政策问答智能体",
        "icon": "策",
        "tag": "知识增强",
        "color": "#315e9f",
        "score": 84,
        "summary": "政策要点提炼、适用范围说明、来源引用和关联文件推荐。",
        "desc": "面向政策法规、制度规范和内部文件提供自然语言问答，并将回答绑定到来源文件和相关条款，便于人工核验。",
        "sources": ["政策法规库", "内部制度库", "公开政策资料", "版本记录"],
        "outputs": ["政策摘要", "适用范围", "来源条款", "关联文件"],
        "workflow": ["解析用户问题", "按权限召回政策片段", "重排并生成回答", "标注来源与版本", "输出核验提示"],
        "checks": ["来源可追溯", "版本有效性", "适用范围", "口径一致性"],
    },
    {
        "id": "search",
        "name": "文件检索智能体",
        "icon": "检",
        "tag": "知识复用",
        "color": "#2f8a5b",
        "score": 91,
        "summary": "全文检索、语义检索、条件筛选、权限过滤和原文定位。",
        "desc": "把分散在部门、个人和系统中的文件转化为可查、可管、可复用的组织知识，减少人工翻找和重复询问。",
        "sources": ["历史公文库", "会议资料库", "合同文本", "项目材料"],
        "outputs": ["相关文件列表", "重点段落定位", "相似材料推荐", "权限过滤结果"],
        "workflow": ["解析查询意图", "执行关键词与语义召回", "叠加元数据筛选", "进行部门权限过滤", "返回原文定位"],
        "checks": ["访问权限", "密级边界", "文件时效", "结果去重"],
    },
    {
        "id": "meeting",
        "name": "会议纪要智能体",
        "icon": "会",
        "tag": "事项沉淀",
        "color": "#b7791f",
        "score": 82,
        "summary": "议题归纳、纪要草稿、决议事项、责任单位和时间节点提取。",
        "desc": "对会议转写文本、议题材料和记录内容进行结构化整理，形成会议纪要草稿和可扩展的督办事项。",
        "sources": ["会议记录", "转写文本", "议题材料", "历史纪要模板"],
        "outputs": ["会议纪要草稿", "决议事项", "责任清单", "时限节点"],
        "workflow": ["识别会议元信息", "归纳议题和主要内容", "抽取决议事项", "匹配纪要模板", "生成待确认纪要"],
        "checks": ["参会人员", "责任主体", "完成时限", "议题完整性"],
    },
    {
        "id": "compare",
        "name": "文件分析比对智能体",
        "icon": "比",
        "tag": "风险识别",
        "color": "#6b5a9a",
        "score": 79,
        "summary": "版本差异、条款变化、政策关联、冲突提示和重点摘要。",
        "desc": "用于新旧文件、制度文件、合同文本和历史公文之间的差异识别，辅助发现口径冲突、责任变化和时间节点调整。",
        "sources": ["新旧版本文件", "政策依据", "合同条款", "历史相似文件"],
        "outputs": ["差异摘要", "条款变化", "冲突提示", "风险清单"],
        "workflow": ["解析文件结构", "对齐段落与条款", "识别差异和变化", "关联政策依据", "输出风险提示"],
        "checks": ["条款遗漏", "责任主体", "时间节点", "指标口径"],
    },
    {
        "id": "review",
        "name": "智能审校智能体",
        "icon": "审",
        "tag": "质量保障",
        "color": "#b0443e",
        "score": 86,
        "summary": "格式规范、用语规范、敏感表述、政策依据和一致性检查。",
        "desc": "围绕正式公文和政务材料进行辅助审校，发现格式、表述、引用、敏感信息和内容一致性问题。",
        "sources": ["公文处理条例", "审校规则库", "敏感词库", "模板规范"],
        "outputs": ["问题清单", "修改建议", "风险等级", "复核结论"],
        "workflow": ["识别材料类型", "执行规则和模板检查", "扫描敏感表述", "核验政策引用", "生成审校建议"],
        "checks": ["格式规范", "敏感内容", "政策依据", "表述一致性", "人工复核"],
    },
]


KNOWLEDGE_ITEMS: list[dict[str, Any]] = [
    {"id": "documents", "name": "历史公文库", "desc": "通知、请示、报告、函、纪要、批复、意见。", "value": 76, "color": "#167060", "count": 1260},
    {"id": "policy", "name": "政策法规库", "desc": "国家、省、市及行业制度规范。", "value": 82, "color": "#315e9f", "count": 480},
    {"id": "meeting", "name": "会议资料库", "desc": "会议通知、记录、纪要、议题与决议事项。", "value": 63, "color": "#b7791f", "count": 218},
    {"id": "template", "name": "模板知识库", "desc": "公文模板、报告模板、合同模板与常用表达。", "value": 71, "color": "#2f8a5b", "count": 156},
    {"id": "vector", "name": "向量知识库", "desc": "语义检索、相似材料和知识片段召回。", "value": 68, "color": "#6b5a9a", "count": 3920},
    {"id": "permission", "name": "权限知识体系", "desc": "部门、岗位、角色、密级和知识范围映射。", "value": 80, "color": "#b0443e", "count": 42},
]


DOCUMENTS: list[dict[str, Any]] = [
    {
        "id": "doc-001",
        "title": "数字政府办公智能化试点工作通知模板",
        "category": "template",
        "security_level": "内部",
        "department": "办公室综合处",
        "summary": "用于起草数字政府、办公智能化、试点建设相关通知的结构化模板。",
        "content": "包含工作目标、试点范围、任务分工、时间安排、材料报送和联系人等常用段落。",
        "created_at": "2026-05-20T09:30:00+08:00",
    },
    {
        "id": "doc-002",
        "title": "政务数据安全与权限管理规范摘编",
        "category": "policy",
        "security_level": "内部",
        "department": "信息化处",
        "summary": "整理政务数据权限、审计留痕、人工确认和边界隔离相关要求。",
        "content": "系统应按照岗位、角色、部门和密级控制访问范围，正式输出必须经过人工确认。",
        "created_at": "2026-05-21T14:20:00+08:00",
    },
    {
        "id": "doc-003",
        "title": "年度重点工作推进会会议记录",
        "category": "meeting",
        "security_level": "内部",
        "department": "督办处",
        "summary": "记录年度重点工作推进会中的责任分工、时间节点和后续督办事项。",
        "content": "会议要求各责任单位按月反馈进展，办公室负责汇总纪要并形成督办台账。",
        "created_at": "2026-05-22T16:00:00+08:00",
    },
]


STAGES: dict[str, list[list[str]]] = {
    "foundation": [
        ["建设目标", "完成平台基础环境和组织知识中枢建设，形成统一入口、基础检索、基础问答和公文辅助生成。"],
        ["关键任务", "私有化部署、安全边界配置、首批知识治理入库、基础检索问答配置、试用入口和初步培训。"],
        ["阶段成果", "形成可运行的基础版本，具备基础文件检索、政策问答和公文辅助生成能力。"],
    ],
    "core": [
        ["建设目标", "完成六大办公智能体建设，形成覆盖公文、政策、检索、纪要、比对和审校的稳定辅助能力。"],
        ["关键任务", "智能体配置开发、流程编排、权限配置、审校规则、典型业务场景测试和试运行反馈优化。"],
        ["阶段成果", "核心办公场景完成试运行，具备稳定的智能检索、辅助生成、会议纪要、文件比对和审校能力。"],
    ],
    "extension": [
        ["建设目标", "推进与现有办公系统协同，形成可持续运营和扩展的组织级智能办公能力。"],
        ["关键任务", "公文风格优化、知识库持续更新、OA 接口预留、督办闭环、数据驱动材料生成和运维移交。"],
        ["阶段成果", "形成稳定版本，具备长期知识运营、办公协同扩展、权限安全管理和持续优化能力。"],
    ],
}


BUDGETS: list[dict[str, Any]] = [
    {"label": "平台基础", "value": 95, "color": "#167060"},
    {"label": "知识底座", "value": 115, "color": "#2f8a5b"},
    {"label": "模型底座", "value": 105, "color": "#315e9f"},
    {"label": "六大智能体", "value": 170, "color": "#b7791f"},
    {"label": "工作流", "value": 75, "color": "#6b5a9a"},
    {"label": "私有化部署", "value": 100, "color": "#4f7d7a"},
    {"label": "安全权限", "value": 65, "color": "#b0443e"},
    {"label": "系统集成", "value": 40, "color": "#6d7f34"},
    {"label": "实施培训", "value": 35, "color": "#8f6b4a"},
]


ARCHITECTURE_LAYERS: list[dict[str, str]] = [
    {"name": "应用层", "desc": "六大办公智能体 / 统一办公入口", "color": "#167060"},
    {"name": "智能协同层", "desc": "工作流编排 / 人工确认 / 结果留痕", "color": "#315e9f"},
    {"name": "模型能力层", "desc": "文本生成 / 理解 / 抽取 / 审校", "color": "#b7791f"},
    {"name": "组织知识层", "desc": "公文 / 政策 / 会议 / 模板 / 向量库", "color": "#2f8a5b"},
    {"name": "基础设施层", "desc": "私有化部署 / 权限 / 审计 / 运维", "color": "#b0443e"},
]


TASKS: list[dict[str, Any]] = [
    {
        "id": "task-20260528-001",
        "title": "数字政府办公智能化试点通知",
        "agent_id": "document",
        "status": "waiting_review",
        "priority": "高",
        "owner": "办公室综合处",
        "created_at": "2026-05-28T09:00:00+08:00",
        "summary": "生成通知初稿并联动政策依据、历史模板和智能审校。",
        "steps": ["权限识别", "知识检索", "智能生成", "规则审校", "人工确认", "本地导出"],
    },
    {
        "id": "task-20260528-002",
        "title": "年度重点工作推进会纪要",
        "agent_id": "meeting",
        "status": "running",
        "priority": "中",
        "owner": "督办处",
        "created_at": "2026-05-28T10:30:00+08:00",
        "summary": "从会议记录中抽取议题、决议事项、责任单位和时间节点。",
        "steps": ["识别会议元信息", "归纳议题", "抽取决议事项", "生成纪要草稿"],
    },
]


AUDIT_LOGS: list[dict[str, str]] = [
    {"level": "success", "message": "统一身份认证已接入本地安全域"},
    {"level": "success", "message": "知识检索已执行部门权限过滤"},
    {"level": "warning", "message": "正式文件输出等待人工确认"},
    {"level": "success", "message": "操作日志已写入审计队列"},
]


STATUS_LABELS = {
    "draft": "草稿",
    "running": "处理中",
    "waiting_review": "待复核",
    "approved": "已确认",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def list_agents() -> list[dict[str, Any]]:
    return deepcopy(AGENTS)


def get_agent(agent_id: str) -> dict[str, Any] | None:
    return deepcopy(next((agent for agent in AGENTS if agent["id"] == agent_id), None))


def get_dashboard() -> dict[str, Any]:
    return {
        "metrics": [
            {"label": "办公智能体", "value": 6},
            {"label": "架构层", "value": 5},
            {"label": "建设阶段", "value": 3},
            {"label": "万元概算", "value": 800},
        ],
        "current_task": list_tasks()[0],
        "architecture": deepcopy(ARCHITECTURE_LAYERS),
        "audit": list_audit_logs(),
    }


def get_knowledge() -> list[dict[str, Any]]:
    return deepcopy(KNOWLEDGE_ITEMS)


def get_roadmap() -> dict[str, Any]:
    return {"stages": deepcopy(STAGES), "budgets": deepcopy(BUDGETS)}


def list_tasks() -> list[dict[str, Any]]:
    tasks = _load_runtime_list(TASKS_FILE, TASKS)
    for task in tasks:
        task["status_label"] = STATUS_LABELS.get(task["status"], task["status"])
    return tasks


def list_audit_logs() -> list[dict[str, str]]:
    return _load_runtime_list(AUDIT_FILE, AUDIT_LOGS)


def list_documents() -> list[dict[str, Any]]:
    return _load_runtime_list(DOCUMENTS_FILE, DOCUMENTS)


def _load_runtime_list(path: Path, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not path.exists():
        return deepcopy(fallback)
    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except json.JSONDecodeError:
        return deepcopy(fallback)
    if not isinstance(payload, list):
        return deepcopy(fallback)
    return deepcopy(payload)


def _save_runtime_list(path: Path, payload: list[dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def append_audit(level: str, message: str) -> None:
    logs = list_audit_logs()
    logs.insert(0, {"level": level, "message": message, "created_at": now_iso()})
    _save_runtime_list(AUDIT_FILE, logs[:80])


def create_document(payload: dict[str, Any]) -> dict[str, Any]:
    title = str(payload.get("title") or "").strip()
    if not title:
        raise ValueError("文件标题不能为空")
    category = str(payload.get("category") or "documents").strip()
    department = str(payload.get("department") or "未标注部门").strip()
    security_level = str(payload.get("security_level") or "内部").strip()
    summary = str(payload.get("summary") or "").strip()
    content = str(payload.get("content") or summary or title).strip()
    documents = list_documents()
    document = {
        "id": f"doc-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "title": title,
        "category": category,
        "security_level": security_level,
        "department": department,
        "summary": summary or content[:120],
        "content": content,
        "created_at": now_iso(),
    }
    documents.insert(0, document)
    _save_runtime_list(DOCUMENTS_FILE, documents)
    append_audit("success", f"知识文件已入库：{title}")
    return deepcopy(document)


def search_documents(payload: dict[str, Any]) -> dict[str, Any]:
    keyword = str(payload.get("keyword") or payload.get("q") or "").strip()
    category = str(payload.get("category") or "").strip()
    documents = list_documents()
    matched = []
    for document in documents:
        haystack = "".join(
            [
                str(document.get("title", "")),
                str(document.get("summary", "")),
                str(document.get("content", "")),
                str(document.get("department", "")),
            ]
        )
        if keyword and keyword not in haystack:
            continue
        if category and category != "all" and document.get("category") != category:
            continue
        item = deepcopy(document)
        item["score"] = _rank_document(item, keyword)
        item["matched_fields"] = _matched_fields(item, keyword)
        matched.append(item)
    matched.sort(key=lambda item: item["score"], reverse=True)
    append_audit("success", f"执行知识检索：{keyword or '全部'}")
    return {"keyword": keyword, "total": len(matched), "items": matched[:20]}


def _rank_document(document: dict[str, Any], keyword: str) -> int:
    if not keyword:
        return 1
    score = 0
    for field, weight in [("title", 8), ("summary", 4), ("content", 2), ("department", 1)]:
        score += str(document.get(field, "")).count(keyword) * weight
    return max(score, 1)


def _matched_fields(document: dict[str, Any], keyword: str) -> list[str]:
    if not keyword:
        return ["all"]
    fields = []
    for field in ["title", "summary", "content", "department"]:
        if keyword in str(document.get(field, "")):
            fields.append(field)
    return fields


def create_task(payload: dict[str, Any]) -> dict[str, Any]:
    title = str(payload.get("title") or "未命名智能体任务").strip()
    agent_id = str(payload.get("agent_id") or "document").strip()
    agent = get_agent(agent_id) or get_agent("document")
    task = {
        "id": f"task-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "title": title,
        "agent_id": agent["id"] if agent else agent_id,
        "status": "waiting_review",
        "priority": str(payload.get("priority") or "中"),
        "owner": str(payload.get("owner") or "未分配"),
        "created_at": now_iso(),
        "summary": str(payload.get("summary") or payload.get("prompt") or "等待补充任务说明。"),
        "steps": agent["workflow"] if agent else [],
    }
    tasks = _load_runtime_list(TASKS_FILE, TASKS)
    tasks.insert(0, task)
    _save_runtime_list(TASKS_FILE, tasks)
    append_audit("success", f"已创建任务：{title}")
    return deepcopy(task)


def update_task_status(task_id: str, status: str) -> dict[str, Any] | None:
    tasks = _load_runtime_list(TASKS_FILE, TASKS)
    for task in tasks:
        if task["id"] == task_id:
            task["status"] = status
            task["updated_at"] = now_iso()
            _save_runtime_list(TASKS_FILE, tasks)
            task["status_label"] = STATUS_LABELS.get(status, status)
            append_audit("success", f"任务状态已更新：{task['title']} -> {task['status_label']}")
            return deepcopy(task)
    return None
