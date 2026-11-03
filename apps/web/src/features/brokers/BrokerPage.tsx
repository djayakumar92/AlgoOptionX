import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiFetch } from "../../shared/lib/http";
import { useIdentity } from "../identity/IdentityContext";

type Connection = { id: string; broker: string; label: string; expires_at: number | null; status: string; capabilities: { account_read?: boolean; market_data?: string; order_submission?: boolean }; updated_at: number };
async function brokerApi<T>(path = "", body?: unknown): Promise<T> {
  const response = await apiFetch(`/api/brokers${path}`, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const value = await response.json();
  if (!response.ok) throw new Error(typeof value.detail === "string" ? value.detail : "Check the connection details and try again.");
  return value;
}
export default function BrokerPage() {
  const { user, loading } = useIdentity();
  const [connections, setConnections] = useState<Connection[]>([]), [loaded, setLoaded] = useState(false), [busy, setBusy] = useState(false);
  const [label, setLabel] = useState("My Dhan account"), [clientId, setClientId] = useState(""), [token, setToken] = useState(""), [expiry, setExpiry] = useState("");
  const [error, setError] = useState(""), [notice, setNotice] = useState("");
  async function load() { const value = await brokerApi<{ connections: Connection[] }>(); setConnections(value.connections); setLoaded(true); }
  useEffect(() => { document.title = "Broker connections | AlgoOptionX"; if (user) void load().catch(failure => setError(failure.message)); }, [user?.tenant_id, user?.user_id]);
  async function act(action: () => Promise<void>) { setBusy(true); setError(""); setNotice(""); try { await action(); } catch (failure) { setError((failure as Error).message); } finally { setBusy(false); } }
  if (loading) return <main id="product-content" className="account-page"><p role="status">Loading broker permissions…</p></main>;
  if (!user) return <main id="product-content" className="account-page"><h1>Broker connections</h1><Link to="/login">Sign in to manage your connections</Link></main>;
  return <main id="product-content" className="account-page"><span className="product-eyebrow">BROKER CONNECTIONS · READ ACCESS</span><h1>Manage your Dhan connection.</h1><p>Connections belong to you within this workspace. Credentials cannot be read back. Saving a token does not authorize order submission or establish market-data licensing.</p>
    {error && <p role="alert" className="identity-error">{error}</p>}{notice && <p role="status">{notice}</p>}
    <section><h2>Your connections</h2>{!loaded && !error && <p role="status">Loading connections…</p>}{loaded && connections.length === 0 && <p>No broker connection saved.</p>}
      <ul>{connections.map(connection => <li key={connection.id}><div><strong>{connection.label}</strong><p>{connection.broker.toUpperCase()} · {connection.status.replaceAll("_", " ")}</p><p>{connection.expires_at ? `Declared expiry: ${new Date(connection.expires_at * 1000).toLocaleString()}` : "Token expiry not supplied; verify it with the broker."}</p><p>Account read: {connection.capabilities.account_read ? "verified at last test" : "not verified"}. Market data: {connection.capabilities.market_data?.replaceAll("_", " ") || "not verified"}. Order submission: disabled.</p></div><div>
        <button disabled={busy || user.role === "viewer" || ["disconnected", "expired"].includes(connection.status)} onClick={() => void act(async () => { const result = await brokerApi<{ notice: string }>(`/${connection.id}/test`, { expected_tenant_id: user.tenant_id }); setNotice(result.notice); await load(); })}>Test read access</button>
        <button disabled={busy || user.role === "viewer" || connection.status === "disconnected"} onClick={() => { if (window.confirm("Remove the saved local token? You must also revoke it in your broker portal to remove provider authority.")) void act(async () => { const result = await brokerApi<{ notice: string }>(`/${connection.id}/disconnect`, { expected_tenant_id: user.tenant_id }); setNotice(result.notice); await load(); }); }}>Disconnect locally</button>
      </div></li>)}</ul>
    </section>
    <section><h2>Connect or replace a token</h2><p>Use a token from your own Dhan account. Replacing it clears the previous test result. Provider access is tested only when you choose “Test read access”.</p>
      <form autoComplete="off" onSubmit={event => { event.preventDefault(); void act(async () => { try { const result = await brokerApi<{ notice: string }>("", { expected_tenant_id: user.tenant_id, broker: "dhan", label, client_id: clientId, access_token: token, expires_at: expiry ? new Date(expiry).toISOString() : null }); setNotice(result.notice); setClientId(""); setExpiry(""); await load(); } finally { setToken(""); } }); }}>
        <label>Connection label<input value={label} required maxLength={80} onChange={event => setLabel(event.target.value)} /></label>
        <label>Dhan client ID<input type="password" autoComplete="off" value={clientId} required maxLength={80} onChange={event => setClientId(event.target.value)} /></label>
        <label>Access token<input type="password" autoComplete="off" spellCheck={false} value={token} required minLength={10} maxLength={8192} onChange={event => setToken(event.target.value)} /></label>
        <label>Token expiry, in your local timezone (optional)<input type="datetime-local" value={expiry} onChange={event => setExpiry(event.target.value)} /></label>
        <button disabled={busy || user.role === "viewer"}>{busy ? "Working…" : "Save encrypted connection"}</button>
      </form>
    </section><Link to="/account">Back to account &amp; security →</Link>
  </main>;
}
