#!/usr/bin/env python3
"""JLCPCB fabrication + assembly (PCBA) package for the flight computer.

Run after scaffold/finish.py, with a plain python3 (it only drives kicad-cli):

    python3 pcb/flight_computer/scaffold/fab.py

Writes pcb/flight_computer/fab/:

    flight_computer-gerbers.zip   upload this as the PCB  (gerbers + Excellon drill)
    flight_computer-bom.csv       JLC BOM:  Comment, Designator, Footprint, LCSC Part #
    flight_computer-cpl.csv       JLC CPL:  Designator, Mid X, Mid Y, Layer, Rotation
    flight_computer-assembly.pdf  F.Fab + silk + outline: EVERY reference, including the 12
                                  whose silk label had no room (finish.py hides those)
    ORDERING.md                   the per-line decisions this table cannot carry

Board: 4 layers, 1.6 mm, JLC04161H-7628 stackup (the impedance numbers in the .kicad_pro
netclasses assume it -- select it explicitly when ordering), ENIG, 1 oz outer.

LCSC numbers live HERE, keyed by (Value, Footprint), rather than as a symbol field: the
schematics are regenerated from scaffold/design.py by gen.py, so a field typed into
Eeschema would be lost on the next regen.  Every number marked (verified) was checked on
its LCSC product page on 2026-09-24 for MPN, package and stock; the rest are flagged in
ORDERING.md.  Stock moves -- JLC's BOM tool re-checks every line at order time.
"""
import csv
import io
import os
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.normpath(os.path.join(HERE, ".."))
OUT = os.path.join(PROJ, "fab")
BOARD = os.path.join(PROJ, "flight_computer.kicad_pcb")
SCH = os.path.join(PROJ, "flight_computer.kicad_sch")
KC = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"

LAYERS = ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu", "F.Paste", "B.Paste", "F.Silkscreen",
          "B.Silkscreen", "F.Mask", "B.Mask", "Edge.Cuts"]

# (Value, footprint name) -> (LCSC, MPN, note).  Footprint is the name without library.
PARTS = {
    ("100nF", "C_0402_1005Metric"): ("C1525", "CL05B104KO5NNNC 16V X7R", "verified"),
    ("100nF/50V", "C_0402_1005Metric"): ("C1525", "CL05B104KO5NNNC 16V X7R",
                                         "verified; 16 V not 50 V -- see ORDERING.md"),
    ("12pF", "C_0402_1005Metric"): ("C1547", "0402CG120J500NT 50V C0G", "verified"),
    ("10nF", "C_0402_1005Metric"): ("C15195", "CL05B103KB5NNNC 50V X7R", "verified"),
    ("1uF", "C_0603_1608Metric"): ("C5673", "CL10A105KA8NNNC 25V X5R", "search"),
    ("2.2uF", "C_0603_1608Metric"): ("C23630", "CL10A225KO8NNNC 16V X5R", "verified"),
    ("2.2uF", "C_0805_2012Metric"): ("C19110", "CL21B225KAFNNNE 25V X7R", "search"),
    ("4.7uF", "C_0805_2012Metric"): ("C1779", "CL21A475KAQNNNE 25V X5R", "verified"),
    ("10uF", "C_0805_2012Metric"): ("C15850", "CL21A106KAYNNNE 25V X5R", "verified"),
    ("10uF/25V", "C_0805_2012Metric"): ("C15850", "CL21A106KAYNNNE 25V X5R", "verified"),
    ("10uF SET/RESET", "C_0805_2012Metric"): ("C15850", "CL21A106KAYNNNE 25V X5R",
                                              "verified"),
    ("22uF/16V", "C_0805_2012Metric"): ("C45783", "CL21A226MAQNNNE 25V X5R", "verified"),
    ("22uF/25V", "C_1210_3225Metric"): ("C52306", "CL32A226KAJNNNE 25V X5R", "search"),
    ("100k", "R_0402_1005Metric"): ("C25741", "0402WGF1003TCE", "verified"),
    ("10k", "R_0402_1005Metric"): ("C25744", "0402WGF1002TCE", "verified"),
    ("5.1k", "R_0402_1005Metric"): ("C25905", "0402WGF5101TCE", "verified"),
    ("10", "R_0402_1005Metric"): ("C25077", "0402WGF100JTCE 10R", "verified"),
    ("1k", "R_0402_1005Metric"): ("C11702", "0402WGF1001TCE", "verified"),
    ("600R@100MHz 2A", "L_0805_2012Metric"): ("C1017", "GZ2012D601TF 600R 0.5A",
                                              "search; 0.5 A not 2 A -- see ORDERING.md"),
    ("600R@100MHz", "L_0603_1608Metric"): ("C1002", "GZ1608D601TF 600R 0.2A", "search"),
    ("2.2uH", "L_1210_3225Metric"): ("C86074", "LQH32PN2R2NN0L 1.55A",
                                     "verified OUT OF STOCK -- pick at order"),
    ("SS14", "D_SOD-123"): ("C8598", "B5819W SL 40V 1A SOD-123", "search; SS14-equivalent"),
    ("green", "LED_0603_1608Metric"): ("C12624", "KT-0603G", "search"),
    ("blue", "LED_0603_1608Metric"): ("", "any 0603 blue, Vf <= 3.0 V", "pick at order"),
    ("8MHz", "Crystal_SMD_3225-4Pin_3.2x2.5mm"): ("C2682775", "X32258MOB4SI 8MHz 12pF",
                                                  "search"),
    ("TPS62162DSGT", "Texas_DSG0008A_WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm"):
        ("C2863597", "TPS62162DSGT", "search"),
    ("STM32F405RGT6", "LQFP-64_10x10mm_P0.5mm"): ("C15742", "STM32F405RGT6", "verified"),
    ("LP2985-33DBVR", "SOT-23-5"): ("C95414", "LP2985-33DBVR", "search"),
    ("USBLC6-2SC6", "SOT-23-6"): ("C7519", "USBLC6-2SC6", "verified"),
    ("ICM-42688-P", "LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y"):
        ("C1850418", "ICM-42688-P", "verified OUT OF STOCK at LCSC -- see ORDERING.md"),
    ("MMC5983MA", "MMC5983MA_LGA-16_3x3mm_P0.5mm"): ("C404329", "MMC5983MA", "search"),
    ("MS5611-01BA03", "LGA-8_3x5mm_P1.25mm"): ("C15639", "MS561101BA03-50", "verified"),
    ("W25Q128JVSIQ", "SOIC-8_5.3x5.3mm_P1.27mm"): ("C97521", "W25Q128JVSIQ", "verified"),
    ("MAX-M10S", "ublox_MAX"): ("C4153167", "MAX-M10S-00B", "search"),
    ("USB-C", "USB_C_Receptacle_HRO_TYPE-C-31-M-12"): ("C165948", "TYPE-C-31-M-12",
                                                        "verified"),
    ("u.FL GNSS ant", "U.FL_Hirose_U.FL-R-SMT-1_Vertical"): ("C88373", "U.FL-R-SMT-1(10)",
                                                             "search"),
    ("SWD (ARM 10-pin 1.27mm)", "PinHeader_2x05_P1.27mm_Vertical_SMD"):
        ("C2962219", "X1270WVS-2x05B-9TV01", "search"),
    ("reset", "SW_SPST_TL3342"): ("C2918453", "TL3342F160QG/TR", "search"),
}

# Not placed by JLC.  Test points, holes and solder jumpers are copper, not parts; the
# 2.54 mm headers are through-hole and cheaper to hand-solder than to pay for THT assembly
# (and J6-J9 may want right-angle or no header at all, depending on the harness); J1 is
# two wire pads for the 18 AWG XT30 pigtail.
NOT_PLACED_PREFIX = ("TP", "MH", "JP", "NT")   # NT1 is a net tie: copper, not a part
HAND_SOLDER = {"J1", "J6", "J7", "J8", "J9", "J10"}


def run(args):
    r = subprocess.run([KC] + args, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("kicad-cli %s failed:\n%s%s" % (args[:3], r.stdout, r.stderr))
    return r.stdout


def gerbers():
    tmp = os.path.join(OUT, "gerbers")
    os.makedirs(tmp, exist_ok=True)
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    run(["pcb", "export", "gerbers", "--layers", ",".join(LAYERS), "--subtract-soldermask",
         "--check-zones", "-o", tmp + "/", BOARD])
    run(["pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th",
         "--generate-map", "--map-format", "pdf", "-u", "mm", "-o", tmp + "/", BOARD])
    z = os.path.join(OUT, "flight_computer-gerbers.zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(os.listdir(tmp)):
            zf.write(os.path.join(tmp, f), f)
    return z, sorted(os.listdir(tmp))


def placed(ref):
    return not ref.startswith(NOT_PLACED_PREFIX) and ref not in HAND_SOLDER


def bom():
    raw = os.path.join(OUT, ".bom_raw.csv")
    run(["sch", "export", "bom", "--fields", "Reference,Value,Footprint",
         "--group-by", "Value,Footprint", "--ref-range-delimiter", "", "-o", raw, SCH])
    rows, missing = [], []
    with open(raw) as f:
        for r in csv.DictReader(f):
            refs = [x for x in r["Reference"].split(",") if placed(x.strip())]
            if not refs:
                continue
            fp = r["Footprint"].split(":")[-1]
            key = (r["Value"], fp)
            if key not in PARTS:
                missing.append(key)
                continue
            lcsc, mpn, _note = PARTS[key]
            rows.append({"Comment": "%s (%s)" % (r["Value"], mpn), "Designator": ",".join(refs),
                         "Footprint": fp, "LCSC Part #": lcsc})
    os.remove(raw)
    if missing:
        raise SystemExit("no LCSC entry for: %s" % missing)
    path = os.path.join(OUT, "flight_computer-bom.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["Comment", "Designator", "Footprint", "LCSC Part #"])
        w.writeheader()
        w.writerows(rows)
    return path, rows


def cpl():
    raw = os.path.join(OUT, ".pos_raw.csv")
    run(["pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both",
         "-o", raw, BOARD])
    out = []
    with open(raw) as f:
        for r in csv.DictReader(f):
            if not placed(r["Ref"]):
                continue
            out.append({"Designator": r["Ref"], "Mid X": r["PosX"] + "mm",
                        "Mid Y": r["PosY"] + "mm",
                        "Layer": "Top" if r["Side"] == "top" else "Bottom",
                        "Rotation": "%g" % float(r["Rot"])})
    os.remove(raw)
    path = os.path.join(OUT, "flight_computer-cpl.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        w.writeheader()
        w.writerows(out)
    return path, out


def assembly_pdf():
    path = os.path.join(OUT, "flight_computer-assembly.pdf")
    run(["pcb", "export", "pdf", "--layers", "F.Fab,F.Silkscreen,Edge.Cuts",
         "--mode-single", "--include-border-title", "-o", path, BOARD])
    return path


ORDERING = """# Ordering the flight computer at JLCPCB

Generated by `scaffold/fab.py` -- edit the script, not this file.

## PCB (upload `flight_computer-gerbers.zip`)

| option | set to | why |
|---|---|---|
| layers | 4 | |
| thickness | 1.6 mm | |
| **impedance control / stackup** | **JLC04161H-7628** | the netclass widths are solved for its 0.2104 mm prepreg: GNSS_RF 0.36 mm = 50 ohm, USB 0.25/0.15 = 90 ohm diff |
| surface finish | ENIG | two LGA sensors at 0.5 mm pitch want a flat finish |
| outer copper | 1 oz | the 2.0 mm VBATT trunk is sized for 1 oz at 4.1 A |
| via covering | tented | no via-in-pad anywhere; U1's exposed pad has no via by design |
| min hole / track | 0.3 mm / 0.15 mm | inside JLC's standard (no surcharge) |

## Assembly (upload `flight_computer-bom.csv` + `flight_computer-cpl.csv`)

Top side only.  61 parts placed.  **Check every rotation in JLC's placement preview** --
KiCad's and JLC's zero-orientation conventions disagree for some packages, and nothing in
this script can see JLC's library.  The ones worth a hard look: U1 (WSON-8), U3 (SOT-23-6),
U4/U5 (LGA -- pin 1 dot), U8 (MAX-M10S), Y1, D1/D2/D3 (polarity), J4.

Not placed by JLC -- hand-solder after:

- **J1**: two wire pads for an **18 AWG XT30 pigtail** (male XT30 on the board side;
  the pack carries the female).  Pad 1 / "+" is VBATT.  Tin the wire, push through, solder
  both sides.  Strain-relieve the lead to the sled, not to the board.
- **J6-J9** (servo, 1x3 2.54 mm) and **J10** (debug UART, 1x4): through-hole headers.
- JP1/JP2 are solder jumpers, TP1-3 test pads, MH1-4 holes: copper, not parts.

## Lines that need a decision at order time

%s

Everything else was checked on its LCSC product page (MPN, package, stock) on 2026-09-24.
"""


def ordering_md():
    lines = []
    for (value, fp), (lcsc, mpn, note) in PARTS.items():
        if note != "verified":
            lines.append("- **%s** (`%s`) -> %s %s -- %s" % (value, fp, lcsc or "(none)", mpn, note))
    extra = [
        "- **ICM-42688-P (U4)** is out of stock at LCSC.  Use JLC Global Sourcing, or "
        "consign parts.  Do not substitute the ICM-42688-V or -45686 without reading docs/14.",
        "- **LQH32PN2R2NN0L (L1)** is out of stock.  Any 2.2 uH 1210 (3.2 x 2.5 mm) power "
        "inductor with Isat >= 1.2 A and DCR <= 0.15 ohm fits the footprint and the TPS62162.",
        "- **FB1** is labelled \"600R@100MHz 2A\"; the part is 0.5 A.  FB1 carries only the "
        "logic branch (~60 mA at 7.4 V), so 8x margin.  The servos never pass through it.",
        "- **C4** is labelled 100nF/50V; C1525 is 16 V.  VIN is 8.4 V max, so 1.9x.",
        "- **Y1** is a 12 pF-load crystal on 12 pF caps (~10 pF effective with stray): a few "
        "ppm fast.  USB full-speed allows 2500 ppm.",
        "- **Blue LED (D3)**: pick any 0603 blue with Vf <= 3.0 V; R7 is 1k.",
    ]
    path = os.path.join(OUT, "ORDERING.md")
    with open(path, "w") as f:
        f.write(ORDERING % "\n".join(extra + ["", "Not individually re-checked (from search "
                                                 "results, not the product page):", ""] + lines))
    return path


def main(argv):
    # optional: fab.py BOARD OUTDIR -- for dry runs against a scratch copy of the board
    global BOARD, OUT
    if len(argv) > 2:
        BOARD, OUT = os.path.abspath(argv[1]), os.path.abspath(argv[2])
    os.makedirs(OUT, exist_ok=True)
    z, files = gerbers()
    print("gerbers:", z, "(%d files)" % len(files))
    b, rows = bom()
    print("bom:", b, "(%d lines, %d parts)" % (len(rows),
                                              sum(len(r["Designator"].split(",")) for r in rows)))
    c, pos = cpl()
    print("cpl:", c, "(%d placements)" % len(pos))
    bom_refs = {x for r in rows for x in r["Designator"].split(",")}
    cpl_refs = {p["Designator"] for p in pos}
    if bom_refs != cpl_refs:
        raise SystemExit("BOM/CPL mismatch: bom-only %s, cpl-only %s"
                         % (sorted(bom_refs - cpl_refs), sorted(cpl_refs - bom_refs)))
    print("assembly drawing:", assembly_pdf())
    print("ordering notes:", ordering_md())
    flagged = [(k, v) for k, v in PARTS.items() if v[2] != "verified"]
    print("lines not fully verified on LCSC: %d (see ORDERING.md)" % len(flagged))


if __name__ == "__main__":
    main(sys.argv)
