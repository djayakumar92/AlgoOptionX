import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { apiFetch } from "../../shared/lib/http";
import { openSandboxCheckout } from "./checkout";
import type { SandboxCheckout } from "./checkout";
import { useIdentity } from "../identity/IdentityContext";

type Plan = { id: string; name: string; features: string[]; amount_paise: number | null; credits: number | null; checkout_available: boolean };
type Plans = { plans: Plan[]; currency: string; mode: string; notice: string };
type Account = { subscription: { plan: string; status: string; period_end: number | null }; credits: number; receipts: { id: string; amount: number; currency: string; created_at: number }[]; credit_history: { kind: string; units: number; created_at: number }[]; notice: string };
async function billing<T>(path: string, body?: unknown): Promise<T> { const response = await apiFetch(`/api/billing/${path}`, body === undefined ? {} : {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)}); const value = await response.json(); if(!response.ok)throw new Error(value.detail || "Billing is unavailable."); return value; }
const money = (value: number) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(value / 100);
export function PricingPage() {
  const [plans, setPlans] = useState<Plans | null>(null); const [error, setError] = useState("");
  useEffect(() => { document.title = "Plans & pricing | AlgoOptionX"; void billing<Plans>("plans").then(setPlans).catch(failure => setError(failure.message)); }, []);
  return <main id="product-content" className="account-page"><span className="product-eyebrow">PLANS &amp; ENTITLEMENTS</span><h1>Choose how you research.</h1><p>Commercial plan definitions are proposals until pricing and integrations are approved. The local synthetic demo remains available.</p>{error && <p role="alert">{error}</p>}{!plans && !error && <p role="status">Loading plan definitions…</p>}
    <div className="product-cards">{plans?.plans.map(plan => <article key={plan.id}><h2>{plan.name}</h2><p>{plan.id === "free" ? "Local demo included" : plan.amount_paise === null ? "Pricing not configured" : `${money(plan.amount_paise)} · sandbox evaluation period`}</p><ul>{plan.features.map(feature => <li key={feature}>{feature}</li>)}</ul><p>{plan.credits === null ? "Commercial quotas pending" : `${plan.credits} platform credits`}</p><Link to={plan.id === "free" ? "/app/start" : "/billing"} className="product-text-link">{plan.id === "free" ? "Explore the demo →" : "View billing readiness →"}</Link></article>)}</div>
    {plans && <section><h2>Transparent boundaries</h2><p>{plans.notice}</p><p>Platform credits, real payments and virtual trading capital are separate. No ₹1–₹2 paper-trade charge has been activated. Data licensing fees and tax policies require approval before launch.</p></section>}
  </main>;
}
export function BillingPage() {
  const { user, loading } = useIdentity();
  const [busy,setBusy]=useState(false),[notice,setNotice]=useState(''),[checkouts,setCheckouts]=useState<{id:string;plan:string;amount:number;status:string;created_at:number}[]>([]);
  const retry=useRef<{plan:string;key:string}|null>(null);
  async function history(){if(user?.role==='owner'){const value=await billing<{checkouts:typeof checkouts}>('checkouts');setCheckouts(value.checkouts);}}
  async function refresh(){setAccount(await billing<Account>('account'));await history();}
  async function act(action:()=>Promise<void>){setBusy(true);setError('');setNotice('');try{await action();await refresh();}catch(failure){setError((failure as Error).message);}finally{setBusy(false);}}
  const [account, setAccount] = useState<Account | null>(null); const [error, setError] = useState(""); const [plans, setPlans] = useState<Plans | null>(null);
  useEffect(() => { document.title = "Billing & usage | AlgoOptionX"; if(user)void Promise.all([billing<Account>("account"), billing<Plans>("plans")]).then(([value,catalog]) => {setAccount(value);setPlans(catalog);void history().catch(failure=>setError(failure.message));}).catch(failure => setError(failure.message)); }, [user?.tenant_id]);
  if(loading)return <main id="product-content" className="account-page"><p role="status">Loading account…</p></main>;
  if(!user)return <main id="product-content" className="account-page"><h1>Billing &amp; usage</h1><Link to="/login" className="product-button">Sign in to view your billing</Link></main>;
  return <main id="product-content" className="account-page"><span className="product-eyebrow">BILLING &amp; USAGE</span><h1>Your platform account</h1>{error && <p role="alert">{error}</p>}{!account && !error && <p role="status">Loading billing history…</p>}{account && <>
    <section><h2>Subscription</h2><p>{account.subscription.plan} · {account.subscription.status}</p><p>{account.subscription.period_end ? `Period ends ${new Date(account.subscription.period_end*1000).toLocaleDateString()}` : "No paid renewal scheduled."}</p><Link to="/pricing">Compare proposed plans →</Link></section>
    <section><h2>Platform usage credits</h2><p><strong>{account.credits}</strong> credits</p><p>{account.notice}</p><p>Closing positions and emergency controls never depend on a credit purchase.</p><ul>{account.credit_history.map((entry,i) => <li key={i}>{entry.kind} · {entry.units > 0 ? "+" : ""}{entry.units} · {new Date(entry.created_at*1000).toLocaleString()}</li>)}</ul></section>
    <section><h2>Sandbox checkout</h2><p>{plans?.notice || "Loading provider readiness…"}</p><p>Only configured test-mode plans can open checkout. Browser callbacks never grant access or credits. Live payments remain disabled.</p>{notice&&<p role="status">{notice}</p>}{user.role==='owner'?<div className="identity-links">{plans?.plans.filter(plan=>plan.id!=='free').map(plan=><button key={plan.id} disabled={busy||!plan.checkout_available} onClick={()=>{if(!window.confirm(`Open TEST MODE checkout for ${plan.name} at ${plan.amount_paise===null?'unconfigured pricing':money(plan.amount_paise)}?`))return;void act(async()=>{if(retry.current?.plan!==plan.id)retry.current={plan:plan.id,key:crypto.randomUUID()};const value=await billing<SandboxCheckout>('checkout',{plan:plan.id,key:retry.current.key,expected_tenant_id:user.tenant_id});await openSandboxCheckout(value,setNotice);});}}>Test {plan.name}{plan.checkout_available?'':' · not configured'}</button>)}</div>:<p>Only a workspace owner can initiate or reconcile checkout.</p>}<button disabled={busy} onClick={()=>void act(refresh)}>Refresh billing status</button></section>
    {user.role==='owner'&&<section><h2>Checkout attempts</h2>{checkouts.length?<ul>{checkouts.map(checkout=><li key={checkout.id}><span>{checkout.plan} · {money(checkout.amount)} · {checkout.status} · {new Date(checkout.created_at*1000).toLocaleString()}</span><button disabled={busy} onClick={()=>void act(async()=>{const value=await billing<{notice:string}>(`checkouts/${checkout.id}/reconcile`,{expected_tenant_id:user.tenant_id});setNotice(value.notice);retry.current=null;})}>Reconcile provider status</button></li>)}</ul>:<p>No checkout attempts.</p>}</section>}
    <section><h2>Payment receipts</h2>{account.receipts.length ? <ul>{account.receipts.map(receipt => <li key={receipt.id}><span>{money(receipt.amount)} · {new Date(receipt.created_at*1000).toLocaleString()}</span><a href={`/api/billing/receipts/${receipt.id}`}>View test receipt</a></li>)}</ul> : <p>No payment receipts.</p>}</section>
  </>}</main>;
}
