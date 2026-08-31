"""Allowables, in one place, so that arguing with a number moves every conclusion at once.

`design/hinge.py` states its bearing and shaft allowables at the top of the file for
exactly this reason, and the moment a SECOND file needed the same fiberglass numbers --
`tube_section.py` for the airframe bore, `hinge.py` for the canard panel that the shaft
plugs into -- keeping them in either one of those files would have meant two copies. Six
scripts once each carried their own copy of the baseline vehicle and reconciling the drift
cost a day (see configure.py). This file is that lesson applied to materials.

THE CAVEAT ON THE FIBERGLASS NUMBERS. These are NEMA G-10 / FR-4 SHEET properties. A
filament wound airframe tube is not sheet: a +/-45 deg wind is stiffer in torsion and
weaker in axial than these, and a hand-rolled or pultruded tube is different again. The
project has only ever committed to one material fact, the 1850 kg/m^3 density in
`configure.py`. So treat every fiberglass margin as indicative until a real tube is bought
and its datasheet read. The convention adopted here: if a margin computed against these
lands under 4x, stop and get the real numbers rather than believing the third digit.
"""

from __future__ import annotations

# --- fiberglass laminate, G-10 / FR-4 class -------------------------------------------
G10_COMPRESSIVE = 310.0e6   # Pa, edgewise / in-plane
G10_TENSILE = 280.0e6       # Pa, in-plane
G10_FLEXURAL = 480.0e6      # Pa, lengthwise flexural
G10_BEARING = 370.0e6       # Pa, pin bearing on a hole
G10_SHEAR = 130.0e6         # Pa, edgewise shear
G10_INTERLAMINAR_SHEAR = 35.0e6  # Pa; also the practical ceiling on a G10-to-G10 epoxy bond
G10_MODULUS = 18.0e9        # Pa, in-plane tensile

# The margin below which the sheet properties above stop being good enough to quote.
DATASHEET_CONFIDENCE_MARGIN = 4.0

# --- metals, for shafts and tangs ------------------------------------------------------
# Yield strengths. The shaft is small and highly stressed where it leaves the tube.
#
# THE PROJECT SELECTS 6061-T6, and this comment used to muse that "303 stainless is the
# sensible part to buy" -- which was never a decision, but it was the only thing in the
# repo agreeing with the CAD, where the shafts sat in 300-series stainless for months
# against docs/04, docs/05 and an explicit instruction saying aluminium. Settled Aug 2026:
#   * better margin. 34.4 MPa of sleeve bending is 8.0x on 6061-T6 and 7.0x on 303;
#   * 15.4 g lighter across four shafts, at nearly the module's full radius, on the roll
#     axis this vehicle actually flies;
#   * far easier to cut. The shaft has a 1.8 mm tang and a 0.95 mm wall around the spline
#     socket, and those are not features you want to take in stainless.
# The one thing stainless would have been better at is the anaerobic retaining compound in
# that socket: steel is an active metal and cures it, 6061 is passive and needs a primer.
# That is a bottle of primer, not a material choice. See design/hinge.py "THE COUPLING".
SHAFT_YIELD = {"6061-T6": 276.0e6, "303 stainless": 240.0e6, "4140 steel": 655.0e6}

# --- FDM print materials, for the canard bay ---------------------------------------------
# THE SAME CAVEAT AS THE FIBERGLASS, ONLY WORSE. A printed part is not a moulded coupon:
# published figures are injection-moulded test bars, and an FDM part typically reaches
# 50-80% of them IN PLANE and far less ACROSS the layers. The numbers below are already
# knocked down toward what a well-tuned printer produces at 100% infill with the load in
# the layer plane. They are for choosing BETWEEN materials and for finding out whether a
# margin is 2x or 20x; they are not for quoting a third digit.
#
# THE LOAD DIRECTION IS THE WHOLE REASON THIS IS USABLE. The bay is printed with the rocket
# axis vertical, so the layers lie in planes normal to that axis. The canard panel's normal
# force is CIRCUMFERENTIAL (the panel is a plate in the axis-radius plane, so deflecting it
# throws lift sideways), which means the couple it hands the collar presses on the bore
# IN THE LAYER PLANE. Print it any other way and the governing property becomes interlayer
# strength, which is roughly half of these and much less repeatable.
#
# PLA is deliberately absent: ~55 C heat deflection is below what a dark airframe reaches
# sitting on a pad, and this part holds the hinge alignment.
class PrintMaterial:
    def __init__(self, name: str, modulus: float, compressive: float,
                 heat_deflection_c: float, note: str = ""):
        self.name = name
        self.modulus = modulus            # Pa, in-plane tensile
        self.compressive = compressive    # Pa, in-plane compressive / bearing
        self.heat_deflection_c = heat_deflection_c
        self.note = note

    def __repr__(self) -> str:
        return f"PrintMaterial({self.name!r})"


PRINT_MATERIALS: dict[str, PrintMaterial] = {
    "PETG": PrintMaterial("PETG", 1.7e9, 50.0e6, 70.0,
                          "cheapest, prints on anything, lowest stiffness"),
    "ASA": PrintMaterial("ASA", 2.0e9, 55.0e6, 95.0,
                         "UV and heat tolerant; wants an enclosure"),
    "PETG-CF": PrintMaterial("PETG-CF", 4.5e9, 65.0e6, 75.0,
                             "chopped carbon; needs a hardened nozzle"),
    "PA6-CF": PrintMaterial("PA6-CF", 6.0e9, 90.0e6, 140.0,
                            "stiffest and most dimensionally stable, but hygroscopic "
                            "-- dry it or the bore moves"),
}

# The bay material the project selects. See design/bay.py for why stiffness, not strength,
# is the property that decides this: the collar shares a bearing seat with a G10 wall 10x
# stiffer than PETG, and load goes where the stiffness is.
BAY_MATERIAL = "PETG-CF"

# --- adhesives for the shaft-to-spline coupling ------------------------------------------
# ANAEROBIC RETAINING COMPOUND is the product category designed for exactly this joint: a
# cylindrical slip fit that has to transmit torque. Loctite 603/638 class. Quoted shear
# strengths run 17-25 MPa on steel; 17 is taken here because the shaft is aluminium and
# because a quoted adhesive number and a joint made by a student in a garage are different
# things.
#
# TWO PROPERTIES THAT DECIDE THE DESIGN, neither of them strength:
#   * it fills a SMALL gap -- best under about 0.1 mm on the radius, and it is a different
#     product from a structural epoxy, which wants a thicker bond line. That sets the
#     socket diameter, not the stress.
#   * it RELEASES at about 250 C. That is the only reason the servo is serviceable at all
#     once its shaft is bonded on, so it is a requirement and not a footnote.
#
# Anaerobics cure by contact with active metal ions. Steel and brass are active; ALUMINIUM
# IS PASSIVE and cures slowly or not at all without an activator/primer. The servo spline
# is steel and the shaft is 6061, so this joint has one of each -- use the primer.
RETAINING_COMPOUND_SHEAR = 17.0e6       # Pa
RETAINING_COMPOUND_MAX_RADIAL_GAP = 0.10e-3  # m
RETAINING_COMPOUND_RELEASE_C = 250.0

# The alternative, for a joint made without primer: a two-part structural epoxy. Stronger
# on paper, wants a thicker bond line, and does NOT come apart again.
STRUCTURAL_EPOXY_SHEAR = 25.0e6         # Pa

# --- polymer plain bearing --------------------------------------------------------------
# Static permissible surface pressure for a polymer plain bearing on a hard shaft.
# 80 MPa is the igus iglidur G class; iglidur J is 35 MPa and iglidur X is ~150 MPa.
BEARING_PRESSURE_LIMIT = 80.0e6  # Pa
BUSHING_MODULUS = 3.0e9          # Pa, iglidur G class
