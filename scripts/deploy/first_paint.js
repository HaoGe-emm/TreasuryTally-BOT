// Read-only cold-context homepage probe. Never uploads or invokes verification.
async (page) => {
  const url = page.url();
  const target = new URL(url);
  if (!["127.0.0.1", "creatoros.top"].includes(target.hostname)) {
    throw new Error("First-paint probe is limited to the local app and existing production host");
  }
  const browser = page.context().browser();
  const results = [];
  for (const width of [1440, 390]) {
    const context = await browser.newContext({ viewport: { width, height: width === 390 ? 844 : 1000 }, deviceScaleFactor: 2 });
    const probe = await context.newPage();
    const errors = [];
    probe.on("pageerror", error => errors.push(String(error.message).slice(0, 200)));
    try {
      const start = Date.now();
      const response = await probe.goto(url, { waitUntil: "commit", timeout: 60000 });
      const responseMs = Date.now() - start;
      await probe.waitForFunction(() => {
        const header = document.querySelector(".hero-copy h1");
        return header && header.getBoundingClientRect().height > 0;
      }, null, { timeout: 30000 });
      const headerMs = Date.now() - start;
      await probe.waitForFunction(() => {
        const logo = document.querySelector(".brand-logo");
        return logo && logo.complete && logo.naturalWidth > 0 && logo.getBoundingClientRect().width > 0;
      }, null, { timeout: 30000 });
      const logoMs = Date.now() - start;
      const dom = await probe.evaluate(() => {
        const logo = document.querySelector(".brand-logo");
        return {
          title: document.title, logoWidth: logo.getBoundingClientRect().width,
          naturalWidth: logo.naturalWidth, fetchPriority: logo.fetchPriority,
          dpr: devicePixelRatio,
          logoPlacements: [...document.querySelectorAll('.brand-logo, .hero-emblem img')].map(el => ({
            url: el.currentSrc, loaded: el.complete && el.naturalWidth > 0,
            naturalWidth: el.naturalWidth, width: el.getBoundingClientRect().width,
          })),
          cssReady: getComputedStyle(document.documentElement).getPropertyValue("--tr-bg-page").trim() === "#0A0A0A",
          exceptions: document.querySelectorAll('[data-testid="stException"]').length,
          overflow: document.documentElement.scrollWidth > innerWidth,
          typography: [...document.querySelectorAll('.stApp *')]
            .filter(el => el.getBoundingClientRect().height && [...el.childNodes].some(node => node.nodeType === 3 && node.textContent.trim()))
            .map(el => ({ text: el.textContent.trim().slice(0, 45), size: getComputedStyle(el).fontSize }))
            .filter(item => !['12px', '14px', '16px', '20px', '24px'].includes(item.size)),
          spacing: ['.block-container', '.hero-main h1', '.workflow-steps', '.signal-grid', '.task-summary', '[class*="st-key-panel-"]', '[data-testid="stHorizontalBlock"]']
            .flatMap(selector => [...document.querySelectorAll(selector)].slice(0, 4).map(el => {
              const css = getComputedStyle(el);
              return { selector, padding: css.padding, gap: css.gap, margin: css.margin, fontSize: css.fontSize, border: css.borderWidth, radius: css.borderRadius };
            })),
          resources: performance.getEntriesByType("resource")
            .filter(entry => /(?:Html\.|StreamlitMarkdown\.|logo\.png|\/media\/.*\.png)/.test(entry.name))
            .map(entry => ({ file: new URL(entry.name).pathname, startMs: entry.startTime, durationMs: entry.duration })),
        };
      });
      if (!dom.cssReady || dom.exceptions || errors.length || dom.overflow) {
        throw new Error(JSON.stringify({ dom, errors }));
      }
      results.push({ width, status: response.status(), responseMs, headerMs, logoMs, ...dom, errors });
    } finally {
      await context.close();
    }
  }
  return { url, mode: "two fresh contexts; initial homepage only", results };
}
