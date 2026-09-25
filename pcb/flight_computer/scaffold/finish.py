#!/usr/bin/env python3
"""Finishing pass: hand-drawn critical copper, autorouting, and silkscreen.

The THIRD one-way pass, after scaffold/gen_pcb.py and scaffold/layout.py (see pcb/README.md
"How the board gets built").  Like layout.py it loads the board, adds to it and saves in
place, so it must run exactly once on layout.py's output -- run twice it lays a second copy
of every pre-routed track on top of the first.

What it does, in order:

  1. Marks In1.Cu/In2.Cu as POWER layers.  They are single full-board GND pours; left as
     "signal" (the default), Freerouting happily routes through them and the zone filler
     then cuts the plane around each track.
  2. Moves C1 (22 uF VBATT bulk) 1.2 mm right and flips it, so its VBATT pad sits ON the
     2.0 mm feed instead of forcing the feed around it -- see route_vbatt().
  3. Draws the copper a netclass cannot express, and LOCKS it (Freerouting exports locked
     copper as fixed wiring and routes around it):
       - VBATT: the J1 trunk and the J6-J9 header spine at 2.0 mm (pcb/README.md "One routing
         rule that is not a netclass").
       - GNSS_RF: U8 pin 11 straight to the u.FL at 0.36 mm = 50 ohm, with a GND via
         fence either side of it and round J5 -- via_fence().
       - U1 pins 2/3 (VIN, EN) to R1, which the autorouter boxes in -- route_u1_inputs().
  4. Exports Specctra DSN, runs Freerouting headless, imports the session, refills the
     planes.  Freerouting is NOT deterministic -- not even single-threaded (two runs on the
     same DSN gave 850 and 879 track segments, both DRC-clean).  So the session that made
     the committed board is saved beside it (routing/board.ses), and
     `--ses routing/board.ses` re-imports exactly that instead of re-routing.  Re-route
     only when placement changes, and re-verify DRC when you do.
  5. Re-places every reference designator on the silkscreen where it overlaps nothing -- no
     pad, via, other label or other part's silk -- at JLCPCB's 1.0 mm minimum text height.
     A part with no free spot has its silk reference HIDDEN rather than printed over a pad;
     the F.Fab reference (assembly drawing) is untouched, and the count is printed.

Must run under KiCad's own bundled Python (has the pcbnew module):
    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3 \\
        scaffold/finish.py flight_computer.kicad_pcb [--ses routing/board.ses]
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from layout import NM, V, mm, fill_zones, net_of

HERE = os.path.dirname(os.path.abspath(__file__))
FREEROUTING_JAR = os.path.join(HERE, "..", "tools", "freerouting-2.4.1.jar")
FREEROUTING_PASSES = 100

# ---------------------------------------------------------------------------------------
# VBATT.  docs/14: 4.1 A with all four servos stalled.  2.0 mm on 1 oz outer copper runs
# ~11 degC over ambient at 4.1 A; 1.2 mm (the ServoPower netclass) runs ~27 degC.
#
# J6-J9 pin 2 (VBATT) all sit at x = 106.04, between pin 1 (signal, x 103.5) and pin 3
# (GND, x 108.5).  A 2.0 mm SPINE straight down that column clears both neighbours by
# 0.69 mm against the 0.3 mm ServoPower clearance, so every header hangs directly off one
# 2.0 mm conductor and the whole run is 2.0 mm -- there is no narrower "branch".  The
# segment J9->J8 carries three servos, so a 1.2 mm branch there would have been wrong
# anyway.
#
# The trunk leaves J1 pad 1 -- a 2.3 mm through-hole pad for the 18 AWG XT30 pigtail, see
# design.py -- jogs 45 deg onto x = 110.375, runs up through TP1 to y = 134.43 and turns
# left onto the spine.  C1 used to sit on that corner with its GND pad in the way; it now
# sits under the corner with its VBATT pad on it.
#
# J1 used to be a JST-GH, rated 1 A per contact, which no copper could fix; it is now two
# wire pads and the XT30 (15 A) is on the pigtail.
SPINE_X = 106.04
TRUNK_Y = 134.425
J1_PIN1 = (108.6, 141.5)
TRUNK_X = 110.375
TRUNK_JOG_Y = 139.725       # 45 deg from pad 1; 0.875 mm clear of pad 2 (GND) at x 113.4
C1_AT = (SPINE_X, 135.9, 270)   # pad 1 (VBATT) at y 134.43, pad 2 (GND) at y 137.38
C1_GND_VIA = (SPINE_X, 138.6)
TRUNK_W = 2.0

# SERVO_GND -- the star-ground servo return (design.py, J1).  A 2.0 mm F.Cu column through
# J6-J9 pin 3 (x ~108.58), 2.5 mm beside the VBATT spine; from J9 pin 3 it drops to B.Cu and
# runs DIRECTLY UNDER the F.Cu trunk (1.6 mm below it) to J1 pad 2, and J1 pad 2 meets GND
# only through NT1.  Supply and return are then a tight pair all the way: the magnetometer
# sees a loop 2.5 x 21 mm on edge, not the whole ground plane.
NT1_TIE_W = 0.5
# The B.Cu return leaves the trunk's column higher than the F.Cu trunk does: J1 pad 1 (VBATT)
# is a 2.6 mm SQUARE on both layers, and its corner at (109.9, 140.2) is what the 2.0 mm
# return has to clear by 0.3 mm.  Bending at y 138.6 gives ~0.48 mm on the diagonal and
# 0.67 mm at the bend (139.3 gave 0.11 -- DRC), and is also where C1's return joins.
RET_JOG_Y = 138.6

# GNSS_RF: U8 pin 11 centre to J5 pin 1 centre, same y.  2.6 mm = 0.015 lambda.
RF_PATH = [(162.97, 129.30), (165.555, 129.30)]
RF_W = 0.36

# U1's input side, left column top to bottom: pin 1 GND (own stitch via at x 115.27),
# pin 2 VIN, pin 3 EN, pin 4 GND (own via).  Left to Freerouting, the VIN track wrapped
# round R1's EN pad on both sides and boxed it in; with EN drawn first, VIN was boxed in
# instead.  Both pins have to leave between the two GND vias, 1.0 mm apart edge to edge.
#
# So R1 turns 180 deg -- VIN pad (1) right, beside U1; EN pad (2) left -- and both links are
# drawn as parallel 0.2 mm tracks: VIN at y 138.25 then up into R1 pin 1, EN at y 138.75
# out to x 113.34 then up into R1 pin 2.  Gaps: 0.15 mm to each via's copper, 0.25 mm to its
# hole, 0.30 mm between the two tracks.  0.25 mm tracks would clear the vias by 0.125,
# 2 um short of the Default clearance.  EN carries nothing; VIN here carries the
# regulator's ~60 mA, and C3/C4 (the input caps) reach pin 2 through R1 pin 1's node.
R1_ROT = 180
NECK_W = 0.2
EN_PATH_X = 113.341
VIN_PATH_Y = 138.25
EN_PATH_Y = 138.75

# J4 (USB-C) pins A1/B12 (GND) were stitched by layout.py with a stub west to a 0.5 mm via
# at x 128.97 -- 0.95 mm from the shield slot, whose clearance ring and the autorouter's
# vias around it left that via on an island of In1/In2 that the zone filler removed:
# DRC "via connected on only one layer".  The shield slot is a plated GND hole through all
# four layers 1.4 mm away, so the pad is tied straight to it on F.Cu instead.
J4_GND_PAD = "A1"           # A1 and B12 are one pad (same position, same net)
J4_SHIELD_AT = (128.68, 137.12)

# GNSS via fence: GND vias in a band FENCE_BAND mm from the RF copper (the GNSS_RF track and
# J5's centre pin), at least FENCE_PITCH apart, each kept only if it clears every pad, track
# and via by the rules below.  lambda/20 at 1575 MHz in this dielectric is ~5 mm; this
# pitch is ~5x tighter than that needs, because the vias are free and the run is short.
FENCE_BAND = (0.70, 1.30)
FENCE_PITCH = 0.9
FENCE_REGION = (161.5, 125.8, 169.4, 132.8)      # x0, y0, x1, y1 around U8 pin 11 and J5
FENCE_VIA = (0.5, 0.3)

# Polarity marks beside the pigtail pads -- a hand-soldered pack lead is the one place on
# this board where a reversal is likely and costly.  (x, y, text)
J1_MARKS = [(106.5, 141.5, "+"), (115.5, 141.5, "-")]

# Silkscreen text: JLCPCB's published minimum is 1.0 mm high, 0.15 mm line.
SILK_H = 1.0
SILK_T = 0.15
SILK_REACH = 4.5   # mm from the part centre; further than this and a label is ambiguous
# Where the search gets it wrong.  J6-J9's nearest free spots are on the VBATT spine,
# between rows, where "J7" reads as belonging to J6; the empty strip right of each
# header's GND pin is unambiguous.
SILK_AT = {"J6": (112.2, 110.0, 0), "J7": (112.2, 117.0, 0),
           "J8": (112.2, 124.0, 0), "J9": (112.2, 131.0, 0),
           # the debug header's only free spot is past its pin 4, clear of U8's body
           "J10": (167.8, 133.8, 90)}


# Items taken off the board are parked here for the life of the process.  Letting Python
# collect the SWIG wrappers of removed PCB_TRACK/PCB_VIA objects corrupts pcbnew's type map
# (later calls return bare SwigPyObjects -- found the hard way in restitch_j4).
_REMOVED = []


def remove(board, items):
    for t in items:
        board.Remove(t)
    _REMOVED.extend(items)
    return len(items)


def track(board, net, pts, width, layer=pcbnew.F_Cu, locked=True):
    n = 0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(V(x0, y0))
        t.SetEnd(V(x1, y1))
        t.SetWidth(int(width * NM))
        t.SetLayer(layer)
        t.SetNet(net)
        t.SetLocked(locked)
        board.Add(t)
        n += 1
    return n


def via(board, net, x, y, dia=0.5, drill=0.3, locked=True):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(V(x, y))
    v.SetWidth(int(dia * NM))
    v.SetDrill(int(drill * NM))
    v.SetNet(net)
    v.SetLocked(locked)
    board.Add(v)
    return v


def set_plane_layers(board):
    for layer in (pcbnew.In1_Cu, pcbnew.In2_Cu):
        board.SetLayerType(layer, pcbnew.LT_POWER)


def move_c1(board):
    """Move C1 onto the VBATT corner, and re-stitch its GND pad.

    layout.py gave C1 a stub-and-via at its old GND pad; that copper would now sit under the
    2.0 mm trunk, so it is removed first (anything GND within 1.5 mm of the old pad).
    """
    c1 = board.FindFootprintByReference("C1")
    pad2 = next(p for p in c1.Pads() if p.GetNumber() == "2")
    old, c1_ret = pad2.GetPosition(), pad2.GetNetname()     # SERVO_GND since the star ground
    doomed = []
    for t in board.GetTracks():
        if t.GetNetname() != c1_ret:
            continue
        pts = [t.GetPosition()] if t.GetClass() == "PCB_VIA" else [t.GetStart(), t.GetEnd()]
        if any(abs(p.x - old.x) < 1.5 * NM and abs(p.y - old.y) < 1.5 * NM for p in pts):
            doomed.append(t)
    n_removed = remove(board, doomed)

    x, y, rot = C1_AT
    c1.SetOrientationDegrees(rot)
    c1.SetPosition(V(x, y))
    pads = {p.GetNumber(): p.GetPosition() for p in c1.Pads()}
    assert abs(mm(pads["1"].y) - TRUNK_Y) < 0.01, "C1 pad 1 not on the trunk: %s" % pads
    ret = net_of(board, c1_ret)
    g = pads["2"]
    track(board, ret, [(mm(g.x), mm(g.y)), C1_GND_VIA], 0.5)
    via(board, ret, *C1_GND_VIA)
    if c1_ret == "SERVO_GND":
        # no plane on this net: join C1's return to the servo return trace on B.Cu
        track(board, ret, [C1_GND_VIA, (TRUNK_X, C1_GND_VIA[1])], 0.6, layer=pcbnew.B_Cu)
    return n_removed


def restitch_j4(board):
    j4 = board.FindFootprintByReference("J4")
    pad = next(p for p in j4.Pads() if p.GetNumber() == J4_GND_PAD).GetPosition()
    doomed = []
    for t in board.GetTracks():
        if t.GetNetname() != "GND":
            continue
        pts = [t.GetPosition()] if t.GetClass() == "PCB_VIA" else [t.GetStart(), t.GetEnd()]
        if any(abs(p.x - pad.x) < 0.9 * NM and abs(p.y - pad.y) < 0.3 * NM for p in pts):
            doomed.append(t)
    n_removed = remove(board, doomed)
    # (plain floats: VECTOR2I arithmetic here corrupts the SWIG type map for later calls)
    shields = [(mm(p.GetPosition().x), mm(p.GetPosition().y))
               for p in j4.Pads() if p.GetNumber() == "SH"]
    sx, sy = min(shields, key=lambda q: (q[0] - J4_SHIELD_AT[0]) ** 2 + (q[1] - J4_SHIELD_AT[1]) ** 2)
    track(board, net_of(board, "GND"), [(mm(pad.x), mm(pad.y)), (sx, sy)], 0.3)
    return n_removed


def dedupe_tracks(board):
    """ImportSpecctraSES brings back every wire the DSN carried, and a few come back twice."""
    seen, doomed = set(), []
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            k = ("v", t.GetPosition().x, t.GetPosition().y)
        else:
            a, b = (t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y)
            k = ("t", min(a, b), max(a, b), t.GetLayer(), t.GetWidth())
        if (k, t.GetNetCode()) in seen:
            doomed.append(t)
        seen.add((k, t.GetNetCode()))
    return remove(board, doomed)


def route_vbatt(board):
    vb = net_of(board, "VBATT")
    p1 = next(p for p in board.FindFootprintByReference("J1").Pads() if p.GetNumber() == "1")
    assert (abs(mm(p1.GetPosition().x) - J1_PIN1[0]) < 0.01
            and abs(mm(p1.GetPosition().y) - J1_PIN1[1]) < 0.01), "J1 moved: %s" % p1.GetPosition()
    n = track(board, vb, [J1_PIN1, (TRUNK_X, TRUNK_JOG_Y), (TRUNK_X, TRUNK_Y),
                          (SPINE_X, TRUNK_Y)], TRUNK_W)
    heads = sorted(mm(p.GetPosition().y)
                   for r in ("J6", "J7", "J8", "J9")
                   for p in board.FindFootprintByReference(r).Pads() if p.GetNumber() == "2")
    n += track(board, vb, [(SPINE_X, TRUNK_Y)] + [(SPINE_X, y) for y in reversed(heads)],
               TRUNK_W)
    return n


def route_servo_gnd(board):
    ret = net_of(board, "SERVO_GND")

    def pad(ref, num):
        p = next(p for p in board.FindFootprintByReference(ref).Pads() if p.GetNumber() == num)
        return mm(p.GetPosition().x), mm(p.GetPosition().y)
    col = sorted((pad(j, "3") for j in ("J6", "J7", "J8", "J9")), key=lambda q: q[1])
    x3 = col[0][0]
    assert all(abs(q[0] - x3) < 0.01 for q in col), col
    j1g, nt = pad("J1", "2"), pad("NT1", "1")
    n = track(board, ret, col, TRUNK_W)
    n += track(board, ret, [col[-1], (x3, TRUNK_Y), (TRUNK_X, TRUNK_Y), (TRUNK_X, RET_JOG_Y),
                            j1g], TRUNK_W, layer=pcbnew.B_Cu)
    n += track(board, ret, [j1g, nt], NT1_TIE_W)
    return n


def route_rf(board):
    return track(board, net_of(board, "GNSS_RF"), RF_PATH, RF_W)


def route_u1_inputs(board):
    r1 = board.FindFootprintByReference("R1")
    r1.SetOrientationDegrees(R1_ROT)

    def pad(ref, num):
        p = next(p for p in board.FindFootprintByReference(ref).Pads() if p.GetNumber() == num)
        return mm(p.GetPosition().x), mm(p.GetPosition().y)
    vin, en = pad("U1", "2"), pad("U1", "3")
    r1_vin, r1_en = pad("R1", "1"), pad("R1", "2")
    assert abs(vin[1] - VIN_PATH_Y) < 0.01 and abs(en[1] - EN_PATH_Y) < 0.01, (vin, en)
    assert r1_vin[0] > r1_en[0] and abs(r1_en[0] - EN_PATH_X) < 0.01, (r1_vin, r1_en)
    n = track(board, net_of(board, "VIN"), [vin, (r1_vin[0], VIN_PATH_Y), r1_vin], NECK_W)
    n += track(board, net_of(board, "EN_3V3"), [en, (EN_PATH_X, EN_PATH_Y), r1_en], NECK_W)
    return n


def _seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy)
                                          / (dx * dx + dy * dy)))
    return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** 0.5


def _rect_dist(px, py, bb):
    x0, y0, x1, y1 = mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())
    dx = max(x0 - px, 0.0, px - x1)
    dy = max(y0 - py, 0.0, py - y1)
    return (dx * dx + dy * dy) ** 0.5


def via_fence(board):
    """Stitch GND vias around the GNSS RF path.  Must run AFTER route_rf() and BEFORE
    autoroute(), so Freerouting routes around the fence rather than the other way round."""
    gnd = net_of(board, "GND")
    rf_segs = [(a[0], a[1], b[0], b[1]) for a, b in zip(RF_PATH, RF_PATH[1:])]
    j5 = next(p for p in board.FindFootprintByReference("J5").Pads() if p.GetNumber() == "1")
    r = FENCE_VIA[0] / 2
    edge = board.GetBoardEdgesBoundingBox()
    ex0, ey0, ex1, ey1 = (mm(edge.GetLeft()), mm(edge.GetTop()),
                          mm(edge.GetRight()), mm(edge.GetBottom()))
    pads = [p for fp in board.GetFootprints() for p in fp.Pads()]
    tracks = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"]
    vias = [(mm(t.GetPosition().x), mm(t.GetPosition().y))
            for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]

    def rf_dist(x, y):
        return min([_seg_dist(x, y, *s) for s in rf_segs]
                   + [_rect_dist(x, y, j5.GetBoundingBox())])

    cands = []
    x0, y0, x1, y1 = FENCE_REGION
    x = x0
    while x <= x1:
        y = y0
        while y <= y1:
            d = rf_dist(x, y)
            if FENCE_BAND[0] <= d <= FENCE_BAND[1]:
                cands.append((d, round(x, 3), round(y, 3)))
            y += 0.1
        x += 0.1
    cands.sort()
    placed = []
    for _, x, y in cands:
        if x - r < ex0 + 0.5 or x + r > ex1 - 0.5 or y - r < ey0 + 0.5 or y + r > ey1 - 0.5:
            continue
        # 0.2 mm copper to any pad (no via-in-pad, GND or not), 0.2 mm to other-net tracks,
        # holes >= 0.25 mm apart edge to edge.
        if any(_rect_dist(x, y, p.GetBoundingBox()) < r + 0.2 for p in pads):
            continue
        if any(t.GetNetname() != "GND" and
               _seg_dist(x, y, mm(t.GetStart().x), mm(t.GetStart().y),
                         mm(t.GetEnd().x), mm(t.GetEnd().y)) < r + t.GetWidth() / NM / 2 + 0.2
               for t in tracks):
            continue
        if any(((x - vx) ** 2 + (y - vy) ** 2) ** 0.5 < max(FENCE_PITCH, 0.3 + 0.25)
               for vx, vy in vias + placed):
            continue
        via(board, gnd, x, y, *FENCE_VIA)
        placed.append((x, y))
    return placed


def autoroute(board, pcb_path, ses=None):
    outdir = os.path.join(os.path.dirname(os.path.abspath(pcb_path)), "routing")
    os.makedirs(outdir, exist_ok=True)
    if ses is None:
        if not os.path.exists(FREEROUTING_JAR):
            raise SystemExit("no Freerouting at %s -- download freerouting-2.4.1.jar from "
                             "github.com/freerouting/freerouting/releases" % FREEROUTING_JAR)
        dsn = os.path.join(outdir, "board.dsn")
        ses = os.path.join(outdir, "board.ses")
        if not pcbnew.ExportSpecctraDSN(board, dsn):
            raise SystemExit("DSN export failed")
        cmd = ["java", "-jar", FREEROUTING_JAR, "-de", dsn, "-do", ses,
               "-mp", str(FREEROUTING_PASSES), "-mt", "1", "--gui.enabled=false"]
        print("freerouting:", " ".join(cmd))
        log = subprocess.run(cmd, capture_output=True, text=True)
        with open(os.path.join(outdir, "freerouting.log"), "w") as f:
            f.write(log.stdout + log.stderr)
        if log.returncode != 0 or not os.path.exists(ses):
            raise SystemExit("freerouting failed:\n" + (log.stdout + log.stderr)[-2000:])
        tail = [l for l in (log.stdout + log.stderr).splitlines()
                if "unrouted" in l or "->" in l or "Net '" in l]
        for l in tail[-20:]:
            print("   ", l.strip()[:160])
    if not pcbnew.ImportSpecctraSES(board, ses):
        raise SystemExit("SES import failed: %s" % ses)
    print("imported", ses)


# --------------------------------------------------------------------------- silkscreen
def _box(bb, grow=0.0):
    g = grow * NM
    return (bb.GetLeft() - g, bb.GetTop() - g, bb.GetRight() + g, bb.GetBottom() + g)


def _hit(a, boxes):
    return any(a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1] for b in boxes)


def silk_text(board, x, y, text, h=1.5):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text)
    t.SetLayer(pcbnew.F_SilkS)
    t.SetPosition(V(x, y))
    t.SetTextSize(pcbnew.VECTOR2I(int(h * NM), int(h * NM)))
    t.SetTextThickness(int(0.25 * NM))
    board.Add(t)
    return t


def place_silk_refs(board):
    for x, y, text in J1_MARKS:
        silk_text(board, x, y, text)
    edge = board.GetBoardEdgesBoundingBox()
    inner = _box(edge, -0.4)
    fixed = []          # exposed copper and every footprint's silk graphics
    for fp in board.GetFootprints():
        for p in fp.Pads():
            fixed.append(_box(p.GetBoundingBox(), 0.1))
        for g in fp.GraphicalItems():
            if g.GetLayer() == pcbnew.F_SilkS and g.GetClass() != "PCB_TEXT":
                fixed.append(_box(g.GetBoundingBox(), 0.05))
        if fp.GetReference().startswith("MH"):
            fixed.append(_box(fp.GetBoundingBox(), 0.1))
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            fixed.append(_box(t.GetBoundingBox(), 0.1))
    for d in board.GetDrawings():
        if d.GetLayer() == pcbnew.F_SilkS and d.GetClass() == "PCB_TEXT":
            fixed.append(_box(d.GetBoundingBox(), 0.1))

    # Other parts' bodies: silk under a part vanishes once it is assembled (the first pass
    # put "J10" under U8's module).  A part's own body only costs a penalty, below.
    bodies = {}
    for fp in board.GetFootprints():
        cy = fp.GetCourtyard(pcbnew.F_CrtYd)
        if cy.OutlineCount() and not fp.GetReference().startswith(("MH", "TP")):
            bodies[fp.GetReference()] = _box(cy.BBox(), -0.1)

    placed, hidden = [], []
    fps = sorted(board.GetFootprints(), key=lambda f: -f.GetPadCount())
    for fp in fps:
        ref = fp.Reference()
        if fp.GetReference().startswith("MH"):
            ref.SetVisible(False)          # four holes need no label
            continue
        ref.SetLayer(pcbnew.F_SilkS)
        ref.SetTextSize(pcbnew.VECTOR2I(int(SILK_H * NM), int(SILK_H * NM)))
        ref.SetTextThickness(int(SILK_T * NM))
        ref.SetKeepUpright(True)
        cy = fp.GetCourtyard(pcbnew.F_CrtYd)
        bb = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False)
        l, t, r, b = mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())
        cx, cyy = (l + r) / 2, (t + b) / 2
        # Nearest free spot to the part's centre, searched outward on a 0.25 mm grid out to
        # SILK_REACH.  Horizontal text is preferred; vertical costs 0.5 mm of "distance".
        cands = []
        # A label under the part's own body is a last resort (it is hidden once assembled).
        steps = int(SILK_REACH / 0.25)
        for i in range(-steps, steps + 1):
            for j in range(-steps, steps + 1):
                dx, dy = i * 0.25, j * 0.25
                d = (dx * dx + dy * dy) ** 0.5
                if d <= SILK_REACH:
                    # under the part's own body the label vanishes once it is assembled
                    if l < cx + dx < r and t < cyy + dy < b:
                        d += 3.0
                    cands.append((d, cx + dx, cyy + dy, 0))
                    cands.append((d + 0.5, cx + dx, cyy + dy, 90))
        cands.sort()
        cands = [(x, y, rot) for _, x, y, rot in cands]
        if fp.GetReference() in SILK_AT:
            cands.insert(0, SILK_AT[fp.GetReference()])
        others = [bx for r_, bx in bodies.items() if r_ != fp.GetReference()]
        for x, y, rot in cands:
            ref.SetTextAngleDegrees(rot)
            ref.SetPosition(V(x, y))
            box = _box(ref.GetBoundingBox(), 0.05)
            if box[0] < inner[0] or box[1] < inner[1] or box[2] > inner[2] or box[3] > inner[3]:
                continue
            if _hit(box, fixed) or _hit(box, placed) or _hit(box, others):
                continue
            ref.SetVisible(True)
            placed.append(box)
            break
        else:
            ref.SetVisible(False)
            hidden.append(fp.GetReference())
    return len(placed), hidden


def main(argv):
    pcb_path = argv[1]
    ses = argv[argv.index("--ses") + 1] if "--ses" in argv else None
    board = pcbnew.LoadBoard(pcb_path)

    set_plane_layers(board)
    print("C1 moved; old GND stub items removed:", move_c1(board))
    print("J4 GND restitched to shield; items removed:", restitch_j4(board))
    print("VBATT segments:", route_vbatt(board))
    print("SERVO_GND (star return) segments:", route_servo_gnd(board))
    print("GNSS_RF segments:", route_rf(board))
    print("GNSS via fence:", len(via_fence(board)), "vias")
    print("U1 VIN/EN segments:", route_u1_inputs(board))
    autoroute(board, pcb_path, ses)
    print("duplicate tracks/vias removed after import:", dedupe_tracks(board))
    fill_zones(board)
    n, hidden = place_silk_refs(board)
    print("silk references placed: %d, hidden (no free spot): %d %s" % (n, len(hidden), hidden))

    pcbnew.SaveBoard(pcb_path, board)
    print("saved", pcb_path)


if __name__ == "__main__":
    main(sys.argv)
