# Local ECharts funds-flow handoff

## API

Import from `trust_receipt.reporting.echarts_flow` (no changes to `app/`):

```python
option = echarts_flow_option(view, attempt="current", offset=0, limit=12, theme="dark")
html = echarts_component_html(view, attempt="current", offset=0, limit=12)
```

`echarts_javascript()` returns the pinned, SHA-256-checked upstream bundle.
The HTML component embeds it and has a fixed script-hash CSP with no network
connections, URL input, or executable code from the report. It is a component,
not the complete offline HTML business report. Use a sandboxed component/iframe,
never inject it into the parent application's document.

For page selection set offset to 0, 12, 24, etc. Default preview is explicitly
labelled `first–last / total`; preserve access to the complete event table.
Limit is 1..20; attempt can be `previous` only if a saved previous report exists.
Both attempts retain their original outcome; switching the graph is not proof
of a verified repair relationship. Graph pan/zoom never triggers business work.

The graph has account nodes and arrow links, exact amount/unit/source/event in
rich-text tooltips, and business difference labels on links. Missing snapshots
produce no edges, not guessed transfers. INCONCLUSIVE remains neutral and never
gets zero-filled amounts. Edge width is constant, not a Number conversion of
an amount. Address casing is normalized only for graph node identity.

## Local asset

`src/trust_receipt/reporting/assets/echarts/echarts-6.0.0.min.js`

ECharts 6.0.0; upstream minified distribution unchanged, Apache-2.0. LICENSE,
NOTICE, provenance and SHA-256 are next to the asset. No runtime CDN or npm
dependency installation. Python package data includes the entire subdirectory.

## Verification boundaries

37 reporting/ECharts tests passed (25 projection + 12 graph). Scoped Ruff passed.
Official ECharts SVG SSR generated ten graphs: FAIL, PASS, INCONCLUSIVE,
repair-current and tiny-200's explicit first page, each at 390 and 1440 px.
The SSR driver rejects missing SVG, scripts and NaN coordinates. Paging tests
reach all 200 edges without duplicates or omitted pages.

These are program/rendering checks, NOT visual/browser acceptance: screenshots,
tooltips, actual mobile legibility, UI pagination and integrated downloads still
need manual verification. User requested browser automation paused; do not
resume their page automatically. DOCX/PDF whole-page QA is separately unfinished.

SSR invocation with the supplied fixed bundled Node runtime:

```text
node tests/reporting/echarts_ssr.cjs .tmp/reporting-qa
```

Inputs are plain `*.option.json` generated from labelled fixture report views.
No RPC, model, public upload, write-chain or production deployment was performed.
