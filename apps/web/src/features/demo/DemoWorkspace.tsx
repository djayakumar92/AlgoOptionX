import {useCallback,useEffect,useRef,useState} from 'react';
import type {ReactNode} from 'react';
import {NavLink,useLocation,useNavigate} from 'react-router-dom';
import {Panel,Badge,EmptyState} from '../../shared/ui';
import {useWorkspaceTheme} from '../../shared/theme/useWorkspaceTheme';
import type {ThemePreference} from '../../shared/theme/useWorkspaceTheme';
import {Candles} from './Charts';
import {BuilderScreen,InsightsScreen,JournalScreen,MarketScreen,Observations,OptionsScreen,PaperScreen,ResearchScreen,RiskScreen,RiskSummary,Stats} from './Screens';
import {clock,demoApi,money,number,strategyName} from './api';
import type {ChartAnnotation,Draft,Position,Preview,Research,State,Strategy} from './types';
import '../workspace/styles/workspace.css';
import './demo.css';

const routes=[['','Command Center','COMMAND'],['market','Market Intelligence','MARKET'],['options','Options Intelligence','OPTIONS'],['strategy','Strategy Builder','STRATEGY'],['paper','Paper Trading','PAPER'],['risk','Risk Monitor','RISK'],['journal','Trading Journal','JOURNAL'],['research','Research & Backtesting','RESEARCH'],['insights','AI Insights & Governance','INSIGHTS']] as const;
const descriptions=['A single view of synthetic market evidence, capital and paper risk.','Inspect completed candles and the observations behind each market description.','Compare synthetic call and put quotes, liquidity assumptions and model Greeks.','Build a bounded strategy. Understand every leg, cost and risk before confirmation.','Practice the complete trade lifecycle with virtual capital and atomic simulated fills.','Understand capital, conservative reserves, loss limits and entry restrictions.','Review immutable trade economics and preserve your own decision notes.','Compute repeatable illustrative evaluations, with costs and uncertainty in view.','Inspect commentary provenance, execution boundaries and local audit evidence.'];
type Confirmation={type:'open';draft:Draft;preview:Preview}|{type:'close';position:Position}|{type:'kill'};

export default function DemoWorkspace() {
 const location=useLocation(),navigate=useNavigate();
 const slug=location.pathname.replace(/^\/demo\/?/,'').split('/')[0];
 const index=routes.findIndex(v=>v[0]===slug),route=routes[index];
 const {theme,changeTheme}=useWorkspaceTheme();
 const [state,setState]=useState<State|null>(null),[transport,setTransport]=useState(true),[connectionError,setConnectionError]=useState(''),[error,setError]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false),[menu,setMenu]=useState(false);
 const [mobile,setMobile]=useState(()=>window.matchMedia('(max-width:760px)').matches);
 useEffect(()=>{const media=window.matchMedia('(max-width:760px)');const update=()=>setMobile(media.matches);media.addEventListener('change',update);return()=>media.removeEventListener('change',update);},[]);
 const [annotations,setAnnotations]=useState<ChartAnnotation[]>([]);
 const [timeframe,setTimeframe]=useState<'5'|'30'>('5'),[expiry,setExpiry]=useState('2026-11-03T15:30:00+05:30');
 const [draft,setDraft]=useState<Draft>({strategy:'bull-put',lots:1,expiry:'2026-11-03T15:30:00+05:30',strikes:[]}),[preview,setPreview]=useState<Preview|null>(null),[previewBusy,setPreviewBusy]=useState(false),[previewError,setPreviewError]=useState('');
 const [previewRetry,setPreviewRetry]=useState(0),[previewRisk,setPreviewRisk]=useState('');
 const [research,setResearch]=useState<Research|null>(null),[researchBusy,setResearchBusy]=useState(false),[confirmation,setConfirmation]=useState<Confirmation|null>(null);
 const alive=useRef(true),fetchSequence=useRef(0),appliedSequence=useRef(0),busyRef=useRef(false),retryRef=useRef<{signature:string;key:string}|null>(null);
 const dialog=useRef<HTMLDialogElement>(null),opener=useRef<HTMLElement|null>(null),cancel=useRef<HTMLButtonElement>(null),heading=useRef<HTMLHeadingElement>(null);
 const refresh=useCallback(async()=>{
  const sequence=++fetchSequence.current;
  try {const value=await demoApi<State>('state');if(alive.current&&sequence>=appliedSequence.current){appliedSequence.current=sequence;setState(value);setTransport(true);setConnectionError('');}return value;}
  catch(e){if(alive.current&&sequence>=appliedSequence.current){appliedSequence.current=sequence;setTransport(false);setConnectionError(e instanceof TypeError?'The local demo server is unavailable. Displayed values may be stale.':(e as Error).message);}return null;}
 },[]);
 useEffect(()=>{alive.current=true;let active=true;let timer:ReturnType<typeof setTimeout>;
  const poll=async()=>{if(!busyRef.current)await refresh();if(active)timer=setTimeout(poll,1500);};void poll();
  return()=>{active=false;alive.current=false;clearTimeout(timer);};
 },[refresh]);
 useEffect(()=>{setMenu(false);},[slug]);
 useEffect(()=>{if(!notice)return;const timer=setTimeout(()=>setNotice(''),6500);return()=>clearTimeout(timer);},[notice]);
 const riskFingerprint=state?JSON.stringify([state.account.open_count,state.account.reserve,state.account.liquidation_equity,state.account.daily_loss,state.limits,state.contracts.length]):'';
 const sessionId=state?.session.id,tick=state?.session.tick,connected=state?.session.connected,killed=state?.session.killed;
 useEffect(()=>{setAnnotations([]);},[sessionId]);
 useEffect(()=>{if(!sessionId||slug!=='strategy')return;let active=true;setPreviewBusy(true);setPreviewError('');
  demoApi<Preview>('preview',draft).then(v=>{if(active){setPreview(v);setPreviewRisk(riskFingerprint);}}).catch(e=>{if(active){setPreview(null);setPreviewError(e instanceof TypeError?'Could not load the strategy preview. Reconnect and retry.':(e as Error).message);}}).finally(()=>{if(active)setPreviewBusy(false);});
  return()=>{active=false;};
 },[slug,draft,sessionId,tick,connected,killed,riskFingerprint,previewRetry]);
 useEffect(()=>{const node=dialog.current;if(!node)return;
  if(confirmation&&!node.open){node.showModal();cancel.current?.focus();}
  if(!confirmation&&node.open){node.close();if(opener.current?.isConnected)opener.current.focus();else heading.current?.focus();}
 },[confirmation]);
 function confirm(value:Confirmation){opener.current=document.activeElement as HTMLElement;setError('');setConfirmation(value);}
 async function act(action:string,fields:Record<string,unknown>={}):Promise<boolean>{
  if(!state||busyRef.current)return false;
  busyRef.current=true;setBusy(true);setError('');
  const signature=JSON.stringify({action,fields,session_id:state.session.id});
  const key=retryRef.current?.signature===signature?retryRef.current.key:crypto.randomUUID();retryRef.current={signature,key};
  try {const result=await demoApi<{ok:boolean;message:string}>('commands',{key,session_id:state.session.id,action,...fields});retryRef.current=null;await refresh();setNotice(result.message);if(action==='session'){setDraft(v=>({...v,strikes:[]}));setResearch(null);}return true;}
  catch(e){setError(e instanceof TypeError?'Could not confirm the response. Refresh the session before retrying; identical retries retain duplicate protection.':(e as Error).message);await refresh();return false;}
  finally{busyRef.current=false;if(alive.current)setBusy(false);}
 }
 async function runConfirmation(){if(!confirmation)return;
  if(confirmation.type==='open')await act('open',{draft:confirmation.draft,quote_token:confirmation.preview.quote_token,reason:'Explicitly reviewed defined-risk demo strategy and costs.'});
  else if(confirmation.type==='close')await act('close',{position_id:confirmation.position.id});else await act('kill');
  setConfirmation(null);
 }
 async function runResearch(strategy:Strategy,scenario:string,split:number){setResearchBusy(true);setError('');try{setResearch(await demoApi<Research>('research',{strategy,scenario,lots:1,split}));}catch(e){setError((e as Error).message);}finally{setResearchBusy(false);}}
 const previewCurrent=!!(state&&preview&&previewRisk===riskFingerprint&&preview.strategy===draft.strategy&&preview.lots===draft.lots&&preview.expiry===draft.expiry&&preview.session_id===state.session.id&&preview.tick===state.session.tick&&(!draft.strikes.length||draft.strikes.every((v,i)=>v===preview.strikes[i])));
 const hasQuotes=!!state?.contracts.length;
 const canReview=!!(previewCurrent&&hasQuotes&&transport&&state?.session.connected&&!state.session.killed&&!busy&&state.session.tick<180&&!previewBusy);
 const isEmpty=!!state&&(slug===''||slug==='market'?state.candles[timeframe].length===0:slug==='options'||slug==='strategy'?state.contracts.length===0:slug==='paper'||slug==='risk'?state.positions.length===0:slug==='journal'?state.journal.length===0:slug==='research'?!research:slug==='insights'?state.analysis.observations.length===0&&state.events.length===0:false);
 const dataState=!state?(connectionError?'error':'loading'):error?'error':!transport||!state.session.connected?'stale':state.session.killed?'disabled':isEmpty?'empty':'ready';
 let content:ReactNode=null;
 if(state){
  if(slug==='')content=<><Stats items={[{label:'NIFTY reference',value:number(state.spot),detail:'Synthetic index points'},{label:'Mark equity',value:money(state.account.equity),detail:`Virtual capital ${money(state.account.capital)}`},{label:'Simulation reserve',value:money(state.account.reserve),detail:'Encumbered capital, not broker margin'},{label:'Daily liquidation loss',value:money(state.account.daily_loss),detail:`Entry lock at ${money(state.limits.daily_loss_limit)}`}]} /><div className="demo-two"><Panel title="NIFTY market overview" eyebrow="COMPLETED SYNTHETIC CANDLES" action={<div role="group" aria-label="Chart timeframe" className="demo-segment">{(['5','30'] as const).map(v=><button key={v} aria-pressed={timeframe===v} onClick={()=>setTimeframe(v)}>{v} min</button>)}</div>}><Candles bars={state.candles[timeframe]} timeframe={timeframe} sessionId={state.session.id} annotations={annotations} onAnnotationsChange={setAnnotations}/><NavLink className="demo-text-link" to="/demo/market">Inspect market observations →</NavLink></Panel><Panel title="Decision context"><Observations state={state}/><NavLink className="demo-primary demo-button" to="/demo/strategy">Analyze a strategy →</NavLink></Panel></div><div className="demo-two"><Panel title="Current paper risk"><RiskSummary state={state}/></Panel><Panel title="Practice the complete lifecycle"><ol className="demo-steps"><li>Review market and option observations.</li><li>Build a defined-risk strategy and inspect costs.</li><li>Confirm a simulated order and follow its risk.</li><li>Close the strategy and review the journal.</li></ol><p className="demo-note">No live execution or guaranteed outcome is provided.</p><NavLink className="demo-text-link" to="/demo/paper">Open Paper Trading →</NavLink></Panel></div></>;
  if(slug==='market')content=<MarketScreen state={state} timeframe={timeframe} setTimeframe={setTimeframe} annotations={annotations} onAnnotationsChange={setAnnotations}/>;
  if(slug==='options')content=<OptionsScreen state={state} expiry={expiry} setExpiry={setExpiry} onBuild={(right,strike,chosenExpiry)=>{setDraft({strategy:right==='PE'?'bull-put':'bear-call',lots:1,expiry:chosenExpiry,strikes:[strike,strike+(right==='PE'?-50:50)]});navigate('/demo/strategy');}}/>;
  if(slug==='strategy')content=<BuilderScreen state={state} draft={draft} setDraft={setDraft} preview={previewCurrent?preview:null} loading={previewBusy} error={previewError} onRetry={()=>setPreviewRetry(v=>v+1)} canReview={canReview} onReview={()=>{if(previewCurrent&&preview)confirm({type:'open',draft:{...draft,strikes:[...draft.strikes]},preview});}}/>;
  if(slug==='paper')content=<PaperScreen state={state} onClose={position=>confirm({type:'close',position})} onKill={()=>confirm({type:'kill'})} disabled={!transport||busy}/>;
  if(slug==='risk')content=<RiskScreen state={state}/>;
  if(slug==='journal')content=<JournalScreen state={state} disabled={!transport||busy} onNote={async(id,note,category)=>{await act('note',{position_id:id,note,category});}}/>;
  if(slug==='research')content=<ResearchScreen result={research} busy={researchBusy||!transport} onRun={(strategy,scenario,split)=>void runResearch(strategy,scenario,split)}/>;
  if(slug==='insights')content=<InsightsScreen state={state}/>;
 }
 return <div className="ax-app demo-app">
  <a className="ax-skip" href="#demo-main">Skip to demo content</a>
  <aside className={`demo-sidebar ${menu?'is-open':''}`} inert={mobile&&!menu} role={mobile&&menu?'dialog':undefined} aria-modal={mobile&&menu?true:undefined} aria-label={mobile&&menu?'Demo navigation menu':undefined} onKeyDown={e=>{if(!mobile||!menu)return;if(e.key==='Escape'){setMenu(false);requestAnimationFrame(()=>document.querySelector<HTMLButtonElement>('.demo-menu')?.focus());}if(e.key==='Tab'){const controls=Array.from(e.currentTarget.querySelectorAll<HTMLElement>('a[href],button:not([disabled])'));const first=controls[0],last=controls[controls.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}}}}><button className="demo-nav-close" aria-label="Close navigation menu" onClick={()=>{setMenu(false);requestAnimationFrame(()=>document.querySelector<HTMLButtonElement>('.demo-menu')?.focus());}}>Close menu ×</button><NavLink to="/demo" className="demo-brand"><span className="demo-symbol">A×</span><span>AlgoOption<span className="demo-brand-x">X</span><small>ENTERPRISE DEMO</small></span></NavLink><div className="demo-workspace-label"><Badge tone="purple">SIMULATION</Badge><span>Virtual capital only</span></div><nav aria-label="Demo navigation">{routes.map(([path,label],i)=><div key={path}>{[0,3,7].includes(i)&&<span className="demo-nav-group">{i===0?'MARKET':i===3?'STRATEGY & PAPER':'RESEARCH & REVIEW'}</span>}<NavLink to={path?`/demo/${path}`:'/demo'} end={!path} onClick={()=>{setMenu(false);if(mobile)requestAnimationFrame(()=>heading.current?.focus());}} className={({isActive})=>isActive?'selected':''}><span aria-hidden="true" className="demo-nav-number">{String(i+1).padStart(2,'0')}</span>{label}</NavLink></div>)}</nav><div className="demo-sidebar-bottom"><strong>Research. Practice. Review.</strong><p>Synthetic observations.<br/>No broker routing.</p><a href="/app/overview">Return to original workspace →</a></div></aside>
  {menu&&<button className="demo-overlay" aria-label="Close demo navigation" onClick={()=>{setMenu(false);requestAnimationFrame(()=>document.querySelector<HTMLButtonElement>('.demo-menu')?.focus());}}/>}
  <div className="demo-main" inert={mobile&&menu}><header className="demo-topbar"><div><button className="demo-menu" aria-label="Toggle demo navigation" aria-expanded={menu} onClick={()=>{setMenu(!menu);if(!menu)requestAnimationFrame(()=>document.querySelector<HTMLButtonElement>('.demo-nav-close')?.focus());}}>☰</button><span className="demo-breadcrumb">Demo / <strong>{route?.[1]||'Page not found'}</strong></span></div><div className="demo-topbar-tools"><label>Theme<select aria-label="Demo theme" value={theme} onChange={e=>changeTheme(e.target.value as ThemePreference)}><option value="light">Light</option><option value="dark">Dark</option><option value="system">System</option></select></label><Badge>NO LIVE ORDERS</Badge></div></header>
  <main id="demo-main" className="demo-content" aria-busy={!state&&!connectionError} data-screen={route?.[2]||'UNKNOWN'} data-state={dataState}>
   <div className="demo-page-head"><div><span className="demo-eyebrow">ALGOOPTIONX / SYNTHETIC WORKSPACE</span><h1 ref={heading} tabIndex={-1}>{route?.[1]||'Page not found'}</h1><p>{index>=0?descriptions[index]:'Choose one of the demo screens.'}</p></div><Badge tone="purple">DEMO MODE</Badge></div>
   <section className="demo-session-bar" aria-label="Synthetic session controls"><div><strong>SYNTHETIC DATA</strong><span>{state?`${clock(state.session.time)} IST`:'Fixed demo clock'}</span>{state&&<small>Bar {state.session.tick} / 180 · quote bar {state.session.quote_tick}</small>}</div><div className="demo-session-actions"><label>Scenario<select aria-label="Demo scenario" value={state?.session.scenario||'bullish'} disabled={!state||!transport||busy||!!state.positions.length} onChange={e=>void act('session',{scenario:e.target.value})}>{(state?.scenarios||[{id:'bullish',label:'A · Bullish trend'}]).map(v=><option key={v.id} value={v.id}>{v.label}</option>)}</select></label><button disabled={!state||!transport||busy||state.session.tick>=180} onClick={()=>void act('step',{steps:5})}>+5 minutes</button>{state&&<button disabled={!transport||busy} onClick={()=>void act(state.session.connected?'disconnect':'reconnect')}>{state.session.connected?'Simulate disconnect':'Reconnect fixture'}</button>}</div>{!!state?.positions.length&&<small className="demo-session-hint">Close all strategies before changing scenario. Previous sessions are preserved.</small>}</section>
   {!state&&!connectionError&&<Panel title="Loading demo session"><div role="status" className="demo-loading">Connecting to the isolated synthetic engine…</div></Panel>}
   {connectionError&&<div role="alert" className="demo-alert"><strong>{state?'Displayed values may be stale.':'Demo session unavailable.'}</strong><p>{connectionError}</p><button onClick={()=>void refresh()}>Retry connection</button></div>}
   {!!state&&!state.session.connected&&<div role="alert" className="demo-alert"><strong>Synthetic data disconnected — entries blocked.</strong><p>Last-valid quotes: {clock(state.session.quote_time)} IST. Emergency simulation exits disclose their last-valid quote source.</p></div>}
   {!!state?.session.killed&&<div role="alert" className="demo-alert"><strong>Emergency stop latched — entries disabled.</strong><p>{state.session.kill_error||'Create a new session only after all strategies are closed. History is retained.'}</p></div>}
   {error&&<div role="alert" className="demo-alert demo-error"><strong>Action could not complete</strong><p>{error}</p><button onClick={()=>setError('')}>Dismiss action message</button></div>}
   {notice&&<div role="status" className="demo-notice">{notice}<button aria-label="Dismiss success message" onClick={()=>setNotice('')}>×</button></div>}
   {isEmpty&&state&&<p className="demo-empty-note">This screen has no {slug==='research'?'evaluation results yet':slug==='paper'||slug==='risk'?'open strategy exposure':slug==='journal'?'trade history yet':'available data for this view'}. Navigation and recovery remain available.</p>}
   {route?content:<Panel title="Choose a demo screen"><EmptyState title="Page not found" text="Use the demo navigation to continue."/></Panel>}
   <footer className="demo-footer"><span>Deterministic synthetic fixtures · virtual capital · offline execution</span><span>No predictive accuracy or profitability established.</span></footer>
  </main></div>
  <dialog ref={dialog} className="demo-dialog" aria-labelledby="demo-confirm-title" onCancel={e=>{e.preventDefault();setConfirmation(null);}} onKeyDown={e=>{if(e.key!=='Tab')return;const controls=Array.from(e.currentTarget.querySelectorAll<HTMLElement>('button:not([disabled]),select:not([disabled]),textarea:not([disabled]),a[href]'));const first=controls[0],last=controls[controls.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}}}><h2 id="demo-confirm-title">{confirmation?.type==='open'?'Confirm simulated strategy':confirmation?.type==='close'?'Confirm strategy close':'Confirm emergency stop'}</h2>{confirmation?.type==='open'?<><p>{strategyName(confirmation.preview.strategy)} · {confirmation.preview.quantity} units per leg.</p><dl className="demo-metrics"><div><dt>Opening net credit</dt><dd>{money(confirmation.preview.entry_net_credit)}</dd></div><div><dt>Conservative reserve</dt><dd>{money(confirmation.preview.reserve)}</dd></div><div><dt>Quote bar</dt><dd>{confirmation.preview.tick}</dd></div></dl>{confirmation.preview.errors.length>0&&<p className="demo-error">This draft will be rejected by risk controls. Submission records the rejected attempt without changing positions or cash.</p>}<p className="demo-note">All legs are validated and filled atomically in the offline demo. No live order is submitted.</p></>:confirmation?.type==='close'?<p>Close every leg of {strategyName(confirmation.position.data.strategy)} at current synthetic executable quotes and include exit fees?</p>:<p>Latch new entries off and close all open strategies. If data is disconnected, explicitly use last-valid synthetic executable quotes. The stop remains latched if any close fails.</p>}{confirmation?.type==='open'&&confirmation.preview.tick!==state?.session.tick&&<p role="alert" className="demo-error">The quote changed while this confirmation was open. Cancel and review a fresh preview.</p>}<div className="demo-dialog-actions"><button ref={cancel} disabled={busy} onClick={()=>setConfirmation(null)}>Cancel</button><button className="demo-primary" disabled={busy||!transport||(confirmation?.type==='open'&&confirmation.preview.tick!==state?.session.tick)} onClick={()=>void runConfirmation()}>{busy?'Validating…':confirmation?.type==='open'?(confirmation.preview.valid?'Confirm simulated order':'Record rejected attempt'):confirmation?.type==='close'?'Confirm strategy close':'Confirm emergency stop'}</button></div></dialog>
 </div>;
}
