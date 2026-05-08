const STORAGE_KEY = "provi_api_base";

export const DEFAULT_API_BASE = "http://localhost:1234";

/**
 * 规范化用户粘贴的地址：可写域名、http(s)、或 127.0.0.1:8000 这种。
 * 最终统一成「以 /api 结尾、无末尾斜杠」的 base，供 fetch 拼 /admin/... 等用。
 */
export function normalizeApiBase(input) {
  let s = (input || "").trim();
  if (!s) return DEFAULT_API_BASE;
  if (!/^https?:\/\//i.test(s)) s = `http://${s}`;
  s = s.replace(/\/$/, "");
  // Only add /api suffix for non-localhost URLs (production uses nginx that routes /api/)
  const isLocal = /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?/.test(s);
  if (!isLocal && !s.endsWith("/api")) s = `${s}/api`;
  return s;
}

/**
 * 浏览器里优先读 localStorage（可页面里粘贴保存）；构建时可 NEXT_PUBLIC 覆盖；否则默认公网。
 */
export function getApiBase() {
  if (typeof window === "undefined") {
    return process.env.NEXT_PUBLIC_API_BASE || DEFAULT_API_BASE;
  }
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored) return stored;
  return process.env.NEXT_PUBLIC_API_BASE || DEFAULT_API_BASE;
}

export function setApiBase(input) {
  if (typeof window === "undefined") return;
  const v = normalizeApiBase(input);
  window.localStorage.setItem(STORAGE_KEY, v);
  return v;
}

export function clearApiBase() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(STORAGE_KEY);
}
