const link = document.querySelector("#engineering-documents-link");

function refreshEngineeringLink() {
  const projectId = new URLSearchParams(location.search).get("project_id");
  if (!link) return;
  link.hidden = !projectId;
  link.href = projectId
    ? `/engineering?project_id=${encodeURIComponent(projectId)}`
    : "/engineering";
}

refreshEngineeringLink();
const status = document.querySelector("#project-save-status");
if (status) new MutationObserver(refreshEngineeringLink).observe(status, { childList: true, subtree: true });

