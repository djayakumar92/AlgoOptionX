// Fixed synthetic scenarios. No instructions, commands or remote URLs from plans.
import { test, expect } from "@playwright/test";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { createHash } from "node:crypto";
import path from "node:path";
const ctx = process.env.ALGOOPTIONX_UI_CONTEXT ? JSON.parse(readFileSync(process.env.ALGOOPTIONX_UI_CONTEXT, "utf8")) : null;
const sha = (data: Buffer) => createHash("sha256").update(data).digest("hex");
const routes: Record<string, string> = { "workspace-overview": "/app/overview", "workspace-order-dialog": "/market", "workspace-activity": "/journal" };
if (ctx) for (const item of ctx.cases) {
  test(`@design ${item.id}`, async ({ page, request, browser }, info) => {
    const results: any[] = [];
    const samples: Record<string, number[]> = {};
    const reference = (file: string) => ({path: path.relative(ctx.root, file).split(path.sep).join("/"), sha256: sha(readFileSync(file))});
    const save = async (name: string, value: unknown) => {
      const file = info.outputPath(name); mkdirSync(path.dirname(file), {recursive: true});
      writeFileSync(file, JSON.stringify(value));
      await info.attach(name, {path:file, contentType:"application/json"});
      return reference(file);
    };
    try {
      expect(browser.version()).toBe(ctx.renderer.version);
      expect(ctx.renderer.operating_system).toBe(process.platform);
      expect(item.state === "ready" || item.state === "empty").toBeTruthy();
      expect(routes[item.scenario]).toBeTruthy();
      await request.post("/api/commands", {data:{key:crypto.randomUUID(),action:"control",running:false,killed:true}});
      expect((await request.post("/api/sessions")).ok()).toBeTruthy();
      if (item.state === "ready") for(let i=0;i<30;i++) expect((await request.post("/api/commands",{data:{key:crypto.randomUUID(),action:"advance"}})).ok()).toBeTruthy();
      await page.clock.setFixedTime(new Date(ctx.fixture_clock));
      await page.setViewportSize({width:item.viewport.width,height:item.viewport.height});
      await page.emulateMedia({colorScheme:item.definition.theme,reducedMotion:"reduce"});
      await page.goto(routes[item.scenario]);
      const theme=page.getByRole("combobox",{name:"Theme",exact:true});
      await theme.selectOption(item.definition.theme);
      await expect(page.locator(".ax-session-bar")).toBeVisible();
      expect(await page.locator(".ax-app").innerText()).toMatch(/paper|virtual|synthetic/i);
      if (item.scenario === "workspace-order-dialog") await page.getByRole("button",{name:"Buy paper"}).first().click();
      if (item.definition.checks.includes("accessibility")) {
        if(item.scenario === "workspace-order-dialog") {
          await expect(page.getByRole("dialog")).toBeVisible();
          await expect(page.getByRole("button",{name:"Close order ticket"})).toBeFocused();
          await expect(page.getByRole("dialog")).toHaveAttribute("aria-modal","true");
        } else { await theme.focus(); await expect(theme).toBeFocused(); }
        expect(await page.locator("[aria-hidden]").evaluateAll(nodes=>nodes.every(n=>["true","false"].includes(n.getAttribute("aria-hidden")||"")))).toBeTruthy();
        const focusVisible=await page.evaluate(()=>{const e=document.activeElement;if(!e||e===document.body)return false;const s=getComputedStyle(e);return s.outlineStyle!=="none"||s.boxShadow!=="none";});
        expect(focusVisible).toBeTruthy();
        await page.keyboard.press("Tab");
        expect(await page.evaluate(()=>document.activeElement!==document.body)).toBeTruthy();
        results.push({area:"accessibility",status:"passed",notes:"Scoped keyboard, focus, role and ARIA assertions; no WCAG certification.",artifacts:[],measurements:[]});
      }
      if (item.definition.checks.includes("responsive")) {
        expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
        await expect(page.locator(".ax-session-bar")).toBeVisible();
        results.push({area:"responsive",status:"passed",notes:"Approved viewport reflow and visible navigation checked.",artifacts:[],measurements:[]});
      }
      if(item.definition.checks.includes("performance")) {
        for(const budget of ctx.budgets) {
          samples[budget.id]=[];
          for(let i=0;i<budget.samples;i++) {
            let measured: number;
            if(budget.metric==="bundle-bytes") measured=ctx.bundle_bytes;
            else {
              if(item.scenario === "workspace-order-dialog") await page.keyboard.press("Escape");
              const start=await page.evaluate(()=>performance.now());
              await theme.selectOption((await theme.inputValue()) === "dark" ? "light" : "dark");
              await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
              measured=(await page.evaluate(()=>performance.now()))-start;
            }
            samples[budget.id].push(measured);
          }
        }
        await theme.selectOption(item.definition.theme);
        if(item.scenario === "workspace-order-dialog" && await page.getByRole("dialog").count()===0) await page.getByRole("button",{name:"Buy paper"}).first().click();
        const measurements=ctx.budgets.map((b:any)=>({budget_id:b.id,observed:Math.max(...samples[b.id]),samples:samples[b.id].length}));
        if(ctx.mode==="verify") for(const b of ctx.budgets) expect(Math.max(...samples[b.id])).toBeLessThanOrEqual(b.maximum);
        results.push({area:"performance",status:ctx.mode==="verify"?"passed":"unverified",notes:"Actual sampled RAF interaction latency or workspace JavaScript bytes; measurement alone grants no budget approval.",measurements,artifacts:[]});
      }
      const checks=await save("checks.json",{scope:"automated-scoped-only",samples,bundle_manifest:ctx.bundle_manifest});
      for(const area of results) if(area.area!=="performance") area.artifacts=[{kind:"report",reference:checks}];
      if(item.definition.checks.includes("visual")) {
        // Same permitted identity normalizations as the existing visual suite.
        await page.locator(".ax-event-seq").evaluateAll(nodes=>nodes.forEach(n=>{n.textContent="#SESSION";}));
        await page.locator(".ax-event div > span").evaluateAll(nodes=>nodes.forEach(n=>{n.textContent=n.textContent?.replace(/[0-9a-f]{16}…/g,"0000000000000000…")||"";}));
        const state=await (await request.get("/api/workspace")).json();
        const identity=page.getByText(`${state.account.id.slice(0,18)}…`,{exact:true});
        if(await identity.count()) await identity.evaluate(n=>{n.textContent="00000000-0000-0000…";});
        let comparison: any=null;
        const target=item.scenario==="workspace-order-dialog"?page.getByRole("dialog"):page;
        if(ctx.mode==="verify") {
          const relative=item.baseline.path.replace(/^apps\/web\/tests\/visual-baselines\//,"");
          await expect(target).toHaveScreenshot(relative.split("/"),{animations:"disabled",caret:"hide",maxDiffPixels:0});
        }
        const image=info.outputPath("actual.png");
        await target.screenshot({path:image,animations:"disabled",caret:"hide"});
        await info.attach("actual",{path:image,contentType:"image/png"});
        const imageRef=reference(image);
        const visualArtifacts=[{kind:"screenshot",reference:imageRef}];
        if(ctx.mode==="verify") {
          comparison=await save("comparison.json",{baseline_sha256:item.baseline.sha256,actual_sha256:imageRef.sha256,maxDiffPixels:0,engine:"playwright"});
          visualArtifacts.push({kind:"comparison",reference:comparison});
        }
        results.push({area:"visual",status:ctx.mode==="verify"?"passed":"unverified",notes:"Actual screenshot captured; only verified mode compares the exact baseline.",artifacts:visualArtifacts,measurements:[]});
      }
    } finally {
      for(const area of item.definition.checks) if(!results.some(r=>r.area===area)) results.push({area,status:"failed",notes:"Required assertion failed or did not execute.",artifacts:[],measurements:[]});
      const report={schema_version:1,kind:"ui-case",case_id:item.id,mode:ctx.mode,plan_sha256:ctx.plan_sha256,source:ctx.source,task_digest:ctx.task_digest,renderer:{...ctx.renderer,version:browser.version(),operating_system:process.platform},fixture_sha256:ctx.fixture_sha256,environment_sha256:ctx.environment_sha256,results,samples};
      const file=info.outputPath("ui-case.json");mkdirSync(path.dirname(file),{recursive:true});writeFileSync(file,JSON.stringify(report));
      await info.attach("ui-case",{path:file,contentType:"application/json"});
    }
  });
}
