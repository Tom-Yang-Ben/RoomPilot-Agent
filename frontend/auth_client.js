/**
 * 帳戶端前端：token 保管、自動附加身分、過期自動續期。
 *
 * 實作成 fetch 攔截器而不是逐一改寫呼叫點：專案裡的 API 呼叫散在
 * scene_v2、engineering、rag 等模組，集中在這裡才不會有人漏加身分。
 *
 * 已知取捨：token 存在 localStorage，因此頁面若被 XSS 注入就會連帶外洩。
 * 更嚴格的做法是 httpOnly cookie 加 CSRF token；那需要後端改寫成 cookie
 * 流程並在每個寫入端點驗證 CSRF，目前刻意不做。相對的，這裡讓 access token
 * 維持短效（預設 30 分鐘）、refresh 一律輪替，縮小外洩後的可用窗口。
 */

const ACCESS_TOKEN_KEY = "roompilot.access_token";
const REFRESH_TOKEN_KEY = "roompilot.refresh_token";
const USER_KEY = "roompilot.user";
const LOGIN_PAGE = "/login";

// 這些端點本身就是拿身分的地方，不能再套用攔截器，否則 401 會無限遞迴。
const AUTH_ENDPOINTS = new Set([
  "/api/auth/login",
  "/api/auth/register",
  "/api/auth/refresh",
  "/api/auth/logout",
]);

export function getAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY) || "";
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY) || "";
}

export function getCurrentUser() {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function isSignedIn() {
  return Boolean(getAccessToken());
}

function storeSession(payload) {
  localStorage.setItem(ACCESS_TOKEN_KEY, payload.access_token);
  localStorage.setItem(REFRESH_TOKEN_KEY, payload.refresh_token);
  localStorage.setItem(USER_KEY, JSON.stringify(payload.user));
}

export function clearSession() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

const originalFetch = window.fetch.bind(window);

async function readError(response) {
  try {
    const body = await response.clone().json();
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    return detail?.message || body?.message || `HTTP ${response.status}`;
  } catch {
    return `HTTP ${response.status}`;
  }
}

export async function register({ email, password, displayName, role }) {
  const response = await originalFetch("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email,
      password,
      display_name: displayName,
      role: role || "designer",
    }),
  });
  if (!response.ok) throw new Error(await readError(response));
  const payload = await response.json();
  storeSession(payload);
  return payload.user;
}

export async function login({ email, password }) {
  const response = await originalFetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) throw new Error(await readError(response));
  const payload = await response.json();
  storeSession(payload);
  return payload.user;
}

export async function logout() {
  const refreshToken = getRefreshToken();
  clearSession();
  if (!refreshToken) return;
  try {
    await originalFetch("/api/auth/logout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  } catch {
    // 本機已清乾淨；伺服器端該 refresh token 會在到期後自然失效。
  }
}

// 同時有多個請求撞到 401 時只跑一次續期，其餘等待同一個 promise。
let refreshInFlight = null;

async function refreshSession() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const response = await originalFetch("/api/auth/refresh", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (!response.ok) {
          clearSession();
          return false;
        }
        storeSession(await response.json());
        return true;
      } catch {
        return false;
      } finally {
        refreshInFlight = null;
      }
    })();
  }
  return refreshInFlight;
}

export function redirectToLogin() {
  const next = encodeURIComponent(
    window.location.pathname + window.location.search,
  );
  window.location.href = `${LOGIN_PAGE}?next=${next}`;
}

function requestPath(input) {
  try {
    const url = new URL(
      typeof input === "string" ? input : input.url,
      window.location.origin,
    );
    return url.origin === window.location.origin ? url.pathname : null;
  } catch {
    return null;
  }
}

function withAuthorization(init, token) {
  const headers = new Headers(init.headers || {});
  if (!headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return { ...init, headers };
}

window.fetch = async function authenticatedFetch(input, init = {}) {
  const path = requestPath(input);
  // 跨網域（CloudFront 上的 GLB 與圖片）絕不能附上身分。
  if (path === null || !path.startsWith("/api/") || AUTH_ENDPOINTS.has(path)) {
    return originalFetch(input, init);
  }

  const token = getAccessToken();
  const response = await originalFetch(
    input,
    token ? withAuthorization(init, token) : init,
  );
  if (response.status !== 401) return response;

  if (await refreshSession()) {
    return originalFetch(input, withAuthorization(init, getAccessToken()));
  }
  clearSession();
  if (!window.location.pathname.startsWith(LOGIN_PAGE)) {
    redirectToLogin();
  }
  return response;
};

// 已配發的 blob URL，換新的時候要撤銷舊的，否則長時間操作會累積記憶體。
const objectUrlCache = new Map();

/**
 * 把需要身分的媒體端點取成 blob URL。
 *
 * `<img src>`、`<iframe src>` 與 `<a href download>` 都由瀏覽器直接發出請求，
 * 不會經過上面的 fetch 攔截器，也就不會帶 Authorization——加了帳戶端之後
 * 這些位置一律會拿到 401。先用帶身分的 fetch 取回內容再轉 blob URL，是
 * 不必把 token 放進網址（會進伺服器 log 與瀏覽器歷史）的作法。
 */
export async function authorizedObjectUrl(url, { cacheKey } = {}) {
  const key = cacheKey || url;
  const response = await window.fetch(url);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${url}`);
  }
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const previous = objectUrlCache.get(key);
  if (previous) URL.revokeObjectURL(previous);
  objectUrlCache.set(key, objectUrl);
  return objectUrl;
}

/** 觸發一次帶身分的下載，檔名沿用伺服器給的名稱。 */
export async function downloadAuthorized(url, fileName) {
  const objectUrl = await authorizedObjectUrl(url, { cacheKey: `download:${url}` });
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = fileName || "";
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
}

/** 需要登入的頁面在啟動時呼叫；未登入直接導向登入頁。 */
export function requireSignedIn() {
  if (!isSignedIn()) {
    redirectToLogin();
    return false;
  }
  return true;
}
