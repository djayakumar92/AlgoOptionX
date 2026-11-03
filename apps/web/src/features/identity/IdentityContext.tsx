import { createContext, useCallback, useContext, useEffect, useState, useRef, useLayoutEffect } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { apiFetch, csrfToken, setUiIdentityContext } from "../../shared/lib/http";

export type Customer = { user_id: string; email: string; name: string; email_verified: number; tenant_id: string; tenant_name: string; role: string; session_id: string };
export type Identity = { user: Customer | null; verification_required: boolean; email_delivery: string };
export async function identityApi<T>(path: string, body?: unknown): Promise<T> {
  const response = await apiFetch(`/api/identity/${path}`, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Check your details and try again.");
  return result;
}
const initial: Identity = { user: null, verification_required: false, email_delivery: "" };
const Context = createContext({ ...initial, loading: false, expired: false, setIdentity: (_value: Identity) => {}, refresh: async () => {}, logout: async () => {} });
export function IdentityProvider({ children }: { children: ReactNode }) {
  const [identity, setIdentity] = useState<Identity>(initial);
  const [loading, setLoading] = useState(true);
  const [expired, setExpired] = useState(false);
  const currentIdentity = useRef(identity); currentIdentity.current = identity;
  const refreshingTenant = useRef(false);
  const generation = useRef(0);
  const channel = useRef<BroadcastChannel | null>(null);
  useLayoutEffect(() => { setUiIdentityContext(identity.user?.user_id || null, identity.user?.tenant_id || null); }, [identity.user?.user_id, identity.user?.tenant_id]);
  const refresh = useCallback(async (broadcast = true) => {
    const sequence = ++generation.current;
    try { const value = await identityApi<Identity>("me"); if(sequence===generation.current) { const previous=currentIdentity.current.user; setIdentity(value); setExpired(!value.user && !!csrfToken()); if(broadcast && (previous?.user_id!==value.user?.user_id || previous?.tenant_id!==value.user?.tenant_id))channel.current?.postMessage("identity-changed"); } }
    finally { if(sequence===generation.current)setLoading(false); }
  }, []);
  useEffect(() => {
    void refresh().catch(() => setLoading(false));
    const lost = () => { generation.current++; setIdentity(initial); setLoading(false); setExpired(true); channel.current?.postMessage("identity-changed"); };
    const invalidate = () => {
      generation.current++; setIdentity(initial); setExpired(true); setLoading(true);
    };
    const observed = (event: Event) => {
      const context = (event as CustomEvent<{tenant:string;user:string}>).detail;
      if ((context.tenant !== currentIdentity.current.user?.tenant_id || context.user !== currentIdentity.current.user?.user_id) && csrfToken() && !refreshingTenant.current) {
        refreshingTenant.current = true;
        invalidate();
        void refresh(false).catch(() => {}).finally(() => { refreshingTenant.current = false; });
      }
    };
    try {
      channel.current = new BroadcastChannel("algooptionx-identity");
      channel.current.onmessage = () => {
        // A known cross-tab identity change invalidates the rendered principal.
        // Hide private children immediately; a failed refresh must stay blocked.
        invalidate();
        void refresh(false).catch(() => {});
      };
    } catch { channel.current = null; }
    const focused = () => { void refresh(false).catch(() => {}); };
    window.addEventListener("focus", focused);
    window.addEventListener("algooptionx-session-expired", lost);
    window.addEventListener("algooptionx-tenant-observed", observed);
    return () => { channel.current?.close(); channel.current=null; window.removeEventListener("focus",focused); window.removeEventListener("algooptionx-session-expired", lost); window.removeEventListener("algooptionx-tenant-observed", observed); };
  }, [refresh]);
  async function logout() {
    await identityApi("logout", {});
    generation.current++; setIdentity(initial); setExpired(false); setLoading(false); channel.current?.postMessage("identity-changed");
  }
  return <Context.Provider value={{ ...identity, loading, expired, setIdentity: value => { generation.current++; setIdentity(value); setExpired(false); setLoading(false); channel.current?.postMessage("identity-changed"); }, refresh, logout }}>
    {expired && <div className="identity-banner" role="alert">Your account access needs verification. <Link to="/login">Sign in again</Link> if your session is unavailable.</div>}
    {identity.user && !identity.user.email_verified && <div className="identity-banner">Email verification pending. {identity.verification_required ? "Verify your email to access the workspace." : "This local evaluation account is unverified."} <Link to="/account">Manage account</Link></div>}
    {children}
  </Context.Provider>;
}
export function useIdentity() { return useContext(Context); }
export function CustomerLink() {
  const { user } = useIdentity();
  return <Link to={user ? "/account" : "/login"}>{user ? "Account & security" : "Sign in"}</Link>;
}

export function TenantBoundary({ children }: { children: ReactNode }) {
  const { user, loading, expired, verification_required } = useIdentity();
  if (loading) return <main className="identity-page"><p role="status">Loading your workspace permissions…</p></main>;
  if (expired) return <main className="identity-page"><h1>Sign in to continue</h1><p>Your private workspace is hidden until your session is verified.</p><Link to="/login">Sign in</Link></main>;
  if (!user && verification_required) return <main className="identity-page"><h1>Sign in to open a customer workspace</h1><Link to="/login">Sign in</Link> · <Link to="/signup">Create an account</Link></main>;
  if (user && verification_required && !user.email_verified) return <main className="identity-page"><h1>Verify your email</h1><p>Complete verification before opening your private workspace.</p><Link to="/account">Account &amp; verification</Link></main>;
  return <div key={user ? `${user.user_id}:${user.tenant_id}` : "anonymous"}>{children}</div>;
}


export function AccountBoundary({children}:{children:ReactNode}) {
  const {user,loading,expired}=useIdentity();
  if(loading)return <main className="identity-page"><p role="status">Loading account permissions…</p></main>;
  if(expired)return <main className="identity-page"><h1>Sign in to continue</h1><Link to="/login">Sign in</Link></main>;
  return <div key={user?`${user.user_id}:${user.tenant_id}`:'anonymous'}>{children}</div>;
}
