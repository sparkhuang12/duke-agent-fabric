import assert from "node:assert/strict";
import test from "node:test";
import {webcrypto} from "node:crypto";
import {chapter, chapterLabel, newBook, notesAt, sampleBook, storyPrompt} from "../prototype/novel-library.mjs";

if (!globalThis.crypto) Object.defineProperty(globalThis, "crypto", {value: webcrypto});

test("earlier chapters cannot see later events, characters or clue resolutions", () => {
  const b = sampleBook();
  b.chapters[3].body = "结局专用短语";
  b.clues[0].resolved = b.chapters[3].id;
  assert.equal(notesAt(b, 0).cast.length, 1);
  assert.equal(notesAt(b, 1).clues.length, 0);
  assert.equal(notesAt(b, 2).clues[0].closed, false);
  assert.equal(notesAt(b, 3).clues[0].closed, true);
  const text = storyPrompt(b, 2, "continue", "多写一个动作");
  for (const word of ["投递簿", "少年时", "未解", "门前", "多写一个动作"]) assert.ok(text.includes(word));
  assert.ok(!text.includes("结局专用短语"));
  const other = newBook("另一卷");
  assert.ok(!storyPrompt(other, 0, "continue").includes("沈砚"));
});

test("long manuscripts retain the active ending and recent canon within a bounded prompt", () => {
  const book = newBook("长卷");
  for (let i = 0; i < 40; i++) book.chapters.push(chapter("旧稿", "前".repeat(20000)));
  book.chapters.at(-1).summary = "最近的约定";
  book.chapters.push(chapter("今夜", "文".repeat(90000) + "窗外响起钟声"));
  const text = storyPrompt(book, book.chapters.length - 1, "check");
  assert.ok(text.length < 30000);
  for (const value of ["核对前文", "最近的约定", "中段省略", "窗外响起钟声"]) assert.ok(text.includes(value));
});


test("chapter headings use consistent Chinese numerals across browsers", () => {
  for (const [n, wording] of [[2, "二"], [10, "十"], [15, "十五"], [20, "二十"], [101, "一百零一"], [1005, "一千零五"]]) {
    assert.equal(chapterLabel({first: n}, 0), "第" + wording + "章");
  }
});
