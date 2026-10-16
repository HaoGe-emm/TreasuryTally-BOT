# Local report renderer

Fixed ECharts 6.0.0 SVG SSR → sharp 0.34.5 PNG, no Python drawing fallback.
Reference runtime: Node 22.23.3 / Python 3.12. Use `npm ci --ignore-scripts` in this directory and retain optional platform dependencies.
Lock generated with npm 10 in the pinned Linux QA toolchain. No node_modules is committed or packaged in the Python wheel.

Sources and licenses:
- [ECharts SSR](https://echarts.apache.org/handbook/en/how-to/cross-platform/server/): Apache-2.0; sibling echarts LICENSE/NOTICE retained.
- [sharp installation](https://sharp.pixelplumbing.com/install/) and [0.34.5 metadata](https://registry.npmjs.org/sharp/0.34.5).
- [sharp 0.34.5 license](https://github.com/lovell/sharp/blob/v0.34.5/LICENSE): Apache-2.0.
- [Node distribution](https://nodejs.org/dist/v22.23.3/): retain its LICENSE when copying the executable.
  The QA image copies `/usr/local/LICENSE` from the official Node image to `/usr/local/share/doc/node/LICENSE`.
The installed @img/sharp-libvips-linux-x64 1.2.4 package declares LGPL-3.0-or-later. Its README lists each bundled
native dependency and license, including the upstream LGPL any-later-version terms. Retain README, package.json,
sharp LICENSE and all dependency license/notice files in deployment artifacts; do not treat Apache-2.0 as the whole stack license.
Worker is project source, not upstream vendor code.

Linux requires Fontconfig and the packaged ReportSans-Regular.ttf installed in the image with fc-cache refreshed.
The fixed fc-match probe rejects a missing report font rather than silently producing Chinese tofu.

Reuse one application-owned instance. Trusted Node/module paths are deployment configuration, never report fields.
Worker has no runtime networking calls; deployment must also deny egress and enforce total native memory/pids limits.
Missing dependencies, invalid option keys/symbols/formatters, limits or report hash mismatches return EXPORT_UNAVAILABLE.
The standalone QA Dockerfile is not production deployment configuration.
