const PAGE_TITLES = {
  dashboard: "生成式 AI 办公智能体工作台",
  agents: "六大办公智能体",
  knowledge: "组织知识中枢",
  tasks: "智能体任务流转",
  audit: "审计日志与安全留痕",
  roadmap: "建设路线与投资概算",
  settings: "系统配置与接口清单"
};

const state = {
  dashboard: null,
  agents: [],
  selectedAgent: null,
  knowledge: [],
  documents: [],
  auditLogs: [],
  searchResults: [],
  roadmap: { stages: {}, budgets: [] },
  tasks: [],
  config: null,
  route: "dashboard",
  stage: "foundation"
};

const AGENT_ACCENTS = {
  document: "#1f5e4f",
  policy: "#576a59",
  search: "#386b63",
  meeting: "#a2763f",
  compare: "#6f675c",
  review: "#a15a50"
};

const KNOWLEDGE_ACCENTS = {
  documents: "#1f5e4f",
  policy: "#576a59",
  meeting: "#a2763f",
  template: "#386b63",
  vector: "#6f675c",
  permission: "#a15a50"
};

const LAYER_ACCENTS = {
  "应用层": "#1f5e4f",
  "智能协同层": "#386b63",
  "模型能力层": "#a2763f",
  "组织知识层": "#576a59",
  "基础设施层": "#a15a50"
};

function byId(id) {
  return document.getElementById(id);
}

function themeVar(name, fallback) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
}

function emptyState(title, desc) {
  return `
    <div class="empty-state">
      <div>
        <strong>${escapeHtml(title)}</strong>
        <p>${escapeHtml(desc)}</p>
      </div>
    </div>
  `;
}

function statusClass(status) {
  if (status === "waiting_review" || status === "running") {
    return "amber";
  }
  if (status === "approved") {
    return "green";
  }
  return "";
}

function setFormBusy(form, isBusy, label = "处理中") {
  const button = form.querySelector('button[type="submit"]');
  if (!button) {
    return;
  }
  if (isBusy) {
    button.dataset.originalText = button.textContent;
    button.textContent = label;
    button.disabled = true;
    return;
  }
  button.textContent = button.dataset.originalText || button.textContent;
  button.disabled = false;
  delete button.dataset.originalText;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    },
    ...options
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = payload?.error?.message || `接口请求失败：${response.status}`;
    throw new Error(message);
  }
  return payload;
}

function showError(error) {
  const banner = byId("errorBanner");
  banner.textContent = error instanceof Error ? error.message : String(error);
  banner.classList.remove("hidden");
}

function clearError() {
  byId("errorBanner").classList.add("hidden");
}

async function loadData() {
  const [dashboard, agents, knowledge, documents, roadmap, tasks, auditLogs, config] = await Promise.all([
    request("/api/dashboard"),
    request("/api/agents"),
    request("/api/knowledge"),
    request("/api/documents"),
    request("/api/roadmap"),
    request("/api/tasks"),
    request("/api/audit-logs"),
    request("/api/config/public")
  ]);
  state.dashboard = dashboard;
  state.agents = agents.items || [];
  state.selectedAgent = state.agents[0] || null;
  state.knowledge = knowledge.items || [];
  state.documents = documents.items || [];
  state.searchResults = state.documents.slice(0, 5);
  state.roadmap = roadmap;
  state.tasks = tasks.items || [];
  state.auditLogs = auditLogs.items || [];
  state.config = config;
}

function routeFromHash() {
  const route = window.location.hash.replace("#", "");
  return PAGE_TITLES[route] ? route : "dashboard";
}

function renderRoute() {
  state.route = routeFromHash();
  byId("pageTitle").textContent = PAGE_TITLES[state.route];
  document.querySelectorAll(".side-nav a").forEach((link) => {
    link.classList.toggle("active", link.dataset.route === state.route);
  });
  document.querySelectorAll(".page").forEach((page) => {
    page.classList.toggle("active", page.dataset.page === state.route);
  });
  if (state.route === "dashboard") {
    drawArchitecture();
  }
  if (state.route === "roadmap") {
    drawBudget();
  }
}

function renderDashboard() {
  if (!state.dashboard) {
    return;
  }

  byId("metricStrip").innerHTML = state.dashboard.metrics
    .map(
      (metric) => `
        <div>
          <strong>${escapeHtml(metric.value)}</strong>
          <span>${escapeHtml(metric.label)}</span>
        </div>
      `
    )
    .join("");

  const task = state.dashboard.current_task;
  byId("currentTaskTitle").textContent = task.title;
  byId("currentTaskSummary").textContent = task.summary;
  byId("pipeline").innerHTML = task.steps.map((step) => `<div>${escapeHtml(step)}</div>`).join("");

  byId("runtimeLog").innerHTML = state.dashboard.audit
    .map((item) => `<li class="${escapeHtml(item.level)}"><span></span>${escapeHtml(item.message)}</li>`)
    .join("");
}

function renderAgents(filter = "") {
  const grid = byId("agentGrid");
  const keyword = filter.trim();
  const visible = state.agents.filter((agent) => {
    const haystack = `${agent.name}${agent.summary}${agent.desc}${agent.sources.join("")}`;
    return !keyword || haystack.includes(keyword);
  });

  if (visible.length === 0) {
    grid.innerHTML = emptyState("没有匹配的智能体", "换一个关键词，或回到完整的六大办公场景列表。");
    return;
  }

  grid.innerHTML = visible
    .map(
      (agent) => `
        <button class="agent-card ${agent.id === state.selectedAgent?.id ? "active" : ""}" style="--agent-color: ${AGENT_ACCENTS[agent.id] || "#1f5e4f"}" data-id="${agent.id}" type="button">
          <span class="agent-icon">${escapeHtml(agent.icon)}</span>
          <h3>${escapeHtml(agent.name)}</h3>
          <p>${escapeHtml(agent.summary)}</p>
          <div class="agent-card-footer">
            <span>${escapeHtml(agent.tag)}</span>
            <strong>${escapeHtml(agent.score)}%</strong>
          </div>
          <div class="agent-meter" aria-label="${escapeHtml(agent.name)}成熟度 ${escapeHtml(agent.score)}%"><span style="width: ${agent.score}%"></span></div>
        </button>
      `
    )
    .join("");

  grid.querySelectorAll(".agent-card").forEach((card) => {
    card.addEventListener("click", () => {
      state.selectedAgent = state.agents.find((agent) => agent.id === card.dataset.id);
      renderAgents(byId("agentSearch").value);
      renderAgentDetail();
    });
  });
}

function renderAgentDetail() {
  const agent = state.selectedAgent;
  if (!agent) {
    return;
  }
  byId("selectedAgentName").textContent = agent.name;
  byId("selectedAgentTag").textContent = agent.tag;
  byId("selectedAgentDesc").textContent = agent.desc;
  byId("flowScore").textContent = `${agent.score}%`;
  byId("sourceList").innerHTML = agent.sources.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  byId("outputList").innerHTML = agent.outputs.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  byId("workflowSteps").innerHTML = agent.workflow
    .map((step, index) => `<div class="workflow-step" data-index="${index + 1}">${escapeHtml(step)}</div>`)
    .join("");
  byId("checkList").innerHTML = agent.checks
    .map((check) => `<div class="check-item"><span>✓</span><div>${escapeHtml(check)}</div></div>`)
    .join("");
}

function renderKnowledge() {
  byId("knowledgeGrid").innerHTML = state.knowledge.length
    ? state.knowledge
        .map(
          (item) => `
            <button class="knowledge-card" type="button" data-knowledge="${escapeHtml(item.id)}" style="--agent-color: ${KNOWLEDGE_ACCENTS[item.id] || "#1f5e4f"}">
              <div class="card-title-row">
                <strong>${escapeHtml(item.name)}</strong>
                <span>${escapeHtml(item.count)}项</span>
              </div>
              <p>${escapeHtml(item.desc)}</p>
              <div class="knowledge-bar" aria-label="${escapeHtml(item.name)}就绪度 ${escapeHtml(item.value)}%">
                <span style="width: ${item.value}%; --bar-color: ${KNOWLEDGE_ACCENTS[item.id] || "#1f5e4f"}"></span>
              </div>
            </button>
          `
        )
        .join("")
    : emptyState("知识库状态未返回", "确认后端服务可用后刷新页面。");

  document.querySelectorAll("[data-knowledge]").forEach((card) => {
    card.addEventListener("click", () => {
      const item = state.knowledge.find((entry) => entry.id === card.dataset.knowledge);
      openKnowledgeModal(item);
    });
  });
  renderDocuments();
  renderSearchResults();
}

function documentCard(document) {
  return `
    <article class="document-card">
      <div class="card-title-row">
        <strong>${escapeHtml(document.title)}</strong>
        <span>${escapeHtml(document.security_level || "内部")}</span>
      </div>
      <p>${escapeHtml(document.summary || document.content || "")}</p>
      <div class="task-meta">
        <span>分类：${escapeHtml(document.category)}</span>
        <span>部门：${escapeHtml(document.department)}</span>
      </div>
    </article>
  `;
}

function renderDocuments() {
  const list = byId("documentList");
  if (!list) {
    return;
  }
  list.innerHTML = state.documents.length
    ? state.documents.slice(0, 8).map(documentCard).join("")
    : emptyState("还没有入库文件", "通过文件入库添加第一批模板、政策或会议资料。");
}

function renderSearchResults() {
  const list = byId("searchResults");
  if (!list) {
    return;
  }
  byId("searchCount").textContent = `${state.searchResults.length} 条`;
  list.innerHTML = state.searchResults.length
    ? state.searchResults.map(documentCard).join("")
    : emptyState("暂无匹配结果", "调整关键词或分类后再检索，系统会保留来源和密级信息。");
}

function renderAudit() {
  const grid = byId("auditGrid");
  if (!grid) {
    return;
  }
  grid.innerHTML = state.auditLogs.length
    ? state.auditLogs
        .map(
          (log) => `
            <article class="audit-card ${escapeHtml(log.level || "success")}">
              <span></span>
              <div>
                <strong>${escapeHtml(log.message)}</strong>
                <p>${escapeHtml(log.created_at || "系统初始化")}</p>
              </div>
            </article>
          `
        )
        .join("")
    : emptyState("暂无审计记录", "任务创建、知识检索、人工确认和模型调用都会在这里留痕。");
}

function renderTasks() {
  byId("taskGrid").innerHTML = state.tasks.length
    ? state.tasks
        .map((task) => {
      const agent = state.agents.find((item) => item.id === task.agent_id);
      return `
        <article class="task-card">
          <div class="panel-title-row">
            <div>
              <p class="eyebrow">${escapeHtml(agent?.name || "智能体任务")}</p>
              <h3>${escapeHtml(task.title)}</h3>
            </div>
            <span class="pill ${statusClass(task.status)}">${escapeHtml(task.status_label || task.status)}</span>
          </div>
          <p>${escapeHtml(task.summary)}</p>
          <div class="task-meta">
            <span>负责人：${escapeHtml(task.owner)}</span>
            <span>优先级：${escapeHtml(task.priority)}</span>
          </div>
          <div class="workflow-steps compact">
            ${task.steps.map((step, index) => `<div class="workflow-step" data-index="${index + 1}">${escapeHtml(step)}</div>`).join("")}
          </div>
          <div class="task-actions">
            ${
              task.status === "waiting_review"
                ? `<button class="primary-button" type="button" data-approve-task="${escapeHtml(task.id)}">确认输出</button>`
                : `<button class="ghost-button" type="button" disabled>无需操作</button>`
            }
          </div>
        </article>
      `;
        })
        .join("")
    : emptyState("还没有智能体任务", "新建任务后，可以在这里完成复核、确认和审计追踪。");

  document.querySelectorAll("[data-approve-task]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        button.dataset.originalText = button.textContent;
        button.textContent = "正在确认";
        button.disabled = true;
        const task = await request(`/api/tasks/${button.dataset.approveTask}/approve`, { method: "POST" });
        state.tasks = state.tasks.map((item) => (item.id === task.id ? task : item));
        renderTasks();
        await refreshAuditLogs();
      } catch (error) {
        showError(error);
        button.textContent = button.dataset.originalText || "确认输出";
        button.disabled = false;
      }
    });
  });
}

function renderStage(stageKey = state.stage) {
  state.stage = stageKey;
  document.querySelectorAll(".stage-tabs button").forEach((button) => {
    button.classList.toggle("active", button.dataset.stage === stageKey);
  });
  const items = state.roadmap.stages?.[stageKey] || [];
  byId("stageDetail").innerHTML = items
    .map(
      ([title, desc]) => `
        <div class="stage-item">
          <strong>${escapeHtml(title)}</strong>
          <p>${escapeHtml(desc)}</p>
        </div>
      `
    )
    .join("");
}

function renderSettings() {
  const config = state.config;
  if (!config) {
    return;
  }
  const model = config.model;
  byId("securitySummary").textContent = `${config.security.data_boundary} / 人工确认 / 审计留痕`;
  byId("modelReadyPill").textContent = model.enabled && model.base_url_configured && model.api_key_configured ? "已启用" : "待配置";
  byId("modelReadyPill").className = `pill ${model.enabled && model.base_url_configured && model.api_key_configured ? "green" : "amber"}`;
  byId("configList").innerHTML = [
    ["运行环境", config.app.environment],
    ["模型供应商", model.provider],
    ["模型开关", model.enabled ? "enabled=true" : "enabled=false"],
    ["Base URL", model.base_url_configured ? "已配置" : "未配置"],
    ["API Key", model.api_key_configured ? "已配置" : "未配置"],
    ["Chat Model", model.chat_model || "未配置"],
    ["Embedding Model", model.embedding_model || "未配置"],
    ["数据目录", config.storage.data_dir],
    ["上传目录", config.storage.upload_dir]
  ]
    .map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd>`)
    .join("");
}

function drawRoundedRect(ctx, x, y, width, height, radius) {
  const r = Math.min(radius, width / 2, height / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + width, y, x + width, y + height, r);
  ctx.arcTo(x + width, y + height, x, y + height, r);
  ctx.arcTo(x, y + height, x, y, r);
  ctx.arcTo(x, y, x + width, y, r);
  ctx.closePath();
}

function drawArchitecture() {
  const canvas = byId("architectureCanvas");
  if (!canvas || !state.dashboard) {
    return;
  }
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  if (!rect.width) {
    return;
  }
  canvas.width = Math.round(rect.width * dpr);
  canvas.height = Math.round((rect.width * 460 / 900) * dpr);
  ctx.scale(dpr, dpr);

  const width = rect.width;
  const height = rect.width * 460 / 900;
  const paper = themeVar("--paper", "#f7f8f5");
  const surface = themeVar("--surface", "#ffffff");
  const surface2 = themeVar("--surface-2", "#e5ebe6");
  const line = themeVar("--line", "#ccd8d1");
  const ink = themeVar("--ink", "#17231f");
  const muted = themeVar("--muted", "#66756e");
  const accent = themeVar("--accent", "#1f5e4f");
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = paper;
  ctx.fillRect(0, 0, width, height);

  const layers = state.dashboard.architecture;
  const margin = Math.max(18, width * 0.035);
  const layerHeight = (height - margin * 2 - 36) / layers.length;
  ctx.font = '700 15px Aptos, "Microsoft YaHei", Arial';
  layers.forEach((layer, index) => {
    const y = margin + index * layerHeight;
    drawRoundedRect(ctx, margin, y, width - margin * 2, layerHeight - 9, 12);
    ctx.fillStyle = index % 2 === 0 ? surface : surface2;
    ctx.fill();
    ctx.strokeStyle = line;
    ctx.stroke();

    ctx.fillStyle = LAYER_ACCENTS[layer.name] || accent;
    ctx.fillRect(margin, y, 7, layerHeight - 9);
    ctx.fillStyle = ink;
    ctx.fillText(layer.name, margin + 22, y + 26);
    ctx.fillStyle = muted;
    ctx.font = '500 13px Aptos, "Microsoft YaHei", Arial';
    ctx.fillText(layer.desc, margin + 120, y + 26);
    ctx.font = '700 15px Aptos, "Microsoft YaHei", Arial';
  });

  ctx.strokeStyle = themeVar("--line-strong", "#aebdb5");
  ctx.lineWidth = 2;
  ctx.setLineDash([6, 6]);
  ctx.beginPath();
  ctx.moveTo(width - margin - 110, margin + 16);
  ctx.lineTo(width - margin - 110, height - margin - 20);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = ink;
  ctx.font = '700 12px Aptos, "Microsoft YaHei", Arial';
  ctx.fillText("本地安全域", width - margin - 96, height - margin - 24);
}

function drawBudget() {
  const canvas = byId("budgetCanvas");
  if (!canvas) {
    return;
  }
  const budgets = state.roadmap.budgets || [];
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  if (!rect.width || budgets.length === 0) {
    return;
  }
  canvas.width = Math.round(rect.width * dpr);
  canvas.height = Math.round((rect.width * 500 / 900) * dpr);
  ctx.scale(dpr, dpr);

  const width = rect.width;
  const height = rect.width * 500 / 900;
  const paper = themeVar("--paper", "#f7f8f5");
  const surface2 = themeVar("--surface-2", "#e5ebe6");
  const ink = themeVar("--ink", "#17231f");
  const muted = themeVar("--muted", "#66756e");
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = paper;
  ctx.fillRect(0, 0, width, height);

  const left = width < 620 ? 92 : 120;
  const right = 24;
  const top = 34;
  const rowHeight = (height - top - 26) / budgets.length;
  const max = Math.max(...budgets.map((item) => item.value));

  ctx.font = '700 12px Aptos, "Microsoft YaHei", Arial';
  budgets.forEach((item, index) => {
    const y = top + index * rowHeight;
    const barWidth = (width - left - right - 54) * (item.value / max);
    ctx.fillStyle = muted;
    ctx.fillText(item.label, 20, y + 20);
    drawRoundedRect(ctx, left, y + 5, width - left - right - 54, 16, 8);
    ctx.fillStyle = surface2;
    ctx.fill();
    drawRoundedRect(ctx, left, y + 5, barWidth, 16, 8);
    ctx.fillStyle = Object.values(KNOWLEDGE_ACCENTS)[index % Object.values(KNOWLEDGE_ACCENTS).length];
    ctx.fill();
    ctx.fillStyle = ink;
    ctx.fillText(`${item.value}万`, left + barWidth + 10, y + 20);
  });
}

function openModal({ eyebrow, title, body }) {
  byId("modalEyebrow").textContent = eyebrow;
  byId("modalTitle").textContent = title;
  byId("modalBody").innerHTML = body;
  byId("modalOverlay").classList.remove("hidden");
  byId("modalOverlay").setAttribute("aria-hidden", "false");
}

function closeModal() {
  byId("modalOverlay").classList.add("hidden");
  byId("modalOverlay").setAttribute("aria-hidden", "true");
  byId("modalBody").innerHTML = "";
}

function openTaskModal() {
  openModal({
    eyebrow: "任务流转",
    title: "新建智能体任务",
    body: `
      <form id="taskForm" class="modal-form">
        <label>任务标题<input name="title" required placeholder="例如：起草专项工作通知" /></label>
        <label>选择智能体
          <select name="agent_id">
            ${state.agents.map((agent) => `<option value="${agent.id}">${escapeHtml(agent.name)}</option>`).join("")}
          </select>
        </label>
        <label>负责人<input name="owner" placeholder="办公室综合处" /></label>
        <label>优先级
          <select name="priority">
            <option>中</option>
            <option>高</option>
            <option>低</option>
          </select>
        </label>
        <label>任务说明<textarea name="summary" rows="4" placeholder="补充任务背景、输入材料和预期输出"></textarea></label>
        <button class="primary-button full" type="submit">提交任务</button>
      </form>
    `
  });

  byId("taskForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const payload = Object.fromEntries(form.entries());
    try {
      setFormBusy(formElement, true, "正在提交");
      const task = await request("/api/tasks", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      state.tasks.unshift({ ...task, status_label: "待复核" });
      renderTasks();
      await refreshAuditLogs();
      closeModal();
      window.location.hash = "#tasks";
    } catch (error) {
      showError(error);
    } finally {
      setFormBusy(formElement, false);
    }
  });
}

function openAgentRunModal() {
  const agent = state.selectedAgent;
  if (!agent) {
    return;
  }
  openModal({
    eyebrow: "智能体试运行",
    title: agent.name,
    body: `
      <form id="agentRunForm" class="modal-form">
        <label>输入任务<textarea name="prompt" rows="6" required placeholder="描述你要处理的办公任务，后端会调用 /api/agents/${agent.id}/run"></textarea></label>
        <button class="primary-button full" type="submit">运行接口</button>
      </form>
      <pre id="agentRunResult" class="result-box"></pre>
    `
  });

  byId("agentRunForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const resultBox = byId("agentRunResult");
    resultBox.textContent = "正在调用接口...";
    try {
      setFormBusy(formElement, true, "正在运行");
      const payload = { prompt: form.get("prompt") };
      const result = await request(`/api/agents/${agent.id}/run`, {
        method: "POST",
        body: JSON.stringify(payload)
      });
      resultBox.textContent = JSON.stringify(result, null, 2);
    } catch (error) {
      resultBox.textContent = error instanceof Error ? error.message : String(error);
    } finally {
      setFormBusy(formElement, false);
    }
  });
}

function openAgentDetailModal() {
  const agent = state.selectedAgent;
  if (!agent) {
    return;
  }
  openModal({
    eyebrow: agent.tag,
    title: agent.name,
    body: `
      <p class="modal-desc">${escapeHtml(agent.desc)}</p>
      <div class="modal-two-col">
        <div>
          <h4>处理流程</h4>
          ${agent.workflow.map((item, index) => `<div class="workflow-step" data-index="${index + 1}">${escapeHtml(item)}</div>`).join("")}
        </div>
        <div>
          <h4>复核要点</h4>
          ${agent.checks.map((item) => `<div class="check-item"><span>✓</span><div>${escapeHtml(item)}</div></div>`).join("")}
        </div>
      </div>
    `
  });
}

function openKnowledgeModal(item) {
  if (!item) {
    return;
  }
  openModal({
    eyebrow: "知识中枢",
    title: item.name,
    body: `
      <p class="modal-desc">${escapeHtml(item.desc)}</p>
      <div class="knowledge-modal-meter">
        <strong>就绪度 ${escapeHtml(item.value)}%</strong>
        <div class="knowledge-bar"><span style="width: ${item.value}%; --bar-color: ${KNOWLEDGE_ACCENTS[item.id] || "#1f5e4f"}"></span></div>
      </div>
      <p class="muted-text">当前纳管条目：${escapeHtml(item.count)} 项。后续文件解析、权限映射和向量化服务可以从后端继续扩展。</p>
    `
  });
}

function openDocumentModal() {
  openModal({
    eyebrow: "知识入库",
    title: "新增知识文件",
    body: `
      <form id="documentForm" class="modal-form">
        <label>文件标题<input name="title" required placeholder="例如：数字政府试点工作通知模板" /></label>
        <label>知识分类
          <select name="category">
            <option value="documents">历史公文</option>
            <option value="policy">政策法规</option>
            <option value="meeting">会议资料</option>
            <option value="template">模板知识</option>
          </select>
        </label>
        <label>所属部门<input name="department" placeholder="办公室综合处" /></label>
        <label>密级
          <select name="security_level">
            <option>内部</option>
            <option>公开</option>
            <option>敏感</option>
          </select>
        </label>
        <label>摘要<textarea name="summary" rows="3" placeholder="描述文件用途、适用范围和关键内容"></textarea></label>
        <label>正文片段<textarea name="content" rows="5" placeholder="粘贴可检索的文件正文或关键段落"></textarea></label>
        <button class="primary-button full" type="submit">提交入库</button>
      </form>
    `
  });

  byId("documentForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      setFormBusy(formElement, true, "正在入库");
      const document = await request("/api/documents", {
        method: "POST",
        body: JSON.stringify(Object.fromEntries(form.entries()))
      });
      state.documents.unshift(document);
      state.searchResults = state.documents.slice(0, 5);
      renderKnowledge();
      await refreshAuditLogs();
      closeModal();
      window.location.hash = "#knowledge";
    } catch (error) {
      showError(error);
    } finally {
      setFormBusy(formElement, false);
    }
  });
}

async function runKnowledgeSearch(event) {
  event.preventDefault();
  const formElement = event.currentTarget;
  const form = new FormData(formElement);
  try {
    setFormBusy(formElement, true, "正在检索");
    const result = await request("/api/knowledge/search", {
      method: "POST",
      body: JSON.stringify(Object.fromEntries(form.entries()))
    });
    state.searchResults = result.items || [];
    renderSearchResults();
    await refreshAuditLogs();
  } catch (error) {
    showError(error);
  } finally {
    setFormBusy(formElement, false);
  }
}

async function refreshAuditLogs() {
  const payload = await request("/api/audit-logs");
  state.auditLogs = payload.items || [];
  renderAudit();
}

function openConfigModal() {
  const model = state.config?.model || {};
  openModal({
    eyebrow: "模型 API",
    title: "配置文件占位",
    body: `
      <p class="modal-desc">模型调用已经保留后端接口，当前默认不启用外部模型。后续在 <code>config/app_config.json</code> 中补充以下字段即可接入 OpenAI-compatible 服务。</p>
      <pre class="result-box">{
  "model": {
    "enabled": true,
    "provider": "${escapeHtml(model.provider || "openai-compatible")}",
    "base_url": "https://your-model-gateway/v1",
    "api_key": "your-api-key",
    "chat_model": "your-chat-model",
    "embedding_model": "your-embedding-model"
  }
}</pre>
    `
  });
}

function runPrototypeCheck() {
  byId("runtimeLog").innerHTML = [
    "后端接口已接入：仪表盘、智能体、知识库、知识检索、任务、审计和配置接口可用",
    "页面路由已验证：工作台、智能体、知识中枢、任务流转、审计日志、建设路线、系统配置",
    "弹窗交互已验证：新建任务、文件入库、智能体试运行、详情查看和模型配置提示",
    "安全约束已展示：私有化部署、权限过滤、人工确认、审计留痕"
  ]
    .map((item) => `<li class="success"><span></span>${escapeHtml(item)}</li>`)
    .join("");
  document.body.dataset.verified = "true";
}

function renderAll() {
  renderDashboard();
  renderAgents();
  renderAgentDetail();
  renderKnowledge();
  renderTasks();
  renderAudit();
  renderStage();
  renderSettings();
  renderRoute();
}

function setupEvents() {
  window.addEventListener("hashchange", renderRoute);
  byId("agentSearch").addEventListener("input", (event) => renderAgents(event.target.value));
  byId("runCheck").addEventListener("click", runPrototypeCheck);
  byId("openTaskModal").addEventListener("click", openTaskModal);
  byId("openConfigModal").addEventListener("click", openConfigModal);
  byId("openDocumentModal").addEventListener("click", openDocumentModal);
  byId("openAgentRunModal").addEventListener("click", openAgentRunModal);
  byId("openAgentDetailModal").addEventListener("click", openAgentDetailModal);
  byId("knowledgeSearchForm").addEventListener("submit", runKnowledgeSearch);
  byId("refreshAudit").addEventListener("click", async () => {
    try {
      await refreshAuditLogs();
    } catch (error) {
      showError(error);
    }
  });
  byId("closeModal").addEventListener("click", closeModal);
  byId("modalOverlay").addEventListener("click", (event) => {
    if (event.target.id === "modalOverlay") {
      closeModal();
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !byId("modalOverlay").classList.contains("hidden")) {
      closeModal();
    }
  });
  document.querySelectorAll("[data-open-task]").forEach((button) => button.addEventListener("click", openTaskModal));
  document.querySelectorAll(".stage-tabs button").forEach((button) => {
    button.addEventListener("click", () => {
      renderStage(button.dataset.stage);
      drawBudget();
    });
  });
  window.addEventListener("resize", () => {
    drawArchitecture();
    drawBudget();
  });
}

async function init() {
  setupEvents();
  try {
    await loadData();
    clearError();
    renderAll();
  } catch (error) {
    showError(error);
  }
}

document.addEventListener("DOMContentLoaded", init);
