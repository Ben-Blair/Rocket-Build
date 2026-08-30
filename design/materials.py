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
# Yield strengths. The shaft is small and highly stressed where it leaves the tube;
# 6061-T6 works but 303 stainless is the sensible part to buy for a 7 mm long journal.
SHAFT_YIELD = {"6061-T6": 276.0e6, "303 stainless": 240.0e6, "4140 steel": 655.0e6}

# --- polymer plain bearing --------------------------------------------------------------
# Static permissible surface pressure for a polymer plain bearing on a hard shaft.
# 80 MPa is the igus iglidur G class; iglidur J is 35 MPa and iglidur X is ~150 MPa.
BEARING_PRESSURE_LIMIT = 80.0e6  # Pa
BUSHING_MODULUS = 3.0e9          # Pa, iglidur G class
