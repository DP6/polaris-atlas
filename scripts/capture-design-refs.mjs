// Captura de referências visuais externas com Playwright (Chromium).
//
// Uso:
//   npm i playwright            # uma vez, em qualquer lugar resolvível (ou -g)
//   node scripts/capture-design-refs.mjs [--site <slug>] [--headed]
//
// Lê docs/design-references/sources.json, tira 2 prints por página
// (viewport + full-page), grava em docs/design-references/captures/<site>/
// e regenera docs/design-references/manifest.json.
//
// Mecanismo primário do repo é o Playwright MCP (ver docs/design-references/README.md);
// este script é o fallback reproduzível / documentação executável das URLs.

import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const REF_DIR = resolve(ROOT, 'docs/design-references');
const OUT_DIR = resolve(REF_DIR, 'captures');

const args = process.argv.slice(2);
const onlySite = args.includes('--site') ? args[args.indexOf('--site') + 1] : null;
const headed = args.includes('--headed');

let chromium;
try {
  // PW_PATH permite apontar para uma instalação de playwright fora do repo
  // (o repo não declara essa dependência — ver README).
  const pw = await import(process.env.PW_PATH || 'playwright');
  chromium = pw.chromium ?? pw.default?.chromium;
} catch {
  console.error(
    'Falta o pacote "playwright". Rode `npm i playwright` (local ou -g) ' +
      'ou use o Playwright MCP (docs/design-references/README.md).',
  );
  process.exit(1);
}

const cfg = JSON.parse(await readFile(resolve(REF_DIR, 'sources.json'), 'utf8'));
const viewport = cfg.viewport ?? { width: 1440, height: 900 };

// Seletores comuns de banner de consentimento — tentativa best-effort.
const CONSENT_SELECTORS = [
  '#onetrust-accept-btn-handler',
  'button[aria-label*="accept" i]',
  'button:has-text("Accept all")',
  'button:has-text("Aceitar todos")',
  'button:has-text("Aceitar")',
  'button:has-text("I agree")',
  '.cookie button:has-text("Accept")',
];

async function dismissConsent(page) {
  for (const sel of CONSENT_SELECTORS) {
    try {
      const el = page.locator(sel).first();
      if (await el.isVisible({ timeout: 800 })) {
        await el.click({ timeout: 1500 });
        await page.waitForTimeout(400);
        return;
      }
    } catch {
      /* segue */
    }
  }
}

// Altura máxima de full-page (px CSS). Listagens com scroll infinito
// (blog, cases) crescem sem limite conforme rola — sem teto, o JPEG
// estourou 60.000 px / 14 MB.
const MAX_FULLPAGE_PX = 12000;

async function autoScroll(page) {
  await page.evaluate(async (maxPx) => {
    await new Promise((done) => {
      let y = 0;
      const step = 400;
      const timer = setInterval(() => {
        window.scrollBy(0, step);
        y += step;
        if (y >= document.body.scrollHeight || y >= maxPx) {
          clearInterval(timer);
          window.scrollTo(0, 0);
          setTimeout(done, 500);
        }
      }, 120);
    });
  }, MAX_FULLPAGE_PX);
}

const browser = await chromium.launch({ headless: !headed });
const ctx = await browser.newContext({
  viewport,
  deviceScaleFactor: 2,
  locale: 'en-US',
});

const manifest = { generatedAt: new Date().toISOString(), viewport, captures: [] };

for (const site of cfg.sites) {
  if (onlySite && site.site !== onlySite) continue;
  await mkdir(resolve(OUT_DIR, site.site), { recursive: true });

  for (const pg of site.pages) {
    const page = await ctx.newPage();
    const base = `captures/${site.site}/${pg.slug}--desktop`;
    console.log(`→ ${site.site}/${pg.slug}  ${pg.url}`);
    try {
      await page.goto(pg.url, { waitUntil: 'networkidle', timeout: 45000 });
    } catch {
      await page.goto(pg.url, { waitUntil: 'domcontentloaded', timeout: 45000 });
      await page.waitForTimeout(3000);
    }
    await dismissConsent(page);

    const hash = new URL(pg.url).hash;
    if (hash && hash.length > 1) {
      // Âncora de single-page: posiciona a seção no viewport (autoScroll
      // levaria pro rodapé e perderia o alvo).
      await page.evaluate((h) => {
        document.querySelector(h)?.scrollIntoView({ block: 'start' });
      }, hash);
    } else {
      await autoScroll(page);
    }
    await page.waitForTimeout(600);

    // Viewport em PNG (nitidez de UI); full-page em JPEG (páginas de
    // marketing são fotográficas e longas — PNG full-page passa de 20 MB).
    const files = [`${base}.png`];
    await page.screenshot({ path: resolve(REF_DIR, `${base}.png`) });
    if (!pg.viewportOnly) {
      const docH = await page.evaluate(() => document.body.scrollHeight);
      const h = Math.min(docH, MAX_FULLPAGE_PX);
      await page.screenshot({
        path: resolve(REF_DIR, `${base}.fullpage.jpg`),
        // fullPage + clip: página inteira, mas com teto de altura para
        // listagens de scroll infinito.
        fullPage: true,
        clip: { x: 0, y: 0, width: viewport.width, height: h },
        type: 'jpeg',
        quality: 82,
      });
      files.push(`${base}.fullpage.jpg`);
    }

    manifest.captures.push({
      site: site.site,
      label: site.label,
      slug: pg.slug,
      url: pg.url,
      title: await page.title(),
      capturedAt: new Date().toISOString(),
      files,
    });
    await page.close();
  }
}

await browser.close();
await writeFile(
  resolve(REF_DIR, 'manifest.json'),
  JSON.stringify(manifest, null, 2) + '\n',
);
console.log(`\n✓ ${manifest.captures.length} páginas · manifest.json atualizado`);
