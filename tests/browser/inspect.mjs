import {createRequire} from 'node:module';
import {readFileSync, mkdirSync, writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
const require = createRequire(resolve('frontend/package.json'));
const {chromium} = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;
const credentials = JSON.parse(readFileSync('.local/accounts.json', 'utf8')).accounts;
const account = credentials.find(row=>row.role==='operator');
mkdirSync('artifacts/screenshots',{recursive:true});
const browser = await chromium.launch({headless:true});
const context = await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
const page = await context.newPage();
const errors=[];
page.on('pageerror',error=>errors.push(String(error)));
await page.goto('http://127.0.0.1:8000');
await page.locator('#username').fill(account.username);
await page.locator('#password').fill(account.password);
await page.getByRole('button',{name:'Enter workspace'}).click();
await page.locator('.overview-grid').waitFor({timeout:30000});
const checks=[];
for(const locale of ['en-CA','fr-CA']) {
  if(locale==='fr-CA') await page.getByRole('button',{name:'Passer en français',exact:true}).click();
  for(const theme of ['light','dark']) {
    if(theme==='dark') await page.getByRole('button',{name:locale==='en-CA'?'Switch to dark theme':'Activer le thème sombre',exact:true}).click();
    for(const width of [1440,1280]) {
      await page.setViewportSize({width,height:900});
      await page.screenshot({path:`artifacts/screenshots/overview-${locale}-${theme}-${width}.png`,fullPage:true});
      const scan=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();
      const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
      checks.push({locale,theme,width,overflow,violations:scan.violations.map(v=>({id:v.id,impact:v.impact,description:v.description,nodes:v.nodes.map(n=>n.target)}))});
    }
    if(theme==='dark') await page.getByRole('button',{name:locale==='en-CA'?'Switch to light theme':'Activer le thème clair',exact:true}).click();
  }
}
// Actual keyboard opening, escape and focus restoration, against a real browser.
await page.keyboard.press('Control+k');
await page.getByRole('dialog').waitFor();
await page.keyboard.press('Escape');
const dialogsClosed=await page.getByRole('dialog').count()===0;
await page.keyboard.press('Tab');
const focus=await page.evaluate(()=>({tag:document.activeElement.tagName,name:document.activeElement.getAttribute('aria-label')||document.activeElement.textContent}));
writeFileSync('artifacts/accessibility.json',JSON.stringify({target:'WCAG 2.2 AA',checks,keyboard:{commandPalette:true,escapeCloses:dialogsClosed,focus},errors,screenReader:'UNVERIFIED: no manual screen-reader assessment performed',scope:'Automated axe scans and scripted keyboard checks, not comprehensive conformance.'},null,2));
console.log(JSON.stringify({checks:checks.length,violations:checks.reduce((n,c)=>n+c.violations.length,0),errors,dialogsClosed}));
await browser.close();
if(errors.length||checks.some(c=>c.overflow||c.violations.length))process.exitCode=1;
