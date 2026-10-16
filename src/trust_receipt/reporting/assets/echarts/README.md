# Apache ECharts local component

Version: **6.0.0**, pinned rather than following a CDN's latest version.

The upstream prebuilt `dist/echarts.min.js` is stored unchanged as
`echarts-6.0.0.min.js`. It was downloaded from:

https://raw.githubusercontent.com/apache/echarts/6.0.0/dist/echarts.min.js

SHA-256: `baa8dfe7e1d9336b98e8986ba7e20ea15e7cdbea1ef42a59d59478632fa45a1d`.

The adjacent LICENSE.txt and NOTICE.txt are unchanged upstream Apache-2.0
license and attribution files from the same tag. The minification is the
upstream distribution format, not a local rewrite to evade file-size rules.
No npm installation, lifecycle scripts, or transitive upgrades are required.

Official documentation:

- https://echarts.apache.org/handbook/en/get-started/
- https://echarts.apache.org/handbook/en/how-to/cross-platform/server/

`reporting.echarts_flow` provides a plain-data graph option and a self-contained
read-only iframe document. No CDN/network access occurs while rendering.
Do not replace richText tooltips with an HTML formatter built from uploaded data.
Financial values are strings, never JavaScript Number values or line widths.
The component's 12-event default page is explicitly labelled; callers must
provide page selection to reach all saved events, not call it a full preview.
