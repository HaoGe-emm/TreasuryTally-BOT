"""Accessible SVG directed account graph; amounts remain decimal strings."""

from html import escape

from trust_receipt.hashing import stable_hash
from trust_receipt.models import FundFlowNodeRole

EDGE_COLOR = "#D1CDC4"


def graph_svg(projection) -> str:
    marker_prefix = f"flow-{projection.attempt}-{stable_hash(projection)[2:12]}"
    groups = [
        [node for node in projection.nodes if node.role is FundFlowNodeRole.TREASURY],
        [node for node in projection.nodes if node.role is FundFlowNodeRole.EXTERNAL],
        [node for node in projection.nodes if node.role is FundFlowNodeRole.RECIPIENT],
    ]
    coordinates = {}
    height = max(220, 80 + max((len(group) for group in groups), default=0) * 90)
    nodes = []
    for column, group in enumerate(groups):
        for row, node in enumerate(group):
            x, y = 100 + column * 260, 70 + row * 90
            coordinates[node.node_id] = (x, y)
            nodes.append(
                f'<g><rect x="{x - 85}" y="{y - 22}" width="170" height="44" rx="12" '
                f'fill="#1C1C1C" stroke="none"/><text x="{x}" y="{y + 5}" '
                f'text-anchor="middle" fill="#F3F1EA" font-size="12">{escape(node.label)}</text></g>'
            )
    edges = []
    for index, edge in enumerate(projection.edges):
        x1, y1 = coordinates[edge.from_node_id]
        x2, y2 = coordinates[edge.to_node_id]
        if x1 != x2:
            direction = 1 if x2 > x1 else -1
            x1 += 85 * direction
            x2 -= 85 * direction
        elif y1 != y2:
            direction = 1 if y2 > y1 else -1
            y1 += 22 * direction
            y2 -= 22 * direction
        else:
            x1 -= 65
            x2 += 65
            y1 += 22
            y2 += 22
        color = EDGE_COLOR
        bend = 30 + index % 4 * 20
        mid_x, mid_y = (x1 + x2) // 2, (y1 + y2) // 2 + bend
        if x1 == x2:
            mid_x += 120
        title = escape(f"{edge.status.value} · {edge.amount_base_units} base units · {edge.event_key}")
        dashed = 'stroke-dasharray="5 4"' if edge.status.value != "MATCHED" else ""
        line_width = "2" if edge.status.value in {"MATCHED", "INTERNAL_TRANSFER"} else "3.5"
        edges.append(
            f'<g><title>{title}</title><path d="M {x1} {y1} Q {mid_x} {mid_y} {x2} {y2}" '
            f'fill="none" stroke="{color}" stroke-width="{line_width}" {dashed} '
            f'marker-end="url(#{marker_prefix}-{index})"/>'
            f'<defs><marker id="{marker_prefix}-{index}" markerWidth="6" markerHeight="6" refX="5" refY="3" '
            f'orient="auto"><path d="M0,0 L6,3 L0,6" fill="{color}"/></marker></defs></g>'
        )
    return (
        '<div class="fund-flow-graph" style="overflow-x:auto">'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 {height}" '
        'width="720" style="width:720px;max-width:none" role="img" '
        'aria-label="账户资金流方向；下方事件列表提供完整状态、金额和证据">'
        + "".join(edges + nodes) + "</svg></div>"
    )
