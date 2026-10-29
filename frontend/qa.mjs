import { chromium } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs'
const account = JSON.parse(readFileSync('../.local/accounts.json', 'utf8')).accounts.find(
  (a) => a.role === 'operator',
)
mkdirSync('test-results', { recursive: true })
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({
  viewport: { width: 1280, height: 900 },
  reducedMotion: 'reduce',
})
const page = await context.newPage()
const errors = []
page.on('pageerror', (error) => errors.push(String(error)))
await page.goto('http://127.0.0.1:8000')
await page.locator('#username').fill(account.username)
await page.locator('#password').fill(account.password)
await page.getByRole('button', { name: 'Enter workspace', exact: true }).click()
await page.locator('.overview-grid').waitFor()
const results = []
for (const locale of ['en', 'fr']) {
  if (locale === 'fr')
    await page.getByRole('button', { name: 'Passer en français', exact: true }).click()
  for (const theme of ['light', 'dark']) {
    if (theme === 'dark')
      await page
        .getByRole('button', {
          name: locale === 'en' ? 'Switch to dark theme' : 'Activer le thème sombre',
          exact: true,
        })
        .click()
    for (const nav of locale === 'en'
      ? ['Batches', 'Reconciliation', 'Ledger', 'Workbench']
      : ['Lots', 'Rapprochement', 'Grand livre', 'Atelier']) {
      await page.locator('.sidebar nav').getByRole('button', { name: nav, exact: false }).click()
      await page.waitForTimeout(1200)
      const scan = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
        .analyze()
      results.push({
        locale,
        theme,
        nav,
        overflow: await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),
        violations: scan.violations.map((v) => ({
          id: v.id,
          nodes: v.nodes.map((n) => ({ target: n.target, summary: n.failureSummary })),
        })),
      })
      await page.screenshot({ path: `test-results/${locale}-${theme}-${nav}.png`, fullPage: true })
    }
    if (theme === 'dark')
      await page
        .getByRole('button', {
          name: locale === 'en' ? 'Switch to light theme' : 'Activer le thème clair',
          exact: true,
        })
        .click()
  }
}
await page.getByRole('button', { name: 'Switch to English', exact: true }).click()
await page.getByRole('button', { name: 'Trace a payment', exact: true }).click()
await page.locator('.trace-hero').waitFor()
for (const tab of ['Calculation', 'Source bytes', 'Ledger & attempts']) {
  await page.getByRole('tab', { name: tab, exact: true }).click()
  const scan = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
    .analyze()
  results.push({
    dialog: tab,
    violations: scan.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => ({ target: n.target, summary: n.failureSummary })),
    })),
  })
  await page.screenshot({ path: `test-results/trace-${tab}.png` })
}
writeFileSync('test-results/quality.json', JSON.stringify({ results, errors }, null, 2))
console.log(
  JSON.stringify({
    checks: results.length,
    failures: results.filter((r) => r.overflow || r.violations.length),
    errors,
  }),
)
await browser.close()
if (errors.length || results.some((result) => result.overflow || result.violations.length))
  process.exitCode = 1
