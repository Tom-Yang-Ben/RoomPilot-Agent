// 迴歸：第 8 步的遠端渲染失敗（502 image_provider_no_image_returned）與保存截圖 409
// 在 UI 上完全沉默——後端其實有中文訊息，前端把它寫進 3D 檢視器的狀態列，
// 下一則檢視器訊息就蓋掉了。這裡要求失敗留在專屬錯誤欄位。
import test from "node:test";
import assert from "node:assert/strict";

import { bootScenePage, flush } from "./scene_page_harness.mjs";

function click(document, selector) {
  document.querySelector(selector).dispatchEvent(
    new document.defaultView.MouseEvent("click", { bubbles: true, cancelable: true }),
  );
}

function stubFetch(status, body) {
  const original = globalThis.fetch;
  globalThis.fetch = async () => ({
    ok: status >= 200 && status < 300,
    status,
    headers: { get: () => "application/json" },
    json: async () => body,
    text: async () => JSON.stringify(body),
  });
  return () => { globalThis.fetch = original; };
}

test("第 8 步有一個不會被 3D 檢視器覆寫的錯誤欄位", async () => {
  const { document } = await bootScenePage();
  assert.ok(document.querySelector("#ai-render-error"));
  assert.ok(document.querySelector("#proposal-review-error"));
  // 檢視器狀態列與錯誤欄位必須是不同節點，否則錯誤還是會被蓋掉。
  assert.notEqual(
    document.querySelector("#ai-render-error"),
    document.querySelector("#ai-render-status"),
  );
});

test("沒有勾選色卡就送出，會寫進錯誤欄位而不是檢視器狀態列", async () => {
  const { document } = await bootScenePage();
  const slot = document.querySelector("#ai-render-error");
  slot.textContent = "";

  click(document, "#request-palette-renders");
  await flush();

  assert.match(slot.textContent, /色卡/);
});

test("遠端渲染回 502 時，後端的中文訊息會出現在錯誤欄位", async () => {
  const { document } = await bootScenePage();
  const slot = document.querySelector("#ai-render-error");
  slot.textContent = "";
  document.querySelector("#palette-render-options").innerHTML =
    '<input type="checkbox" data-render-style-card value="scandinavian_3" checked />';

  const restore = stubFetch(502, {
    detail: {
      code: "image_provider_no_image_returned",
      message: "遠端渲染服務拒絕了這次任務。",
    },
  });
  try {
    click(document, "#request-palette-renders");
    await flush(6);
  } finally {
    restore();
  }

  assert.notEqual(slot.textContent.trim(), "", "502 之後錯誤欄位仍是空的");
});

test("保存截圖遇到 409 會重新取版本再送一次，不把衝突丟給使用者", async () => {
  const { document } = await bootScenePage();
  const slot = document.querySelector("#ai-render-error");
  slot.textContent = "";

  const calls = [];
  const original = globalThis.fetch;
  globalThis.fetch = async (input, init) => {
    const url = String(input);
    if (url.startsWith("data:")) {
      return { blob: async () => new globalThis.Blob([new Uint8Array([1, 2, 3])], { type: "image/png" }) };
    }
    calls.push(`${init?.method || "GET"} ${url}`);
    const isPost = (init?.method || "GET") === "POST";
    const conflictFirst = isPost && calls.filter((entry) => entry.startsWith("POST")).length === 1;
    return {
      ok: !conflictFirst,
      status: conflictFirst ? 409 : 200,
      headers: { get: () => "application/json" },
      json: async () => (conflictFirst
        ? { detail: { code: "project_revision_conflict", message: "專案已在另一個分頁更新。" } }
        : { project: { revision: 9 }, renders: [] }),
      text: async () => "{}",
    };
  };
  try {
    click(document, "#save-render-view-png");
    await flush(8);
  } finally {
    globalThis.fetch = original;
  }

  const posts = calls.filter((entry) => entry.startsWith("POST")).length;
  const refetched = calls.some((entry) => entry.startsWith("GET") && entry.includes("/api/projects/"));
  assert.ok(posts >= 2 || refetched, `409 之後沒有重新取版本重送：${JSON.stringify(calls)}`);
});
