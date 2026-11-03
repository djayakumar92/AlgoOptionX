import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { identityApi, useIdentity } from "./IdentityContext";
import type { Identity } from "./IdentityContext";
import "./identity.css";

export function IdentityPage({ mode }: { mode: "login" | "signup" | "recover" | "reset" | "verify" | "invite" }) {
  const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [authenticationCode, setAuthenticationCode] = useState(""); const [name, setName] = useState("");
  const [token] = useState(() => new URLSearchParams(window.location.hash.slice(1)).get("token") || "");
  const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [message, setMessage] = useState("");
  const { setIdentity, refresh } = useIdentity(); const navigate = useNavigate(); const location = useLocation();
  const titles = { login: "Welcome back", signup: "Create your workspace", recover: "Recover your account", reset: "Choose a new password", verify: "Verify your email", invite: "Join a workspace" };
  useEffect(() => { document.title = `${titles[mode]} | AlgoOptionX`; }, [mode]);
  useEffect(() => { if (location.hash && (mode === "reset" || mode === "verify" || mode === "invite")) navigate(location.pathname, { replace: true }); }, [location.hash, location.pathname, mode, navigate]);
  async function submit(event: React.FormEvent) {
    event.preventDefault(); if (busy) return; setBusy(true); setError(""); setMessage("");
    try {
      if (mode === "login" || mode === "signup") {
        const result = await identityApi<Identity>(mode === "login" ? "login" : "register", { email, password, ...(authenticationCode ? {authentication_code:authenticationCode} : {}), ...(mode === "signup" ? { name } : {}) });
        setIdentity(result); setPassword(""); navigate(result.verification_required && !result.user?.email_verified ? "/account" : "/demo");
      } else if (mode === "recover") {
        const value = await identityApi<{ message: string }>("request-reset", { email }); setMessage(value.message);
      } else if (mode === "reset") {
        const value = await identityApi<{ message: string }>("reset-password", { token, password }); setPassword(""); setMessage(value.message);
      } else {
        await identityApi(mode === "invite" ? "accept-invite" : "verify-email", { token }); await refresh(); setMessage(mode === "invite" ? "Invitation accepted. Choose your workspace in account settings." : "Email verified. Your workspace is ready.");
      }
    } catch (failure) { setError((failure as Error).message); } finally { setBusy(false); }
  }
  return <main id="product-content" className="identity-page"><span className="product-eyebrow">ALGOOPTIONX ACCOUNT</span><h1>{titles[mode]}</h1>
    <p>{mode === "signup" ? "Keep your research and paper accounts separate from other customers. Trading remains synthetic and paper-only." : "Secure access to your research workspace."}</p>
    <form onSubmit={event => void submit(event)}>
      {mode === "signup" && <label>Your name<input autoComplete="name" value={name} onChange={event => setName(event.target.value)} required maxLength={80} /></label>}
      {["login", "signup", "recover"].includes(mode) && <label>Email<input type="email" autoComplete="email" value={email} onChange={event => setEmail(event.target.value)} required maxLength={254} /></label>}
      {["login", "signup", "reset"].includes(mode) && <label>Password<input type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} value={password} onChange={event => setPassword(event.target.value)} aria-describedby={mode === "login" ? undefined : "password-guidance"} required minLength={mode === "login" ? 1 : 12} maxLength={128} /></label>}{["signup", "reset"].includes(mode) && <small id="password-guidance">Use 12–128 characters. Never reuse broker credentials.</small>}
      {mode === "login" && <label>Authenticator or recovery code (if enabled)<input autoComplete="one-time-code" value={authenticationCode} onChange={event => setAuthenticationCode(event.target.value)} maxLength={40}/></label>}
      {(mode === "reset" || mode === "verify" || mode === "invite") && !token && <p role="alert">Open the complete link from your email. No valid token was provided.</p>}
      {error && <p role="alert" className="identity-error">{error}</p>}{message && <p role="status">{message}</p>}
      {!message && <button className="product-button" disabled={busy || ((mode === "reset" || mode === "verify" || mode === "invite") && !token)}>{busy ? "Please wait…" : mode === "login" ? "Sign in" : mode === "signup" ? "Create account" : mode === "recover" ? "Send recovery link" : mode === "reset" ? "Reset password" : mode === "invite" ? "Accept invitation" : "Verify email"}</button>}
    </form>
    <div className="identity-links">{mode === "login" ? <><Link to="/signup">Create an account</Link><Link to="/recover">Forgot password?</Link></> : <Link to="/login">Back to sign in</Link>}<Link to="/app/start">Explore the local demo</Link></div>
  </main>;
}

type Tenant = {id: string; name: string; role: string};
type Member = {id: string; name: string; email: string; role: string};
type Session = { id: string; created_at: number; last_seen: number; expires_at: number; current: boolean };
export function AccountPage() {
  const { user, loading, refresh, logout, email_delivery } = useIdentity();
  const [sessions, setSessions] = useState<Session[]>([]); const [name, setName] = useState(""); const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [message, setMessage] = useState("");
  const [tenants, setTenants] = useState<Tenant[]>([]); const [members, setMembers] = useState<Member[]>([]); const [workspaceName, setWorkspaceName] = useState(""); const [inviteEmail, setInviteEmail] = useState(""); const [inviteRole, setInviteRole] = useState("viewer");
  const navigate = useNavigate();
  async function load() { const value = await identityApi<{ sessions: Session[] }>("sessions"); setSessions(value.sessions); }
  useEffect(() => { document.title = "Account & security | AlgoOptionX"; if (user) { setName(user.name); void load().catch(failure => setError(failure.message)); } }, [user?.user_id]);
  async function act(action: () => Promise<void>) { setBusy(true); setError(""); setMessage(""); try { await action(); } catch (failure) { setError((failure as Error).message); } finally { setBusy(false); } }
  if (loading) return <main id="product-content" className="identity-page"><p role="status">Loading your account…</p></main>;
  if (!user) return <main id="product-content" className="identity-page"><h1>Sign in to manage your account</h1><Link className="product-button" to="/login">Sign in</Link></main>;
  return <main id="product-content" className="account-page"><span className="product-eyebrow">ACCOUNT &amp; SECURITY</span><h1>{user.name}'s account</h1><p>{user.email} · {user.email_verified ? "Verified" : "Verification pending"}</p>
    {error && <p role="alert" className="identity-error">{error}</p>}{message && <p role="status">{message}</p>}
    <section><h2>Workspace</h2><p>{user.tenant_name} · {user.role}</p><p>Customer paper and demo history is isolated from the anonymous local workspace.</p><Link to="/demo" className="product-button">Open workspace →</Link></section>
    <section><h2>Workspaces &amp; members</h2>
      <button disabled={busy} onClick={() => void act(async () => { const value = await identityApi<{tenants: Tenant[]}>("tenants"); setTenants(value.tenants); if(user.role === "owner") { const people = await identityApi<{members: Member[]}>("members"); setMembers(people.members); } })}>Load workspaces &amp; members</button>
      <ul>{tenants.map(tenant => <li key={tenant.id}><span>{tenant.name} · {tenant.role}{tenant.id === user.tenant_id ? " · Current" : ""}</span>{tenant.id !== user.tenant_id && <button disabled={busy} onClick={() => void act(async () => { await identityApi("switch-tenant", {tenant_id: tenant.id, expected_tenant_id: user.tenant_id}); await refresh(); navigate("/demo"); })}>Switch workspace</button>}</li>)}</ul>
      <form onSubmit={event => { event.preventDefault(); void act(async () => { await identityApi("tenants", {name: workspaceName}); setWorkspaceName(""); const value = await identityApi<{tenants: Tenant[]}>("tenants"); setTenants(value.tenants); setMessage("Workspace created. Switch to it when ready."); }); }}><label>New workspace name<input value={workspaceName} onChange={event => setWorkspaceName(event.target.value)} required maxLength={80}/></label><button disabled={busy}>Create workspace</button></form>
      {user.role === "owner" && <><ul>{members.map(member => <li key={member.id}><span>{member.name} · {member.email} · {member.role}</span>{member.role !== "owner" && <button disabled={busy} onClick={() => void act(async () => { await identityApi(`members/${member.id}/remove`, {expected_tenant_id: user.tenant_id}); const value = await identityApi<{members: Member[]}>("members"); setMembers(value.members); })}>Remove member</button>}</li>)}</ul><form onSubmit={event => { event.preventDefault(); void act(async () => { const value = await identityApi<{message: string}>("invite", {email: inviteEmail, role: inviteRole, expected_tenant_id: user.tenant_id}); setInviteEmail(""); setMessage(value.message); }); }}><label>Invite email<input type="email" value={inviteEmail} onChange={event => setInviteEmail(event.target.value)} required/></label><label>Permission<select value={inviteRole} onChange={event => setInviteRole(event.target.value)}><option value="viewer">Read-only viewer</option><option value="trader">Paper trader</option></select></label><button disabled={busy}>Send invitation</button></form></>}
    </section>
    <section><h2>Profile</h2><form onSubmit={event => { event.preventDefault(); void act(async () => { await identityApi("profile", { name }); await refresh(); setMessage("Profile updated."); }); }}><label>Name<input value={name} onChange={event => setName(event.target.value)} required maxLength={80} /></label><button disabled={busy}>Save profile</button></form></section>
    {!user.email_verified && <section><h2>Verify email</h2><p>{email_delivery === "file" ? "Development delivery writes emails to the private local outbox. Configure SMTP before hosted use." : "Send a verification link to your registered email."}</p><button disabled={busy} onClick={() => void act(async () => { const value = await identityApi<{ message: string }>("request-verification", {}); setMessage(value.message); })}>Send verification email</button></section>}
    <section><h2>Active sessions</h2><ul>{sessions.map(session => <li key={session.id}><span>{session.current ? "This session" : "Other session"} · last active {new Date(session.last_seen * 1000).toLocaleString()}</span><button disabled={busy} onClick={() => void act(async () => { await identityApi(`sessions/${session.id}/revoke`, {}); if (session.current) { await refresh(); navigate("/login"); } else await load(); })}>Revoke{session.current ? " this session" : " session"}</button></li>)}</ul></section>
    <div className="identity-links"><Link to="/account/mfa">Authenticator security</Link><Link to="/brokers">Broker connections</Link><Link to="/operations">Workspace operations</Link><Link to="/billing">Billing &amp; usage</Link><Link to="/recover">Reset password</Link><button disabled={busy} onClick={() => void act(async () => { await logout(); navigate("/login"); })}>Sign out</button></div>
  </main>;
}
