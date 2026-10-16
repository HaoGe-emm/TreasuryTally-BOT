'use strict';
// Offline ECharts integration test. No browser, generated code or monetary arithmetic.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const assets = path.resolve(__dirname, '../../../src/trust_receipt/reporting/assets/echarts');
const echarts = require(path.join(assets, 'echarts-6.0.0.min.js'));
const attach = require(path.join(assets, 'card-edge-geometry.js'));
const original = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));

function apply(p, m) {
  return !m ? p.slice() : [m[0] * p[0] + m[2] * p[1] + m[4], m[1] * p[0] + m[3] * p[1] + m[5]];
}
function verify(chart) {
  const graph = chart.getModel().getSeriesByIndex(0).getGraph();
  chart.renderToSVGString(); // Updates actual arrow and label transforms.
  graph.eachEdge(edge => {
    const group = edge.getGraphicEl();
    const line = group.getLinePath();
    for (const [node, point] of [[edge.node1, line.pointAt(0)], [edge.node2, line.pointAt(1)]]) {
      const symbol = node.getGraphicEl().childAt(0);
      const rect = symbol.getBoundingRect();
      const lo = apply([rect.x, rect.y], symbol.getComputedTransform());
      const hi = apply([rect.x + rect.width, rect.y + rect.height], symbol.getComputedTransform());
      const actual = apply(point, group.getComputedTransform());
      assert(actual[0] >= lo[0] - 0.01 && actual[0] <= hi[0] + 0.01);
      assert(actual[1] >= lo[1] - 0.01 && actual[1] <= hi[1] + 0.01);
      const gap = Math.min(Math.abs(actual[0] - lo[0]), Math.abs(actual[0] - hi[0]),
        Math.abs(actual[1] - lo[1]), Math.abs(actual[1] - hi[1]));
      assert(gap < 0.01, `card contact gap ${gap}`);
    }
    const arrow = group.childOfName('toSymbol');
    const endpoint = line.pointAt(1);
    assert(Math.abs(arrow.x - endpoint[0]) < 0.01 && Math.abs(arrow.y - endpoint[1]) < 0.01);
  });
}

let checks = 0;
for (const curved of [false, true]) {
  for (const reversed of [false, true]) {
    const option = structuredClone(original);
    for (const edge of option.series[0].links) {
      edge.lineStyle.curveness = curved ? 0.25 : 0;
      if (reversed) [edge.source, edge.target] = [edge.target, edge.source];
    }
    const before = JSON.stringify(option);
    const chart = echarts.init(null, null, {renderer: 'svg', ssr: true, width: 720, height: 480});
    const repaint = () => { attach(chart); chart.getZr().refreshImmediately(); };
    chart.setOption(option);
    chart.on('graphRoam', repaint);
    repaint();
    verify(chart); checks++;
    for (const width of [960, 1440]) {
      chart.resize({width}); repaint(); verify(chart); checks++;
    }
    chart.dispatchAction({type: 'graphRoam', seriesIndex: 0, zoom: 1.5, originX: 200, originY: 200});
    verify(chart); checks++;
    chart.dispatchAction({type: 'graphRoam', seriesIndex: 0, dx: 30, dy: 20});
    verify(chart); checks++;
    assert.equal(JSON.stringify(option), before);
    chart.dispose();
  }
}
console.log(`PASSED ${checks} straight/curved/reversed/resize/zoom/pan card-contact checks`);
