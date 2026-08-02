import { isSignedIn, login, register } from "./auth_client.js?v=sha256-b35a4ff11b37";

const form = document.getElementById("auth-form");
const errorBox = document.getElementById("auth-error");
const submitButton = document.getElementById("auth-submit");
const loginTab = document.getElementById("tab-login");
const registerTab = document.getElementById("tab-register");
const passwordInput = document.getElementById("password");
const displayNameInput = document.getElementById("display-name");

let mode = "login";

/** 只接受同源的相對路徑，避免 ?next= 被拿來做開放轉址。 */
function safeNextTarget() {
  const raw = new URLSearchParams(window.location.search).get("next");
  if (!raw) return "/projects";
  if (!raw.startsWith("/") || raw.startsWith("//")) return "/projects";
  return raw;
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = false;
}

function clearError() {
  errorBox.textContent = "";
  errorBox.hidden = true;
}

function setMode(next) {
  mode = next;
  const registering = mode === "register";
  loginTab.classList.toggle("active", !registering);
  registerTab.classList.toggle("active", registering);
  loginTab.setAttribute("aria-selected", String(!registering));
  registerTab.setAttribute("aria-selected", String(registering));
  document.body.classList.toggle("is-registering", registering);
  submitButton.textContent = registering ? "建立帳號" : "登入";
  displayNameInput.required = registering;
  passwordInput.autocomplete = registering ? "new-password" : "current-password";
  clearError();
}

loginTab.addEventListener("click", () => setMode("login"));
registerTab.addEventListener("click", () => setMode("register"));

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError();

  const email = form.email.value.trim();
  const password = form.password.value;
  if (!email || !password) {
    showError("請填寫 email 與密碼。");
    return;
  }
  if (mode === "register" && password.length < 8) {
    showError("密碼至少需要 8 個字元。");
    return;
  }

  submitButton.disabled = true;
  submitButton.textContent = mode === "register" ? "建立中…" : "登入中…";
  try {
    if (mode === "register") {
      await register({
        email,
        password,
        displayName: displayNameInput.value.trim() || email.split("@")[0],
        role: form.role.value,
      });
    } else {
      await login({ email, password });
    }
    window.location.href = safeNextTarget();
  } catch (error) {
    showError(error?.message || "登入失敗，請稍後再試。");
    submitButton.disabled = false;
    submitButton.textContent = mode === "register" ? "建立帳號" : "登入";
  }
});

if (isSignedIn()) {
  window.location.replace(safeNextTarget());
} else {
  setMode("login");
}
