import {
  getCurrentUser,
  logout,
  requireSignedIn,
} from "./auth_client.js?v=sha256-b35a4ff11b37";

const STEP_LABELS = {
  project: "1 建立專案",
  upload: "2 上傳平面圖",
  recognition: "2 平面圖辨識",
  calibration: "3 比例標定",
  space_confirmation: "4 空間校正",
  requirements: "5 風格與需求",
  layout_2d: "6 家具配置",
  white_model_3d: "6 家具配置",
  realistic_3d: "6 家具配置",
  proposal_review: "7 方案視角",
  ai_render: "8 AI 渲染與成果",
};

const ROLE_LABELS = {
  owner: "擁有者",
  editor: "可編輯",
  viewer: "唯讀",
};

const listElement = document.getElementById("projects-list");
const errorBox = document.getElementById("projects-error");
const identityLine = document.getElementById("projects-identity");
const createForm = document.getElementById("create-form");
const newProjectButton = document.getElementById("new-project");
const cancelButton = document.getElementById("create-cancel");
const createSubmit = document.getElementById("create-submit");

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = false;
}

function clearError() {
  errorBox.textContent = "";
  errorBox.hidden = true;
}

async function readError(response) {
  try {
    const body = await response.json();
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    return detail?.message || `HTTP ${response.status}`;
  } catch {
    return `HTTP ${response.status}`;
  }
}

function formatTimestamp(value) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value || "";
  return parsed.toLocaleString("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function renderIdentity() {
  const user = getCurrentUser();
  if (!user) return;
  const roleText =
    user.role === "admin"
      ? "管理者"
      : user.role === "client"
        ? "屋主"
        : "設計師";
  identityLine.textContent = `${user.display_name}（${roleText}） · ${user.email}`;
  // 屋主只能檢視被分享的專案，不給建立入口。
  newProjectButton.hidden = user.role === "client";
}

function projectCard(project) {
  const card = document.createElement("article");
  card.className = "project-card";

  const heading = document.createElement("h2");
  const link = document.createElement("a");
  link.href = `/scene?project_id=${encodeURIComponent(project.project_id)}`;
  link.textContent = project.name;
  heading.append(link);

  const badges = document.createElement("p");
  badges.className = "project-badges";
  const roleBadge = document.createElement("span");
  roleBadge.className = `project-badge role-${project.project_role}`;
  roleBadge.textContent = ROLE_LABELS[project.project_role] || project.project_role;
  const stepBadge = document.createElement("span");
  stepBadge.className = "project-badge";
  stepBadge.textContent = STEP_LABELS[project.current_step] || project.current_step;
  badges.append(roleBadge, stepBadge);

  const meta = document.createElement("p");
  meta.className = "project-meta";
  meta.textContent = `更新於 ${formatTimestamp(project.updated_at)}`;

  card.append(heading, badges, meta);

  if (project.notes) {
    const notes = document.createElement("p");
    notes.className = "project-notes";
    notes.textContent = project.notes;
    card.append(notes);
  }

  const actions = document.createElement("div");
  actions.className = "project-actions";
  const open = document.createElement("a");
  open.className = "project-open";
  open.href = link.href;
  open.textContent = "繼續設計";
  actions.append(open);

  if (project.project_role === "owner") {
    const share = document.createElement("button");
    share.type = "button";
    share.className = "project-share";
    share.textContent = "分享給屋主";
    share.addEventListener("click", () => shareProject(project));
    actions.append(share);
  }
  card.append(actions);
  return card;
}

async function shareProject(project) {
  const email = window.prompt(
    `把「${project.name}」分享給哪個 email？\n對方必須已經註冊 RoomPilot 帳號。`,
  );
  if (!email) return;
  clearError();
  const response = await fetch(
    `/api/projects/${encodeURIComponent(project.project_id)}/members`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email.trim(), project_role: "viewer" }),
    },
  );
  if (!response.ok) {
    showError(await readError(response));
    return;
  }
  const members = await response.json();
  window.alert(`已分享。目前成員 ${members.length} 人。`);
}

async function loadProjects() {
  clearError();
  const response = await fetch("/api/projects");
  if (!response.ok) {
    listElement.replaceChildren();
    showError(await readError(response));
    return;
  }
  const projects = await response.json();
  listElement.replaceChildren();
  if (!projects.length) {
    const empty = document.createElement("p");
    empty.className = "projects-empty";
    empty.textContent =
      getCurrentUser()?.role === "client"
        ? "還沒有設計師把專案分享給你。"
        : "還沒有專案。點右上角「建立新專案」開始第一個設計。";
    listElement.append(empty);
    return;
  }
  projects.forEach((project) => listElement.append(projectCard(project)));
}

newProjectButton.addEventListener("click", () => {
  createForm.hidden = false;
  newProjectButton.hidden = true;
  document.getElementById("project-name").focus();
});

cancelButton.addEventListener("click", () => {
  createForm.hidden = true;
  newProjectButton.hidden = false;
  clearError();
});

createForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError();
  const name = createForm.name.value.trim();
  if (!name) {
    showError("請輸入專案名稱。");
    return;
  }
  createSubmit.disabled = true;
  createSubmit.textContent = "建立中…";
  try {
    const response = await fetch("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, notes: createForm.notes.value.trim() }),
    });
    if (!response.ok) {
      showError(await readError(response));
      return;
    }
    const { project } = await response.json();
    window.location.href = `/scene?project_id=${encodeURIComponent(project.project_id)}`;
  } finally {
    createSubmit.disabled = false;
    createSubmit.textContent = "建立並開始";
  }
});

document.getElementById("sign-out").addEventListener("click", async () => {
  await logout();
  window.location.href = "/login";
});

if (requireSignedIn()) {
  renderIdentity();
  loadProjects().catch((error) => {
    showError(error?.message || "無法載入專案列表。");
  });
}
