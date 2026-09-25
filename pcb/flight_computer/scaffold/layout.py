#!/usr/bin/env python3
"""Hand layout pass: passive placement, plane pours, and routing.

Runs AFTER scaffold/gen_pcb.py, on the already-generated flight_computer.kicad_pcb --
it loads the board with pcbnew (KiCad's own engine, not the s-expression writer used
by gen_pcb.py), places the passives that gen_pcb.py parks off-board, pours the ground
planes, routes every net, and saves back in place.  This is NOT part of the
netlist-driven regen pipeline: re-running gen_pcb.py wipes this and this must be run
again afterward, in that order.  See pcb/README.md.

Must run under KiCad's own bundled Python (has the pcbnew module):
    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3
"""
import math
import os
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design
import pcbnew

NM = 1_000_000.0  # nm per mm


def mm(v):
    return v / NM


def V(x, y):
    return pcbnew.VECTOR2I(int(round(x * NM)), int(round(y * NM)))


X0, Y0, W, H = 100.0, 100.0, 70.0, 45.0

# SIGNAL ROUTING NOW LIVES IN scaffold/finish.py (hand-drawn critical copper + Freerouting),
# the third pass.  What follows is the history of why it is not done here.
#
# The greedy 2-bend MST router below gets connectivity (very few unconnected pads)
# but not clean geometry on this board: ~1/3 of the longer MCU-to-peripheral nets
# have no collision-free 2-segment path across a board this populated, and fall
# back to a colliding one. That is not a "route it, then clean up a few DRC hits"
# state -- it is hundreds of real crossing/shorting violations. Left in (as
# route_signal_nets) for anyone who wants to pick the router back up, but this
# script does NOT run it by default; see pcb/README.md "What is not done".
SKIP_SIGNAL_ROUTING = True

MAJOR_REFS = {"J1", "NT1", "J6", "J7", "J8", "J9", "U1", "L1", "J10", "U2", "U4", "U9", "Y1",
              "U7", "U3", "J4", "J3", "U6", "U8", "J5", "U5", "SW1", "TP3",
              "MH1", "MH2", "MH3", "MH4"}
# SW1 is pinned like a connector rather than auto-placed: where a reset button sits is an
# ergonomic decision (it is pressed by a finger, on a board in a jig), not a parasitic one,
# and the solver has no term for that.  It is grouped with J3/J10 in gen_pcb.PLACE.

# Ambiguous rail/bulk decoupling that a shared +3V3/VBATT/GND net can't disambiguate
# on its own (many members, all electrically identical) -- paired by design intent
# (one bulk/HF cap per specific IC power pin) instead.  Format: ref -> (anchor_ref,
# anchor_pin_on_that_ref).
OVERRIDE_ANCHOR = {
    "C1": ("J1", "1"),                                   # VBATT input bulk, at the pack
    # C2 (100 uF) anchors at FB1, not at J1: FB1 is the star point where docs/14's "separate
    # feed and filter off a star point at the pack" actually lives, and the bulk cap belongs
    # on that node.  Anchored at J1 it measured 11.21 mm from FB1 and 21 mm from J1 itself --
    # near neither, because MANUAL_FIXUP had to evict it from a corner J10 was filling.
    "C2": ("FB1", "1"),
    # The TPS62162 switches at 2.25 MHz and VIN is its input-cap hot loop -- the largest di/dt
    # on a board that also carries an 18.0 mgauss magnetometer budget.  C3 measured 3.75 mm
    # (VIN) + 3.81 mm (PGND), a ~7.5 mm loop.  C4 (100 nF VIN bypass) and R1 (100 k on EN)
    # were 13.6 and 14.3 mm away, doing nothing at all where they sat.
    "C3": ("U1", "2"), "C4": ("U1", "2"), "R1": ("U1", "3"),
    # Crystal load caps belong at the CRYSTAL.  Without these two they resolve through the
    # generic path below, which prefers any "U*" reference over a non-"U*" one and therefore
    # anchored them to U2 -- the single largest placement defect on the first board.
    "C7": ("Y1", "1"), "C8": ("Y1", "3"),
    "C5": ("L1", "2"), "C6": ("U1", "6"),                # +3V3 output, at the regulator
    "C14": ("U2", "19"),                                 # MCU +3V3 bulk (5 pins already
                                                          # covered individually by C9-C13)
    "C20": ("U4", "5"), "C21": ("U4", "8"), "C22": ("U4", "5"),   # IMU +3V3 (pins 5 & 8)
    "C24": ("U5", "2"), "C25": ("U5", "13"),             # mag +3V3 (pins 2 & 13)
    # IMU LDO: without these C30 (VIN) would resolve to U1 -- VIN's other IC -- 30 mm away.
    "C30": ("U9", "1"), "C31": ("U9", "4"), "C32": ("U9", "5"), "R33": ("U9", "1"),
    "C26": ("U6", "1"),                                  # baro +3V3
    "C27": ("U7", "8"),                                  # flash +3V3
    "C28": ("U8", "6"), "C29": ("U8", "7"),               # GNSS +3V3
    "R3": ("U1", "6"),                                   # power-good LED pair, at the reg
                                                          # (D2 auto-anchors to R3 via
                                                          # LED_PWR, which is now resolved)
    "TP1": ("J1", "1"), "TP2": ("L1", "2"),
    # No TP3 entry: it is pinned in gen_pcb.PLACE and listed in MAJOR_REFS.  An override here
    # would still be honoured by resolve_anchors (which iterates this dict without checking
    # MAJOR_REFS) and place_passives would move it straight back off its pinned spot.
}
# One cap per MCU +3V3 pin (pins 1, 19, 32, 48, 64) -- decoupling, not bulk.
OVERRIDE_ANCHOR.update({"C9": ("U2", "1"), "C10": ("U2", "19"), "C11": ("U2", "32"),
                         "C12": ("U2", "48"), "C13": ("U2", "64")})

# Mirrors flight_computer.kicad_pro net_settings.netclass_patterns -- Power covers
# +3V3/GND/VIN, ServoPower covers VBATT, USB covers USB_D*, everything else Default.
NETCLASS_PATTERNS = [("Power", {"+3V3", "GND", "VIN"}), ("ServoPower", {"VBATT", "SERVO_GND"}),
                     ("RF", {"GNSS_RF"})]
# RF = 0.36 mm because that is 50 ohm on THIS stackup, and 50 ohm is what the part wants:
# MAX-M10S RF_IN has Zin = 50 ohm with a built-in DC block (u-blox UBX-20035208 R08,
# Table 13).  Hammerstad microstrip over In1 with h = 0.2104 mm prepreg, er = 4.5,
# t = 35 um copper gives 59.9 ohm at the Default 0.25 mm and 50.0 ohm at 0.360 mm -- so
# GNSS_RF sitting in Default was a ~20% impedance error on the one net that has an
# impedance.  scripts/pcb_placement_report.py prints the solve.
TRACK_WIDTH = {"Default": 0.25, "Power": 0.3, "ServoPower": 1.2, "USB": 0.25, "RF": 0.36}
VIA_SIZE = {"Default": (0.6, 0.3), "Power": (0.6, 0.3), "ServoPower": (1.0, 0.5),
            "USB": (0.6, 0.3), "RF": (0.6, 0.3)}


def netclass_of(net):
    if net.startswith("USB_D"):
        return "USB"
    for cls, names in NETCLASS_PATTERNS:
        if net in names:
            return cls
    return "Default"


def net_members():
    out = {}
    for _, _, comps in design.SHEETS:
        for ref, lib_id, value, fp, pinmap in comps:
            for pin, net in pinmap.items():
                if net != design.NC:
                    out.setdefault(net, []).append((ref, pin))
    return out


def comp_info():
    out = {}
    for _, _, comps in design.SHEETS:
        for ref, lib_id, value, fp, pinmap in comps:
            out[ref] = (lib_id, value, fp, pinmap)
    return out


def fp_bbox(fp, margin=0.22):
    """True F.CrtYd courtyard extent (what KiCad's own courtyard-overlap DRC check
    uses), not a pad-based guess -- a JST connector or a switch's real body is much
    bigger than its pads and a pad-only estimate under-counts it badly."""
    cb = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
    x0, y0 = mm(cb.GetLeft()), mm(cb.GetTop())
    x1, y1 = mm(cb.GetRight()), mm(cb.GetBottom())
    if x1 - x0 < 0.01 or y1 - y0 < 0.01:
        p = fp.GetPosition()
        x0 = y0 = -1.0
        x1 = y1 = 1.0
        x0, x1 = mm(p.x) + x0, mm(p.x) + x1
        y0, y1 = mm(p.y) + y0, mm(p.y) + y1
    return (x0 - margin, y0 - margin, x1 + margin, y1 + margin)


def resolve_anchors(fpmap, ci, nm):
    """ref -> (anchor_ref, anchor_pin, own_pin) for every non-major passive."""
    all_refs = set(ci) - MAJOR_REFS - {"MH1", "MH2", "MH3", "MH4"}
    resolved = set(MAJOR_REFS)
    out = {}
    remaining = set(all_refs)
    # seed centre-ish position estimate for "nearest" tie-breaks before anything
    # of ours is placed: use the part's own park position already in the board.
    est = {r: (mm(fpmap[r].GetPosition().x), mm(fpmap[r].GetPosition().y))
           for r in all_refs}

    def anchor_pad_pos(ref, pin):
        fp = fpmap[ref]
        for pad in fp.Pads():
            if pad.GetNumber() == pin:
                p = pad.GetPosition()
                return (mm(p.x), mm(p.y))
        raise KeyError((ref, pin))

    for ref, (aref, apin) in OVERRIDE_ANCHOR.items():
        _, _, _, pinmap = ci[ref]
        anet = ci[aref][3][apin]
        own_pin = next(p for p, n in pinmap.items() if n == anet)
        out[ref] = (aref, apin, own_pin)
        resolved.add(ref)
        remaining.discard(ref)
        est[ref] = anchor_pad_pos(aref, apin)

    progress = True
    while remaining and progress:
        progress = False
        for ref in sorted(remaining):
            _, _, _, pinmap = ci[ref]
            nets = [(n, p) for p, n in pinmap.items() if n != design.NC]
            nets.sort(key=lambda np_: len(nm.get(np_[0], [])))
            for net, own_pin in nets:
                others = [(r, p) for r, p in nm.get(net, []) if r != ref]
                resolved_others = [(r, p) for r, p in others if r in resolved]
                if resolved_others:
                    rx, ry = est[ref]

                    def d(rp):
                        ax, ay = anchor_pad_pos(*rp)
                        return (ax - rx) ** 2 + (ay - ry) ** 2
                    # Prefer an IC/major over a connector when both sit on the same
                    # net (e.g. a NRST filter cap belongs at the MCU pin, not out at
                    # the SWD header) -- only falls back to raw nearest within a tier.
                    ic_others = [rp for rp in resolved_others if rp[0].startswith("U")]
                    pool = ic_others or resolved_others
                    aref, apin = min(pool, key=d)
                    out[ref] = (aref, apin, own_pin)
                    resolved.add(ref)
                    remaining.discard(ref)
                    est[ref] = anchor_pad_pos(aref, apin)
                    progress = True
                    break
    if remaining:
        raise SystemExit("could not anchor: %s" % remaining)
    return out


def best_rotation(fp, own_pin, want_dx, want_dy):
    """Rotation in {0,90,180,270} that points own_pin's pad most toward (want_dx,want_dy)
    from the footprint's own centre, tested in-place with pcbnew's own pad math."""
    origin = fp.GetPosition()
    fp.SetPosition(V(0, 0))
    best, best_score = 0, -1e9
    for r in (0, 90, 180, 270):
        fp.SetOrientationDegrees(r)
        for pad in fp.Pads():
            if pad.GetNumber() == own_pin:
                p = pad.GetPosition()
                px, py = mm(p.x), mm(p.y)
                n = math.hypot(px, py) or 1.0
                score = (px / n) * want_dx + (py / n) * want_dy
                if score > best_score:
                    best_score, best = score, r
    fp.SetOrientationDegrees(0)
    fp.SetPosition(origin)
    return best


def place_passives(board, fpmap, ci, nm, anchors):
    # Several passives legitimately share one anchor pin (e.g. C1/C2/TP1 all sit at
    # J1 pin 1). Seeding them at the exact same point forces relax() to blindly
    # untangle a stack, which can fling one of them across the board. Spread the
    # group around the anchor instead, in a small fan, before relax ever runs.
    groups = {}
    for ref, (aref, apin, own_pin) in anchors.items():
        groups.setdefault((aref, apin), []).append(ref)

    for (aref, apin), refs in groups.items():
        afp = fpmap[aref]
        for pad in afp.Pads():
            if pad.GetNumber() == apin:
                ap = pad.GetPosition()
                break
        ac = afp.GetPosition()
        dx, dy = mm(ap.x) - mm(ac.x), mm(ap.y) - mm(ac.y)
        n = math.hypot(dx, dy)
        if n < 1e-6:
            dx, dy = 1.0, 0.0
            n = 1.0
        dx, dy = dx / n, dy / n
        base_angle = math.atan2(dy, dx)
        refs.sort()
        spread = math.radians(35)
        for i, ref in enumerate(refs):
            k = i - (len(refs) - 1) / 2.0
            a = base_angle + k * spread
            fdx, fdy = math.cos(a), math.sin(a)
            _, _, own_pin = anchors[ref]
            fp = fpmap[ref]
            rot = best_rotation(fp, own_pin, -fdx, -fdy)
            offset = 2.3 + 0.6 * abs(k)
            fp.SetOrientationDegrees(rot)
            # Deterministic sub-mm jitter so two DIFFERENT groups whose anchor pins
            # happen to sit close together (e.g. a crystal pin and an MCU pin both
            # in the centre zone) don't seed exactly on top of each other -- that
            # gives relax()'s pairwise push a zero gradient to work with and it can
            # stall in a coincident tie instead of separating.
            jx = ((zlib.crc32(ref.encode()) % 1000) / 1000.0 - 0.5) * 0.5
            jy = ((zlib.crc32((ref + "y").encode()) % 1000) / 1000.0 - 0.5) * 0.5
            fp.SetPosition(V(mm(ap.x) + fdx * offset + jx, mm(ap.y) + fdy * offset + jy))


def relax(board, fpmap, pinned, iters=6000, anchor_xy=None, pull=0.25):
    """Push overlapping footprints apart, and pull everything else back toward its anchor pad.

    THE PULL IS NOT COSMETIC.  Without it this is a pure separation solver: it has a repulsive
    term and nothing else, so a passive seeded into a crowded pocket is shoved out and then
    has no reason to ever come back.  On the first board C2 (a 1210 bulk cap) ended 61 mm from
    the star point it decouples -- the far corner of a 70 mm board -- and C8 ended on the wrong
    side of the MCU from its own crystal.  Anchoring a part correctly is worthless if the
    solver is then free to fling it.

    Only parts that are currently CLEAR get pulled.  A part that is overlapping is being shoved
    this iteration, and pulling it at the same time just makes the two terms fight.  The gain
    anneals to zero over the run so the two cannot oscillate forever -- a part pulled into a
    collision, shoved out, and pulled back in would otherwise never settle.
    """
    refs = list(fpmap)
    pos = {r: [mm(fpmap[r].GetPosition().x), mm(fpmap[r].GetPosition().y)] for r in refs}
    anchor_xy = anchor_xy or {}
    for it in range(iters):
        moved = False
        boxes = {r: fp_bbox_at(fpmap[r], pos[r]) for r in refs}
        busy = set()
        for i, a in enumerate(refs):
            for b in refs[i + 1:]:
                ax0, ay0, ax1, ay1 = boxes[a]
                bx0, by0, bx1, by1 = boxes[b]
                ox = min(ax1, bx1) - max(ax0, bx0)
                oy = min(ay1, by1) - max(ay0, by0)
                if ox <= 0.02 or oy <= 0.02:
                    continue
                moved = True
                busy.add(a)
                busy.add(b)
                if ox < oy:
                    d = (ox + 0.3) / 2
                    s = -1 if (ax0 + ax1) < (bx0 + bx1) else 1
                    shove(pos, pinned, a, b, s * d, 0)
                else:
                    d = (oy + 0.3) / 2
                    s = -1 if (ay0 + ay1) < (by0 + by1) else 1
                    shove(pos, pinned, a, b, 0, s * d)
        gain = pull * max(0.0, 1.0 - it / float(iters))
        if gain > 1e-4:
            for r in refs:
                if r in pinned or r in busy or r not in anchor_xy:
                    continue
                ax, ay = anchor_xy[r]
                dx, dy = ax - pos[r][0], ay - pos[r][1]
                dist = math.hypot(dx, dy)
                if dist < 0.05:
                    continue
                step = min(gain * dist, 0.3)
                pos[r][0] += dx / dist * step
                pos[r][1] += dy / dist * step
                moved = True
        for r in refs:
            if r in pinned:
                continue
            x0, y0, x1, y1 = fp_bbox_at(fpmap[r], pos[r])
            if x0 < X0 + 0.6:
                pos[r][0] += (X0 + 0.6 - x0)
            elif x1 > X0 + W - 0.6:
                pos[r][0] -= (x1 - (X0 + W - 0.6))
            if y0 < Y0 + 0.6:
                pos[r][1] += (Y0 + 0.6 - y0)
            elif y1 > Y0 + H - 0.6:
                pos[r][1] -= (y1 - (Y0 + H - 0.6))
        if not moved:
            break
    for r in refs:
        if r not in pinned:
            fpmap[r].SetPosition(V(round(pos[r][0], 3), round(pos[r][1], 3)))


def bring_home(fpmap, pinned, anchor_xy, limit=4.0, reach=14.0):
    """Last-resort repair: put any stranded passive in the nearest free pocket to its anchor.

    relax()'s pull only acts on parts that are CURRENTLY CLEAR, which is the right rule -- a
    part being shoved and pulled in the same iteration just makes the two terms fight -- but
    it means the worst cases are exactly the ones it cannot help.  A big part in a saturated
    corner (C2 is a 1210 among four servo headers, the pack connector and the regulator) is
    overlapping on almost every iteration, so it is shoved outward, never becomes eligible to
    be pulled back, and ends up wherever the shoving ran out.  C2 measured 58 mm from the star
    point it decouples with the pull alone.

    So: for anything still further than `limit` from its anchor, spiral outward FROM THE
    ANCHOR and take the first spot that clears everything.

    This does not fight relax() -- it runs after it, and only touches parts relax() failed.
    """
    def off_by(ref):
        ax, ay = anchor_xy[ref]
        return math.hypot(mm(fpmap[ref].GetPosition().x) - ax,
                          mm(fpmap[ref].GetPosition().y) - ay)

    live = {r: fp_bbox_at(fpmap[r], [mm(fpmap[r].GetPosition().x), mm(fpmap[r].GetPosition().y)])
            for r in fpmap}
    moved = {}
    candidates = [r for r in anchor_xy if r not in pinned]
    # WORST FIRST, and twice.  Ordering by footprint area was the obvious choice and it is
    # the wrong one: it hands the good pockets to whichever part is physically biggest rather
    # than to whichever part needs them most, so the 0402s -- which is what the enable pull-up
    # and the input bypass are -- pick last, from what is left.  Two passes because the first
    # one frees pockets that later parts could not have used while they were still occupied.
    for _pass in (0, 1):
        for ref in sorted(candidates, key=off_by, reverse=True):
            _relocate(fpmap, ref, anchor_xy[ref], live, moved, limit, reach)
    return [(r, w, n) for r, (w, n) in moved.items()]


def _relocate(fpmap, ref, anchor, live, moved, limit, reach):
    """Spiral out from `anchor` for the nearest free pocket; move `ref` there if it improves."""
    ax, ay = anchor
    px, py = mm(fpmap[ref].GetPosition().x), mm(fpmap[ref].GetPosition().y)
    was = math.hypot(px - ax, py - ay)
    if was <= limit:
        return
    best = None
    radius = 0.6
    while radius <= reach and best is None:
        # Step the ring finely enough that a 0402 cannot slip between samples.
        steps = max(12, int(2 * math.pi * radius / 0.35))
        for k in range(steps):
            th = 2 * math.pi * k / steps
            cx, cy = ax + radius * math.cos(th), ay + radius * math.sin(th)
            box = fp_bbox_at(fpmap[ref], [cx, cy])
            if (box[0] < X0 + 0.6 or box[1] < Y0 + 0.6
                    or box[2] > X0 + W - 0.6 or box[3] > Y0 + H - 0.6):
                continue
            if any(other != ref and box[0] < ob[2] and ob[0] < box[2]
                   and box[1] < ob[3] and ob[1] < box[3]
                   for other, ob in live.items()):
                continue
            best = (cx, cy)
            break
        radius += 0.25
    if best and math.hypot(best[0] - ax, best[1] - ay) < was:
        fpmap[ref].SetPosition(V(round(best[0], 3), round(best[1], 3)))
        live[ref] = fp_bbox_at(fpmap[ref], [best[0], best[1]])
        now = round(math.hypot(best[0] - ax, best[1] - ay), 2)
        # Keep the ORIGINAL distance across both passes, so the printed line reports the
        # whole journey rather than just the second hop.
        first = moved.get(ref, (round(was, 2), now))[0]
        moved[ref] = (first, now)


def fp_bbox_at(fp, pos):
    x0, y0, x1, y1 = fp_bbox(fp)
    cx, cy = mm(fp.GetPosition().x), mm(fp.GetPosition().y)
    dx, dy = pos[0] - cx, pos[1] - cy
    return x0 + dx, y0 + dy, x1 + dx, y1 + dy


def clamp_to_board(fpmap, pinned):
    for ref, fp in fpmap.items():
        if ref in pinned:
            continue
        x0, y0, x1, y1 = fp_bbox(fp)
        dx = dy = 0.0
        if x0 < X0 + 0.6:
            dx = X0 + 0.6 - x0
        elif x1 > X0 + W - 0.6:
            dx = -(x1 - (X0 + W - 0.6))
        if y0 < Y0 + 0.6:
            dy = Y0 + 0.6 - y0
        elif y1 > Y0 + H - 0.6:
            dy = -(y1 - (Y0 + H - 0.6))
        if dx or dy:
            p = fp.GetPosition()
            fp.SetPosition(V(mm(p.x) + dx, mm(p.y) + dy))


def final_squeeze(fpmap, pinned, rounds=60):
    """Sequential, one-pair-at-a-time separation for whatever relax()'s simultaneous
    batch update couldn't fully untangle -- a handful of genuinely tight local
    clusters (e.g. everything crowding one MCU pin) can stall a batch update in a
    near-tie; resolving one true (zero-margin) overlap at a time, fully, converges
    where the batch version plateaus."""
    refs = list(fpmap)
    for _ in range(rounds):
        fixed_any = False
        for i, a in enumerate(refs):
            for b in refs[i + 1:]:
                if a in pinned and b in pinned:
                    continue
                ax0, ay0, ax1, ay1 = fp_bbox(fpmap[a], margin=0.12)
                bx0, by0, bx1, by1 = fp_bbox(fpmap[b], margin=0.12)
                ox = min(ax1, bx1) - max(ax0, bx0)
                oy = min(ay1, by1) - max(ay0, by0)
                if ox <= 0 or oy <= 0:
                    continue
                fixed_any = True
                if ox < oy:
                    d = ox + 0.05
                    s = -1 if (ax0 + ax1) < (bx0 + bx1) else 1
                    move2(fpmap, pinned, a, b, s * d, 0)
                else:
                    d = oy + 0.05
                    s = -1 if (ay0 + ay1) < (by0 + by1) else 1
                    move2(fpmap, pinned, a, b, 0, s * d)
                clamp_to_board(fpmap, pinned)
        if not fixed_any:
            break
    return not fixed_any


def move2(fpmap, pinned, a, b, dx, dy):
    pa, pb = a not in pinned, b not in pinned
    ap, bp = fpmap[a].GetPosition(), fpmap[b].GetPosition()
    if pa and pb:
        fpmap[a].SetPosition(V(mm(ap.x) + dx, mm(ap.y) + dy))
        fpmap[b].SetPosition(V(mm(bp.x) - dx, mm(bp.y) - dy))
    elif pa:
        fpmap[a].SetPosition(V(mm(ap.x) + 2 * dx, mm(ap.y) + 2 * dy))
    elif pb:
        fpmap[b].SetPosition(V(mm(bp.x) - 2 * dx, mm(bp.y) - 2 * dy))


def shove(pos, pinned, a, b, dx, dy):
    pa, pb = a not in pinned, b not in pinned
    if pa and pb:
        pos[a][0] += dx; pos[a][1] += dy
        pos[b][0] -= dx; pos[b][1] -= dy
    elif pa:
        pos[a][0] += 2 * dx; pos[a][1] += 2 * dy
    elif pb:
        pos[b][0] -= 2 * dx; pos[b][1] -= 2 * dy


def net_of(board, name):
    return board.GetNetInfo().GetNetItem(name)


def pour_gnd(board):
    """In1.Cu and In2.Cu: one solid GND pour each, the whole board.

    In2 USED TO BE SPLIT IN TWO at x=120.5, with a 1.5 mm copper gap, on the stated grounds
    that "servo return current has no direct path under the sensors -- it has to go back
    through In1 and the star point at the pack".  That did not work and could not have:
    BOTH HALVES ARE NET GND AND In1 IS A SOLID FULL-BOARD POUR, so every stitching via ties
    them together.  The two halves were one node the whole time.

    What the gap did do was real, and harmful.  The stackup is F.Cu / 0.2104 prepreg / In1 /
    1.065 core / In2 / 0.2104 prepreg / B.Cu, so a B.Cu trace references In2 at 0.21 mm while
    In1 is 1.28 mm away.  Any B.Cu trace crossing x=120.5 lost its return path -- and
    SERVO1-4, +3V3 and VIN all have to cross it, because the MCU is at x=137 and the servo
    headers and the regulator are at x=103.5-117.

    Servo-return isolation comes from ROUTING, not from a slot: keep the VBATT trunk tight
    over In1 so its return image stays directly underneath it.  At 0.21 mm of prepreg that
    image is a ~0.1 mgauss dipole at the magnetometer, against the 18.0 mgauss budget in
    estimation.required_magnetic_cleanliness() -- four orders of margin, which is why the
    real magnetic risk in that budget is the untwisted servo LEADS off-board and never the
    on-board copper.

    If a genuine split is ever wanted it has to slot In1 as well and enforce a single star
    point, and it would put a plane slot under a board carrying both an IMU and a
    magnetometer.  That is a decision, not a default.
    """
    gnd = net_of(board, "GND")
    filler_zones = []

    def rect_zone(layer, x0, y0, x1, y1):
        z = pcbnew.ZONE(board)
        ol = z.Outline()
        ol.NewOutline()
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            ol.Append(int(x * NM), int(y * NM))
        z.SetLayer(layer)
        z.SetNetCode(gnd.GetNetCode())
        z.SetMinThickness(int(0.15 * NM))
        z.SetZoneName("GND_%s_%d" % (board.GetLayerName(layer), len(filler_zones)))
        board.Add(z)
        filler_zones.append(z)
        return z

    rect_zone(pcbnew.In1_Cu, X0 + 0.4, Y0 + 0.4, X0 + W - 0.4, Y0 + H - 0.4)
    rect_zone(pcbnew.In2_Cu, X0 + 0.4, Y0 + 0.4, X0 + W - 0.4, Y0 + H - 0.4)

    return gnd.GetNetCode()


def fill_zones(board):
    """Fill LAST, after every via and track exists -- filling earlier means the
    filler carves clearance around whatever copper existed at that moment, and
    anything routed afterward can end up sitting right against stale zone copper."""
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(list(board.Zones()))


def stitch_gnd_vias(board, fpmap, nm):
    """Every GND pad gets its own short stub + via down into the In1 pour (which,
    being solid everywhere, is always reachable regardless of which side of the
    In2 split the pad is on)."""
    gnd_net = net_of(board, "GND")
    # Default (narrow) sizing on purpose, not Power-netclass: this is a single-pin
    # escape stub into the plane, and several GND pins sit on 0.5 mm pitch parts
    # (LQFP-64, the LGA sensors) where a 0.6 mm/0.8 mm Power-class stub-and-via
    # would land on the neighbouring pad. The plane, not this stub, carries current.
    # Smaller than the Default netclass via: a few GND escapes on the LQFP-64 have
    # under 0.7 mm total clearance to the next pin regardless of which of the 4
    # directions is picked, so the standard 0.6/0.3 via leaves under the required
    # 0.25 mm hole-to-hole gap. 0.5/0.25 is still within common prototype fab specs
    # (check against the house you actually order from before fab).
    dia, drill = 0.5, 0.3
    width = TRACK_WIDTH["Default"]
    n = 0
    stubs = []
    unplaced = []
    # Every pad's (net, x, y), once, so each GND escape can pick whichever of the
    # 4 cardinal directions actually has room -- a plain centre-to-pad vector picks
    # the wrong side for a corner-adjacent pin, and is undefined for an exposed
    # thermal pad sitting exactly at the footprint centre (U1's WSON-8 EP).
    # Pad BOUNDING BOXES, not pad centres.  Centre-to-centre was the old metric and it is
    # what produced all 11 DRC violations on the first board: it treats a 1.7 mm LQFP-64
    # finger and an 0402 terminal as the same point, so an escape "1.4 mm from the centre"
    # of a long pad can be 0.10 mm from its edge.  A bounding box is never smaller than the
    # pad, so a clearance measured against it is conservative in the safe direction.
    all_pads = []
    for afp in fpmap.values():
        for apad in afp.Pads():
            bb = apad.GetBoundingBox()
            all_pads.append((apad.GetNetname(),
                             mm(bb.GetLeft()), mm(bb.GetTop()),
                             mm(bb.GetRight()), mm(bb.GetBottom())))

    def clear_at(cx, cy):
        """Smallest gap from (cx, cy) to any non-GND pad's bounding box, mm."""
        best = 99.0
        for onet, ox0, oy0, ox1, oy1 in all_pads:
            if onet == "GND":
                continue
            dx = max(ox0 - cx, 0.0, cx - ox1)
            dy = max(oy0 - cy, 0.0, cy - oy1)
            d = math.hypot(dx, dy)
            if d < best:
                best = d
        return best

    # What the via centre has to clear, from the two rules that actually fired:
    #   copper: via pad radius (0.25) + netclass clearance (0.127) = 0.377
    #   hole:   via drill radius (0.15) + board hole clearance (0.25) = 0.400
    # The hole rule governs, so that is the target.
    NEED_CLEAR = 0.40

    # U1's WSON-8 EP (pin 9) sits exactly at the footprint centre with pins 6/7
    # straddling it on a 2x2 mm body -- there is no cardinal direction out of it
    # that doesn't run close past one of them, and a via dropped into the pad
    # itself would be an unplugged 0.3 mm drill under a bottom-terminated part,
    # i.e. a solder-wicking risk for ~40 mW of dissipation that needs no thermal
    # path at all. It is stitched instead by MANUAL_GND_STITCH below, with a short
    # track to U1 pin 5 (GND, already stubbed and via'd).
    SKIP = {("U1", "9")}
    # A step further out than the default, so the escape clears the local crowd of
    # other-net pads and lands in open pour.
    OFFSET = {("SW1", "2"): 1.4, ("J5", "2"): 1.4}
    for ref, pin in nm.get("GND", []):
        if (ref, pin) in SKIP:
            continue
        fp = fpmap[ref]
        # EVERY pad carrying this number, not just the first.  SW1 (SW_SPST_TL3342)
        # has two pads numbered "2" and J5 (U.FL) has two as well -- one physical
        # net pin, two separate lumps of copper.  Taking only the first left the
        # other one an island, which is what pcb/README.md used to blame on the
        # zone filler; the filler was innocent, this loop was skipping the pad.
        # A through-hole pad already reaches In1 through its own barrel, so it
        # needs no escape via (J4's four USB-C shield tabs are the case that
        # matters: 4 same-numbered PTH pads that are already connected).
        pads = [p for p in fp.Pads() if p.GetNumber() == pin
                and p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD]
        if not pads:
            continue
        off = OFFSET.get((ref, pin), 0.78)
        for pad in pads:
            pp = pad.GetPosition()
            px, py = mm(pp.x), mm(pp.y)
            # Search 8 directions at progressively larger offsets and take the FIRST that
            # actually clears, rather than the best of 4 at one fixed distance.  On a
            # 0.5 mm-pitch part the cardinal directions all run down a row of pins and the
            # diagonals are the only way out; on a crowded corner no short offset works at
            # all and only stepping further out does.
            DIRS = ((1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0),
                    (0.707, 0.707), (0.707, -0.707), (-0.707, 0.707), (-0.707, -0.707))
            best = None
            chosen = None
            for step in (off, off * 1.25, off * 1.55, off * 1.9, off * 2.3):
                for dx, dy in DIRS:
                    cx, cy = px + dx * step, py + dy * step
                    if not (X0 + 0.6 <= cx <= X0 + W - 0.6 and Y0 + 0.6 <= cy <= Y0 + H - 0.6):
                        continue
                    c = clear_at(cx, cy)
                    if best is None or c > best[0]:
                        best = (c, cx, cy)
                    if c >= NEED_CLEAR:
                        chosen = (cx, cy)
                        break
                if chosen:
                    break
            if chosen:
                vx, vy = chosen
            else:
                # Nowhere clears.  Place the best available and SAY SO -- a stitch via that
                # silently lands 0.1 mm off a signal pad is exactly how the first board
                # shipped 11 DRC errors into a routing pass.
                _, vx, vy = best
                unplaced.append((ref, pin, round(best[0], 4)))
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(V(px, py)); t.SetEnd(V(vx, vy))
            t.SetWidth(int(width * NM)); t.SetLayer(pcbnew.F_Cu)
            t.SetNetCode(gnd_net.GetNetCode())
            board.Add(t)
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(V(vx, vy))
            via.SetDrill(int(drill * NM)); via.SetWidth(int(dia * NM))
            via.SetNetCode(gnd_net.GetNetCode())
            board.Add(via)
            stubs.append(((px, py), (vx, vy)))
            n += 1
    if unplaced:
        print("  WARNING: %d GND escape(s) could not meet the %.2f mm clearance target:"
              % (len(unplaced), NEED_CLEAR))
        for ref, pin, got in unplaced:
            print("    %s pad %s -- best available %.3f mm" % (ref, pin, got))
    return n, stubs


# Hand-drawn GND copper for the pads the automatic escape above deliberately
# leaves alone.  Each entry is (start, end, width) in mm on F.Cu, all on GND.
#
# U1 pin 9, the TPS62162 WSON-8 exposed pad: 0.90 x 1.60 mm centred on the
# footprint origin, so its copper spans x 116.880..117.780, y 137.700..139.300.
# This track leaves the pad at y = 139.25 and runs east to pin 5 (GND) at
# (118.280, 139.250), which already has its own stub and via into In1.  The only
# other-net copper it passes is pin 6 (+3V3, y 138.625..138.875): a 0.25 mm track
# centred on y = 139.25 reaches down to y = 139.125, so the gap is 0.250 mm
# against the 0.127 mm Power-netclass requirement.  Checked with kicad-cli pcb
# drc, not by eye -- see pcb/README.md.
MANUAL_GND_STITCH = [
    ((117.400, 139.250), (118.280, 139.250), 0.25),
]


def stitch_gnd_manual(board):
    gnd_net = net_of(board, "GND")
    for (ax, ay), (bx, by), w in MANUAL_GND_STITCH:
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(V(ax, ay)); t.SetEnd(V(bx, by))
        t.SetWidth(int(w * NM)); t.SetLayer(pcbnew.F_Cu)
        t.SetNetCode(gnd_net.GetNetCode())
        board.Add(t)
    return len(MANUAL_GND_STITCH)


def seg_intersect(p1, p2, p3, p4):
    def ccw(a, b, c):
        return (c[1] - a[1]) * (b[0] - a[0]) - (b[1] - a[1]) * (c[0] - a[0])
    d1, d2 = ccw(p3, p4, p1), ccw(p3, p4, p2)
    d3, d4 = ccw(p1, p2, p3), ccw(p1, p2, p4)
    return (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0)


def seg_hits_rect(a, b, rect):
    x0, y0, x1, y1 = rect
    ax, ay = a
    bx, by = b
    if x0 <= ax <= x1 and y0 <= ay <= y1:
        return True
    if x0 <= bx <= x1 and y0 <= by <= y1:
        return True
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    for i in range(4):
        c, d = corners[i], corners[(i + 1) % 4]
        if seg_intersect(a, b, c, d):
            return True
    return False


def build_pad_obstacles(fpmap):
    """(bbox, net) for every pad on the board, expanded by a flat courtesy clearance
    -- a straight MST edge has to actually detour around unrelated silicon, not just
    avoid other already-routed tracks, or it walks straight across someone else's
    pads (which DRC rightly calls a short/solder-mask-bridge, not a near miss)."""
    obstacles = []
    pad_r = 0.22
    for fp in fpmap.values():
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            rect = (mm(bb.GetLeft()) - pad_r, mm(bb.GetTop()) - pad_r,
                    mm(bb.GetRight()) + pad_r, mm(bb.GetBottom()) + pad_r)
            p = pad.GetPosition()
            obstacles.append((rect, pad.GetNetname(), (mm(p.x), mm(p.y))))
    return obstacles


def path_hits_obstacles(path, obstacles, net, endpoints):
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        for rect, pnet, pcenter in obstacles:
            if pnet == net:
                continue
            # the two pads this edge actually terminates at aren't obstacles for it
            if any(math.hypot(pcenter[0] - ex, pcenter[1] - ey) < 0.05
                   for ex, ey in endpoints):
                continue
            x0, y0, x1, y1 = rect
            if (a[0] < x0 and b[0] < x0) or (a[0] > x1 and b[0] > x1):
                continue
            if (a[1] < y0 and b[1] < y0) or (a[1] > y1 and b[1] > y1):
                continue
            if seg_hits_rect(a, b, rect):
                return True
    return False


def path_collides(path, placed_on_layer, obstacles=None, net=None, endpoints=()):
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        for (c, d) in placed_on_layer:
            if seg_intersect(a, b, c, d):
                return True
    if obstacles is not None and path_hits_obstacles(path, obstacles, net, endpoints):
        return True
    return False


def mst_edges(points):
    """points: list of (ref, pin, x, y). Returns edges as index pairs, Prim's MST."""
    n = len(points)
    if n < 2:
        return []
    in_tree = [False] * n
    in_tree[0] = True
    dist = [math.hypot(points[i][2] - points[0][2], points[i][3] - points[0][3])
            for i in range(n)]
    parent = [0] * n
    edges = []
    for _ in range(n - 1):
        best, bd = -1, 1e18
        for i in range(n):
            if not in_tree[i] and dist[i] < bd:
                bd, best = dist[i], i
        in_tree[best] = True
        edges.append((parent[best], best))
        for i in range(n):
            if not in_tree[i]:
                d = math.hypot(points[i][2] - points[best][2],
                                points[i][3] - points[best][3])
                if d < dist[i]:
                    dist[i] = d
                    parent[i] = best
    return edges


def route_signal_nets(board, fpmap, nm, gnd_stubs=()):
    tracks_f, tracks_b = list(gnd_stubs), []  # (p1,p2) placed, per layer, for collisions
    obstacles = build_pad_obstacles(fpmap)
    routed, failed = 0, []
    for net, members in nm.items():
        if net == "GND" or len(members) < 2:
            continue
        netinfo = net_of(board, net)
        if netinfo is None:
            continue
        width = TRACK_WIDTH[netclass_of(net)]
        pts = []
        for ref, pin in members:
            fp = fpmap[ref]
            pad = next((p for p in fp.Pads() if p.GetNumber() == pin), None)
            if pad is None:
                continue
            p = pad.GetPosition()
            pts.append((ref, pin, mm(p.x), mm(p.y)))
        if len(pts) < 2:
            continue
        for i, j in mst_edges(pts):
            x1, y1 = pts[i][2], pts[i][3]
            x2, y2 = pts[j][2], pts[j][3]
            candA = [(x1, y1), (x2, y1), (x2, y2)]
            candB = [(x1, y1), (x1, y2), (x2, y2)]
            endpoints = [(x1, y1), (x2, y2)]
            layer, placed = pcbnew.F_Cu, tracks_f
            path = None
            for cand in (candA, candB):
                if not path_collides(cand, tracks_f, obstacles, net, endpoints):
                    path, layer, placed = cand, pcbnew.F_Cu, tracks_f
                    break
            if path is None:
                for cand in (candA, candB):
                    if not path_collides(cand, tracks_b, obstacles, net, endpoints):
                        path, layer, placed = cand, pcbnew.B_Cu, tracks_b
                        break
            if path is None:
                path, layer, placed = candA, pcbnew.F_Cu, tracks_f
                failed.append((net, pts[i][0], pts[j][0]))
            for k in range(len(path) - 1):
                a, b = path[k], path[k + 1]
                if abs(a[0] - b[0]) < 1e-6 and abs(a[1] - b[1]) < 1e-6:
                    continue
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(V(*a)); t.SetEnd(V(*b))
                t.SetWidth(int(width * NM)); t.SetLayer(layer)
                t.SetNetCode(netinfo.GetNetCode())
                board.Add(t)
                placed.append((a, b))
            if layer == pcbnew.B_Cu:
                # Every pad on this board is F.Cu-side (single-sided placement), so
                # a B.Cu detour needs a via at each end to actually reach it.
                dia, drill = VIA_SIZE[netclass_of(net)]
                for pt in (path[0], path[-1]):
                    via = pcbnew.PCB_VIA(board)
                    via.SetPosition(V(*pt))
                    via.SetDrill(int(drill * NM)); via.SetWidth(int(dia * NM))
                    via.SetNetCode(netinfo.GetNetCode())
                    board.Add(via)
            routed += 1
    return routed, failed


def main(pcb_path):
    board = pcbnew.LoadBoard(pcb_path)
    fpmap = {fp.GetReference(): fp for fp in board.GetFootprints()}
    nm_ = net_members()
    ci = comp_info()

    anchors = resolve_anchors(fpmap, ci, nm_)
    print("resolved %d passive anchors" % len(anchors))
    place_passives(board, fpmap, ci, nm_, anchors)
    # Where each passive WANTS to be: the pad it was anchored to. relax() pulls toward these
    # so that a part shoved out of a crowded pocket finds its way back instead of drifting.
    anchor_xy = {}
    for ref, (aref, apin, _own) in anchors.items():
        for pad in fpmap[aref].Pads():
            if pad.GetNumber() == apin:
                p = pad.GetPosition()
                anchor_xy[ref] = (mm(p.x), mm(p.y))
                break
    relax(board, fpmap, pinned=MAJOR_REFS, anchor_xy=anchor_xy)
    for _ in range(4):
        clean = final_squeeze(fpmap, pinned=MAJOR_REFS)
        relax(board, fpmap, pinned=MAJOR_REFS, iters=1500, anchor_xy=anchor_xy)
        if clean:
            break
    print("final squeeze clean:", clean)
    rescued = bring_home(fpmap, MAJOR_REFS, anchor_xy)
    for ref, was, now in rescued:
        print("  brought home: %s %.2f -> %.2f mm from its anchor" % (ref, was, now))

    # A handful of straggler pockets the automatic pass can't win: J10's bottom
    # edge and J1/U1's top edge leave under 0.05 mm of column between them (a real
    # board-density fact, not a solver bug), and one +3V3 cap landed flush on U4's
    # own body. Hand-relocated to open space nearby, each verified against its new
    # neighbours with kicad-cli pcb drc before this script was finalised.
    MANUAL_FIXUP = {
        # C2/C4/R1 used to be pinned here, with the note "the whole aft/left corner
        # (4 servo headers + J1 + regulator + J10) is saturated -- no pocket near J1
        # itself is big enough for these three".  That was true and it was the right
        # call at the time.  What it could not say is that the thing filling the
        # corner was J10, a bring-up-only debug header holding a 3.5 x 11.2 mm
        # channel right beside U1.  J10 is grouped with J3 on the aft edge now, the
        # channel is free, and all three have OVERRIDE_ANCHOR entries at U1/FB1, so
        # the solver places them on the pin they serve instead of being evicted.
        # design/pcb_placement.py is the check that this stays true.
        "C22": (136.89, 108.55, 180),  # 0.4 mm off U4's courtyard edge
        # The power corner, frozen.  relax() is chaotic in the sense that matters: changing
        # ONE footprint's courtyard (J1, JST-GH -> XT30-pigtail wire pads, 2026-09-24)
        # reshuffled all seven of these, TP1 landing between J1's two pads.  finish.py's
        # hand-drawn copper -- the 2.0 mm VBATT trunk through TP1, U1's VIN/EN necks into
        # R1 -- is built on this exact geometry, and it passed DRC and the placement gate
        # here, so it is pinned rather than re-solved.  (C1 is moved again by finish.py.)
        "C1": (104.875, 135.702, 90), "C2": (113.663, 130.039, 180),
        "C3": (114.575, 133.368, 180), "C4": (115.318, 135.411, 180),
        "FB1": (117.696, 134.921, -90), "R1": (113.851, 136.993, 0),
        "TP1": (110.375, 136.114, 0),
        # IMU LDO caps.  relax() left C32 on U9 and C31 on C22 (courtyard overlaps).  Three
        # parts round one SOT-23-5, so placed by hand: each on the pin it serves, pad 1
        # facing the pin.  C30 VIN above-left of pin 1, C32 VOUT above pin 5, C31 BYPASS
        # vertical under pin 4.
        "C30": (129.4, 104.2, -90), "C32": (133.0, 101.35, 180),
        "C31": (133.44, 106.9, -90),
        # R33 (the LDO's RC pre-filter) stacked above C30: VIN in at the top, VIN_IMU out
        # at the bottom straight into C30 pad 1 and U9 pin 1.  C27 (U7's +3V3 bypass) moves
        # 1 mm up-left out of C30's way, still 2.2 mm from U7 pin 8.
        "R33": (129.4, 101.6, -90), "C27": (127.3, 102.9, 0),
    }
    for ref, (x, y, rot) in MANUAL_FIXUP.items():
        fpmap[ref].SetOrientationDegrees(rot)
        fpmap[ref].SetPosition(V(x, y))

    pour_gnd(board)
    n_gnd, gnd_stubs = stitch_gnd_vias(board, fpmap, nm_)
    print("GND vias stitched:", n_gnd)
    print("GND manual stitches:", stitch_gnd_manual(board))
    if SKIP_SIGNAL_ROUTING:
        print("signal routing: skipped (SKIP_SIGNAL_ROUTING=True) -- see pcb/README.md")
    else:
        n_routed, failed = route_signal_nets(board, fpmap, nm_, gnd_stubs)
        print("nets routed:", n_routed, "collision fallbacks:", len(failed))
        for net, a, b in failed:
            print("  UNRESOLVED COLLISION:", net, a, b)
    fill_zones(board)

    out = pcb_path
    pcbnew.SaveBoard(out, board)
    print("saved", out)


if __name__ == "__main__":
    main(sys.argv[1])
