'use strict';
// Fixed presentation adapter for ECharts 6.0.0's circular graph-edge clipping.
// Never reads amount fields, executes input code, or changes graph identities.
function treasuryTallyAttachCardEdges(chart) {
  const series = chart.getModel().getSeriesByIndex(0);
  if (!series || series.subType !== 'graph') return;
  const graph = series.getGraph();

  function apply(point, matrix) {
    if (!matrix) return point.slice();
    return [matrix[0] * point[0] + matrix[2] * point[1] + matrix[4],
      matrix[1] * point[0] + matrix[3] * point[1] + matrix[5]];
  }
  function inverse(matrix) {
    if (!matrix) return null;
    const [a, b, c, d, e, f] = matrix;
    const det = a * d - b * c;
    if (!Number.isFinite(det) || Math.abs(det) < 1e-10) throw Error('card transform');
    return [d / det, -b / det, -c / det, a / det,
      (c * f - d * e) / det, (b * e - a * f) / det];
  }
  function bounds(node, line) {
    const path = node.getGraphicEl().childAt(0);
    const box = path.getBoundingRect();
    const toLine = inverse(line.getComputedTransform());
    const corners = [[box.x, box.y], [box.x + box.width, box.y],
      [box.x, box.y + box.height], [box.x + box.width, box.y + box.height]]
      .map(p => apply(apply(p, path.getComputedTransform()), toLine));
    return [Math.min(...corners.map(p => p[0])), Math.min(...corners.map(p => p[1])),
      Math.max(...corners.map(p => p[0])), Math.max(...corners.map(p => p[1]))];
  }
  function inside(point, box) {
    return point[0] >= box[0] && point[0] <= box[2]
      && point[1] >= box[1] && point[1] <= box[3];
  }
  function at(points, t) {
    const [start, end, control] = points;
    if (!control) return start.map((v, i) => v + t * (end[i] - v));
    return start.map((v, i) => (1 - t) ** 2 * v
      + 2 * (1 - t) * t * control[i] + t * t * end[i]);
  }
  function boundary(points, box, reverse) {
    // Bracket the first exit from each card, including non-monotonic curves.
    const origin = reverse ? 1 : 0;
    let inner = origin;
    for (let step = 1; step <= 128; step++) {
      let outer = reverse ? 1 - step / 128 : step / 128;
      if (inside(at(points, outer), box)) { inner = outer; continue; }
      for (let i = 0; i < 30; i++) {
        const middle = (inner + outer) / 2;
        if (inside(at(points, middle), box)) inner = middle;
        else outer = middle;
      }
      return (inner + outer) / 2;
    }
    return origin;
  }

  graph.eachEdge(edge => {
    const line = edge.getGraphicEl();
    const layout = edge.getLayout();
    const points = layout.__original || layout;
    const start = boundary(points, bounds(edge.node1, line), false);
    const end = boundary(points, bounds(edge.node2, line), true);
    if (start >= end) return; // No visible segment when cards overlap.
    const trimmed = [at(points, start), at(points, end)];
    if (points[2]) {
      const control = points[0].map((value, i) => trimmed[0][i] + (end - start)
        * ((1 - start) * (points[2][i] - value) + start * (points[1][i] - points[2][i])));
      trimmed.push(control);
    }
    line.setLinePoints(trimmed);
  });
}
if (typeof module !== 'undefined' && module.exports) module.exports = treasuryTallyAttachCardEdges;
