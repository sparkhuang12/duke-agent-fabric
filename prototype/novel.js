import {chapter, chapterLabel, listBooks, newBook, notesAt, openLibrary, sampleBook, saveBook, storyPrompt, uid} from "./novel-library.mjs";

const $ = id => document.getElementById(id);
const panel = $("panel");
const state = {book: null, chapterId: "", db: null, scope: "", session: null, auth: "", token: "", dev: "", dirty: false, saving: null, version: 0, panelEpoch: 0};

function message(text = "") {
  $("notice").textContent = text;
  $("notice").hidden = !text;
}

function element(tag, text = "", className = "") {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
}

function action(text, fn, className = "quiet") {
  const button = element("button", text, className);
  button.type = "button";
  button.onclick = async () => {
    button.disabled = true;
    try { await fn(); } catch (error) { report(error); }
    finally { button.disabled = false; }
  };
  return button;
}

function report(error) {
  const text = error.message || String(error);
  if (!panel.open) return message(text);
  let notice = panel.querySelector('[role="alert"]');
  if (!notice) {
    notice = element("p");
    notice.setAttribute("role", "alert");
    $("panelBody").prepend(notice);
  }
  notice.textContent = text;
}

function openPanel(title) {
  state.panelEpoch++;
  $("panelTitle").textContent = title;
  $("panelBody").replaceChildren();
  if (!panel.open) panel.showModal();
  return $("panelBody");
}

function field(form, labelText, value = "", type = "input", max = 150) {
  const label = element("label", labelText);
  const input = document.createElement(type);
  input.value = value;
  input.maxLength = max;
  label.append(input);
  form.append(label);
  return input;
}

function submitForm(form, caption, fn) {
  const submit = element("button", caption, "primary");
  submit.type = "submit";
  form.append(submit);
  form.onsubmit = async event => {
    event.preventDefault();
    if (submit.disabled) return;
    submit.disabled = true;
    try { await fn(); } catch (error) { report(error); }
    finally { submit.disabled = false; }
  };
}

function currentIndex() { return state.book.chapters.findIndex(ch => ch.id === state.chapterId); }
function current() { return state.book.chapters[currentIndex()]; }
function viewKey() { return "duke.novel.view." + state.scope; }

function rememberView() {
  try { localStorage.setItem(viewKey(), JSON.stringify([state.book.id, state.chapterId])); }
  catch { /* The manuscript itself is saved through IndexedDB. */ }
}

function resizeEditor() {
  const editor = $("chapterBody");
  editor.style.height = "auto";
  editor.style.height = Math.min(editor.scrollHeight + 2, Math.max(450, window.innerHeight * .83)) + "px";
}

function counts() {
  $("count").textContent = "正文 · " + (current().body.match(/[\p{L}\p{N}]/gu) || []).length + " 字";
  resizeEditor();
}

function setActive(book, chapterId) {
  state.book = book;
  state.chapterId = book.chapters.some(ch => ch.id === chapterId) ? chapterId : book.chapters[0].id;
  if (state.scope) rememberView();
  render();
}

function render() {
  const book = state.book;
  const index = currentIndex();
  $("bookTitle").textContent = book.title;
  $("volumeName").textContent = book.volume;
  document.title = book.title + " · 山海手卷";
  $("chapterTitle").textContent = current().title;
  $("chapterNumber").textContent = chapterLabel(book, index);
  $("chapterBody").value = current().body;
  $("chapterBody").disabled = !state.scope;
  for (const id of ["addChapter", "castTab", "clueTab", "shelf", "chapterSettings", "check", "continue"]) $(id).disabled = !state.scope;
  $("chapters").replaceChildren();
  $("chapterPicker").replaceChildren();
  book.chapters.forEach((ch, i) => {
    const entry = action("", () => selectChapter(ch.id), "entry");
    entry.append(element("small", chapterLabel(book, i)), element("strong", ch.title));
    if (i === index) entry.setAttribute("aria-current", "true");
    $("chapters").append(entry);
    $("chapterPicker").add(new Option(chapterLabel(book, i) + "　" + ch.title, ch.id, false, i === index));
  });
  const notes = notesAt(book, index);
  for (const [key, target, items, empty] of [["cast", "sideCast", notes.cast, "尚未设定人物"], ["clues", "sideClues", notes.clues.filter(n => !n.closed), "暂无未解伏笔"]]) {
    const side = $(target);
    side.replaceChildren();
    if (!items.length) side.append(element("p", empty));
    for (const n of items) {
      const button = action(n.name, () => editNote(key, n.id), "");
      button.disabled = !state.scope;
      side.append(button, element("p", n.detail));
    }
  }
  counts();
}

async function writeChanges() {
  while (state.dirty) {
    const version = state.version;
    const saved = await saveBook(state.db, state.scope, structuredClone(state.book));
    state.book.revision = saved.book.revision;
    if (saved.conflict) {
      state.book.id = saved.book.id;
      state.book.title = saved.book.title;
      $("bookTitle").textContent = saved.book.title;
      document.title = saved.book.title + " · 山海手卷";
      rememberView();
      message("另一窗口也修改了本书，已将此窗口的编辑保存为独立副本。两份书稿均可在书架打开。");
    }
    if (state.version === version) state.dirty = false;
  }
  $("saveState").textContent = "本机已存";
}

async function flush() {
  if (!state.dirty && !state.saving) return;
  if (!state.saving) {
    state.saving = writeChanges().catch(() => {
      $("saveState").textContent = "保存失败";
      throw new Error("本机保存失败。请在书架导出当前手稿，检查浏览器存储空间后再试。");
    }).finally(() => { state.saving = null; });
  }
  return state.saving;
}

function changed() {
  state.version++;
  state.dirty = true;
  $("saveState").textContent = "保存中";
  return flush();
}

async function selectChapter(id) {
  if (!state.scope) return;
  await flush();
  setActive(state.book, id);
}

function exportBook() {
  const b = state.book;
  const parts = [b.title, b.volume];
  b.chapters.forEach((ch, i) => parts.push(chapterLabel(b, i) + "　" + ch.title, ch.body, ch.summary && "提要：" + ch.summary));
  parts.push("人物", ...b.cast.map(n => [n.name, n.detail, n.motive, n.ties].filter(Boolean).join(" / ")));
  const when = id => b.chapters.find(ch => ch.id === id)?.title || "全书";
  parts.push("伏笔", ...b.clues.map(n => [n.name, n.detail, "埋下：" + when(n.from), n.resolved ? "回收：" + when(n.resolved) : "未解"].join(" / ")));
  const url = URL.createObjectURL(new Blob([parts.filter(Boolean).join("\n\n")], {type: "text/plain;charset=utf-8"}));
  const a = element("a");
  a.href = url;
  a.download = b.title + ".txt";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function shelf() {
  const body = openPanel("作品书架");
  body.append(element("p", "书稿保存在当前浏览器，清理站点数据前可导出手稿。"));
  const list = element("div", "", "records");
  const tools = element("div", "", "actions");
  tools.append(action("新建作品", () => bookForm(true), "primary"), action("修改书名与卷名", () => bookForm(false)), action("导出当前手稿", exportBook));
  body.append(list, tools);
  await flush();
  const books = await listBooks(state.db, state.scope);
  for (const book of books) {
    const entry = action("", async () => {
      await flush();
      const latest = (await listBooks(state.db, state.scope)).find(b => b.id === book.id);
      setActive(latest, book.id === state.book.id ? state.chapterId : null);
      panel.close();
    }, "record");
    entry.append(element("strong", book.title), element("small", (book.id === state.book.id ? "当前作品 · " : "") + book.chapters.length + " 个章节"));
    list.append(entry);
  }
}

function bookForm(create) {
  const body = openPanel(create ? "新建作品" : "修改作品");
  const form = element("form", "", "dialog-form");
  body.append(form);
  const title = field(form, "书名", create ? "" : state.book.title, "input", 80);
  const volume = field(form, "卷名（选填）", create ? "" : state.book.volume, "input", 80);
  title.required = true;
  submitForm(form, create ? "开始写作" : "保存作品", async () => {
    if (!title.value.trim()) throw new Error("请填写书名。");
    await flush();
    if (create) {
      const saved = await saveBook(state.db, state.scope, newBook(title.value.trim(), volume.value.trim()));
      setActive(saved.book);
    } else {
      Object.assign(state.book, {title: title.value.trim(), volume: volume.value.trim()});
      await changed(); render();
    }
    panel.close();
  });
}

function chapterForm(create) {
  const body = openPanel(create ? "新建章节" : "章节设置");
  const form = element("form", "", "dialog-form");
  body.append(form);
  const title = field(form, "章名", create ? "" : current().title);
  title.required = true;
  const summary = field(form, "前情提要（选填，供后续章回引用）", create ? "" : current().summary, "textarea", 1500);
  submitForm(form, create ? "添加章节" : "保存章节", async () => {
    if (!title.value.trim()) throw new Error("请填写章名。");
    if (create) {
      const ch = chapter(title.value.trim(), "", summary.value.trim());
      state.book.chapters.push(ch);
      state.chapterId = ch.id;
    } else Object.assign(current(), {title: title.value.trim(), summary: summary.value.trim()});
    await changed(); setActive(state.book, state.chapterId); panel.close(); $("chapterBody").focus();
  });
}

function notebook(key) {
  const cast = key === "cast";
  const body = openPanel(cast ? "人物册" : "伏笔簿");
  const list = element("div", "", "records");
  body.append(list, action(cast ? "添加人物" : "埋下伏笔", () => editNote(key), "primary"));
  if (!state.book[key].length) list.append(element("p", cast ? "还没有人物设定。" : "还没有记录伏笔。"));
  for (const n of state.book[key]) {
    const entry = action("", () => editNote(key, n.id), "record");
    entry.append(element("strong", n.name), element("small", (cast ? "" : n.resolved ? "已安排回收 · " : "未解 · ") + n.detail));
    list.append(entry);
  }
}

function chapterSelect(form, label, first, value) {
  const node = element("label", label);
  const select = element("select");
  select.add(new Option(first, ""));
  state.book.chapters.forEach((ch, i) => select.add(new Option(chapterLabel(state.book, i) + "　" + ch.title, ch.id)));
  select.value = value || "";
  node.append(select);
  form.append(node);
  return select;
}

function editNote(key, id) {
  const cast = key === "cast";
  const n = state.book[key].find(note => note.id === id);
  const body = openPanel(cast ? "人物设定" : "伏笔设定");
  const form = element("form", "", "dialog-form");
  body.append(form);
  const name = field(form, cast ? "姓名" : "线索名称", n?.name, "input", 70);
  name.required = true;
  const detail = field(form, cast ? "身份与特征" : "线索与疑问", n?.detail, "textarea", 1000);
  const motive = cast && field(form, "动机与顾虑", n?.motive, "textarea", 700);
  const ties = cast && field(form, "人物关系", n?.ties, "textarea", 700);
  const from = chapterSelect(form, cast ? "从哪一章出场" : "从哪一章埋下", "全书", n ? n.from : state.chapterId);
  const resolved = !cast && chapterSelect(form, "在哪一章回收", "尚未回收", n?.resolved);
  submitForm(form, "保存设定", async () => {
    if (!name.value.trim()) throw new Error("请填写名称。");
    const index = value => state.book.chapters.findIndex(ch => ch.id === value);
    if (resolved?.value && index(resolved.value) < index(from.value)) throw new Error("回收章节须在埋下伏笔的章节之后或同一章。");
    const note = {id: id || uid(), name: name.value.trim(), detail: detail.value.trim(), from: from.value};
    if (cast) Object.assign(note, {motive: motive.value.trim(), ties: ties.value.trim()});
    else note.resolved = resolved.value;
    if (n) Object.assign(n, note); else state.book[key].push(note);
    await changed(); render(); notebook(key);
  });
}

async function api(path, payload) {
  const headers = {"Content-Type": "application/json"};
  if (state.auth === "development_headers") {
    headers["X-Duke-Tenant"] = "workbench";
    headers["X-Duke-User"] = state.dev;
  } else if (state.token) headers.Authorization = "Bearer " + state.token;
  const response = await fetch("/api/v1/" + path, {
    method: payload === undefined ? "GET" : "POST", headers, cache: "no-store",
    body: payload === undefined ? undefined : JSON.stringify(payload)
  });
  if (response.status === 401) throw new Error("请在连接设置中验证当前身份。");
  if (response.status === 403) throw new Error("当前身份无权操作此稿件。");
  if (!response.ok) throw new Error("服务请求失败（" + response.status + "），请稍后重试。");
  return response.json();
}

async function connect(token = state.token) {
  await flush();
  const reconnect = $("connect");
  if (reconnect.disabled) return;
  reconnect.disabled = true;
  const oldScope = state.scope;
  state.scope = "";
  state.session = null;
  state.token = token;
  try {
    if (oldScope) {
      const demo = sampleBook();
      setActive(demo, demo.chapters[2].id);
    }
    $("saveState").textContent = "正在连接";
    state.auth = (await api("workbench")).auth_mode;
    if (state.auth === "development_headers" && !state.dev) {
      state.dev = localStorage.getItem("duke.novel.development-user") || "novelist-" + uid();
      localStorage.setItem("duke.novel.development-user", state.dev);
    }
    const session = await api("workbench/session");
    state.db ||= await openLibrary();
    const scope = JSON.stringify([session.tenant_id, session.user_id]);
    const books = await listBooks(state.db, scope);
    let view = [];
    try { view = JSON.parse(localStorage.getItem("duke.novel.view." + scope) || "[]"); } catch { /* Start from the shelf. */ }
    let book = books.find(b => b.id === view?.[0]) || books[0];
    if (!book) book = (await saveBook(state.db, scope, sampleBook(), true)).book;
    state.session = session;
    state.scope = scope;
    setActive(book, view?.[0] === book.id ? view[1] : book.id === "sample-letters" ? book.chapters[2].id : null);
    $("saveState").textContent = "本机已存";
    message();
  } catch (error) {
    state.scope = "";
    state.session = null;
    const demo = sampleBook();
    setActive(demo, demo.chapters[2].id);
    $("saveState").textContent = "示例预览";
    message(error.message + (oldScope ? " 已退出原书架。" : " 可通过页尾的连接设置重试。"));
    throw error;
  } finally {
    reconnect.disabled = false;
  }
}

function connection() {
  const body = openPanel("连接设置");
  if (state.session) body.append(element("p", state.session.model_configured ? "模型网关已配置。" : "模型尚未配置。你仍可写作、整理设定并导出手稿。"));
  if (!state.session?.model_configured) body.append(element("p", "模型接入由管理员设置 DUKE_MODEL_API_BASE、DUKE_MODEL_API_KEY 和 DUKE_MODEL_NAME，重启服务后重新连接。"));
  const form = element("form", "", "dialog-form");
  body.append(form);
  let token;
  if (state.auth === "oidc") {
    token = field(form, "组织访问令牌（仅当前页面使用）", "", "input", 16000);
    token.type = "password";
    token.autocomplete = "off";
  }
  submitForm(form, "重新连接", async () => { await connect(token?.value || state.token); panel.close(); });
}

function modelPanel(mode, reset = false, fetchNow = false) {
  const ch = current();
  const owner = state.scope;
  const book = state.book;
  const ticket = ch.tickets?.[mode];
  const body = openPanel(mode === "check" ? "核对前文" : "续写本章");
  const epoch = state.panelEpoch;
  if (!state.session?.fiction_available) {
    body.append(element("p", "当前身份可以编辑本机手稿。调用小说协作编辑需要相应的组织角色。"));
    return;
  }
  if (ticket && !reset && ticket.mode === mode) {
    const status = element("p", ticket.runId ? "正在读取上次结果……" : "上次请求尚未确认，可重新获取。");
    status.setAttribute("role", "status");
    body.append(status);
    const active = () => state.scope === owner && state.book === book && ch.tickets?.[mode] === ticket;
    const visible = () => active() && panel.open && state.panelEpoch === epoch;
    const load = async () => {
      if (!visible()) return;
      const buttons = body.querySelectorAll("button");
      buttons.forEach(b => b.disabled = true);
      try {
        const run = ticket.runId ? await api("runs/" + encodeURIComponent(ticket.runId)) : await api("runs", {
          agent_id: "fiction", thread_id: "novel-" + ticket.key, input: ticket.input, idempotency_key: ticket.key
        });
        if (!active()) return;
        if (!ticket.runId) { ticket.runId = run.run_id; await changed(); }
        if (!visible()) return;
        body.replaceChildren(status);
        const restart = action("重新填写要求", () => modelPanel(mode, true));
        if (run.status === "completed" && run.output) {
          status.textContent = mode === "check" ? "核对意见" : "续文预览";
          const result = element("div", run.output, "result");
          body.append(result);
          if (mode === "continue") {
            const unchanged = () => storyPrompt(book, currentIndex(), mode, ticket.instruction) === ticket.input;
            const apply = action("接到正文末尾", async () => {
              if (!active() || !unchanged()) throw new Error("手稿或设定已更新，请按新材料重新生成。");
              ch.body = [ch.body.trimEnd(), run.output.trim()].filter(Boolean).join("\n\n");
              delete ch.tickets[mode];
              await changed(); render(); panel.close();
              $("chapterBody").focus();
              $("chapterBody").setSelectionRange(ch.body.length, ch.body.length);
            }, "primary");
            apply.disabled = !unchanged();
            if (apply.disabled) status.textContent = "手稿或设定已更新，可重新生成续文。";
            const actions = element("div", "", "actions");
            actions.append(apply, restart); body.append(actions);
          } else body.append(restart);
        } else if (["queued", "running", "waiting_approval"].includes(run.status)) {
          status.textContent = run.status === "waiting_approval" ? "本次内容需要独立复核。请联系有权限的复核人处理此请求，之后可在这里刷新。" : "正在处理，可稍后刷新结果。";
          body.append(action("刷新结果", load));
        } else {
          status.textContent = run.status === "denied" ? "本次请求未获准，结果未写入正文。" : "未能取得模型结果，请检查模型连接后重试。";
          body.append(restart);
        }
      } catch (error) {
        if (visible()) {
          status.textContent = error.message;
          body.replaceChildren(status, action("重新获取", load), action("返回要求", () => modelPanel(mode, true)));
        }
      }
    };
    if (ticket.runId || fetchNow) void load();
    else body.append(action("获取结果", load, "primary"));
    return;
  }
  if (!state.session.model_configured) {
    body.append(element("p", "本章可继续手写。连接模型后，可以按本书人物、伏笔和前情生成建议。"), action("连接设置", connection, "primary"));
    return;
  }
  const notes = notesAt(book, currentIndex());
  body.append(element("p", "本次参考本章正文、此前 " + currentIndex() + " 个章回、" + notes.cast.length + " 位人物和 " + notes.clues.length + " 条伏笔。长篇取节选。"));
  const form = element("form", "", "dialog-form");
  body.append(form);
  const direction = field(form, mode === "check" ? "想核对什么（选填）" : "希望下一段怎样发展（选填）", "", "textarea", 1500);
  submitForm(form, mode === "check" ? "开始核对" : "生成续文", async () => {
    const instruction = direction.value.trim();
    ch.tickets ||= {};
    ch.tickets[mode] = {mode, instruction, key: uid(), input: storyPrompt(book, currentIndex(), mode, instruction), runId: ""};
    await changed();
    if (!panel.open || epoch !== state.panelEpoch) return;
    modelPanel(mode, false, true);
  });
}

function start() {
  const demo = sampleBook();
  setActive(demo, demo.chapters[2].id);
  $("chapterBody").oninput = () => {
    current().body = $("chapterBody").value;
    counts();
    void changed().catch(report);
  };
  $("chapterPicker").onchange = () => { void selectChapter($("chapterPicker").value).catch(report); };
  $("deskTab").onclick = () => $("chapterBody").focus();
  $("castTab").onclick = () => notebook("cast");
  $("clueTab").onclick = () => notebook("clues");
  $("shelf").onclick = () => { void shelf().catch(report); };
  $("addChapter").onclick = () => chapterForm(true);
  $("chapterSettings").onclick = () => chapterForm(false);
  $("continue").onclick = () => modelPanel("continue");
  $("check").onclick = () => modelPanel("check");
  $("connect").onclick = connection;
  $("closePanel").onclick = () => panel.close();
  panel.addEventListener("close", () => { state.panelEpoch++; });
  window.addEventListener("resize", resizeEditor);
  document.fonts.ready.then(resizeEditor);
  window.addEventListener("beforeunload", event => {
    if (state.dirty) { event.preventDefault(); event.returnValue = ""; }
  });
  void connect().catch(() => { /* The connection notice includes the recovery action. */ });
}
start();
