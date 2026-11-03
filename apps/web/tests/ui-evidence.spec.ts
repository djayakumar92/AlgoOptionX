import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import os from 'node:os';

const root = path.resolve(import.meta.dirname, '../../..');
const spec = JSON.parse(fs.readFileSync(path.join(root, 'docs/designs/UI-CONTROL-001/r0002/design.json'), 'utf8'));
test('UI::CASE-001', async ({page, browser}, info) => {
  const item = spec.validation_cases[0];
  await page.setViewportSize({width:390,height:844});
  const durations:number[]=[];
  for(let i=0;i<5;i++) {
    const start=performance.now(); await page.goto('/settings');
    await expect(page.getByRole('heading',{name:'A workspace on your terms.'})).toBeVisible();
    await expect(page.locator('.ax-session-bar')).toBeVisible();
    durations.push(performance.now()-start);
  }
  await page.getByLabel('Theme',{exact:true}).selectOption('light');
  await page.locator('.ax-app').evaluate(el => (el as HTMLElement).style.fontFamily='DejaVu Sans');
  await expect(page.getByLabel('Theme',{exact:true})).toHaveValue('light');
  await page.getByLabel('Theme',{exact:true}).focus();
  await expect(page.getByLabel('Theme',{exact:true})).toBeFocused();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
  const folder=path.join(process.env.ALGOOPTIONX_EVIDENCE_DIR || info.outputDir,'ui',item.id);
  fs.mkdirSync(folder,{recursive:true});
  const attach=async(name:string,value:unknown)=> {
    const file=path.join(folder,name+'.json'); fs.writeFileSync(file,JSON.stringify(value));
    await info.attach(name,{path:file,contentType:'application/json'});
  };
  const screenshot=path.join(folder,'screenshot.png');
  await page.screenshot({path:screenshot,fullPage:true,animations:'disabled'});
  await info.attach('ui-screenshot',{path:screenshot,contentType:'image/png'});
  await attach('ui-context',{
    renderer:{...spec.renderer,version:browser.version(),operating_system:os.platform(),
      fonts_sha256:crypto.createHash('sha256').update(fs.readFileSync('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')).digest('hex'),
      locale:await page.evaluate(()=>navigator.language),timezone:await page.evaluate(()=>Intl.DateTimeFormat().resolvedOptions().timeZone)},
    fixture:spec.fixture, viewport:spec.viewports[0], theme:'light'
  });
  for(const area of ['accessibility','responsive','visual'])
    await attach('ui-'+area,{case_id:item.id,area,status:'passed',method:'Executed named-control, focus, overflow and visible-layout assertions; candidate capture only, no human approval.'});
  await attach('ui-comparison',{case_id:item.id,status:'passed',screenshot_sha256:crypto.createHash('sha256').update(fs.readFileSync(screenshot)).digest('hex'),method:'Actual visible-layout assertions plus candidate capture; no approved pixel baseline is asserted.'});
  expect(Math.max(...durations)).toBeLessThanOrEqual(2000);
  await attach('ui-performance',{case_id:item.id,area:'performance',status:'passed',measurements:[{budget_id:'BUDGET-001',observed:Math.max(...durations),samples:durations.length}],samples_ms:durations});
});
