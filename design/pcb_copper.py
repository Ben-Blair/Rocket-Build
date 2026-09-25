"""The flight-computer board's routed copper, read straight from the .kicad_pcb.

No pcbnew and no KiCad: a plain-Python reader like design/pcb_placement.py, so the
simulations in scripts/pcb_sim_report.py run on a normal python3 with numpy/scipy.

What it gives:
  - every track segment and via, with net, layer, width;
  - `path_resistance(net, a, b)`: DC resistance of the routed copper between two pads,
    Dijkstra over the track graph (shortest-resistance path -- parallel paths are ignored,
    so this is an UPPER bound, which is the conservative side for a voltage drop);
  - `path_segments(net, a, b)`: the same path as geometry, for Biot-Savart.

Copper constants are 1 oz outer layers, 20 degC, 20 um via plating -- the JLC04161H-7628
build pcb/flight_computer/fab/ORDERING.md orders.
"""

from __future__ import annotations

import heapq
import math
import re
from dataclasses import dataclass
from pathlib import Path

from design.pcb_placement import BOARD, Pad, _blocks, load_pads

RHO_CU = 1.72e-8          # ohm m, 20 degC
T_OUTER = 35e-6           # m, 1 oz
BOARD_T = 1.6e-3          # m
VIA_PLATING = 20e-6       # m


@dataclass(frozen=True)
class Seg:
    net: str
    layer: str
    x0: float
    y0: float
    x1: float
    y1: float
    width: float           # mm

    @property
    def length(self) -> float:
        return math.hypot(self.x1 - self.x0, self.y1 - self.y0)

    @property
    def ohms(self) -> float:
        return RHO_CU * (self.length * 1e-3) / (self.width * 1e-3 * T_OUTER)


@dataclass(frozen=True)
class Via:
    net: str
    x: float
    y: float
    drill: float           # mm

    @property
    def ohms(self) -> float:
        return RHO_CU * BOARD_T / (math.pi * self.drill * 1e-3 * VIA_PLATING)


_F = r"(-?[\d.]+)"


def load_copper(path: Path | str = BOARD) -> tuple[list[Seg], list[Via]]:
    text = Path(path).read_text()
    segs, vias = [], []
    for b in _blocks(text, "segment"):
        s = re.search(r"\(start %s %s\)" % (_F, _F), b)
        e = re.search(r"\(end %s %s\)" % (_F, _F), b)
        w = re.search(r"\(width %s\)" % _F, b)
        layer = re.search(r'\(layer "([^"]+)"\)', b)
        net = re.search(r'\(net "([^"]*)"\)', b)
        segs.append(Seg(net.group(1) if net else "", layer.group(1),
                        float(s.group(1)), float(s.group(2)),
                        float(e.group(1)), float(e.group(2)), float(w.group(1))))
    for b in _blocks(text, "via"):
        at = re.search(r"\(at %s %s\)" % (_F, _F), b)
        d = re.search(r"\(drill %s\)" % _F, b)
        net = re.search(r'\(net "([^"]*)"\)', b)
        vias.append(Via(net.group(1) if net else "", float(at.group(1)), float(at.group(2)),
                        float(d.group(1))))
    return segs, vias


def _key(x: float, y: float, layer: str) -> tuple:
    return (round(x, 3), round(y, 3), layer)


class NetGraph:
    """One net's tracks and vias as a resistor graph."""

    def __init__(self, net: str, path: Path | str = BOARD):
        segs, vias = load_copper(path)
        self.net = net
        self.segs = [s for s in segs if s.net == net]
        self.vias = [v for v in vias if v.net == net]
        self.adj: dict[tuple, list[tuple[tuple, float, object]]] = {}
        for s in self.segs:
            a, b = _key(s.x0, s.y0, s.layer), _key(s.x1, s.y1, s.layer)
            self._edge(a, b, s.ohms, s)
        for v in self.vias:
            a, b = _key(v.x, v.y, "F.Cu"), _key(v.x, v.y, "B.Cu")
            self._edge(a, b, v.ohms, v)
        self.pads = {(p.ref, p.number): p for p in load_pads(path) if p.net == net}
        # A pad joins every track end that lands on it, on ANY layer: a through-hole pad
        # (J1, the servo headers) is where F.Cu and B.Cu copper meet, exactly like a via.
        for (ref, num), p in self.pads.items():
            hub = ("pad", ref, num)
            for n in self._pad_nodes(p):
                self._edge(hub, n, 1e-6, None)

    def _edge(self, a, b, r, item):
        self.adj.setdefault(a, []).append((b, r, item))
        self.adj.setdefault(b, []).append((a, r, item))

    def _pad_nodes(self, pad: Pad, reach: float = 1.2) -> list[tuple]:
        """Track endpoints that land on this pad (within `reach` mm of its centre)."""
        return [n for n in self.adj
                if n[0] != "pad" and math.hypot(n[0] - pad.x, n[1] - pad.y) <= reach]

    def path(self, a: tuple[str, str], b: tuple[str, str]):
        """(ohms, [Seg|Via, ...]) along the least-resistance routed path from pad a to pad b."""
        src, dst = self._pad_nodes(self.pads[a]), set(self._pad_nodes(self.pads[b]))
        if not src or not dst:
            raise ValueError("no track reaches %s or %s on %s" % (a, b, self.net))
        dist = {n: 0.0 for n in src}
        prev: dict = {}
        heap = [(0.0, n) for n in src]
        heapq.heapify(heap)
        while heap:
            d, n = heapq.heappop(heap)
            if n in dst:
                items = []
                hops = []
                while n in prev:
                    m, item = prev[n]
                    if item is not None:          # skip the pad-hub links
                        items.append(item)
                        hops.append((m, n, item))
                    n = m
                self.last_hops = hops[::-1]       # (from_node, to_node, item) in travel order
                return d, items[::-1]
            if d > dist.get(n, math.inf):
                continue
            for m, r, item in self.adj.get(n, []):
                if d + r < dist.get(m, math.inf):
                    dist[m] = d + r
                    prev[m] = (n, item)
                    heapq.heappush(heap, (d + r, m))
        raise ValueError("%s and %s are not joined by copper on %s" % (a, b, self.net))


def oriented(graph: "NetGraph", a, b):
    """The path a -> b as (layer, x0, y0, x1, y1) in the direction of travel (vias dropped).

    Seg objects keep whatever start/end order KiCad stored, which is NOT the direction current
    flows along a path -- use this for anything directional (Biot-Savart)."""
    graph.path(a, b)
    out = []
    for fr, to, item in graph.last_hops:
        if isinstance(item, Seg):
            out.append((item.layer, fr[0], fr[1], to[0], to[1]))
    return out


def ipc2221_rise_c(amps: float, width_mm: float, oz: float = 1.0) -> float:
    """Temperature rise of an EXTERNAL trace, IPC-2221: I = 0.048 dT^0.44 A^0.725 (A in mil^2).

    Conservative against IPC-2152 for short traces over planes (the planes sink heat), which is
    the side to be wrong on.
    """
    area_mil2 = (width_mm / 0.0254) * (oz * 1.378)
    return (amps / (0.048 * area_mil2 ** 0.725)) ** (1 / 0.44)
