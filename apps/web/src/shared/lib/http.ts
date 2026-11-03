let uiTenant: string | null = null;
let uiUser: string | null = null;
export function setUiIdentityContext(user: string | null, tenant: string | null) { uiUser = user; uiTenant = tenant; }
export function csrfToken(): string | null {
  try {
    const value = document.cookie.split(";").map(value => value.trim()).find(value => value.startsWith("algooptionx_csrf="));
    return value ? decodeURIComponent(value.slice("algooptionx_csrf=".length)) : null;
  } catch { return null; }
}
export async function apiFetch(url: string, options: RequestInit = {}): Promise<Response> {
  if (!url.startsWith("/api/")) throw new Error("API requests must use a same-origin application route.");
  const headers = new Headers(options.headers);
  headers.set("X-AlgoOptionX-Client", "browser-v1");
  if (uiTenant) headers.set("X-Expected-Tenant", uiTenant);
  if (uiUser) headers.set("X-Expected-User", uiUser);
  const csrf = csrfToken();
  if (csrf && options.method && !["GET", "HEAD", "OPTIONS"].includes(options.method)) headers.set("X-AlgoOptionX-CSRF", csrf);
  const response = await fetch(url, { ...options, headers, credentials: "same-origin" });
  if (response.status === 401 && !url.endsWith("/identity/login") && !url.endsWith("/identity/register")) window.dispatchEvent(new Event("algooptionx-session-expired"));
  const tenant = response.headers.get("X-AlgoOptionX-Tenant");
  if (tenant && !url.endsWith("/identity/me")) window.dispatchEvent(new CustomEvent("algooptionx-tenant-observed", {detail:{tenant,user:response.headers.get("X-AlgoOptionX-User")}}));
  return response;
}
