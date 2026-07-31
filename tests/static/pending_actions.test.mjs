// 迴歸：第 6 步待處理家具的修復按鈕曾經全部靜默無效（不發請求、不報錯、不提示），
// 而當時的契約測試只比對原始碼字串，所以整段 handler 死掉仍然全綠。
// 這裡改成真的按下去，並要求每一個動作都留下使用者看得見的訊息。
import test from "node:test";
import assert from "node:assert/strict";

import { bootScenePage, clickPendingAction, flush } from "./scene_page_harness.mjs";

const ACTIONS = [
  {
    name: "同意擇優配置",
    markup: '<button type="button" data-prioritize-configuration-room="room-not-in-state">同意擇優配置</button>',
  },
  {
    name: "只重排此家具",
    markup: '<button type="button" data-reflow-configuration-furniture="missing-furniture">只重排此家具</button>',
  },
  {
    name: "更換較小款",
    markup: '<button type="button" data-replace-configuration-furniture="missing-furniture">更換較小款</button>',
  },
  {
    name: "移除此家具",
    markup: '<button type="button" data-remove-configuration-furniture="missing-furniture">移除此家具</button>',
  },
  {
    name: "暫緩全部待處理家具並繼續",
    markup: '<button type="button" data-defer-all-configuration-furniture>暫緩全部待處理家具並繼續</button>',
  },
];

test("scene_v2.js 能在真實 DOM 上完成初始化", async () => {
  const { document } = await bootScenePage();
  assert.ok(document.querySelector("#configuration-pending-list"));
  assert.ok(document.querySelector("#confirm-white-model"));
});

for (const action of ACTIONS) {
  test(`待處理清單的「${action.name}」按下去一定有反應`, async () => {
    const { document } = await bootScenePage();
    const status = document.querySelector("#global-status");
    const layoutError = document.querySelector("#layout-error");
    status.textContent = "";
    layoutError.textContent = "";

    clickPendingAction(document, action.markup);
    await flush();

    assert.notEqual(
      status.textContent.trim(),
      "",
      `「${action.name}」按下後沒有任何狀態訊息，使用者只會看到按了沒反應`,
    );
    assert.notEqual(
      layoutError.textContent.trim(),
      "",
      `「${action.name}」失敗時沒有寫進目前步驟的錯誤欄位`,
    );
  });
}

test("點擊待處理清單的空白處不會被當成失敗", async () => {
  const { document } = await bootScenePage();
  const status = document.querySelector("#global-status");
  const pendingList = document.querySelector("#configuration-pending-list");
  pendingList.innerHTML = '<p class="rp-configuration-clear">目前沒有待處理家具。</p>';
  status.textContent = "";

  pendingList.querySelector("p").dispatchEvent(
    new document.defaultView.MouseEvent("click", { bubbles: true, cancelable: true }),
  );
  await flush();

  assert.equal(status.textContent.trim(), "");
});
