#!/usr/bin/env python3
"""Scaffold the KiCad project for the Stage 2 flight computer.

THIS IS A ONE-SHOT SCAFFOLD, NOT A BUILD STEP.  It wrote the .kicad_sch files once;
from that point on THE KICAD FILES ARE THE SOURCE OF TRUTH.  Re-running it overwrites
whatever has been done in Eeschema.  It is kept in the repo because `design.py` is the
annotated netlist -- every pin assignment with the reason next to it -- and because it
is how the netlist was checked against docs/14 in the first place.

If you want to change a net BEFORE doing any layout, edit design.py and re-run:

    python pcb/flight_computer/scaffold/gen.py pcb/flight_computer

after which regenerate the netlist and the board (see pcb/README.md).  Once you have
started placing and routing, do not.

Writes KiCad 8 format (opens unchanged in 8, 9 and 10).  Connectivity is carried by
global labels and power symbols on short stubs at every pin, rather than by drawn
wires: the netlist is exact, and placement stays a layout job.
"""
import hashlib
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ksym
import design

OUT = sys.argv[1] if len(sys.argv) > 1 else "pcb/flight_computer"
PROJECT = "flight_computer"
SCH_VER = "20231120"
PCB_VER = "20240108"
GEN_VER = "8.0"

_ctr = [0]


def uid(seed=None):
    """Deterministic UUIDs so regeneration produces a stable diff."""
    _ctr[0] += 1
    h = hashlib.sha1(("rocketsenior-fc-%s-%d" % (seed or "", _ctr[0])).encode()).hexdigest()
    return "%s-%s-%s-%s-%s" % (h[0:8], h[8:12], h[12:16], h[16:20], h[20:32])


def q(s):
    return ksym.quote(s)


# --------------------------------------------------------------------- symbols
def mk_pin(num, name, etype, x, y, ang, length=5.08, style="line"):
    return ('\t\t\t(pin %s %s (at %s %s %d) (length %s)\n'
            '\t\t\t\t(name %s (effects (font (size 1.27 1.27))))\n'
            '\t\t\t\t(number %s (effects (font (size 1.27 1.27))))\n'
            '\t\t\t)' % (etype, style, fmt(x), fmt(y), ang, fmt(length),
                         q(name), q(num)))


def fmt(v):
    s = "%.4f" % float(v)
    s = s.rstrip('0').rstrip('.')
    return s if s else "0"


def custom_symbol(name, desc, datasheet, footprint, left, right):
    """left/right are lists of (number, name, etype) laid top-to-bottom."""
    rows = max(len(left), len(right))
    half_h = max(rows * 2.54 / 2 + 2.54, 7.62)
    half_w = 12.7
    body = []
    body.append('\t\t(symbol %s\n\t\t\t(rectangle (start %s %s) (end %s %s)\n'
                '\t\t\t\t(stroke (width 0.254) (type default))\n'
                '\t\t\t\t(fill (type background))\n\t\t\t)\n\t\t)'
                % (q(name + "_0_1"), fmt(-half_w), fmt(half_h), fmt(half_w), fmt(-half_h)))
    pins = []
    top = (rows - 1) * 2.54 / 2
    for i, (num, pname, etype) in enumerate(left):
        pins.append(mk_pin(num, pname, etype, -half_w - 5.08, top - i * 2.54, 0))
    for i, (num, pname, etype) in enumerate(right):
        pins.append(mk_pin(num, pname, etype, half_w + 5.08, top - i * 2.54, 180))
    body.append('\t\t(symbol %s\n%s\n\t\t)' % (q(name + "_1_1"), '\n'.join(pins)))
    props = [
        ("Reference", "U", half_h + 2.54, False),
        ("Value", name, half_h + 0.0, False),
        ("Footprint", footprint, 0, True),
        ("Datasheet", datasheet, 0, True),
        ("Description", desc, 0, True),
    ]
    ptxt = []
    for k, v, yy, hide in props:
        h = " (hide yes)" if hide else ""
        ptxt.append('\t\t(property %s %s (at 0 %s 0)\n'
                    '\t\t\t(effects (font (size 1.27 1.27))%s)\n\t\t)'
                    % (q(k), q(v), fmt(yy), h))
    return ('\t(symbol %s\n\t\t(pin_names (offset 1.016))\n'
            '\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n%s\n%s\n\t)'
            % (q(name), '\n'.join(ptxt), '\n'.join(body)))


ICM_LEFT = [("12", "AP_CS", "input"), ("13", "AP_SCLK", "input"),
            ("14", "AP_SDI", "input"), ("1", "AP_SDO", "tri_state"),
            ("4", "INT1", "output"), ("9", "INT2/FSYNC/CLKIN", "bidirectional")]
ICM_RIGHT = [("8", "VDD", "power_in"), ("5", "VDDIO", "power_in"),
             ("6", "GND", "power_in")] + \
            [(n, "RESV%s" % n, "passive") for n in ("2", "3", "7", "10", "11")]

MMC_LEFT = [("1", "SPI_SCK", "input"), ("16", "SPI_SDI", "input"),
            ("5", "SPI_SDO", "tri_state"), ("4", "~{SPI_CS}", "input"),
            ("15", "INT", "output"), ("10", "CAP", "passive")]
MMC_RIGHT = [("2", "VDD", "power_in"), ("13", "VDDIO", "power_in"),
             ("9", "GND", "power_in"), ("11", "GND", "power_in")] + \
            [(n, "NC%s" % n, "no_connect") for n in ("3", "6", "7", "8", "12", "14")]


def fork_symbol(lib, name, newname, pin_types, note):
    """Clone a stock symbol, overriding pin electrical types.

    Used where a stock symbol's pin type is wrong for THIS board -- e.g. an SPI
    slave's data-out pin typed `output` rather than `tri_state`, which ERCs as a
    driver conflict the moment two slaves share a MISO line.
    """
    sym = [x for x in ksym.get_symbol(lib, name)]
    old = sym[1][1]
    sym[1] = ('q', newname)
    for i, c in enumerate(sym):
        if not isinstance(c, list):
            continue
        if ksym.head(c) == 'symbol':
            c[1] = ('q', newname + c[1][1][len(old):])
            for p in ksym.findall(c, 'pin'):
                num = ksym.sval(p, 'number')
                if num in pin_types:
                    p[1] = pin_types[num]
        elif ksym.head(c) == 'property' and c[1][1] == 'Value':
            c[2] = ('q', newname)
        elif ksym.head(c) == 'property' and c[1][1] == 'Description':
            c[2] = ('q', note)
    return '\t' + ksym.dumps(sym, 1)


def write_symbol_lib(path):
    syms = [
        custom_symbol(
            "ICM-42688-P",
            "6-axis IMU, +/-2000 dps / +/-16 g, SPI, LGA-14 2.5x3.0 mm. Pin 7 RESV "
            "must be tied to GND (DS-000347 rev 1.6 Table 10); pins 2/3/10/11 may be NC.",
            "https://invensense.tdk.com/download-pdf/icm-42688-p-datasheet/",
            "Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y",
            ICM_LEFT, ICM_RIGHT),
        custom_symbol(
            "MMC5983MA",
            "3-axis magnetometer, SPI/I2C, LGA-16 3x3 mm, 4 pads per side. Pin 10 CAP "
            "needs 10uF. Footprint is project-local so its pad 1 IS the chip's pin 1 "
            "(right end of the top row, CCW); U5 therefore sits at 0 deg and the mag "
            "axes are board axes. See pcb/README.md before placing U5.",
            "https://www.memsic.com/Public/Uploads/uploadfile/files/20220119/MMC5983MADatasheetRevA.pdf",
            # MEMSIC Rev A p.20 LAND PATTERN: 4 pads per side, 0.5 pitch, 0.45 x 0.30
            # pads, 2.550 mm centre-to-centre both ways.  NOT _LayoutBorder3x5y, which
            # is 5+3 per side and would not have soldered -- and NOT the stock
            # Package_LGA:LGA-16_3x3mm_P0.5mm either: same copper, but its pad 1 is the
            # top of the LEFT column, so matching the chip meant rotating U5 270 deg,
            # which un-does the side pads' local 90 deg (KiCad stores pad rotation
            # absolutely) and collapses adjacent-pad gaps to 0.05 mm.  RocketSenior.pretty
            # carries the same land pattern with the chip's own numbering instead.
            "RocketSenior:MMC5983MA_LGA-16_3x3mm_P0.5mm",
            MMC_LEFT, MMC_RIGHT),
        fork_symbol(
            "Sensor_Pressure", "MS5611-01BA", "MS5611-01BA03", {"6": "tri_state"},
            "MS5611-01BA03 barometer. Fork of Sensor_Pressure:MS5611-01BA with SDO "
            "retyped output->tri_state: it shares SPI2 MISO with the magnetometer, "
            "and `output` ERCs as a driver conflict. Pins 4 and 5 are both CSB, "
            "internally connected (datasheet PIN CONFIGURATION, merged cell)."),
    ]
    txt = ('(kicad_symbol_lib\n\t(version %s)\n\t(generator "kicad_symbol_editor")\n'
           '\t(generator_version "%s")\n%s\n)\n' % (SCH_VER, GEN_VER, '\n'.join(syms)))
    open(path, 'w').write(txt)


# ------------------------------------------------------------------- schematic
class Sheet:
    def __init__(self, name, title, page, sheet_uuid):
        self.name = name
        self.title = title
        self.page = page
        self.sheet_uuid = sheet_uuid   # uuid of the sheet symbol in the root
        self.own_uuid = uid("file-" + name)
        self.items = []
        self.libs = {}

    def add(self, s):
        self.items.append(s)

    def need(self, lib_id):
        if lib_id not in self.libs:
            lib, nm = lib_id.split(':', 1)
            if lib == "RocketSenior":
                self.libs[lib_id] = CUSTOM[nm]
            else:
                self.libs[lib_id] = ksym.get_symbol(lib, nm)
        return self.libs[lib_id]


CUSTOM = {}


def load_custom(path):
    root = ksym.parse(open(path).read())[0]
    for s in ksym.findall(root, 'symbol'):
        CUSTOM[s[1][1]] = s


STUB = 6.35


def pin_geometry(sym):
    out = []
    for unit in ksym.findall(sym, 'symbol'):
        for p in ksym.findall(unit, 'pin'):
            at = ksym.find(p, 'at')
            x, y = float(at[1]), float(at[2])
            ang = int(float(at[3])) if len(at) > 3 else 0
            out.append((ksym.sval(p, 'number'), x, y, ang))
    return out


def place(sheet, ref, lib_id, value, footprint, pinmap, x, y):
    sym = sheet.need(lib_id)
    su = uid(ref)
    geo = pin_geometry(sym)
    props = [("Reference", ref, x, y - 1.27, False),
             ("Value", value, x, y + 1.27, False),
             ("Footprint", footprint, x, y, True),
             ("Datasheet", "~", x, y, True),
             ("Description", "", x, y, True)]
    ptxt = []
    for k, v, px, py, hide in props:
        h = " (hide yes)" if hide else ""
        ptxt.append('\t\t(property %s %s\n\t\t\t(at %s %s 0)\n'
                    '\t\t\t(effects (font (size 1.27 1.27))%s)\n\t\t)'
                    % (q(k), q(v), fmt(px), fmt(py), h))
    pintxt = ['\t\t(pin %s (uuid %s))' % (q(n), q(uid(ref + n))) for n, _, _, _ in geo]
    sheet.add('\t(symbol\n\t\t(lib_id %s)\n\t\t(at %s %s 0)\n\t\t(unit 1)\n'
              '\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n'
              '\t\t(dnp no)\n\t\t(uuid %s)\n%s\n%s\n'
              '\t\t(instances\n\t\t\t(project %s\n\t\t\t\t(path %s\n'
              '\t\t\t\t\t(reference %s) (unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)'
              % (q(lib_id), fmt(x), fmt(y), q(su), '\n'.join(ptxt), '\n'.join(pintxt),
                 q(PROJECT), q("/" + sheet.sheet_uuid), q(ref)))

    for num, px, py, ang in geo:
        net = pinmap.get(num)
        if net is None:
            raise SystemExit("%s: pin %s has no net assigned" % (ref, num))
        ex, ey = x + px, y - py
        dx, dy = -math.cos(math.radians(ang)), math.sin(math.radians(ang))
        dx, dy = round(dx), round(dy)
        sx, sy = ex + dx * STUB, ey + dy * STUB
        if net == design.NC:
            sheet.add('\t(no_connect (at %s %s) (uuid %s))' % (fmt(ex), fmt(ey), q(uid())))
            continue
        sheet.add('\t(wire (pts (xy %s %s) (xy %s %s))\n'
                  '\t\t(stroke (width 0) (type default))\n\t\t(uuid %s)\n\t)'
                  % (fmt(ex), fmt(ey), fmt(sx), fmt(sy), q(uid())))
        attach(sheet, net, sx, sy, dx, dy)


LABEL_ANG = {(-1, 0): 180, (1, 0): 0, (0, 1): 270, (0, -1): 90}
PWRSYM_ROT = {(0, -1): 0, (0, 1): 180, (-1, 0): 270, (1, 0): 90}
GND_ROT = {(0, 1): 0, (0, -1): 180, (-1, 0): 90, (1, 0): 270}

POWER_SYMBOLS = {"GND": "power:GND", "+3V3": "power:+3V3"}


def attach(sheet, net, sx, sy, dx, dy):
    lib_id = POWER_SYMBOLS.get(net)
    if lib_id:
        rot = (GND_ROT if net == "GND" else PWRSYM_ROT)[(dx, dy)]
        power_symbol(sheet, lib_id, net, sx, sy, rot)
    else:
        ang = LABEL_ANG[(dx, dy)]
        just = "left" if ang in (0, 90) else "right"
        sheet.add('\t(global_label %s\n\t\t(shape bidirectional)\n\t\t(at %s %s %d)\n'
                  '\t\t(effects (font (size 1.27 1.27)) (justify %s))\n\t\t(uuid %s)\n\t)'
                  % (q(net), fmt(sx), fmt(sy), ang, just, q(uid())))


_pwr_n = [0]


def power_symbol(sheet, lib_id, net, x, y, rot):
    sheet.need(lib_id)
    _pwr_n[0] += 1
    ref = "#PWR%03d" % _pwr_n[0]
    su = uid(ref)
    off = 3.81 if rot in (0, 180) else 0
    props = [("Reference", ref, x, y, True),
             ("Value", net, x, y + (off if rot == 180 else -off), False),
             ("Footprint", "", x, y, True), ("Datasheet", "", x, y, True),
             ("Description", "", x, y, True)]
    ptxt = []
    for k, v, px, py, hide in props:
        h = " (hide yes)" if hide else ""
        ptxt.append('\t\t(property %s %s\n\t\t\t(at %s %s 0)\n'
                    '\t\t\t(effects (font (size 1.27 1.27))%s)\n\t\t)'
                    % (q(k), q(v), fmt(px), fmt(py), h))
    sheet.add('\t(symbol\n\t\t(lib_id %s)\n\t\t(at %s %s %d)\n\t\t(unit 1)\n'
              '\t\t(exclude_from_sim no)\n\t\t(in_bom no)\n\t\t(on_board yes)\n'
              '\t\t(dnp no)\n\t\t(uuid %s)\n%s\n\t\t(pin "1" (uuid %s))\n'
              '\t\t(instances\n\t\t\t(project %s\n\t\t\t\t(path %s\n'
              '\t\t\t\t\t(reference %s) (unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)'
              % (q(lib_id), fmt(x), fmt(y), rot, q(su), '\n'.join(ptxt),
                 q(uid(ref + "p")), q(PROJECT), q("/" + sheet.sheet_uuid), q(ref)))


def place_pwr_flag(sheet, net, x, y):
    """PWR_FLAG + a stub to `net`, so ERC sees the rail as driven."""
    place(sheet, "#FLG%03d" % (_flg(),), "power:PWR_FLAG", net, "", {"1": net}, x, y)


_flgn = [0]


def _flg():
    _flgn[0] += 1
    return _flgn[0]


def sym_extent(sym):
    geo = pin_geometry(sym)
    if not geo:
        return 10, 10
    xs = [g[1] for g in geo]
    ys = [g[2] for g in geo]
    return max(xs) - min(xs), max(ys) - min(ys)


def snap(v):
    return round(v / 1.27) * 1.27


# A net label is text, and the longest one here is GNSS_TIMEPULSE.  Cells have to
# allow for the stub plus that text on every side or sheets overrun the page.
LABEL_ALLOW = 27.0


def layout(sheet, comps, x0=25.0, y0=45.0, pagew=594.0, pageh=420.0):
    """Row-major flow with per-symbol cells; placement is cosmetic, nets are not."""
    x, y, rowh = x0, y0, 0.0
    for ref, lib_id, value, fp, pinmap in comps:
        sym = sheet.need(lib_id)
        w, h = sym_extent(sym)
        cw = w + 2 * LABEL_ALLOW
        ch = h + 2 * LABEL_ALLOW
        if x + cw > pagew - 20:
            x, y = x0, y + rowh + 8.0
            rowh = 0.0
        place(sheet, ref, lib_id, value, fp, pinmap, snap(x + cw / 2), snap(y + ch / 2))
        x += cw + 8.0
        rowh = max(rowh, ch)
    bottom = y + rowh
    if bottom > pageh - 20:
        raise PageOverrun(bottom)
    return bottom


class PageOverrun(Exception):
    pass


PAPERS = [("A3", 420.0, 297.0), ("A2", 594.0, 420.0),
          ("A1", 841.0, 594.0), ("A0", 1189.0, 841.0)]


def fit(sheet, title, comps, extra=None):
    """Lay the sheet out on the smallest ISO paper that holds it."""
    for paper, pw, ph in PAPERS:
        sheet.items = []
        sheet.libs = {}
        try:
            sheet_text(sheet, title, 25, 30, 2.5)
            yend = layout(sheet, comps, pagew=pw, pageh=ph)
            if extra:
                extra(sheet, yend, pw, ph)
            return paper
        except PageOverrun:
            continue
    raise SystemExit("sheet %s does not fit on A0" % sheet.name)


def sheet_text(sheet, s, x, y, size=2.0):
    sheet.add('\t(text %s\n\t\t(exclude_from_sim no)\n\t\t(at %s %s 0)\n'
              '\t\t(effects (font (size %s %s) (bold yes)) (justify left bottom))\n'
              '\t\t(uuid %s)\n\t)' % (q(s), fmt(x), fmt(y), fmt(size), fmt(size), q(uid())))


def lib_symbols_block(sheet):
    out = []
    for lib_id, sym in sorted(sheet.libs.items()):
        node = [x for x in sym]
        node[1] = ('q', lib_id)
        out.append('\t\t' + ksym.dumps(node, 2))
    return '\t(lib_symbols\n%s\n\t)' % '\n'.join(out)


TITLE = ('\t(title_block\n\t\t(title "RocketSenior Stage 2 flight computer")\n'
         '\t\t(date "")\n\t\t(rev "A")\n'
         '\t\t(company "RocketSenior -- docs/14-flight-computer-bom.md")\n'
         '\t\t(comment 1 %s)\n\t)')


def write_sheet(sheet, path, paper="A2"):
    body = '\n'.join(sheet.items)
    txt = ('(kicad_sch\n\t(version %s)\n\t(generator "eeschema")\n'
           '\t(generator_version "%s")\n\t(uuid %s)\n\t(paper "%s")\n%s\n%s\n%s\n'
           '\t(sheet_instances\n\t\t(path "/" (page %s))\n\t)\n)\n'
           % (SCH_VER, GEN_VER, q(sheet.own_uuid), paper,
              TITLE % q(sheet.title), lib_symbols_block(sheet), body, q(str(sheet.page))))
    open(path, 'w').write(txt)


ROOT_UUID = uid("root-file")


def write_root(path, sheets):
    items = []
    libs = {}
    x = 30.0
    notes = [
        "Stage 2 flight computer -- schematic scaffold.",
        "Bus map is docs/14-flight-computer-bom.md; CS1..CS4 net names follow it.",
        "Connectivity is by GLOBAL LABEL at every pin stub -- there are no drawn buses.",
        "No pyro on this board: an independent StratoLoggerCF fires the charges.",
        "Servo header rail is RAW 2S (VBATT), fed from the pack star point, NOT from +3V3.",
        "Layout and routing are NOT done. See pcb/README.md before fabbing anything.",
    ]
    for i, s in enumerate(sheets):
        items.append(
            '\t(sheet\n\t\t(at %s 50)\n\t\t(size 60 30)\n'
            '\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n\t\t(dnp no)\n'
            '\t\t(stroke (width 0.1524) (type solid))\n'
            '\t\t(fill (color 0 0 0 0.0000))\n\t\t(uuid %s)\n'
            '\t\t(property "Sheetname" %s\n\t\t\t(at %s 49.3 0)\n'
            '\t\t\t(effects (font (size 1.27 1.27)) (justify left bottom))\n\t\t)\n'
            '\t\t(property "Sheetfile" %s\n\t\t\t(at %s 80.7 0)\n'
            '\t\t\t(effects (font (size 1.27 1.27)) (justify left top))\n\t\t)\n'
            '\t\t(instances\n\t\t\t(project %s\n\t\t\t\t(path %s\n'
            '\t\t\t\t\t(page %s)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)'
            % (fmt(x), q(s.sheet_uuid), q(s.name), fmt(x),
               q(s.name + ".kicad_sch"), fmt(x), q(PROJECT),
               q("/" + ROOT_UUID), q(str(s.page))))
        x += 66.0
    for i, n in enumerate(notes):
        items.append('\t(text %s\n\t\t(exclude_from_sim no)\n\t\t(at 30 %s 0)\n'
                     '\t\t(effects (font (size 1.6 1.6)) (justify left bottom))\n'
                     '\t\t(uuid %s)\n\t)' % (q(n), fmt(110 + i * 7), q(uid())))
    txt = ('(kicad_sch\n\t(version %s)\n\t(generator "eeschema")\n'
           '\t(generator_version "%s")\n\t(uuid %s)\n\t(paper "A3")\n%s\n'
           '\t(lib_symbols\n\t)\n%s\n'
           '\t(sheet_instances\n\t\t(path "/" (page "1"))\n\t)\n)\n'
           % (SCH_VER, GEN_VER, q(ROOT_UUID),
              TITLE % q("root -- sheet index and board-level notes"),
              '\n'.join(items)))
    open(path, 'w').write(txt)


# Netclasses and board rules for the .kicad_pro.  Kept OUT of the JSON template below:
# this used to carry '#' comments inside the JSON string itself, so every regeneration
# wrote an invalid .kicad_pro -- which is why the RF class below never reached the
# project file that was actually on disk (found 2026-09-24, pcb/README.md "Routing").
#
# Default/Power/USB clearance 0.127: anything wider fails against the LQFP-64 and LGA
#   pad pitches.  JLCPCB 4-layer minimum is 0.09.
# Power 0.3 mm: +3V3 is 112 mA and VIN ~60 mA; 0.3 mm on 1 oz outer copper is ~1 A at a
#   10 degC rise.  It was 0.6, which cannot enter a 0.3 mm-wide pin on a 0.5 mm pitch
#   (U1 WSON, U2 LQFP, U4/U5 LGA) without violating clearance to the neighbouring pin.
# ServoPower 1.2 mm: the per-header branches.  The J1 trunk and the header spine are 2.0 mm
#   and drawn by scaffold/finish.py, because a netclass cannot say "this part of this net".
# USB 0.25 / 0.15 gap: 90.9 ohm edge-coupled on this stackup (IPC-2141 coupling over the
#   Hammerstad Z0 in scripts/pcb_placement_report.py).  It was 0.4 / 0.2, about 75 ohm.
#   At USB full speed (12 Mbit/s) over ~25 mm this is bookkeeping, not signal integrity.
# RF 0.36 mm: 50 ohm on this stackup (F.Cu over 0.2104 mm prepreg, er 4.5, 35 um), and
#   50 ohm is MAX-M10S RF_IN's Zin -- u-blox UBX-20035208 R08 Table 13.  0.2 clearance.
# Board rules are JLCPCB's published 4-layer capabilities, with margin: via hole to track
#   0.2, min track 0.15 (Freerouting necks 0.25 tracks to 0.187 at fine-pitch pads),
#   silkscreen text 1.0 mm high.
NETCLASSES = [
    # name,        clearance, track, via dia, via drill, dp gap, dp width
    ("Default",    0.127, 0.25, 0.6, 0.3, 0.25, 0.2),
    ("Power",      0.127, 0.3,  0.6, 0.3, 0.25, 0.2),
    ("ServoPower", 0.3,   1.2,  1.0, 0.5, 0.25, 0.2),
    ("USB",        0.127, 0.25, 0.6, 0.3, 0.15, 0.25),
    ("RF",         0.2,   0.36, 0.6, 0.3, 0.25, 0.2),
]
NETCLASS_PATTERNS = [("Power", "+3V3"), ("Power", "GND"), ("Power", "VIN"),
                     ("ServoPower", "VBATT"), ("ServoPower", "SERVO_GND"),
                     ("USB", "USB_D*"), ("RF", "GNSS_RF")]
BOARD_RULES = {
    "min_clearance": 0.0, "min_copper_edge_clearance": 0.5, "min_hole_clearance": 0.2,
    "min_hole_to_hole": 0.25, "min_through_hole_diameter": 0.3, "min_track_width": 0.15,
    "min_via_annular_width": 0.1, "min_via_diameter": 0.5, "min_microvia_diameter": 0.2,
    "min_microvia_drill": 0.1, "min_silk_clearance": 0.0, "min_text_height": 1.0,
    "min_text_thickness": 0.15, "max_error": 0.005,
}


def pro_json(sheet_entries):
    import json
    classes = [{"name": n, "clearance": c, "track_width": w, "via_diameter": vd,
                "via_drill": vdr, "microvia_diameter": 0.3, "microvia_drill": 0.1,
                "diff_pair_gap": g, "diff_pair_width": dw}
               for n, c, w, vd, vdr, g, dw in NETCLASSES]
    pro = {
        "board": {"design_settings": {"defaults": {"board_outline_line_width": 0.1},
                                      "rules": BOARD_RULES}},
        "boards": [],
        "cvpcb": {"equivalence_files": []},
        "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
        "meta": {"filename": "%s.kicad_pro" % PROJECT, "version": 1},
        "net_settings": {
            "classes": classes, "net_colors": None, "netclass_assignments": None,
            "netclass_patterns": [{"netclass": c, "pattern": p}
                                  for c, p in NETCLASS_PATTERNS]},
        "pcbnew": {"last_paths": {"gencad": "", "idf": "", "netlist": "",
                                  "specctra_dsn": "", "step": "", "vrml": ""},
                   "page_layout_descr_file": ""},
        "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
        "sheets": sheet_entries,
        "text_variables": {},
    }
    return json.dumps(pro, indent=2) + "\n"


def write_project(path, sheets):
    entries = [[ROOT_UUID, "Root"]] + [[s.sheet_uuid, s.name] for s in sheets]
    open(path, 'w').write(pro_json(entries))


def main():
    os.makedirs(OUT, exist_ok=True)
    write_symbol_lib(os.path.join(OUT, "RocketSenior.kicad_sym"))
    load_custom(os.path.join(OUT, "RocketSenior.kicad_sym"))

    open(os.path.join(OUT, "sym-lib-table"), 'w').write(
        '(sym_lib_table\n  (version 7)\n'
        '  (lib (name "RocketSenior")(type "KiCad")'
        '(uri "${KIPRJMOD}/RocketSenior.kicad_sym")(options "")'
        '(descr "Parts with no stock KiCad symbol"))\n)\n')

    # Project-local FOOTPRINT library.  Only one entry so far, and it exists for
    # a specific reason: the stock Package_LGA:LGA-16_3x3mm_P0.5mm has the right
    # copper but numbers pad 1 at the top of the LEFT column, while the
    # MMC5983MA's own pin 1 is the right end of the TOP row.  Correcting that by
    # rotating the part 270 deg breaks the pad rectangles (KiCad stores pad
    # rotation absolutely, so the side pads' local 90 deg is undone and the
    # 0.45 mm dimension ends up along the 0.5 mm pitch -- 0.05 mm gaps).  The
    # local footprint carries the same land pattern with the chip's own
    # numbering, so U5 is placed at 0 deg and nothing has to be rotated.
    open(os.path.join(OUT, "fp-lib-table"), 'w').write(
        '(fp_lib_table\n  (version 7)\n'
        '  (lib (name "RocketSenior")(type "KiCad")'
        '(uri "${KIPRJMOD}/RocketSenior.pretty")(options "")'
        '(descr "Footprints redrawn for this board"))\n)\n')

    sheets = []
    for i, (name, title, comps) in enumerate(design.SHEETS):
        sh = Sheet(name, title, i + 2, uid("sheet-" + name))
        sheets.append(sh)

    def flags(sh, yend, pw, ph):
        if yend + 40 > ph - 20:
            raise PageOverrun(yend + 40)
        sheet_text(sh, "Rail drivers -- PWR_FLAG so ERC sees each rail driven",
                   25, yend + 14, 2.0)
        x = 34.0
        for net in design.POWER_FLAGS:
            place(sh, "#FLG%03d" % _flg(), "power:PWR_FLAG", net, "",
                  {"1": net}, snap(x), snap(yend + 32))
            x += 30.0

    for sh, (name, title, comps) in zip(sheets, design.SHEETS):
        _flgn[0] = 0
        paper = fit(sh, title, comps, flags if name == "power" else None)
        write_sheet(sh, os.path.join(OUT, name + ".kicad_sch"), paper)
        print("  %-8s %s" % (name, paper))

    write_root(os.path.join(OUT, PROJECT + ".kicad_sch"), sheets)
    write_project(os.path.join(OUT, PROJECT + ".kicad_pro"), sheets)

    nets = {}
    for _, _, comps in design.SHEETS:
        for ref, lib_id, value, fp, pinmap in comps:
            for pin, net in pinmap.items():
                if net != design.NC:
                    nets.setdefault(net, []).append("%s.%s" % (ref, pin))
    print("%d components, %d nets" % (
        sum(len(c) for _, _, c in design.SHEETS), len(nets)))
    for n, v in sorted(nets.items()):
        if len(v) < 2:
            print("  WARNING single-pin net %s: %s" % (n, v))


if __name__ == "__main__":
    main()
