// Manuscripts are local to this browser and partitioned by the authenticated author.
export function uid() {
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), b => b.toString(16).padStart(2, "0")).join("");
}

export function chapter(title, body = "", summary = "") {
  return {id: uid(), title, body, summary, tickets: {}};
}

export function newBook(title, volume = "") {
  return {id: uid(), title, volume, first: 1, revision: 0, chapters: [chapter("未题章")], cast: [], clues: []};
}

export function sampleBook() {
  const book = newBook("第十三封来信", "卷一　·　潮生");
  book.id = "sample-letters";
  book.first = 5;
  book.chapters = [
    chapter("河岸旧址", "河水退下去以后，沈砚在泥滩上捡到了一枚生锈的信箱钥匙。拴钥匙的布条上，绣着旧邮局的名字。", "沈砚在断桥旧址捡到旧邮局的钥匙。"),
    chapter("失踪的邮差", "许澄最后一次出门投递，是在三天前的清晨。那天的投递簿上少了一页，只有夹在装订线里的一小角蓝纸还在。", "邮差许澄失踪，投递簿缺了一页。"),
    chapter("没有寄件人的信", [
      "邮差失踪的第三天，沈砚收到一封信。信封上的笔迹，和他的一模一样。",
      "信封上没有地址。蓝黑色的墨水绕开了他的名字，只在右下角画了一座桥。沈砚认得那座桥。十七年前的暴雨里，他亲眼看着最后一孔桥拱沉进河底。",
      "他把信纸摊在窗台上。纸上只有一句话。", "", "「今晚九点，别替我开门。」",
      "楼下传来铃声。第一声很远，第二声已经到了门前。"
    ].join("\n")),
    chapter("门后的潮声")
  ];
  book.cast = [
    {id: uid(), name: "沈砚", detail: "旧邮局的代班员，认得信封上的沉桥。", motive: "找回许澄，弄清是谁模仿自己的笔迹。", ties: "少年时曾和许澄在断桥附近送过信。", from: ""},
    {id: uid(), name: "许澄", detail: "失踪的邮差，三天前最后一次投递。", motive: "把最后一封信送到。", ties: "沈砚的旧识。", from: book.chapters[1].id}
  ];
  book.clues = [{id: uid(), name: "信封上的桥", detail: "河上的桥早已坍塌，谁还记得当年的桥形？", from: book.chapters[2].id, resolved: ""}];
  return book;
}

export function openLibrary() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open("duke-novel-library", 1);
    req.onupgradeneeded = () => {
      const books = req.result.createObjectStore("books", {keyPath: ["scope", "id"]});
      books.createIndex("author", "scope");
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export function listBooks(db, scope) {
  return new Promise((resolve, reject) => {
    const req = db.transaction("books").objectStore("books").index("author").getAll(scope);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

// Read and compare the revision inside one transaction. Both edits survive a collision.
export function saveBook(db, scope, snapshot, seed = false) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction("books", "readwrite");
    const store = tx.objectStore("books");
    const read = store.get([scope, snapshot.id]);
    let saved, conflict = false;
    read.onsuccess = () => {
      const old = read.result;
      if (seed && old) { saved = old; return; }
      conflict = Boolean(old && old.revision !== snapshot.revision);
      saved = {...snapshot, scope, revision: snapshot.revision + 1};
      if (conflict) {
        saved.id = uid();
        saved.title += "（并行修改副本）";
        saved.revision = 1;
      }
      store.put(saved);
    };
    tx.oncomplete = () => resolve({book: saved, conflict});
    tx.onabort = () => reject(tx.error || new Error("书稿保存中断"));
  });
}

export function chapterLabel(book, index) {
  const digits = String(book.first + index);
  if (digits.length > 4) return "第" + digits + "章";
  const places = ["", "十", "百", "千"];
  let numeral = "";
  for (const [i, digit] of Array.from(digits).entries()) {
    const n = Number(digit);
    if (n) numeral += "零一二三四五六七八九"[n] + places[digits.length - 1 - i];
    else if (!numeral.endsWith("零")) numeral += "零";
  }
  return "第" + numeral.replace(/^一十/, "十").replace(/零$/, "") + "章";
}

export function notesAt(book, index) {
  const position = id => book.chapters.findIndex(ch => ch.id === id);
  const introduced = note => !note.from || position(note.from) <= index;
  return {
    cast: book.cast.filter(introduced),
    clues: book.clues.filter(introduced).map(note => ({...note, closed: Boolean(note.resolved && position(note.resolved) <= index)}))
  };
}

function excerpt(text, limit) {
  if (text.length <= limit) return text;
  const head = Math.floor(limit / 4);
  return text.slice(0, head) + "\n〔中段省略〕\n" + text.slice(-(limit - head));
}

// Budget each source independently so a long book cannot displace the active chapter.
export function storyPrompt(book, index, mode, instruction = "") {
  const active = book.chapters[index];
  const notes = notesAt(book, index);
  const previous = book.chapters.slice(0, index);
  const past = previous.map((ch, i) =>
    chapterLabel(book, i) + " " + ch.title + "\n" +
    (ch.summary ? "提要：" + ch.summary + "\n" : "") + excerpt(ch.body, i >= index - 2 ? 2200 : 220)
  );
  const task = mode === "check" ? "核对前文，指出有依据的连续性问题。" : "从本章末句续写两至四段，将下一步行动交给角色。";
  return [
    "操作：" + task, "作者要求：" + (instruction.trim() || "沿用当前叙事视角和语言风格。"),
    "作品：" + book.title + "\n卷名：" + book.volume,
    "人物设定：\n" + excerpt(notes.cast.map(n => [n.name, n.detail, n.motive, n.ties].filter(Boolean).join(" / ")).join("\n"), 3200),
    "伏笔：\n" + excerpt(notes.clues.map(n => (n.closed ? "已回收" : "未解") + " / " + n.name + " / " + n.detail).join("\n"), 2400),
    "此前章回：\n" + excerpt(past.join("\n\n"), 7200),
    "当前章节：" + chapterLabel(book, index) + " " + active.title + "\n本章提要：" + active.summary,
    "当前正文：\n" + excerpt(active.body, 10500)
  ].join("\n\n");
}
