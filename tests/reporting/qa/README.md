# Offline reporting QA

These helpers exercise real receipt-derived views, ECharts SSR, sharp PNG, DOCX and PDF.
They are not a production Dockerfile, browser acceptance test or remote-service probe.
Never mount `.env`, production configuration, data or private receipts into the QA containers.

## Authoring and parity

1. `prepare_views.py <output-directory>` runs with the project verifier dependencies and constructs synthetic evidence.
2. `author_artifacts.py <directory> <trusted-node-executable> <trusted-node-modules-directory>` runs with
   loader-selected bundled Python. No generated picture is substituted for the business graph.
3. Repeat authoring in the independent Python 3.12 / Node 22.23.3 / sharp 0.34.5 QA image.
4. `check_exports.py` with the same arguments checks true formats, full event references, report/receipt identity,
   embedded fonts, source labels, privacy, HTML escaping and limits. Its JSON deliberately does not claim visual approval.
5. `render_all.py <inputs> <outputs> <canonical-render_docx.py>` renders DOCX through the skill renderer and PDF
   through Poppler. Inspect **every** individual page PNG at original resolution before handing off.

The seven fixtures are PASS, FAIL, INCONCLUSIVE, repaired delivery with preserved original FAIL, uint256-scale
amount, token decimals 255 and 200 separately identified tiny transfers. They are not real chain acceptance evidence.
Optional fourth authoring/rendering argument is a comma-separated fixture-name filter for iterative repairs.

## Isolation and reproducibility

Use `--network none --read-only --cpus 2 --memory 1g --pids-limit 128 --tmpfs /tmp:rw,size=128m` for authoring/parity.
Only fixture outputs are writable. Page rendering needs a separate writable output mount and may use 2 GiB memory,
256 pids and a 512 MiB temporary filesystem. No ports, production keys or application credentials are needed.
The fixed Node worker has a 20-second Python timeout; page-render subprocesses have 120-second timeouts.

`Dockerfile` builds the standalone Debian document-tools base. `Dockerfile.renderer` combines it with pinned official
Node and Python image digests and installs the renderer lock in `/opt/renderer`. Build-time package downloads are
distinct from network-disabled runtime verification. Fontconfig must register the packaged report font.
Record actual `python --version`, `node --version`, `sharp.versions`, `pip check` and image ID; do not infer versions
from a mutable image tag. Preserve native dependency README/package.json and license notices.

Review final table borders, repeated headers, row integrity, readable hashes/amounts, arrowheads, card proportions,
Chinese glyphs and page breaks. Rerender after a fix. Unchanged page hashes may link to already-inspected originals;
inspect all changed pages again. Do not approve contact sheets alone or merely a successful conversion command.

## Application composition

Reuse a single application-owned `EChartsRenderer(node_path=..., modules_path=...)` instance.
Pass `renderer=renderer` explicitly to `export_docx`, `export_pdf`, `export_html`, `graph_png` and `graph_svg`.
Functions return in-memory bytes (SVG is text), without upload or write-chain authority.
`ExportUnavailable` disables the affected export without inventing another format or Python-drawn fallback.
The original JSON receipt is independent of these document dependencies.

Static diagrams preview at most four rows, or one if repeated account pairs would overlap. The complete appendix
preserves every saved event. These print limits do not replace the web graph's 12-row explicit pagination.
Native total-memory and egress enforcement belongs to deployment, not the JavaScript heap flag.

## Card-contact regression

`node check_card_geometry.cjs <saved-echarts-option.json>` uses the actual pinned ECharts runtime, not a drawing mock.
It checks rendered card bounds, line endpoints and arrow positions for straight/curved/reversed edges, resize, zoom
and pan, and asserts the input option remains unchanged. The fixed geometry adapter is shared by SSR and the web
component. It relies on ECharts 6.0.0 graphic internals: rerun and review it before any upstream version upgrade.
Inspect long amount/status/unit labels too; geometric contact alone is not visual approval.
