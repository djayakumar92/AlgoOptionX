import {test,expect} from '@playwright/test';
import type {APIRequestContext,Page,CDPSession} from '@playwright/test';
import {spawn,spawnSync} from 'node:child_process';
import fs from 'node:fs';import path from 'node:path';import crypto from 'node:crypto';import os from 'node:os';
import type {State,Preview,Research} from '../src/features/demo/types';
const root=path.resolve(import.meta.dirname,'../../..');
const design=JSON.parse(fs.readFileSync(path.join(root,'docs/designs/DEMO-001/r0003/design.json'),'utf8'));
const fixture=JSON.parse(fs.readFileSync(path.join(root,design.fixture.reference.path),'utf8'));
const screens:Record<string,[string,string]>={COMMAND:['','Command Center'],MARKET:['market','Market Intelligence'],OPTIONS:['options','Options Intelligence'],STRATEGY:['strategy','Strategy Builder'],PAPER:['paper','Paper Trading'],RISK:['risk','Risk Monitor'],JOURNAL:['journal','Trading Journal'],RESEARCH:['research','Research & Backtesting'],INSIGHTS:['insights','AI Insights & Governance']};
const url=(s:string)=>'/demo'+(screens[s][0]?'/'+screens[s][0]:'');
const hash=(p:string)=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
async function state(r:APIRequestContext):Promise<State>{const v=await r.get('/api/demo/state');expect(v.ok()).toBeTruthy();return v.json();}
async function cmd(r:APIRequestContext,action:string,fields:Record<string,unknown>={}){const v=await state(r);return r.post('/api/demo/commands',{data:{key:crypto.randomUUID(),session_id:v.session.id,action,...fields}});}
async function fresh(r:APIRequestContext,scenario='bullish'){expect((await cmd(r,'kill')).ok()).toBeTruthy();expect((await cmd(r,'session',{scenario})).ok()).toBeTruthy();return state(r);}
async function enter(r:APIRequestContext){const p:Preview=await (await r.post('/api/demo/preview',{data:{}})).json();expect(p.valid).toBeTruthy();expect((await cmd(r,'open',{draft:{},quote_token:p.quote_token})).ok()).toBeTruthy();return p;}
async function nav(p:Page,name:string){const b=p.getByRole('button',{name:'Toggle demo navigation'});if(await b.isVisible())await b.click();await p.getByRole('navigation',{name:'Demo navigation',exact:true}).getByRole('link',{name,exact:false}).click();}

// A separate real server prevents legacy paper journeys from changing the
// account while these tests verify demo-only storage isolation.
const workflowTest=test.extend<{}, {workflowUrl:string}>({workflowUrl:[async({playwright},use,worker)=>{
 void playwright;
 const directory=fs.mkdtempSync(path.join(process.env.ALGOOPTIONX_EVIDENCE_DIR||os.tmpdir(),'demo-workflow-'));
 const port=8020+worker.parallelIndex,baseURL=`http://127.0.0.1:${port}`;
 const server=spawn(path.join(root,'.venv/bin/python'),['-m','uvicorn','algooptionx.api.app:app','--host','127.0.0.1','--port',String(port)],{cwd:root,env:{PATH:process.env.PATH,PYTHONDONTWRITEBYTECODE:'1',ALGOOPTIONX_DB:path.join(directory,'paper.db'),ALGOOPTIONX_DEMO_DB:path.join(directory,'demo.db')},stdio:'ignore'});
 try{let ready=false;for(let i=0;i<100;i++){try{if((await fetch(baseURL+'/api/health')).ok){ready=true;break;}}catch{}await new Promise(resolve=>setTimeout(resolve,100));}expect(ready,'Isolated real demo server startup').toBeTruthy();await use(baseURL);}finally{server.kill('SIGTERM');await new Promise<void>(resolve=>{if(server.exitCode!==null)resolve();else server.once('exit',()=>resolve());});}
},{scope:'worker'}],baseURL:async({workflowUrl},use)=>{await use(workflowUrl);}});
workflowTest.describe('Demo workflows',()=>{
 workflowTest.describe.configure({mode:'parallel'});
 workflowTest.beforeEach(async({request})=>{await fresh(request);});
 workflowTest('complete lifecycle, keyboard confirmation and journal persistence',async({page,request})=>{
  const original=await (await request.get('/api/workspace')).json();const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/demo');await expect(page.getByRole('heading',{name:'Command Center',exact:true})).toBeVisible();await nav(page,'Options Intelligence');
  await page.getByRole('button',{name:'Build put spread'}).click();await page.getByLabel('Strategy',{exact:true}).selectOption('iron-condor');
  const review=page.getByRole('button',{name:'Review simulated order'});await expect(review).toBeEnabled();await review.click();
  await expect(page.getByRole('button',{name:'Cancel',exact:true})).toBeFocused();await page.keyboard.press('Shift+Tab');await expect(page.getByRole('button',{name:'Confirm simulated order',exact:true})).toBeFocused();await page.keyboard.press('Escape');await expect(review).toBeFocused();
  await review.click();await page.getByRole('button',{name:'Confirm simulated order',exact:true}).click();await expect(page.getByRole('dialog')).toHaveCount(0);await nav(page,'Paper Trading');
  await expect(page.getByRole('button',{name:'Close strategy',exact:true})).toHaveCount(1);expect((await state(request)).positions[0].data.legs).toHaveLength(4);
  await page.getByRole('button',{name:'+5 minutes'}).click();await expect.poll(async()=> (await state(request)).session.tick).toBe(65);
  await page.getByRole('button',{name:'Close strategy',exact:true}).click();await page.getByRole('button',{name:'Confirm strategy close',exact:true}).click();await expect(page.getByText('No open strategies',{exact:true})).toBeVisible();
  const closed=await state(request);expect(closed.account.cash).toBe(closed.account.capital+closed.account.realized);expect(closed.account.reserve).toBe(0);expect(closed.account.fees).toBe(16000);
  await nav(page,'Trading Journal');await page.getByRole('button',{name:'Review trade',exact:true}).first().click();await page.getByLabel('Post-trade notes').fill('Followed plan; review timing.');await page.getByLabel('Review category').selectOption('Timing');await page.getByRole('button',{name:'Save review note'}).click();
  await expect.poll(async()=> (await state(request)).journal[0].note).toBe('Followed plan; review timing.');await page.reload();await page.getByRole('button',{name:'Review trade',exact:true}).first().click();await expect(page.getByLabel('Post-trade notes')).toHaveValue('Followed plan; review timing.');
  expect((await (await request.get('/api/workspace')).json()).account).toEqual(original.account);expect(errors).toEqual([]);
 });
 workflowTest('risk scenario audits rejection without economic effects',async({page,request})=>{
  await fresh(request,'risk-rejection');const before=await state(request);await page.goto('/demo/strategy');await expect(page.getByText('Risk validation will reject this draft.')).toBeVisible();await page.getByRole('button',{name:'Review rejected attempt'}).click();await page.getByRole('button',{name:'Record rejected attempt',exact:true}).click();
  await expect(page.getByText('Action could not complete',{exact:true})).toBeVisible();const after=await state(request);expect(after.positions).toEqual([]);expect(after.account).toEqual(before.account);expect(after.events.some(e=>e.kind==='REJECTED')).toBeTruthy();
 });
 workflowTest('disconnection freezes quotes and emergency exit remains latched',async({page,request})=>{
  await enter(request);await page.goto('/demo/paper');await page.getByRole('button',{name:'Simulate disconnect'}).click();await expect(page.getByText('Synthetic data disconnected — entries blocked.',{exact:true})).toBeVisible();const before=await state(request);
  await page.getByRole('button',{name:'+5 minutes'}).click();await expect.poll(async()=> (await state(request)).session.tick).toBe(before.session.tick+5);expect((await state(request)).session.quote_tick).toBe(before.session.quote_tick);await expect(page.getByRole('button',{name:'Close strategy',exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'Emergency stop simulation'}).click();await expect(page.getByRole('dialog')).toContainText('last-valid synthetic executable quotes');await page.getByRole('button',{name:'Confirm emergency stop',exact:true}).click();await expect(page.getByText('Emergency stop latched — entries disabled.',{exact:true})).toBeVisible();
  const after=await state(request);expect(after.positions).toEqual([]);expect(after.session.killed).toBe(1);expect(after.journal[0].data.quote_source).toBe('LAST_VALID_SYNTHETIC');await page.getByRole('button',{name:'Reconnect fixture'}).click();await page.getByLabel('Demo scenario').selectOption('gap-up');await expect.poll(async()=> (await state(request)).session.scenario).toBe('gap-up');expect((await state(request)).analysis.gap).toBe(200);
 });
 workflowTest('market scenarios expiry and stale confirmation protection',async({page,request})=>{
  await page.goto('/demo/market');for(const scenario of ['bullish','bearish','sideways','gap-up','gap-down']){await page.getByLabel('Demo scenario').selectOption(scenario);await expect.poll(async()=> (await state(request)).session.scenario).toBe(scenario);const v=await state(request);expect(v.analysis.observations.length).toBeGreaterThan(0);expect(v.candles['30']).toHaveLength(2);}
  await nav(page,'Options Intelligence');await page.getByLabel('Option expiry').selectOption('2026-11-10T15:30:00+05:30');await expect(page.locator('table').first()).toContainText('CALLS');await nav(page,'Strategy Builder');await page.getByRole('button',{name:'Review simulated order'}).click();const stale=await (await request.post('/api/demo/preview',{data:{}})).json();await cmd(request,'step',{steps:5});await expect(page.getByRole('button',{name:'Confirm simulated order',exact:true})).toBeDisabled();await page.keyboard.press('Escape');const before=await state(request);expect((await cmd(request,'open',{draft:{},quote_token:stale.quote_token})).status()).toBe(409);expect((await state(request)).account).toEqual(before.account);
 });
 workflowTest('research is computed isolated and explicitly illustrative',async({page,request})=>{
  const before=await state(request);await page.goto('/demo/research');await page.getByLabel('Research strategy').selectOption('bear-call');await page.getByLabel('Research scenario').selectOption('bearish');await page.getByLabel('Chronological split').selectOption('0.7');await page.getByRole('button',{name:'Run synthetic evaluation'}).click();await expect(page.getByRole('heading',{name:'Computed split and sequential folds'})).toBeVisible();expect((await state(request)).account).toEqual(before.account);await expect(page.getByText('Sequential fold 3',{exact:true})).toBeVisible();await nav(page,'AI Insights & Governance');await expect(page.getByText('SIM-COMMENTARY-1',{exact:true})).toBeVisible();
 });
 workflowTest('same-tick exposure changes invalidate risk preview and invalid legs recover',async({page,request})=>{
  await page.goto('/demo/strategy');await expect(page.getByRole('button',{name:'Review simulated order'})).toBeEnabled();
  await enter(request);await enter(request);await enter(request);
  await expect(page.getByText('Maximum three open strategies.',{exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Review rejected attempt'})).toBeVisible();
  await cmd(request,'kill');await cmd(request,'session',{scenario:'bullish'});
  await expect(page.getByRole('button',{name:'Review simulated order'})).toBeEnabled();
  const other=await page.getByLabel('Leg 2 strike').inputValue();await page.getByLabel('Leg 1 strike').selectOption(other);
  await expect(page.getByText('Bull put: short put strike must exceed long put strike.',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Reset strategy legs'}).click();await expect(page.getByRole('button',{name:'Review simulated order'})).toBeEnabled();
 });
 workflowTest('preview transport failures have explicit recovery',async({page})=>{
  let failed=false;await page.route('**/api/demo/preview',async route=>{if(!failed){failed=true;await route.abort('failed');}else await route.continue();});
  await page.goto('/demo/strategy');await expect(page.getByRole('button',{name:'Retry preview'})).toBeVisible();await page.getByRole('button',{name:'Retry preview'}).click();await expect(page.getByRole('button',{name:'Review simulated order'})).toBeEnabled();
 });
 workflowTest('interactive chart zoom pan crosshair indicators and timeframes',async({page,request})=>{
  await page.goto('/demo');const surface=page.getByRole('group',{name:'Interactive NIFTY 5-minute chart',exact:true});await expect(surface).toHaveAttribute('data-range-from',/\S+/);
  const span=async()=>Number(await surface.getAttribute('data-range-to'))-Number(await surface.getAttribute('data-range-from'));
  const initial=await span();await page.getByRole('button',{name:'Zoom in',exact:true}).click();await expect.poll(span).toBeLessThan(initial);
  const beforePan=Number(await surface.getAttribute('data-range-from'));await page.getByRole('button',{name:'Pan left',exact:true}).click();await expect.poll(async()=>Number(await surface.getAttribute('data-range-from'))).toBeLessThan(beforePan);
  const leftRange=Number(await surface.getAttribute('data-range-from'));await page.getByRole('button',{name:'Pan right',exact:true}).click();await expect.poll(async()=>Number(await surface.getAttribute('data-range-from'))).toBeGreaterThan(leftRange);const preserved=Number(await surface.getAttribute('data-range-from'));await page.waitForTimeout(1700);expect(Number(await surface.getAttribute('data-range-from'))).toBeCloseTo(preserved,3);
  await page.getByRole('button',{name:'Fit data',exact:true}).click();await surface.focus();await page.keyboard.press('ArrowLeft');const first=await surface.getAttribute('data-crosshair-time');expect(first).toBeTruthy();await expect(page.getByTestId('keyboard-crosshair-announcement')).toContainText('Synthetic candle');await page.keyboard.press('ArrowLeft');await expect(surface).not.toHaveAttribute('data-crosshair-time',first!);
  const box=await surface.boundingBox();expect(box).toBeTruthy();await page.mouse.move(box!.x+box!.width*.45,box!.y+box!.height*.3);await expect(surface).toHaveAttribute('data-crosshair-time',/\S+/);
  const data=await state(request);const selected=await surface.getAttribute('data-crosshair-time');expect(data.candles['5'].some(b=>b.time===selected)).toBeTruthy();
  await page.getByRole('heading',{name:'Command Center',exact:true}).hover();const before=crypto.createHash('sha256').update(await surface.screenshot()).digest('hex');await page.getByRole('button',{name:'Volume',exact:true}).click();await expect(page.getByRole('button',{name:'Volume',exact:true})).toHaveAttribute('aria-pressed','false');await expect.poll(async()=>crypto.createHash('sha256').update(await surface.screenshot()).digest('hex')).not.toBe(before);
  for(const name of ['EMA9','Session VWAP']){await page.getByRole('button',{name,exact:true}).click();await expect(page.getByRole('button',{name,exact:true})).toHaveAttribute('aria-pressed','false');await page.getByRole('button',{name,exact:true}).click();}
  await page.getByRole('button',{name:'30 min',exact:true}).click();await expect(page.getByRole('group',{name:'Interactive NIFTY 30-minute chart',exact:true})).toBeVisible();await expect(page.getByTestId('chart-readout')).toContainText('warm-up 2/9');
 });
 workflowTest('chart annotations use pointer or keyboard without changing paper state',async({page,request})=>{
  const before=await state(request);await page.goto('/demo');
  await page.getByRole('button',{name:'Horizontal line',exact:true}).click();await page.getByLabel('Horizontal price',{exact:true}).fill('24450');await page.getByRole('button',{name:'Add horizontal line',exact:true}).click();
  const list=page.getByRole('list',{name:'Session chart annotations'});await expect(list.locator('li')).toHaveCount(1);await expect(list).toContainText('Horizontal level 24,450');
  await page.getByRole('button',{name:'Trendline',exact:true}).click();await page.getByRole('button',{name:'Add trendline',exact:true}).click();await expect(list.locator('li')).toHaveCount(2);await nav(page,'Market Intelligence');await expect(list.locator('li')).toHaveCount(2);
  await page.getByRole('button',{name:'Horizontal line',exact:true}).click();await page.getByLabel('Horizontal price',{exact:true}).fill('0');await page.getByRole('button',{name:'Add horizontal line',exact:true}).click();await expect(page.getByText('Drawing prices must be finite and greater than zero.',{exact:true})).toBeVisible();await expect(list.locator('li')).toHaveCount(2);await page.getByRole('button',{name:'Cancel drawing',exact:true}).click();
  const surface=page.getByRole('group',{name:'Interactive NIFTY 5-minute chart',exact:true});await surface.scrollIntoViewIfNeeded();const box=await surface.boundingBox();
  await page.getByRole('button',{name:'Horizontal line',exact:true}).click();await surface.click({position:{x:box!.width*.5,y:box!.height*.4}});await expect(list.locator('li')).toHaveCount(3);
  await page.getByRole('button',{name:'Trendline',exact:true}).click();await surface.click({position:{x:box!.width*.25,y:box!.height*.4}});await expect(page.getByText('First trend point selected. Choose a different candle for the second point.',{exact:false})).toBeVisible();await surface.click({position:{x:box!.width*.75,y:box!.height*.5}});await expect(list.locator('li')).toHaveCount(4);
  await page.getByRole('button',{name:'Remove drawing 1',exact:true}).click();await expect(list.locator('li')).toHaveCount(3);await page.getByRole('button',{name:'Clear drawings',exact:true}).click();await expect(list).toHaveCount(0);expect((await state(request)).account).toEqual(before.account);
  await page.getByRole('button',{name:'Horizontal line',exact:true}).click();await page.getByLabel('Horizontal price',{exact:true}).fill('24450');await page.getByRole('button',{name:'Add horizontal line',exact:true}).click();await expect(list.locator('li')).toHaveCount(1);await page.getByLabel('Demo scenario').selectOption('bearish');await expect(list).toHaveCount(0);
 });
 workflowTest('desktop tablet mobile routes and navigation focus',async({page},info)=>{
  for(const width of [1440,1024,390]){await page.setViewportSize({width,height:1000});await page.goto('/demo');for(const [screen,[,name]] of Object.entries(screens)){if(screen!=='COMMAND')await nav(page,name);await expect(page.getByRole('heading',{name,exact:true})).toBeVisible();await expect(page.locator('main')).not.toHaveAttribute('data-state','loading');expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();}await nav(page,'Command Center');await expect(page.locator('.demo-stat').first()).toBeVisible();await page.screenshot({path:info.outputPath(`command-${width}.png`),fullPage:true});}
  await page.getByRole('button',{name:'Toggle demo navigation'}).click();await expect(page.getByRole('dialog',{name:'Demo navigation menu'})).toBeVisible();await page.getByRole('button',{name:'Close navigation menu'}).focus();await page.keyboard.press('Shift+Tab');await expect(page.getByRole('link',{name:'Return to original workspace →'})).toBeFocused();await page.keyboard.press('Escape');await expect(page.getByRole('button',{name:'Toggle demo navigation'})).toBeFocused();
 });
});

type Case={id:string;component_id:string;state_id:string;viewport_id:string;theme:'light'|'dark';checks:string[]};
let snapshots:Record<string,State>={},previews:Record<string,Preview>={},research:Research;
function prepareMatrixSnapshots(){
  if(snapshots.ready)return;
  const script=`
import json, tempfile, uuid
from pathlib import Path
from algooptionx.demo.engine import DemoEngine
from algooptionx.demo.research import evaluate
with tempfile.TemporaryDirectory(prefix='algooptionx-ui-fixture-') as folder:
 e=DemoEngine(Path(folder)/'demo.db')
 def cmd(action,**fields):
  return e.command(dict(action=action,key=str(uuid.uuid4()),session_id=e.state()['session']['id'],**fields))
 p=e.preview({}); assert p['valid']; assert cmd('open',draft={},quote_token=p['quote_token'])['ok']
 snapshots={'ready':e.state()}; previews={'ready':e.preview({})}
 cmd('disconnect');cmd('step',steps=5);snapshots['stale']=e.state();previews['stale']=e.preview({})
 cmd('reconnect');cmd('close',position_id=snapshots['ready']['positions'][0]['id']);snapshots['empty']=e.state();previews['empty']=e.preview({})
 cmd('kill');snapshots['disabled']=e.state();previews['disabled']=e.preview({})
 print(json.dumps(dict(snapshots=snapshots,previews=previews,research=evaluate())))
`;
  const result=spawnSync(path.join(root,'.venv/bin/python'),['-c',script],{cwd:root,encoding:'utf8',timeout:20000,env:{PATH:process.env.PATH,TMPDIR:'/tmp'}});
  expect(result.status, result.stderr).toBe(0);
  const data=JSON.parse(result.stdout);snapshots=data.snapshots;previews=data.previews;research=data.research;
  expect(snapshots.ready.source).toBe('SYNTHETIC');expect(snapshots.ready.account.capital).toBe(fixture.capital_paise);expect(snapshots.ready.session.tick).toBe(fixture.initial_tick);
}
// Reuse one renderer per worker. Every case still fully navigates, restores its
// measured theme/viewport, installs its own isolated fixture routes and removes
// them in finally. This avoids measuring repeated browser-context creation.
const matrixTest=test.extend<{}, {matrixRenderer:{page:Page;protocol:CDPSession}}>({matrixRenderer:[async({browser},use)=>{
 prepareMatrixSnapshots();
 const context=await browser.newContext({locale:'en-IN',timezoneId:'Asia/Kolkata',reducedMotion:'reduce',deviceScaleFactor:1,viewport:{width:1440,height:1000},baseURL:'http://127.0.0.1:8011'});
 try{const page=await context.newPage();await page.goto('/api/health');const protocol=await context.newCDPSession(page);await protocol.send('Page.setWebLifecycleState',{state:'frozen'});await use({page,protocol});}finally{await context.close();}
},{scope:'worker'}],page:async({matrixRenderer},use,info)=>{
 const {page:matrixPage,protocol}=matrixRenderer;
 // Two active matrix renderers match the environment's two-CPU quota. FIFO
 // tickets prevent starvation; all waiting is outside navigation measurements.
 const directory=path.join(process.env.ALGOOPTIONX_EVIDENCE_DIR||path.resolve(info.outputDir,'..'),'matrix-resources');
 const queue=path.join(directory,'queue');fs.mkdirSync(queue,{recursive:true});
 const name=String(Date.now()).padStart(16,'0')+'-'+crypto.randomUUID(),ticket=path.join(queue,name);fs.mkdirSync(ticket);
 let slot:string|undefined;const deadline=performance.now()+20000;
 try{
  while(!slot){
   if(fs.readdirSync(queue).sort().slice(0,2).includes(name))for(let i=0;i<2;i++){
    const candidate=path.join(directory,'slot-'+i);try{fs.mkdirSync(candidate);slot=candidate;break;}catch(error){if((error as NodeJS.ErrnoException).code!=='EEXIST')throw error;}
   }
   if(!slot){if(performance.now()>deadline)throw new Error('Matrix resource acquisition exceeded 20 seconds.');await new Promise(resolve=>setTimeout(resolve,25));}
  }
  await protocol.send('Page.setWebLifecycleState',{state:'active'});
  await use(matrixPage);
 }finally{
  // Pause only idle renderers, after assertions/captures and route cleanup.
  // Every timed full navigation runs active, with unchanged cache behavior.
  try{await protocol.send('Page.setWebLifecycleState',{state:'frozen'});}finally{if(slot)fs.rmdirSync(slot);fs.rmdirSync(ticket);}
 }
}});
matrixTest.describe('Frozen demo UI matrix',()=>{
 // Only controlled UI cases run in parallel. Each worker derives coherent
 // snapshots in its own temporary SQLite DB; real API workflows stay sequential.
 matrixTest.describe.configure({mode:'parallel'});

 for(const item of design.validation_cases as Case[])matrixTest(`UI::${item.id}`,async({page,browser},info)=>{
  const component=design.components.find((c:{id:string})=>c.id===item.component_id),interaction=component.states.find((s:{id:string})=>s.id===item.state_id).name,screen=component.screen_id.replace('SCREEN-',''),viewport=design.viewports.find((v:{id:string})=>v.id===item.viewport_id);
  await page.setViewportSize({width:viewport.width,height:viewport.height});await page.evaluate(theme=>localStorage.setItem('algooptionx.theme',theme),item.theme);
  const snapshot=structuredClone(snapshots[interaction]||snapshots.ready);if(interaction==='empty'){snapshot.contracts=[];snapshot.candles={'5':[],'30':[]};snapshot.positions=[];snapshot.journal=[];snapshot.events=[];snapshot.analysis.observations=[];}
  let release=()=>{};const held=new Promise<void>(resolve=>{release=resolve;});
  await page.route('**/api/demo/state',async route=>{if(interaction==='loading')await held;if(interaction==='error')await route.fulfill({status:503,json:{detail:'Controlled synthetic service failure; retry connection.'}});else await route.fulfill({json:snapshot});});
  await page.route('**/api/demo/preview',route=>route.fulfill({json:previews[interaction]||previews.ready}));await page.route('**/api/demo/research',route=>route.fulfill({json:research}));
  const samples:number[]=[];const load=async()=>{
   const start=performance.now();await page.goto(url(screen),{waitUntil:'domcontentloaded'});
   if(screen==='RESEARCH'&&interaction==='ready'){
    await page.waitForFunction(()=>Array.from(document.querySelectorAll('button')).some(b=>b.textContent==='Run synthetic evaluation'&&!b.disabled));
    await page.getByRole('button',{name:'Run synthetic evaluation'}).click();
    await page.waitForFunction(()=>Array.from(document.querySelectorAll('h2')).some(h=>h.textContent==='Computed split and sequential folds'&&h.getBoundingClientRect().height>0));
    await expect(page.getByRole('heading',{name:'Computed split and sequential folds'})).toBeVisible();
   }
   // Observe the same ready conditions each animation frame, avoiding test
   // assertion polling delays in the measured user-visible navigation time.
   await page.waitForFunction(({state,chart,builder})=>{
    if(document.querySelector('main[data-screen]')?.getAttribute('data-state')!==state)return false;
    if(chart&&!document.querySelector('.demo-chart-surface')?.getAttribute('data-range-from'))return false;
    if(builder&&!Array.from(document.querySelectorAll('button')).some(b=>b.textContent==='Review simulated order'&&!b.disabled))return false;
    return true;
   },{state:interaction,chart:interaction==='ready'&&['COMMAND','MARKET'].includes(screen),builder:interaction==='ready'&&screen==='STRATEGY'});
   await expect(page.locator('main[data-screen]')).toHaveAttribute('data-state',interaction);
   if(screen==='STRATEGY'&&interaction==='ready')await expect(page.getByRole('button',{name:'Review simulated order'})).toBeEnabled();
   if(interaction==='ready'&&['COMMAND','MARKET'].includes(screen))await expect(page.locator('.demo-chart-surface')).not.toHaveAttribute('data-range-from','');
   samples.push(performance.now()-start);
  };
  try{
   await load();if(item.checks.includes('performance'))for(let i=1;i<5;i++)await load();
   const fields=await page.locator('main select,main textarea').all();
   await Promise.all([
    expect(page.getByRole('heading',{level:1,name:screens[screen][1],exact:true})).toBeVisible(),
    expect(page.getByRole('link',{name:'Skip to demo content'})).toHaveAttribute('href','#demo-main'),
    page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth).then(value=>expect(value).toBeTruthy()),
    ...fields.map(async field=>{if(await field.isVisible())await expect(field).toHaveAccessibleName(/.+/);}),
   ]);
   const menu=page.getByRole('button',{name:'Toggle demo navigation'});if(await menu.isVisible()){await menu.focus();await expect(menu).toBeFocused();}else{const link=page.getByRole('navigation',{name:'Demo navigation',exact:true}).getByRole('link',{name:'Command Center'});await link.focus();await expect(link).toBeFocused();}
   const actual=await page.locator('.demo-app').evaluate(el=>({font:getComputedStyle(el).fontFamily,width:innerWidth,height:innerHeight,ratio:devicePixelRatio,locale:navigator.language,timezone:Intl.DateTimeFormat().resolvedOptions().timeZone,reduced:matchMedia('(prefers-reduced-motion: reduce)').matches}));expect(actual.font).toContain('DejaVu Sans');expect(actual.width).toBe(viewport.width);expect(actual.height).toBe(viewport.height);expect(actual.reduced).toBeTruthy();expect(browser.version()).toBe(design.renderer.version);
   const reportDirectory=process.env.ALGOOPTIONX_EVIDENCE_DIR||path.resolve(info.outputDir,'..');
   const directory=path.join(reportDirectory,'ui',item.id);fs.mkdirSync(directory,{recursive:true});
   const reference=(name:string,file:string,contentType='application/json')=>info.attachments.push({name,path:file,contentType});
   const attach=(name:string,value:unknown)=>{const file=path.join(directory,name+'.json');fs.writeFileSync(file,JSON.stringify(value));reference(name,file);};
   const context=JSON.stringify({renderer:{...design.renderer,version:browser.version(),operating_system:os.platform(),fonts_sha256:hash('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),locale:actual.locale,timezone:actual.timezone,device_scale_factor:actual.ratio},fixture:design.fixture,viewport,theme:item.theme});
   const profiles=path.join(reportDirectory,'ui-profiles');fs.mkdirSync(profiles,{recursive:true});const profile=path.join(profiles,crypto.createHash('sha256').update(context).digest('hex')+'.json');
   const temporary=profile+'.'+crypto.randomUUID()+'.tmp';fs.writeFileSync(temporary,context,{flag:'wx'});try{fs.linkSync(temporary,profile);}catch(error){if((error as NodeJS.ErrnoException).code!=='EEXIST')throw error;expect(fs.readFileSync(profile,'utf8')).toBe(context);}finally{fs.unlinkSync(temporary);}reference('ui-context',profile);
   const areas:Record<string,unknown>={};
   for(const area of item.checks){if(area==='performance'){expect(Math.max(...samples)).toBeLessThanOrEqual(design.performance_budgets[0].maximum);areas[area]={case_id:item.id,area,status:'passed',measurements:[{budget_id:design.performance_budgets[0].id,observed:Math.max(...samples),samples:samples.length}],samples_ms:samples};}else areas[area]={case_id:item.id,area,status:'passed',state:interaction,method:area==='accessibility'?'Executed headings, named controls, skip link and keyboard focus; scoped automation, not WCAG certification.':area==='responsive'?'Actual viewport and document/table overflow assertions.':'Executed wireframe headings and visible layout; candidate capture, no approved pixel baseline.'};}
   const bundle=path.join(directory,'areas.json');fs.writeFileSync(bundle,JSON.stringify({case_id:item.id,areas}));for(const area of item.checks)reference('ui-'+area,bundle);
   if(item.checks.includes('visual')){const screenshot=path.join(directory,'screenshot.png');await page.screenshot({path:screenshot,fullPage:true,animations:'disabled'});reference('ui-screenshot',screenshot,'image/png');attach('ui-comparison',{case_id:item.id,status:'passed',screenshot_sha256:hash(screenshot),design_sha256:hash(path.join(root,'docs/designs/DEMO-001/r0003/design.json')),method:'Wireframe heading/layout/visibility assertions plus real candidate capture for human review; no approved pixel baseline claimed.'});}
  }finally{release();await page.unrouteAll({behavior:'ignoreErrors'});}
 });
});
