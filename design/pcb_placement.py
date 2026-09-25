"""Placement geometry read straight out of `pcb/flight_computer/flight_computer.kicad_pcb`.

THE GAP THIS FILE CLOSES. Every other number in this project is computed and then gated, so
it cannot silently regress. The board was the exception: `pcb/README.md` records ERC, DRC and
a footprint-assignment count, all of which are *connectivity* checks, and none of which can
see that a 12 pF crystal load cap is sitting 21 mm from its crystal. Connectivity was right
and the geometry was wrong, and nothing in the repo could tell.

WHAT IT MEASURES, AND WHY THAT ONE THING. For a pad, the distance to the NEAREST pad of the
same net on another component. That is a lower bound on the trace that will exist after
routing -- the router can only make it longer. It needs no netlist topology, no routing, and
no pcbnew: it is the shortest possible parasitic, so if it is already too big, routing cannot
save it.

WHAT IT DOES *NOT* MEASURE, which took one wrong version to learn. Run over every pad on the
board, this metric is worthless: it flags SERVO1-4 at 33 mm (MCU to the servo headers), the
whole SWD header at 28-32 mm, and MAG_INT at 33 mm. Those are long because the board is
70 mm wide and the parts are at opposite ends of it BY DESIGN -- docs/14's zoning is the
reason, and shortening them would mean unzoning the board. A gate that fires on the
intended design teaches everyone to ignore it.

So the check is scoped to the case where "short" is the entire job of the part:

  1. TWO-TERMINAL PASSIVES (C/R/L/FB). A decoupling cap, a load cap, a series ferrite or a
     pull-up exists to be local to one pin. If one is far from its nearest same-net
     neighbour, that is a defect with no design intent behind it -- every time.
  2. A NAMED LIST OF NETS that must be short whatever is on their ends (`END_TO_END_MM`).
     Three of them, each with a physical reason written next to it.

Everything else is the router's problem, not placement's.

WHY NOT DISTANCE-TO-ANCHOR. `scaffold/layout.py` anchors each passive to a pin by design
intent, so "distance from its anchor" looks like the natural metric. It is the wrong one: it
measures whether the SOLVER did what it was told, not whether the resulting board is good. A
cap anchored to the right pin and shoved 14 mm away by a collision passes that check. This one
fails it.

GND IS EXCLUDED. Every GND pad has a stitching via within a millimetre or two and two solid
plane layers under it; nearest-same-net-pad is meaningless there. In1.Cu is a full-board pour,
so GND return is a plane question, not a placement one.

Read by `scripts/pcb_placement_report.py` for the ranked table and by `scripts/baseline.py`
for the pass/fail, so this cannot regress quietly the way it did the first time.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

BOARD = (Path(__file__).resolve().parents[1] / "pcb" / "flight_computer"
         / "flight_computer.kicad_pcb")

# Prefixes of the two-terminal parts whose whole job is to be local. SW/JP/TP/D are NOT here:
# a reset button, a solder jumper, a test point and an LED are all placed for a human's
# convenience, and none of them has a parasitic worth gating.
PASSIVE_PREFIXES = ("C", "R", "L", "FB")

# The general limit for those. Median across the passives is ~2.3 mm, so this is not a tight
# budget -- it is a tripwire for a part that has been flung somewhere silly.
GENERAL_LIMIT_MM = 6.0

# BULK capacitors get a looser limit than HF bypasses, because they are doing a different
# job. A 100 nF 0402 exists to supply a nanosecond-scale edge, and the ~1 nH per mm of the
# trace getting there is most of what decides whether it works. A 100 uF reservoir exists to
# hold the rail up over milliseconds while the regulator responds; a few extra nH in series
# with 100 uF is nothing, and its self-resonance is well below the frequencies where the
# layout matters. Holding both to one number would either wave through a bad bypass or fail
# a bulk cap for no physical reason -- and on a 70 x 45 mm board with a saturated power
# corner, the bulk caps are exactly the parts with nowhere else to go.
BULK_UF = 10.0
BULK_LIMIT_MM = 8.0

_VALUE_UF = re.compile(r"^\s*([\d.]+)\s*(p|n|u|µ)?F", re.I)


def bulk_uf(value: str) -> float | None:
    """Capacitance in uF parsed from a KiCad Value string, or None if it is not a cap value."""
    m = _VALUE_UF.match(value)
    if not m:
        return None
    scale = {"p": 1e-6, "n": 1e-3, "u": 1.0, "µ": 1.0, None: 1e6}[
        m.group(2).lower() if m.group(2) else None]
    return float(m.group(1)) * scale

# Tighter limits for passives whose parasitic matters more than the general case, with the
# reason. Keyed by net.
CRITICAL_LIMIT_MM = {
    # TPS62162 switches at 2.25 MHz; VIN is its input-cap hot loop and the largest di/dt on
    # the board. It is also the board's biggest radiated-EMI source, on a board carrying a
    # magnetometer with an 18.0 mgauss budget (estimation.required_magnetic_cleanliness()).
    "VIN": 2.5,
    # 100 kOhm enable node. The real constraint on EN is ROUTING -- do not run it alongside
    # the SW node -- which a distance cannot express; this is only a sanity bound so the
    # pull-up cannot end up on the far side of the board. Deliberately looser than VIN: the
    # node is DC and draws about a microamp, so trace inductance is irrelevant to it.
    "EN_3V3": 5.0,
    # 12 pF crystal load caps. See END_TO_END_MM.
    "OSC_IN": 5.0,
    "OSC_OUT": 5.0,
}

# Nets that must be short END TO END, whatever sits on their ends -- the only three where a
# long net is wrong even though both ends are major parts. Everything else long is zoning.
END_TO_END_MM = {
    # 8 MHz high-impedance oscillator loop: crystal, both load caps and the MCU pins want to
    # be one tight cluster. This board runs OSC_IN past the IMU, which is how it was found.
    "OSC_IN": 5.0,
    "OSC_OUT": 5.0,
    # 1.575 GHz, and RF_IN's Zin is 50 ohm (u-blox UBX-20035208 R08, Table 13). Every
    # millimetre is loss and impedance discontinuity, and the u.FL sits at a board edge, so
    # there is no reason for a long one.
    "GNSS_RF": 4.0,
}

# Long on purpose, or long and harmless. Each one needs a reason, not just an entry --
# an exemption list without reasons is how a gate stops meaning anything.
EXEMPT = {
    ("R12", "1"): "10k pull-up on FLASH_WP, DC. Long is ugly, not wrong.",
    ("R2", "2"): "PGOOD pull-up to the MCU, DC.",
    ("R10", "1"): "10k pull-up rail tap, DC.",
    ("R7", "1"): "1k LED series rail tap, DC.",
    ("R6", "1"): "USB-C CC2 5.1k. CC is a DC sense line, not the diff pair.",
    ("R5", "1"): "USB-C CC1 5.1k. Same.",
    # FB1 sits IN SERIES in the VIN path, so it cannot be at zero distance from the pin it
    # feeds -- the VIN limit is there for the input CAPACITOR's hot loop (C3), which is a
    # di/dt question, and a series ferrite is not part of that loop.
    ("FB1", "2"): "Series ferrite feeding U1's VIN; the 2.5 mm limit targets C3's hot loop.",
    # Same shape as FB1.2: the INPUT side of a series ferrite only taps the rail, and the
    # rail is decoupled everywhere. FB2's output side (VDDA -> C17/C18/U2 pin 13) is the one
    # that has to be tight, and it is checked normally -- currently 1.74 mm.
    ("FB2", "1"): "Series ferrite tapping +3V3 for VDDA; its VDDA side is the checked one.",
    # Same shape again: R33 is the series R of the IMU LDO's RC pre-filter, at the FAR end of
    # the VIN run on purpose (it filters what arrives there).  Its VIN_IMU side, into C30 and
    # U9 pin 1, is the one that has to be tight, and is checked normally.
    ("R33", "1"): "Series R of U9's RC pre-filter, fed by the VIN run; VIN_IMU side is checked.",
}

# Not real nets: KiCad emits one of these per unconnected pin.
_NC = re.compile(r"^unconnected-\(")


@dataclass(frozen=True)
class Pad:
    ref: str
    number: str
    x: float
    y: float
    net: str
    value: str = ""


@dataclass(frozen=True)
class Link:
    """One pad and the nearest same-net pad on another component."""
    ref: str
    number: str
    net: str
    mm: float
    to_ref: str
    to_number: str
    limit: float
    exempt_reason: str = ""

    @property
    def over(self) -> bool:
        return not self.exempt_reason and self.mm > self.limit


@dataclass
class PlacementCheck:
    links: list[Link]
    failures: list[Link] = field(default_factory=list)
    median_mm: float = 0.0
    n_pads: int = 0

    @property
    def ok(self) -> bool:
        return not self.failures

    def worst(self, n: int = 12) -> list[Link]:
        return sorted(self.links, key=lambda l: -l.mm)[:n]


def _blocks(text: str, tag: str) -> list[str]:
    """Every top-level `(tag ...)` block, paren-balanced.

    The board file is one s-expression; regexes alone cannot find the end of a footprint
    because pads nest arbitrarily. Written against KiCad 10's board format (20260206), which
    indents top-level blocks with a single tab -- see pcb/README.md on the format bump.
    """
    out: list[str] = []
    i = 0
    needle = "\n\t(" + tag
    while True:
        i = text.find(needle, i)
        if i < 0:
            return out
        start = i + 2
        depth = 0
        k = start
        while k < len(text):
            if text[k] == "(":
                depth += 1
            elif text[k] == ")":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        out.append(text[start:k + 1])
        i = k


_AT = re.compile(r"\n\t\t\(at (-?[\d.]+) (-?[\d.]+)(?: (-?[\d.]+))?\)")
_REF = re.compile(r'\(property "Reference" "([^"]*)"')
_VAL = re.compile(r'\(property "Value" "([^"]*)"')
_PAD = re.compile(
    r'\(pad "([^"]*)" \w+ \w+\s*\n\s*\(at (-?[\d.]+) (-?[\d.]+)(?: (-?[\d.]+))?\)(.*?)\n\t\t\)',
    re.S,
)
_NET = re.compile(r'\(net "([^"]*)"\)')


def load_pads(path: Path | str = BOARD) -> list[Pad]:
    """Every pad in global board coordinates.

    KiCad stores a pad's `(at ...)` in the footprint's own frame and the footprint's rotation
    separately; the board file's Y axis points DOWN, which is why the rotation below is
    applied as -theta. Verified against a number pcb/README.md independently records: U5 pad 1
    lands at (162.7500, 109.2250). `self_check()` asserts it.
    """
    text = Path(path).read_text()
    pads: list[Pad] = []
    for block in _blocks(text, "footprint"):
        at = _AT.search(block)
        ref = _REF.search(block)
        if not at or not ref:
            continue
        val = _VAL.search(block)
        value = val.group(1) if val else ""
        fx, fy = float(at.group(1)), float(at.group(2))
        theta = math.radians(-float(at.group(3) or 0.0))
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        for m in _PAD.finditer(block):
            px, py = float(m.group(2)), float(m.group(3))
            net = _NET.search(m.group(5))
            pads.append(Pad(
                ref=ref.group(1),
                number=m.group(1),
                x=fx + px * cos_t - py * sin_t,
                y=fy + px * sin_t + py * cos_t,
                net=net.group(1) if net else "",
                value=value,
            ))
    return pads


def _is(ref: str, prefixes) -> bool:
    """Prefix match on a reference designator, requiring the rest to be the number.

    The trailing-digit test is what stops `L` matching a future `LED1`, and `C` matching a
    `CONN3`. Without it the prefix list silently widens every time a part is added.
    """
    for prefix in prefixes:
        if ref.startswith(prefix) and ref[len(prefix):].isdigit():
            return True
    return False


def is_passive(ref: str) -> bool:
    """True for a two-terminal C/R/L/FB -- the parts whose whole job is to be local."""
    return _is(ref, PASSIVE_PREFIXES)


def serves(ref: str) -> bool:
    """True for a part a bypass/pull-up can legitimately be measured AGAINST.

    A capacitor sitting 2 mm from another capacitor has not done its job, and measuring to
    "the nearest same-net pad on another component" lets it claim it has. That is not
    hypothetical: C3, the TPS62162's input cap, reported 2.06 mm -- to R1 -- while the VIN
    cluster it belongs to was nearly 5 mm off U1's actual VIN pin. The cap was being marked
    correct by its neighbour.

    So a C or R is measured to something that is NOT a C or R: an IC, a connector, the
    crystal, the inductor, the ferrites. L and FB are exempt from this narrowing because they
    sit IN SERIES in the power path -- their neighbours genuinely are the circuit.
    """
    return not _is(ref, ("C", "R"))


def check_placement(path: Path | str = BOARD) -> PlacementCheck:
    """Nearest-same-net-pad, for passives and for the END_TO_END_MM nets. See module docstring."""
    pads = load_pads(path)
    by_net: dict[str, list[Pad]] = {}
    for p in pads:
        if not p.net or p.net == "GND" or _NC.match(p.net):
            continue
        by_net.setdefault(p.net, []).append(p)

    links: list[Link] = []
    for net, members in by_net.items():
        for p in members:
            # Scope: a passive anywhere, or any pad on a net that must be short end to end.
            if is_passive(p.ref):
                limit = CRITICAL_LIMIT_MM.get(net, GENERAL_LIMIT_MM)
                # Bulk reservoirs get the looser limit -- but never on a net that is in
                # CRITICAL_LIMIT_MM. C3 is 10 uF and would qualify by value, yet it is the
                # input cap of a 2.25 MHz buck, which makes it an HF part no matter how big
                # it is. The net knows that; the value does not.
                if net not in CRITICAL_LIMIT_MM and p.ref.startswith("C"):
                    uf = bulk_uf(p.value)
                    if uf is not None and uf >= BULK_UF:
                        limit = max(limit, BULK_LIMIT_MM)
            elif net in END_TO_END_MM:
                limit = END_TO_END_MM[net]
            else:
                continue
            # A C or R must be near something that is not a C or R (see serves()). If its net
            # has no such member at all -- a divider or filter built only from passives -- the
            # narrowing has nothing to measure against, so fall back to any other component
            # rather than skipping the pad silently.
            pool = [q for q in members if q.ref != p.ref]
            if _is(p.ref, ("C", "R")):
                strict = [q for q in pool if serves(q.ref)]
                pool = strict or pool
            best: tuple[float, Pad] | None = None
            for q in pool:
                d = math.hypot(p.x - q.x, p.y - q.y)
                if best is None or d < best[0]:
                    best = (d, q)
            if best is None:
                continue  # single-component net (e.g. MS5611's two internally-tied CSB pads)
            links.append(Link(
                ref=p.ref, number=p.number, net=net, mm=best[0],
                to_ref=best[1].ref, to_number=best[1].number, limit=limit,
                exempt_reason=EXEMPT.get((p.ref, p.number), ""),
            ))

    ordered = sorted(l.mm for l in links)
    return PlacementCheck(
        links=links,
        failures=sorted((l for l in links if l.over), key=lambda l: -l.mm),
        median_mm=ordered[len(ordered) // 2] if ordered else 0.0,
        n_pads=len(links),
    )


def self_check(path: Path | str = BOARD) -> None:
    """Assert the coordinate maths against a value recorded independently in pcb/README.md.

    A pad-rotation sign error is invisible in the aggregate -- every distance stays plausible
    and the gate keeps passing while measuring the wrong geometry. pcb/README.md pins U5 pad 1
    at (162.7500, 109.2250) as evidence the footprint redraw moved nothing, so it is the one
    number here that was written down by something other than this file.
    """
    pads = load_pads(path)
    pad1 = next(p for p in pads if p.ref == "U5" and p.number == "1")
    assert abs(pad1.x - 162.7500) < 1e-3 and abs(pad1.y - 109.2250) < 1e-3, (
        f"U5 pad 1 at ({pad1.x:.4f}, {pad1.y:.4f}), expected (162.7500, 109.2250) -- "
        "pad rotation maths or the board file moved"
    )
