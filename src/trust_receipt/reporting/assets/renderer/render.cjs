'use strict';
// No browser, network, user code, URL or file input. stdin is adapter-derived JSON.
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const bundle = path.join(__dirname, '../echarts/echarts-6.0.0.min.js');
const expected = 'baa8dfe7e1d9336b98e8986ba7e20ea15e7cdbea1ef42a59d59478632fa45a1d';
const allowed = new Set(('animation backgroundColor textStyle color fontSize fontFamily title text subtext '
  + 'fontWeight subtextStyle lineHeight left top tooltip trigger renderMode formatter confine aria enabled '
  + 'label description series type layout width height roam scaleLimit min max data links edgeSymbol '
  + 'edgeSymbolSize show position edgeLabel emphasis focus id name x y symbol symbolSize symbolKeepAspect '
  + 'rich icon role address itemStyle borderWidth source target edge_id event_ref source_label status '
  + 'amount_base_units finding_ids lineStyle curveness opacity rotate align verticalAlign offset padding '
  + 'borderRadius amount state unit').split(' '));
const card = 'path://M12 0H164Q176 0 176 12V68Q176 80 164 80H12Q0 80 0 68V12Q0 0 12 0Z';

function validate(value, depth = 0) {
  if (depth > 12) throw Error('depth');
  if (typeof value === 'string' && value.length > 4096) throw Error('text');
  if (typeof value === 'number' && !Number.isFinite(value)) throw Error('number');
  if (Array.isArray(value)) value.forEach(item => validate(item, depth + 1));
  else if (value && typeof value === 'object') {
    for (const [key, child] of Object.entries(value)) {
      if (!allowed.has(key)) throw Error('key');
      validate(child, depth + 1);
    }
  }
}

async function main() {
  if (process.platform === 'linux') {
    const font = execFileSync('fc-match', ['-f', '%{family}', 'TreasuryTally Report Sans'],
      {timeout: 1000, maxBuffer: 1024}).toString();
    if (!font.includes('TreasuryTally Report Sans')) throw Error('font');
  }
  if (crypto.createHash('sha256').update(fs.readFileSync(bundle)).digest('hex') !== expected) throw Error('asset');
  const echarts = require(bundle);
  const sharp = require('sharp');
  if (sharp.versions.sharp !== '0.34.5') throw Error('version');
  sharp.cache(false);
  sharp.concurrency(1);
  const chunks = [];
  let size = 0;
  for await (const chunk of process.stdin) {
    size += chunk.length;
    if (size > 256000) throw Error('input');
    chunks.push(chunk);
  }
  const input = JSON.parse(Buffer.concat(chunks).toString('utf8'));
  if (Object.keys(input).sort().join(',') !== 'binding,option') throw Error('envelope');
  if (!/^[a-f0-9]{64}$/.test(input.binding)) throw Error('binding');
  const option = input.option;
  validate(option);
  const series = option.series;
  if (!Array.isArray(series) || series.length !== 1 || series[0].type !== 'graph'
      || series[0].layout !== 'none' || series[0].links.length > 4 || series[0].data.length > 8) throw Error('graph');
  if (option.tooltip.formatter !== '{b}' || option.tooltip.renderMode !== 'richText') throw Error('tooltip');
  for (const node of series[0].data) {
    if (node.symbol !== card || node.symbolSize !== 176) throw Error('symbol');
  }
  option.textStyle.fontFamily = 'TreasuryTally Report Sans, sans-serif';
  const columns = [0, 500].map(x => series[0].data.filter(node => node.x === x).length);
  const width = 720;
  const count = Math.max(...columns);
  const height = Math.max(count <= 1 ? 320 : 480, (count - 1) * 160 + 280);
  if (height > 880 || width * height * 4 > 2600000) throw Error('pixels');
  const chart = echarts.init(null, null, {renderer: 'svg', ssr: true, width, height});
  try {
    chart.setOption(option);
    require('../echarts/card-edge-geometry.js')(chart);
    const svg = chart.renderToSVGString();
    if (Buffer.byteLength(svg) > 512000 || /<script|<image|<foreignObject|<!DOCTYPE/i.test(svg)) throw Error('svg');
    const png = await sharp(Buffer.from(svg), {density: 144, limitInputPixels: 2600000}).png().toBuffer();
    if (png.length > 4000000) throw Error('output');
    process.stdout.write(JSON.stringify({binding: input.binding, svg, png: png.toString('base64')}));
  } finally { chart.dispose(); }
}

main().catch(() => { process.stderr.write('EXPORT_UNAVAILABLE'); process.exitCode = 1; });
