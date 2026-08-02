// 在 jsdom 裡開起真正的 scene.html + scene_v2.js，讓測試可以像使用者一樣真的按下按鈕。
// 這是字串比對測不到的部分：handler 有沒有掛上、按下去有沒有反應、失敗有沒有說出來。
import { readFileSync } from "node:fs";
import { register } from "node:module";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { JSDOM } from "jsdom";

import { STATIC_DIR } from "./paths.mjs";

const WINDOW_GLOBALS = [
  "Element",
  "HTMLElement",
  "HTMLAnchorElement",
  "HTMLButtonElement",
  "HTMLCanvasElement",
  "HTMLImageElement",
  "HTMLInputElement",
  "HTMLSelectElement",
  "HTMLTextAreaElement",
  "Node",
  "NodeList",
  "NodeFilter",
  "Event",
  "CustomEvent",
  "MouseEvent",
  "KeyboardEvent",
  "DOMParser",
  "XMLSerializer",
  "Image",
  "Blob",
  "File",
  "FileReader",
  "FormData",
  "getComputedStyle",
  "requestAnimationFrame",
  "cancelAnimationFrame",
  "matchMedia",
  "localStorage",
  "sessionStorage",
  "history",
  "location",
  "navigator",
  "screen",
  "alert",
  "confirm",
  "prompt",
];

let booted = null;

function installGlobals(window) {
  Object.defineProperty(globalThis, "window", { value: window, configurable: true });
  Object.defineProperty(globalThis, "document", { value: window.document, configurable: true });
  for (const key of WINDOW_GLOBALS) {
    if (!(key in window)) continue;
    const value = typeof window[key] === "function" && !/^[A-Z]/.test(key)
      ? window[key].bind(window)
      : window[key];
    Object.defineProperty(globalThis, key, { value, configurable: true, writable: true });
  }
}

/**
 * 開一次頁面就好：scene_v2.js 是有副作用的模組，重複 import 只會拿到同一份實例。
 */
export async function bootScenePage() {
  if (booted) return booted;
  register("./module_stub_hooks.mjs", import.meta.url);

  const html = readFileSync(path.join(STATIC_DIR, "scene.html"), "utf8");
  const dom = new JSDOM(html, {
    url: "http://localhost/scene",
    pretendToBeVisual: true,
    runScripts: "outside-only",
  });
  installGlobals(dom.window);

  const requests = [];
  globalThis.fetch = async (input, init) => {
    requests.push({ url: String(input), method: init?.method || "GET" });
    return {
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => ({}),
      text: async () => "{}",
    };
  };
  dom.window.fetch = globalThis.fetch;

  await import(pathToFileURL(path.join(STATIC_DIR, "scene_v2.js")).href);
  await flush();

  booted = { dom, document: dom.window.document, window: dom.window, requests };
  return booted;
}

export function flush(times = 3) {
  return new Promise((resolve) => {
    let remaining = times;
    const tick = () => {
      remaining -= 1;
      if (remaining <= 0) resolve();
      else setTimeout(tick, 0);
    };
    setTimeout(tick, 0);
  });
}

export function clickPendingAction(document, markup) {
  const pendingList = document.querySelector("#configuration-pending-list");
  pendingList.innerHTML = markup;
  const button = pendingList.querySelector("button");
  button.dispatchEvent(new document.defaultView.MouseEvent("click", {
    bubbles: true,
    cancelable: true,
  }));
  return button;
}
