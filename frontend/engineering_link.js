const link = document.querySelector("#engineering-documents-link");
const exportButton = document.querySelector("#export-proposal");

function refreshEngineeringLink() {
  const projectId = new URLSearchParams(location.search).get("project_id");
  if (link) {
    link.hidden = !projectId;
    link.href = projectId
      ? `/engineering?project_id=${encodeURIComponent(projectId)}`
      : "/engineering";
  }
  if (exportButton) exportButton.hidden = !projectId;
}

if (exportButton) {
  // 第 8 步「輸出簡報」：帶 auto=1 進成果報告頁，該頁會自動跑
  // 保存快照→鎖定 revision→產生成果包，做完直接預覽提案文件。
  exportButton.addEventListener("click", () => {
    const projectId = new URLSearchParams(location.search).get("project_id");
    if (!projectId) return;
    location.href = `/engineering?project_id=${encodeURIComponent(projectId)}&auto=1`;
  });
}

refreshEngineeringLink();
const status = document.querySelector("#project-save-status");
if (status) new MutationObserver(refreshEngineeringLink).observe(status, { childList: true, subtree: true });
