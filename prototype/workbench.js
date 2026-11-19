"use strict";

const el = id => document.getElementById(id);
const statusNames = {waiting_approval: "待复核", completed: "已完成", denied: "未通过", failed: "运行失败", running: "处理中", queued: "排队中"};
const examples = {
  document: "请起草一份通知，说明报送目的、所需材料和提交方式；尚未确定的联系人标为待核。",
  policy: "请根据提供的文件，核实专项经费的适用对象、申报条件和截止日期，并列明对应条款。",
  search: "请查找涉及数字政务办公的试点通知，列出文件名称、来源及相关段落。",
  meeting: "会议记录：办公室建议周五汇总需求，信息中心表示需先核对清单。会议决定由办公室牵头整理清单，完成日期另行确认。请整理纪要。",
  compare: "旧文：各单位应于每月五日前报送上月台账。\n新文：各单位应于每月十日前报送上月台账及情况说明。\n请列出变更的时限和材料。",
  review: "请审校以下通知的对象和时限是否一致。\n各直属单位：请于周三前报送清单。各处室务必于周五前完成报送。"
};
const statusHelp = {
  waiting_approval: "草稿已送复核。复核通过后，在本稿件内提交下一轮修改意见。",
  completed: "已写入本稿件上下文，可继续提出修改意见。",
  denied: "本轮未通过，未进入稿件上下文。可调整材料后重新提交。",
  failed: "本轮运行失败，未进入稿件上下文。请检查连接后重试。",
  running: "正在处理，请稍后刷新状态。",
  queued: "请求已排队，请稍后刷新状态。"
};
const legacyRoutes = ["dashboard", "agents", "knowledge", "tasks", "audit", "roadmap", "settings"];
const state = {
  config: null, session: null, agent: null, token: "", storageKey: "", index: {},
  active: null, records: new Map(), forms: new Map(), busy: false, viewing: null, epoch: 0
};

function uid() {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");
}

function notice(message = "") {
  el("pageNotice").textContent = message;
  el("pageNotice").hidden = !message;
}

let devUser;
function identityHeaders() {
  if (state.config?.auth_mode === "development_headers") {
    if (!devUser) {
      devUser = sessionStorage.getItem("duke.development-user") || "desk-" + uid();
      sessionStorage.setItem("duke.development-user", devUser);
    }
    return {"X-Duke-Tenant": "workbench", "X-Duke-User": devUser};
  }
  return state.token ? {Authorization: "Bearer " + state.token} : {};
}

async function api(path, payload) {
  const response = await fetch("/api/v1/" + path, {
    method: payload === undefined ? "GET" : "POST",
    headers: {"Content-Type": "application/json", ...identityHeaders()},
    body: payload === undefined ? undefined : JSON.stringify(payload),
    cache: "no-store"
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401) throw new Error("身份验证失败，请在连接设置中重新连接组织身份。");
    if (response.status === 403) throw new Error("当前身份没有读取或操作此稿件的权限。");
    throw new Error(data.error?.message || (typeof data.detail === "string" && data.detail) || "服务请求失败（" + response.status + "），请重试。");
  }
  return data;
}

function newFile() {
  return {id: "desk-" + uid(), runs: [], created: Date.now()};
}

function saveIndex() {
  sessionStorage.setItem(state.storageKey, JSON.stringify(state.index));
}

function stack() { return state.index[state.agent.id]; }
function hasApproved() { return !!state.active?.approved || state.active?.runs.some(id => state.records.get(id)?.status === "completed"); }
function latest() { return state.records.get(state.active?.runs.at(-1)); }
function blocked(record) { return ["waiting_approval", "running", "queued"].includes(record?.status); }

function readForm() {
  return {document_type: el("docType").value, audience: el("audience").value, materials: el("materials").value, input: el("instruction").value};
}

function retainForm() {
  if (state.active && !el("fields").disabled) state.forms.set(state.active.id, readForm());
}

function putForm() {
  const current = state.forms.get(state.active.id);
  const values = current || latest()?.metadata?.writing_brief || {};
  el("docType").value = values.document_type || "通知";
  el("audience").value = values.audience || "";
  el("materials").value = values.materials || "";
  el("instruction").value = current?.input || "";
}

function option(label, value) { return new Option(label, value); }

function renderThreadList() {
  const {files} = stack();
  el("threads").replaceChildren(...files.map((file, i) => {
    const date = new Date(file.created).toLocaleDateString("zh-CN", {month: "numeric", day: "numeric"});
    return option("稿件 " + (i + 1) + " · " + date + " · " + file.runs.length + " 轮", file.id);
  }).reverse());
  el("threads").value = state.active.id;
}

function paint() {
  const role = state.agent;
  if (!role || !state.active) return;
  const file = state.active;
  const record = latest();
  const isDoc = role.id === "document";
  const hasHistory = hasApproved();
  const unavailable = file.runs.length > 0 && !record;
  const title = role.role_title || role.name;
  el("roleTitle").textContent = title;
  el("roleDescription").textContent = role.description;
  document.title = title + " · Duke 办公写作台";
  el("deliverable").textContent = role.deliverable || role.description;
  el("boundary").textContent = role.boundary || "按授权材料处理，缺失事项请经办人确认。";
  el("formTitle").textContent = hasHistory ? "修订单" : isDoc ? "起草单" : "任务单";
  el("threadState").textContent = unavailable ? "正在读取" : statusNames[record?.status] || "新稿";
  el("briefFields").hidden = !isDoc;
  el("instructionLabel").textContent = hasHistory ? "本轮修改或补充要求" : isDoc ? "本轮起草要求" : "任务要求与材料";
  el("instruction").placeholder = hasHistory ? "指出要修改的位置、修改理由和需保留的内容。" : isDoc ? "说明行文目的，以及希望收文单位采取的行动。" : "粘贴材料，说明希望此角色处理的问题。";
  const submitNote = role.require_approval ? "提交后由另一位复核人确认。" : "本轮沿用当前角色的稿件上下文。";
  el("formNote").textContent = blocked(record) ? statusHelp[record.status] : state.session.model_configured ? submitNote : "可先填写材料，在连接设置中查看模型配置。";
  el("submitRun").textContent = state.busy ? "处理中…" : blocked(record) ? statusNames[record.status] : hasHistory ? "提交修订" : isDoc ? "生成草稿" : "提交任务";
  el("fields").disabled = state.busy || unavailable;
  el("submitRun").disabled = blocked(record) || !state.session.model_configured || unavailable;
  el("example").disabled = !!el("instruction").value.trim() || state.busy;
  el("newThread").disabled = state.busy;
  renderThreadList();
  el("threads").disabled = state.busy || stack().files.length < 2;
  el("roles").querySelectorAll("button").forEach(button => {
    button.disabled = state.busy;
    button.setAttribute("aria-pressed", String(button.value === role.id));
  });
  const visible = state.records.get(state.viewing);
  el("output").hidden = !visible;
  if (visible) {
    const round = file.runs.indexOf(visible.run_id) + 1;
    el("outputTitle").textContent = "第 " + round + " 轮 · " + (statusNames[visible.status] || visible.status);
    const feedback = visible.metadata?.approval?.comment;
    el("outputState").textContent = (statusHelp[visible.status] || "") + (feedback ? " 复核意见：" + feedback : "");
    el("draftText").textContent = ["completed", "waiting_approval"].includes(visible.status) ? visible.output || (visible.metadata?.retention?.payload_scrubbed_at ? "本轮正文已到保留期限。" : "本轮没有正文。") : "";
    el("refreshRun").disabled = state.busy;
  }
  const list = el("versions");
  list.replaceChildren();
  if (!file.runs.length) {
    const empty = document.createElement("p");
    empty.textContent = "提交后，可在这里查看每轮版本。";
    list.append(empty);
  }
  file.runs.forEach((id, i) => {
    const button = document.createElement("button");
    button.className = "version";
    button.textContent = "第 " + (i + 1) + " 轮　" + (statusNames[state.records.get(id)?.status] || "查看版本");
    button.setAttribute("aria-pressed", String(id === state.viewing));
    button.disabled = state.busy;
    button.onclick = () => viewRun(id);
    list.prepend(button);
  });
}

function remember(record) {
  state.records.set(record.run_id, record);
  if (record.status === "completed") state.active.approved = true;
  saveIndex();
}

async function viewRun(id) {
  const epoch = ++state.epoch;
  try {
    const record = await api("runs/" + encodeURIComponent(id));
    if (epoch !== state.epoch) return;
    state.viewing = id;
    remember(record);
    notice();
    paint();
    el("output").scrollIntoView({block: "nearest"});
  } catch (err) { if (epoch === state.epoch) notice(err.message); }
}

async function activate(role, fileId) {
  retainForm();
  const epoch = ++state.epoch;
  state.agent = role;
  if (!state.index[role.id]) {
    const file = newFile();
    state.index[role.id] = {files: [file], selected: file.id};
  }
  const group = stack();
  state.active = group.files.find(file => file.id === (fileId || group.selected)) || group.files[0];
  group.selected = state.active.id;
  saveIndex();
  state.viewing = state.active.runs.at(-1);
  notice();
  putForm();
  paint();
  if (state.viewing) {
    try {
      const record = await api("runs/" + encodeURIComponent(state.viewing));
      if (epoch !== state.epoch) return;
      const previouslyLoaded = !!latest();
      remember(record);
      if (!previouslyLoaded) putForm();
      paint();
    } catch (err) { if (epoch === state.epoch) notice(err.message); }
  }
}

async function connect() {
  if (state.busy) return;
  state.busy = true;
  el("reconnect").disabled = true;
  el("identityForm").querySelector("button").disabled = true;
  if (state.agent) { retainForm(); paint(); }
  const previousScope = state.storageKey;
  try {
    state.config = await api("workbench");
    el("operations").hidden = !state.config.legacy_enabled;
    const session = await api("workbench/session");
    state.storageKey = "duke.desk.v1." + session.tenant_id + "/" + session.user_id;
    state.session = session;
    if (state.storageKey !== previousScope) {
      state.agent = state.active = state.viewing = null;
      state.records.clear();
      state.forms.clear();
      state.index = JSON.parse(sessionStorage.getItem(state.storageKey) || "{}");
    }
    el("openReviews").hidden = !session.can_review;
    el("roleNav").hidden = !session.agents.length;
    el("roles").replaceChildren(...session.agents.map(role => {
      const button = document.createElement("button");
      button.value = role.id;
      button.textContent = role.role_title || role.name;
      button.onclick = () => {
        const url = new URL(location.href);
        url.searchParams.set("agent", role.id);
        history.replaceState(null, "", url);
        activate(role);
      };
      return button;
    }));
    const desired = new URLSearchParams(location.search).get("agent") || "document";
    const role = session.agents.find(item => item.id === desired) || session.agents[0];
    el("editor").querySelector(".desk").hidden = !role;
    if (role) {
      el("studioTitle").textContent = "写作工作室";
      document.querySelector(".cover-copy p").textContent = "从一份材料开始，在这里起草、复核，逐轮成稿。";
      await activate(role);
    }
    else {
      state.agent = state.active = null;
      el("studioTitle").textContent = "复核工作台";
      document.querySelector(".cover-copy p").textContent = "从「待我复核」查看分配给当前身份的稿件。";
      el("newThread").disabled = true;
    }
    el("connectionLabel").textContent = session.model_configured ? "模型已配置" : "模型待配置";
    el("connection").dataset.ready = String(session.model_configured);
    el("connectionInfo").textContent = session.model_configured ? "模型网关已配置。" : "模型网关尚未配置。你可以先填写起草单。";
    el("modelHelp").hidden = session.model_configured;
    el("identityForm").hidden = state.config.auth_mode !== "oidc";
  } catch (err) {
    ++state.epoch;
    state.session = state.agent = state.active = null;
    state.records.clear();
    state.forms.clear();
    state.storageKey = "";
    state.index = {};
    el("roles").replaceChildren();
    el("reviews").replaceChildren();
    el("openReviews").hidden = true;
    el("fields").disabled = el("newThread").disabled = el("threads").disabled = true;
    el("editor").querySelector(".desk").hidden = true;
    el("connectionLabel").textContent = "连接设置";
    el("connection").dataset.ready = "false";
    el("connectionInfo").textContent = err.message;
    el("identityForm").hidden = state.config?.auth_mode !== "oidc";
    notice(err.message);
  } finally {
    state.busy = false;
    el("reconnect").disabled = false;
    el("identityForm").querySelector("button").disabled = false;
    paint();
  }
}

let attempt = null;
async function submit(event) {
  event.preventDefault();
  if (state.busy || !state.session?.model_configured || el("submitRun").disabled) return;
  const {input, ...brief} = readForm();
  if (!input.trim()) { el("instruction").focus(); return; }
  const file = state.active;
  const payload = {agent_id: state.agent.id, thread_id: file.id, input: input.trim()};
  if (state.agent.id === "document") payload.writing_brief = brief;
  const signature = JSON.stringify(payload);
  if (attempt?.signature !== signature) attempt = {signature, key: uid()};
  payload.idempotency_key = attempt.key;
  state.busy = true;
  ++state.epoch;
  notice();
  paint();
  try {
    const record = await api("runs", payload);
    if (!file.runs.includes(record.run_id)) file.runs.push(record.run_id);
    remember(record);
    state.viewing = record.run_id;
    attempt = null;
    if (["completed", "waiting_approval"].includes(record.status)) el("instruction").value = "";
    state.forms.set(file.id, readForm());
  } catch (err) { notice(err.message); }
  finally { state.busy = false; paint(); }
  if (!el("output").hidden) el("output").scrollIntoView({block: "nearest"});
}

async function loadReviews() {
  const list = el("reviews");
  list.replaceChildren();
  el("reviewStatus").textContent = "正在读取…";
  try {
    const {items} = await api("approvals");
    el("reviewStatus").textContent = items.length ? "请选择稿件，核对正文与原始要求后作出决定。" : "当前没有需要你复核的稿件。";
    for (const run of items) {
      const item = document.createElement("details");
      item.className = "review-item";
      const summary = document.createElement("summary");
      summary.textContent = run.address.user_id + " · " + run.address.agent_id + " · " + new Date(run.created_at).toLocaleString("zh-CN");
      const body = document.createElement("pre");
      body.textContent = "原始要求\n" + run.input + "\n\n待复核正文\n" + run.output;
      const feedback = document.createElement("textarea");
      feedback.rows = 2;
      feedback.maxLength = 4000;
      const label = document.createElement("label");
      label.textContent = "复核意见（选填）";
      label.append(feedback);
      item.append(summary, body, label);
      for (const [approved, label] of [[true, "通过复核"], [false, "退回稿件"]]) {
        const button = document.createElement("button");
        button.className = approved ? "primary" : "secondary";
        button.textContent = label;
        button.onclick = async () => {
          item.querySelectorAll("button").forEach(b => b.disabled = true);
          try {
            const updated = await api("runs/" + run.run_id + "/approval", {approved, comment: feedback.value.trim()});
            await loadReviews();
            el("reviewStatus").textContent = "该稿件状态：" + (statusNames[updated.status] || updated.status);
          } catch (err) {
            el("reviewStatus").textContent = err.message;
            item.querySelectorAll("button").forEach(b => b.disabled = false);
          }
        };
        item.append(button);
      }
      list.append(item);
    }
  } catch (err) { el("reviewStatus").textContent = err.message; }
}

function start() {
  if (legacyRoutes.includes(location.hash.slice(1))) {
    location.replace("./operations.html" + location.hash);
    return;
  }
  el("compose").onsubmit = submit;
  el("instruction").oninput = () => { el("example").disabled = !!el("instruction").value.trim(); };
  el("example").onclick = () => {
    const amended = hasApproved();
    el("instruction").value = amended ? "保留已确认的事实和依据，压缩背景说明，并把责任单位和时限列在同一段。" : examples[state.agent.id] || "请基于所附材料整理一份初稿并标出待核事项。";
    if (!amended && state.agent.id === "document") {
      if (!el("audience").value) el("audience").value = "各直属单位";
      if (!el("materials").value) el("materials").value = "办公室汇总年度培训需求。请各单位于12月10日前通过内网报送需求清单，材料包含课程名称、人数和联系人。";
    }
    el("instruction").focus();
    paint();
  };
  el("newThread").onclick = () => {
    const file = newFile();
    stack().files.push(file);
    activate(state.agent, file.id);
  };
  el("threads").onchange = () => activate(state.agent, el("threads").value);
  el("refreshRun").onclick = () => viewRun(state.viewing);
  el("connection").onclick = () => el("connectionDialog").showModal();
  el("reconnect").onclick = async () => { await connect(); if (state.session) el("connectionDialog").close(); };
  el("identityForm").onsubmit = async event => {
    event.preventDefault();
    state.token = el("token").value.trim();
    el("token").value = "";
    await connect();
    if (state.session) el("connectionDialog").close();
  };
  el("openReviews").onclick = () => { el("reviewDialog").showModal(); loadReviews(); };
  document.querySelectorAll("[data-close]").forEach(button => button.onclick = () => button.closest("dialog").close());
  connect();
}
start();
