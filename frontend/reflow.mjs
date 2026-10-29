import { chromium, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
const account = JSON.parse(readFileSync('../.local/accounts.json', 'utf8')).accounts.find(a => a.role === 'operator')
const browser = await chromium.launch({headless:true})
const context = await browser.newContext({viewport:{width:1280,height:900}, reducedMotion:'reduce'})
const page = await context.newPage()
const errors=[];page.on('pageerror', error=>errors.push(String(error)))
mkdirSync('test-results',{recursive:true})
await page.goto('http://127.0.0.1:8000')
await page.locator('#username').fill(account.username)
await page.locator('#password').fill(account.password)
await page.getByRole('button',{name:'Enter workspace',exact:true}).click()
await page.locator('.overview-grid').waitFor()
await page.getByRole('button',{name:'Passer en français',exact:true}).click()
await page.getByRole('button',{name:'Activer le thème sombre',exact:true}).click()
await page.locator('.sidebar nav').getByRole('button',{name:'Atelier',exact:true}).click()
await page.getByRole('button',{name:'Suivre un paiement',exact:true}).click()
await page.locator('.trace-hero').waitFor()
await page.getByRole('tab',{name:'Octets sources',exact:true}).click()
await page.screenshot({path:'test-results/trace-fr-dark-1280.png'})
const traceScan=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze()
// Actual keyboard ARIA tab operation.
await page.getByRole('tab',{name:'Octets sources',exact:true}).focus()
await page.keyboard.press('ArrowLeft')
await expect(page.getByRole('tab',{name:'Calcul',exact:true})).toHaveAttribute('aria-selected','true')
await page.keyboard.press('End')
await expect(page.getByRole('tab',{name:'Écritures et tentatives',exact:true})).toHaveAttribute('aria-selected','true')
await page.keyboard.press('Escape')
await expect(page.getByRole('button',{name:'Suivre un paiement',exact:true})).toBeFocused()
await page.locator('.sidebar nav').getByRole('button',{name:'Vue d’ensemble',exact:true}).click()
const checks=[]
for(const width of [640,390,320]){
 await page.setViewportSize({width,height:900})
 await page.waitForTimeout(250)
 const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)
 const oversized=width===320?await page.evaluate(()=>[...document.querySelectorAll('main,.topbar,.topbar-actions,.metric-card,.metric-value,.context-strip,.page-heading,.page-footer')].filter(el=>el.getBoundingClientRect().right>innerWidth).map(el=>({class:el.className,right:el.getBoundingClientRect().right,width:el.getBoundingClientRect().width}))):[]
 const scan=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze()
 checks.push({width,overflow,oversized,violations:scan.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))})
 await page.screenshot({path:`test-results/reflow-fr-dark-${width}.png`,fullPage:true})
}
await page.setViewportSize({width:1280,height:900})
const beforeZoom=await page.evaluate(()=>({width:innerWidth,ratio:devicePixelRatio}))
for(let i=0;i<4;i++)await page.keyboard.press('Control+Equal')
const afterZoom=await page.evaluate(()=>({width:innerWidth,ratio:devicePixelRatio}))
await page.keyboard.press('Control+0')
const report={checks,traceViolations:traceScan.violations.map(v=>v.id),keyboardArrowHomeEnd:true,dialogFocusRestored:true,errors,browserZoomAttempt:{before:beforeZoom,after:afterZoom,changed:beforeZoom.width!==afterZoom.width||beforeZoom.ratio!==afterZoom.ratio},zoomScope:'320/390/640 CSS-pixel viewport reflow verified. Manual browser zoom and screen-reader assessment remain unverified. Exploratory CSS body.zoom=2 overflowed; CSS zoom does not adjust media-query viewport and is not used as evidence for browser zoom.'}
writeFileSync('test-results/reflow.json',JSON.stringify(report,null,2))
console.log(JSON.stringify(report))
await browser.close()
if(errors.length||checks.some(c=>c.overflow||c.violations?.length)||traceScan.violations.length)process.exitCode=1
