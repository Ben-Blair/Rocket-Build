#!/usr/bin/env python3
"""Emit flight_computer.kicad_pcb from KiCad's own exported netlist.

The netlist is read back from `kicad-cli sch export netlist` rather than from
design.py, so the board can only ever disagree with the schematic if KiCad itself
disagrees with it.  Board outline is 70 x 45 mm per docs/14; placement of the major
parts follows docs/14's zoning rules (IMU central over ground, magnetometer as far
from the servo feed and battery lead as the outline allows).  Passives are parked
off-board -- routing and final placement are not done here.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ksym
from gen import uid, fmt, q, PCB_VER, GEN_VER


# board outline, mm, in page coordinates
X0, Y0, W, H = 100.0, 100.0, 70.0, 45.0

# ref -> (x, y, rotation, layer).  docs/14: hold 70 x 45; if layout wants more,
# take it out of height, not width.
PLACE = {
    # --- aft / noisy end: pack in, servos out -------------------------------
    # Pad 1 (VBATT) of the XT30-pigtail solder pads; pad 2 (GND) is 4.8 mm east at 113.4.
    # 2.6 mm of copper clear of MH3's hole, and pad 1 feeds finish.py's 2.0 mm trunk.
    "J1":  (108.6, 141.5, 0),
    # Star point: SERVO_GND (pad 1) meets GND (pad 2) here and nowhere else.  Pad 1 is
    # tied to J1 pad 2 by finish.py; layout.py stitches pad 2 into the planes.
    "NT1": (115.4, 143.2, 0),
    "J6":  (103.5, 110.0, 90),
    "J7":  (103.5, 117.0, 90),
    "J8":  (103.5, 124.0, 90),
    "J9":  (103.5, 131.0, 90),
    "U1":  (117.0, 138.5, 0),
    "L1":  (122.0, 138.5, 0),
    # --- centre: MCU and the IMU it must not shake --------------------------
    "U2":  (137.0, 119.0, 0),
    "U4":  (137.0, 106.0, 0),
    # Hard against U2's OSC_IN/OSC_OUT pins (5 and 6, at 131.32/117.25 and
    # 131.32/117.75).  It was at (127.0, 130.0) -- 14.4 mm away, with C7 stranded
    # a further 8 mm past the MCU in the congested strip beside U4, making OSC_IN
    # a 21.5 mm high-impedance loop routed past the IMU.  The crystal, both load
    # caps and the MCU pins are one cluster now; see OVERRIDE_ANCHOR in layout.py
    # for C7/C8, which used to anchor to U2 instead of to Y1.
    # 180, not 0: Y1's pads 1 and 3 sit on opposite corners, so the rotation decides which
    # one faces the MCU.  At 0 the OSC_IN pad points AWAY and the net measured 5.05 mm against
    # a 5.0 limit; at 180 it points at U2 and the pair measure 2.79 (OSC_IN) and 4.96
    # (OSC_OUT).  It also puts them in the MCU's own pin order -- U2 pin 5 (OSC_IN) is above
    # pin 6 (OSC_OUT), and at 180 so are Y1's -- so the two traces do not cross.
    "Y1":  (127.5, 117.5, 180),
    "U7":  (123.0, 107.0, 0),
    # IMU LDO, in the free pocket west of U4 (x 130-134.5, y 101-107): pin 5 (VOUT) faces
    # U4, so the quiet rail is the short run and VIN -- which is already filtered by FB1 --
    # is the long one.
    "U9":  (132.3, 104.2, 0),
    "U3":  (131.0, 137.0, 0),
    # 141.3, not "as close to the edge as the courtyard allows": J4 is EDGE_MOUNT (below) and
    # sits where its F.Fab body front -- the receptacle mouth, local y +3.70 -- lands exactly
    # on the aft edge at y 145.0.  Clamped inside the outline like everything else it sat at
    # 140.25 with the mouth 1.1 mm inboard, and a USB-C plug's overmold, which is centred on
    # a receptacle ~1.6 mm above the copper, would have hit the PCB edge before seating.
    "J4":  (133.0, 141.3, 0),
    # --- bring-up cluster, aft edge: SWD, debug UART, reset -----------------
    # J10 and SW1 are bring-up-only parts and they were both parked in prime
    # real estate: J10 held a 3.5 x 11.2 mm channel right beside U1 in the
    # saturated power corner (which is why C2/C4/R1 had to be hand-relocated
    # 14 mm away -- see MANUAL_FIXUP in layout.py, now unwound), and SW1 sat in
    # the only pocket that could take the crystal.  Grouped with J3 instead:
    # NRST is on the SWD header anyway, so SW1 belongs next to it electrically
    # as well as ergonomically, and a debug cable and a probe want to land in
    # the same place.
    "J3":  (149.0, 142.0, 0),
    "J10": (157.5, 134.0, 90),
    "SW1": (158.5, 140.0, 90),
    # TP3 is pinned for the same reason, plus one of its own: a test point's courtyard is
    # 1.25 x 0.00 mm, so it slips into gaps no other part can claim -- and the gap it claimed
    # was the one between U1 and its VIN cluster, the single most valuable spot in the power
    # corner.  A GND probe point can sit anywhere on a board with two solid GND planes.
    "TP3": (142.5, 137.5, 0),
    # --- forward / quiet end: magnetometer and RF ---------------------------
    "U6":  (150.0, 133.0, 0),
    # Nudged 2.0 mm aft (was 160.5) purely to open the forward-edge strip for
    # J5.  U8's courtyard is 11.8 mm wide against a 9.7 x 10.1 mm package, so at
    # 160.5 it reached x=166.4 and left only 3.0 mm to the board edge -- and the
    # u.FL needs 4.4 mm.  Nothing else about U8's position was load-bearing.
    "U8":  (158.5, 126.0, 0),
    # On the FORWARD edge, level with U8's RF pad (pin 11, now at 163.25/129.30),
    # which points forward at the nose -- where correction 32 put the antenna.
    # Was (158.5, 140.5) on the lateral edge, a 13.93 mm GNSS_RF run that left
    # the RF pin, turned, and came back down the board.  2.02 mm now.  u.FL pad 1
    # sits 1.53 mm aft of the footprint centre, so the signal pad faces U8.
    "J5":  (166.8, 129.3, 0),
    # 0, and it must stay 0.  This was 270 for one revision, to compensate for
    # the stock LGA-16 footprint numbering pad 1 at the top of the LEFT column
    # while the chip's pin 1 is the right end of the TOP row.  That fixed the
    # axes and broke the copper: KiCad stores each pad's rotation ABSOLUTELY in
    # the file, so rotating the footprint 270 deg subtracts 270 from every pad's
    # effective local angle -- the side pads lose the 90 deg that made 0.45 x 0.30
    # fit a 0.5 mm pitch, and adjacent gaps collapse from 0.20 mm to 0.05 mm,
    # under JLCPCB's 0.127 mm minimum and under the Default/Power netclass.
    # The renumbering now lives in the footprint (RocketSenior.pretty, pad 1 =
    # chip pin 1), so the part is upright at 0 deg with its rectangles intact.
    # Do not put a rotation back here.
    "U5":  (162.0, 110.5, 0),
    # --- corners ------------------------------------------------------------
    "MH1": (103.5, 103.5, 0),
    "MH2": (166.5, 103.5, 0),
    "MH3": (103.5, 141.5, 0),
    "MH4": (166.5, 141.5, 0),
}

LAYERS = [
    (0, "F.Cu", "signal"), (1, "In1.Cu", "signal"), (2, "In2.Cu", "signal"),
    (31, "B.Cu", "signal"),
    (32, "B.Adhes", "user", "B.Adhesive"), (33, "F.Adhes", "user", "F.Adhesive"),
    (34, "B.Paste", "user"), (35, "F.Paste", "user"),
    (36, "B.SilkS", "user", "B.Silkscreen"), (37, "F.SilkS", "user", "F.Silkscreen"),
    (38, "B.Mask", "user"), (39, "F.Mask", "user"),
    (40, "Dwgs.User", "user", "User.Drawings"),
    (41, "Cmts.User", "user", "User.Comments"),
    (42, "Eco1.User", "user", "User.Eco1"), (43, "Eco2.User", "user", "User.Eco2"),
    (44, "Edge.Cuts", "user"), (45, "Margin", "user"),
    (46, "B.CrtYd", "user", "B.Courtyard"), (47, "F.CrtYd", "user", "F.Courtyard"),
    (48, "B.Fab", "user"), (49, "F.Fab", "user"),
]


def layers_block():
    out = []
    for l in LAYERS:
        extra = (" " + q(l[3])) if len(l) > 3 else ""
        out.append("\t\t(%d %s %s%s)" % (l[0], q(l[1]), l[2], extra))
    return "\t(layers\n%s\n\t)" % "\n".join(out)


STACKUP = '''\t(setup
\t\t(stackup
\t\t\t(layer "F.SilkS" (type "Top Silk Screen"))
\t\t\t(layer "F.Paste" (type "Top Solder Paste"))
\t\t\t(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
\t\t\t(layer "F.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 1" (type "prepreg") (thickness 0.2104) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
\t\t\t(layer "In1.Cu" (type "copper") (thickness 0.0175))
\t\t\t(layer "dielectric 2" (type "core") (thickness 1.065) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
\t\t\t(layer "In2.Cu" (type "copper") (thickness 0.0175))
\t\t\t(layer "dielectric 3" (type "prepreg") (thickness 0.2104) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
\t\t\t(layer "B.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
\t\t\t(layer "B.Paste" (type "Bottom Solder Paste"))
\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen"))
\t\t\t(copper_finish "ENIG")
\t\t\t(dielectric_constraints no)
\t\t)
\t\t(pad_to_mask_clearance 0)
\t\t(allow_soldermask_bridges_in_footprints no)
\t\t(aux_axis_origin %s %s)
\t\t(grid_origin %s %s)
\t)''' % (fmt(X0), fmt(Y0), fmt(X0), fmt(Y0))


def reuuid(node):
    """Fresh uuids throughout, so N copies of one footprint stay distinct."""
    if not isinstance(node, list):
        return
    if ksym.head(node) == 'uuid' and len(node) > 1:
        node[1] = ('q', uid())
        return
    for c in node:
        reuuid(c)


def load_fp(libfp):
    return ksym.parse(open(ksym.fp_path(libfp)).read())[0]


# Per-ref extra geometry welded onto a footprint as it is instantiated.
#
# U5's oversized F.Fab pin-1 dot used to live here, because U5 was placed at 270
# deg on a reused (MMC5883MA-labelled) stock footprint and nobody should have had
# to work out where a sub-mm library chamfer had rotated to.  U5 is now at 0 deg
# on RocketSenior:MMC5983MA_LGA-16_3x3mm_P0.5mm, drawn for this board, and the
# dot is drawn INTO that footprint at (1.9, -1.9) -- the top-right corner, which
# is where the chip's own pin 1 is.  Keeping it in the footprint means it is
# right in the footprint editor and in any other board too, not just in whatever
# gen_pcb.py happens to emit.  Do not re-add a U5 entry here; it would double the
# dot.  The mechanism stays for the next part that needs it.
EXTRA_FAB_MARK = {}


def build_footprint(libfp, ref, value, x, y, rot, path, padnets, netidx):
    fp = load_fp(libfp)
    body = [c for c in fp[2:]
            if ksym.head(c) not in ('version', 'generator', 'generator_version')]
    reuuid(body)
    for c in body:
        if ksym.head(c) == 'property' and isinstance(c[1], tuple):
            if c[1][1] == 'Reference':
                c[2] = ('q', ref)
            elif c[1][1] == 'Value':
                c[2] = ('q', value)
        if ksym.head(c) == 'pad':
            pad = c[1][1] if isinstance(c[1], tuple) else c[1]
            net = padnets.get(pad)
            if net:
                c.append(['net', str(netidx[net]), ('q', net)])
    if ref in EXTRA_FAB_MARK:
        body.append(ksym.parse(EXTRA_FAB_MARK[ref] % q(uid()))[0])
    parts = ['\t(footprint %s' % q(libfp),
             '\t\t(layer "F.Cu")',
             '\t\t(uuid %s)' % q(uid()),
             '\t\t(at %s %s%s)' % (fmt(x), fmt(y), (' %d' % rot) if rot else ''),
             '\t\t(path %s)' % q(path)]
    for c in body:
        parts.append('\t\t' + ksym.dumps(c, 2))
    parts.append('\t)')
    return '\n'.join(parts)


PINNED = {"MH1", "MH2", "MH3", "MH4"}   # mechanical; everything else may shift
# Registered to the board edge by their own body, so neither shoved nor clamped inside the
# outline -- their courtyard is MEANT to cross it.  See J4 in PLACE.
EDGE_MOUNT = {"J4"}
PINNED |= EDGE_MOUNT
# J1 and NT1 carry scaffold/finish.py's hand-drawn VBATT trunk and SERVO_GND star return;
# relax() moved them 0.4 mm and the B.Cu return shorted onto J1's VBATT pad.  Pinned.
PINNED |= {"J1", "NT1"}
EDGE_GAP = 0.6


def crtyd_bbox(fp):
    """F.CrtYd bounding box in footprint-local mm; falls back to pad extents."""
    xs, ys = [], []
    for c in fp:
        if not isinstance(c, list):
            continue
        if ksym.head(c) in ('fp_line', 'fp_rect', 'fp_poly', 'fp_circle', 'fp_arc') \
                and ksym.sval(c, 'layer') == 'F.CrtYd':
            for key in ('start', 'end', 'center', 'mid'):
                n = ksym.find(c, key)
                if n:
                    xs.append(float(n[1]))
                    ys.append(float(n[2]))
            pts = ksym.find(c, 'pts')
            if pts:
                for xy in ksym.findall(pts, 'xy'):
                    xs.append(float(xy[1]))
                    ys.append(float(xy[2]))
    if not xs:
        for c in ksym.findall(fp, 'pad'):
            at, sz = ksym.find(c, 'at'), ksym.find(c, 'size')
            px, py = float(at[1]), float(at[2])
            w = float(sz[1]) / 2 if sz else 0.6
            h = float(sz[2]) / 2 if sz else 0.6
            xs += [px - w, px + w]
            ys += [py - h, py + h]
    if not xs:
        return (-0.6, -0.6, 0.6, 0.6)
    return (min(xs), min(ys), max(xs), max(ys))


def local_box(libfp, rot):
    x0, y0, x1, y1 = crtyd_bbox(load_fp(libfp))
    if rot % 180 == 90:
        x0, y0, x1, y1 = y0, x0, y1, x1
    return x0, y0, x1, y1


def relax(place, fpof, iters=400):
    """Push overlapping courtyards apart, keep everything inside the outline.

    The anchors in PLACE carry the design intent from docs/14 (noisy end aft,
    magnetometer forward, IMU central); this only removes the physical collisions
    that hand-placing them leaves behind.  Edge-mounted parts stay pinned.
    """
    pos = {r: [float(v[0]), float(v[1])] for r, v in place.items()}
    rot = {r: v[2] for r, v in place.items()}
    box = {r: local_box(fpof[r], rot[r]) for r in place}
    refs = list(place)
    for _ in range(iters):
        moved = False
        for i, a in enumerate(refs):
            for b in refs[i + 1:]:
                ax0 = pos[a][0] + box[a][0]; ax1 = pos[a][0] + box[a][2]
                ay0 = pos[a][1] + box[a][1]; ay1 = pos[a][1] + box[a][3]
                bx0 = pos[b][0] + box[b][0]; bx1 = pos[b][0] + box[b][2]
                by0 = pos[b][1] + box[b][1]; by1 = pos[b][1] + box[b][3]
                ox = min(ax1, bx1) - max(ax0, bx0)
                oy = min(ay1, by1) - max(ay0, by0)
                if ox <= 0.02 or oy <= 0.02:
                    continue
                moved = True
                if ox < oy:
                    d = (ox + 0.4) / 2
                    s = -1 if (ax0 + ax1) < (bx0 + bx1) else 1
                    shove(pos, a, b, s * d, 0)
                else:
                    d = (oy + 0.4) / 2
                    s = -1 if (ay0 + ay1) < (by0 + by1) else 1
                    shove(pos, a, b, 0, s * d)
        for r in refs:
            if r in EDGE_MOUNT:
                continue
            x0, y0, x1, y1 = box[r]
            pos[r][0] = min(max(pos[r][0], X0 + EDGE_GAP - x0), X0 + W - EDGE_GAP - x1)
            pos[r][1] = min(max(pos[r][1], Y0 + EDGE_GAP - y0), Y0 + H - EDGE_GAP - y1)
        if not moved:
            break
    return {r: (round(pos[r][0], 2), round(pos[r][1], 2), rot[r]) for r in refs}


def shove(pos, a, b, dx, dy):
    pa, pb = a not in PINNED, b not in PINNED
    if pa and pb:
        pos[a][0] += dx; pos[a][1] += dy
        pos[b][0] -= dx; pos[b][1] -= dy
    elif pa:
        pos[a][0] += 2 * dx; pos[a][1] += 2 * dy
    elif pb:
        pos[b][0] -= 2 * dx; pos[b][1] -= 2 * dy


def outline():
    pts = [(X0, Y0), (X0 + W, Y0), (X0 + W, Y0 + H), (X0, Y0 + H)]
    out = []
    for i in range(4):
        a, b = pts[i], pts[(i + 1) % 4]
        out.append('\t(gr_line (start %s %s) (end %s %s)\n'
                   '\t\t(stroke (width 0.1) (type default))\n'
                   '\t\t(layer "Edge.Cuts")\n\t\t(uuid %s)\n\t)'
                   % (fmt(a[0]), fmt(a[1]), fmt(b[0]), fmt(b[1]), q(uid())))
    notes = [
        ("Stage 2 flight computer  --  70.0 x 45.0 mm, 4 layer, 1.6 mm, ENIG", 4.0, 2.0),
        ("docs/14: hold 70 x 45. If layout wants more, take it out of height, not width.", 8.0, 1.5),
        ("In1.Cu = solid GND under the IMU.  In2.Cu = 3V3 / servo return, kept apart.", 11.0, 1.5),
        ("Magnetometer U5 sits as far from the servo feed and battery lead as the outline allows:", 14.0, 1.5),
        ("estimation.required_magnetic_cleanliness() gives 18.0 mgauss against 40 mgauss from a", 17.0, 1.5),
        ("single untwisted 1 A servo lead at 50 mm -- twisted pairs, and keep the 2S run off this end.", 20.0, 1.5),
        ("NOT DONE: placement is a starting point, nothing is routed, no zones. See pcb/README.md.", 24.0, 1.5),
    ]
    for text, dy, size in notes:
        out.append('\t(gr_text %s\n\t\t(at %s %s)\n\t\t(layer "Cmts.User")\n'
                   '\t\t(uuid %s)\n\t\t(effects (font (size %s %s) (thickness 0.25))'
                   ' (justify left bottom))\n\t)'
                   % (q(text), fmt(X0), fmt(Y0 - 32 + dy), q(uid()), fmt(size), fmt(size)))
    return out


def main(outdir):
    netfile = os.path.join(outdir, 'net.net')
    root = ksym.parse(open(netfile).read())[0]

    netidx = {}
    nets_block = ['\t(net 0 "")']
    for n in ksym.findall(ksym.find(root, 'nets'), 'net'):
        name = ksym.sval(n, 'name')
        code = int(ksym.sval(n, 'code'))
        netidx[name] = code
        nets_block.append('\t(net %d %s)' % (code, q(name)))

    padnets = {}
    for n in ksym.findall(ksym.find(root, 'nets'), 'net'):
        name = ksym.sval(n, 'name')
        for nd in ksym.findall(n, 'node'):
            padnets.setdefault(ksym.sval(nd, 'ref'), {})[ksym.sval(nd, 'pin')] = name

    comps = ksym.findall(ksym.find(root, 'components'), 'comp')
    fpof = {}
    for c in comps:
        ref, libfp = ksym.sval(c, 'ref'), ksym.sval(c, 'footprint')
        if libfp and ref in PLACE:
            fpof[ref] = libfp
    placed = relax(PLACE, fpof)

    fps = []
    park_x, park_y, col = X0 + W + 20.0, Y0, 0
    missing = []
    for c in comps:
        ref = ksym.sval(c, 'ref')
        value = ksym.sval(c, 'value')
        libfp = ksym.sval(c, 'footprint')
        if not libfp:
            missing.append(ref)
            continue
        sp = ksym.sval(ksym.find(c, 'sheetpath'), 'tstamps')
        path = sp + ksym.sval(c, 'tstamps')
        if ref in placed:
            x, y, rot = placed[ref]
        else:
            x, y, rot = park_x + col * 11.0, park_y, 0
            col += 1
            if col == 12:
                col = 0
                park_y += 11.0
        fps.append(build_footprint(libfp, ref, value, x, y, rot, path,
                                   padnets.get(ref, {}), netidx))
    if missing:
        raise SystemExit("no footprint assigned: %s" % ", ".join(missing))

    txt = ('(kicad_pcb\n\t(version %s)\n\t(generator "pcbnew")\n'
           '\t(generator_version "%s")\n'
           '\t(general\n\t\t(thickness 1.6)\n\t\t(legacy_teardrops no)\n\t)\n'
           '\t(paper "A3")\n%s\n%s\n%s\n%s\n%s\n)\n'
           % (PCB_VER, GEN_VER, layers_block(), STACKUP,
              '\n'.join(nets_block), '\n'.join(fps), '\n'.join(outline())))
    open(os.path.join(outdir, 'flight_computer.kicad_pcb'), 'w').write(txt)
    print("%d footprints, %d nets, outline %.0f x %.0f mm"
          % (len(fps), len(netidx), W, H))


if __name__ == '__main__':
    main(sys.argv[1])
