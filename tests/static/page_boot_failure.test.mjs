// 迴歸：home / styles / library 的頂層 await 沒有 catch，型錄回 503 時模組被拒絕，
// 瀏覽器只留一片白畫布——使用者連「為什麼」都看不到。這裡要求失敗會留下可見橫幅，
// 而且原本的頁面內容還在。
import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { JSDOM } from "jsdom";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const STATIC_DIR = path.resolve(HERE, "..", "..", "backend", "server", "static");

test("啟動失敗會留下可見橫幅，且不洗掉既有內容", async () => {
  const dom = new JSDOM("<!doctype html><body><main id=\"content\">內容</main></body>");
  Object.defineProperty(globalThis, "document", {
    value: dom.window.document,
    configurable: true,
  });

  const { reportPageBootFailure } = await import(
    pathToFileURL(path.join(STATIC_DIR, "common.js")).href
  );

  reportPageBootFailure(new Error("HTTP 503: /api/home-data"), "首頁資料");

  const banner = dom.window.document.getElementById("page-boot-error");
  assert.ok(banner, "沒有產生錯誤橫幅");
  assert.match(banner.textContent, /首頁資料載入失敗/);
  assert.match(banner.textContent, /503/);
  assert.equal(banner.getAttribute("role"), "alert");
  // 原本的內容不能被洗掉，否則等於換了一種白畫布。
  assert.ok(dom.window.document.getElementById("content"));

  reportPageBootFailure(new Error("HTTP 503: /api/home-data"), "首頁資料");
  assert.equal(
    dom.window.document.querySelectorAll("#page-boot-error").length,
    1,
    "重複失敗不該疊出一整排橫幅",
  );
});
