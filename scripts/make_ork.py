"""Generate an OpenRocket .ork file from the frozen baseline design.

Run:  python scripts/make_ork.py [-o out/RocketSenior.ork]

An .ork is a zip archive containing a single `rocket.ork` XML document. This writes one
directly from `DesignParams`, so the OpenRocket model cannot drift away from the Python
model -- regenerate it whenever the design changes rather than editing geometry by hand in
the GUI.

What is being cross-checked, and what is not
--------------------------------------------
The point of building this model is to check the *aerodynamics* against an independent
Barrowman implementation. The margin Monte Carlo in scripts/robustness.py found that CP
prediction error dominates every other uncertainty in the design, and nothing in the
Python tool can find an error in the Python tool.

So the mass budget is transferred faithfully -- every subsystem goes in as a mass
component at the same station this tool uses. That is deliberate. If OpenRocket used its
own mass assumptions, a static margin disagreement would blend CP error with mass error
and you could not tell which you were looking at. With mass pinned, any CP disagreement is
purely aerodynamic.

Structural mass is the exception: nose, tubes, fins and the motor mount are described
geometrically and OpenRocket computes their mass from the material density. That gives one
genuinely independent number to compare against this tool's structural estimate, without
polluting the CP comparison much.

Double counting is the thing to watch. Each budget line below is either modelled
geometrically in OpenRocket or transferred as a mass component, never both.
"""

from __future__ import annotations

import argparse
import sys
import uuid
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import mass as mass_mod
from design.packaging import SERVOS
from design.configure import (
    BASELINE_MOTOR_FILE as MOTOR_FILE,
    DesignParams,
    baseline,
    build_vehicle,
    evaluate,
)

# RASP headers carry a short vendor tag; OpenRocket's database wants the full name it
# files the motor under. Anything not listed passes through unchanged, which is the right
# failure mode -- a wrong-looking name in the dialog beats a silently wrong motor.
ORK_MANUFACTURER = {
    "CTI": "Cesaroni Technology",
    "Cesaroni": "Cesaroni Technology",
    "Aerotech": "AeroTech",
    "AeroTech": "AeroTech",
    "AT": "AeroTech",
    "Loki": "Loki Research",
    "AMW": "Animal Motor Works",
}
from design.geometry import Rocket

ROOT = Path(__file__).resolve().parents[1]

BASELINE = baseline()

FIBERGLASS = 1850.0
MOTOR_MOUNT_ID = 0.054  # 54 mm motor
MOTOR_MOUNT_WALL = 0.0015
DROGUE_DIAMETER = 0.4572  # 18 in
DROGUE_CD = 1.5
MAIN_DIAMETER = 1.524  # 60 in, one standard size up from the 57 in the sizing calls for
MAIN_CD = 2.2
MAIN_DEPLOY_ALTITUDE = 200.0  # m AGL, matches design/recovery.py
RAIL_LENGTH = 3.66
RAIL_ANGLE_DEG = 5.0
WIND_MPS = 4.47  # 10 mph


def uid(name: str) -> str:
    """Deterministic ids so regenerating the file produces a clean diff."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"rocketsenior/{name}"))


def fg(kind: str = "bulk") -> str:
    return f'<material type="{kind}" density="{FIBERGLASS}" group="Composites">Fiberglass</material>'


class Xml:
    def __init__(self) -> None:
        self.parts: list[str] = []
        self.depth = 0

    def open(self, tag: str, attrs: str = "") -> None:
        self.parts.append("  " * self.depth + f"<{tag}{(' ' + attrs) if attrs else ''}>")
        self.depth += 1

    def close(self, tag: str) -> None:
        self.depth -= 1
        self.parts.append("  " * self.depth + f"</{tag}>")

    def leaf(self, tag: str, value: object, attrs: str = "") -> None:
        text = escape(str(value))
        self.parts.append("  " * self.depth + f"<{tag}{(' ' + attrs) if attrs else ''}>{text}</{tag}>")

    def raw(self, text: str) -> None:
        for line in text.strip("\n").split("\n"):
            self.parts.append("  " * self.depth + line)

    def render(self) -> str:
        return "\n".join(self.parts) + "\n"


def locate(rocket: Rocket, station: float) -> tuple[int, float]:
    """Map an absolute station to (tube index, offset from that tube's top)."""
    for i, tube in enumerate(rocket.tubes):
        x0 = rocket.tube_station(i)
        if x0 <= station <= x0 + tube.length or i == len(rocket.tubes) - 1:
            return i, min(max(station - x0, 0.0), tube.length)
    return 0, 0.0


def fins_root_offset_guard(tube_length: float, separation: float, clearance: float = 0.030) -> float:
    """Distance back from the tube's aft end at which to anchor the forward rail button."""
    return separation + clearance


def mass_component(x: Xml, name: str, mass: float, offset: float, radius: float,
                   kind: str = "masscomponent") -> None:
    x.open("masscomponent")
    x.leaf("name", name)
    x.leaf("id", uid(f"mass/{name}"))
    x.leaf("axialoffset", f"{offset:.6f}", 'method="top"')
    x.leaf("position", f"{offset:.6f}", 'type="top"')
    x.leaf("packedlength", f"{max(0.02, min(0.12, mass * 0.15)):.4f}")
    x.leaf("packedradius", f"{radius * 0.7:.5f}")
    x.leaf("radialposition", "0.0")
    x.leaf("radialdirection", "0.0")
    x.leaf("mass", f"{mass:.6f}")
    x.leaf("masscomponenttype", kind)
    x.close("masscomponent")


def finset(x: Xml, name: str, fins, offset: float, angle_deg: float) -> None:
    x.open("trapezoidfinset")
    x.leaf("name", name)
    x.leaf("id", uid(f"fins/{name}"))
    x.leaf("instancecount", fins.count)
    x.leaf("fincount", fins.count)
    x.leaf("radiusoffset", "0.0", 'method="surface"')
    x.leaf("angleoffset", f"{angle_deg:.1f}", 'method="relative"')
    x.leaf("rotation", "0.0")
    x.leaf("axialoffset", f"{offset:.6f}", 'method="top"')
    x.leaf("position", f"{offset:.6f}", 'type="top"')
    x.leaf("finish", "normal")
    x.raw(fg())
    x.leaf("thickness", f"{fins.thickness:.5f}")
    x.leaf("crosssection", "airfoil")
    x.leaf("cant", "0.0")
    x.leaf("filletradius", "0.0")
    x.leaf("rootchord", f"{fins.root_chord:.6f}")
    x.leaf("tipchord", f"{fins.tip_chord:.6f}")
    x.leaf("sweeplength", f"{fins.sweep_length:.6f}")
    x.leaf("height", f"{fins.semispan:.6f}")
    x.close("trapezoidfinset")


def parachute(x: Xml, name: str, diameter: float, cd: float, mass: float, offset: float,
              radius: float, event: str, altitude: float = 0.0) -> None:
    x.open("parachute")
    x.leaf("name", name)
    x.leaf("id", uid(f"chute/{name}"))
    x.leaf("axialoffset", f"{offset:.6f}", 'method="top"')
    x.leaf("position", f"{offset:.6f}", 'type="top"')
    x.leaf("overridemass", f"{mass:.6f}")
    x.leaf("overridesubcomponentsmass", "false")
    x.leaf("packedlength", f"{0.10 if diameter > 1.0 else 0.05:.4f}")
    x.leaf("packedradius", f"{radius * 0.85:.5f}")
    x.leaf("radialposition", "0.0")
    x.leaf("radialdirection", "0.0")
    x.leaf("cd", f"{cd:.2f}")
    x.raw('<material type="surface" density="0.0670" group="Fabrics">Ripstop nylon</material>')
    x.leaf("deployevent", event)
    if event == "altitude":
        x.leaf("deployaltitude", f"{altitude:.1f}")
    x.leaf("deploydelay", "0.0")
    x.leaf("diameter", f"{diameter:.4f}")
    x.leaf("linecount", 8)
    x.leaf("linelength", f"{diameter * 1.0:.4f}")
    x.raw('<linematerial type="line" density="6.56168E-4" group="Custom">'
          "Spectra 200 lb</linematerial>")
    x.close("parachute")


def build_xml(params: DesignParams) -> tuple[str, dict[str, float]]:
    rocket = build_vehicle(params)
    masses = mass_mod.build_mass(
        rocket, params.motor,
        servo_mass_each=SERVOS[params.servo].mass, n_servos=params.n_canards,
        nose_ballast_kg=params.nose_ballast_kg,
        nose_ballast_station=params.nose_ballast_station,
    )
    motor = params.motor
    d = params.outer_diameter
    radius = d / 2.0
    config = uid("config/j449")

    by_name = {item.name: item for item in masses.items}

    # Split the budget between "OpenRocket computes this from geometry" and "transfer as a
    # mass component". Anything modelled geometrically below is excluded from the
    # transferred list so it is not counted twice.
    mount_length = motor.length + 0.01
    mount_outer_r = MOTOR_MOUNT_ID / 2.0 + MOTOR_MOUNT_WALL
    mount_tube_mass = (
        FIBERGLASS * 3.141592653589793
        * (mount_outer_r**2 - (MOTOR_MOUNT_ID / 2.0) ** 2) * mount_length
    )

    chute_mass = (
        mass_mod.DEFAULT_RECOVERY_BUDGET["drogue_chute"]
        + mass_mod.DEFAULT_RECOVERY_BUDGET["main_chute"]
    )

    # Fin panels are modelled geometrically, but this tool doubles panel mass to account
    # for tabs and internal fillets. Transfer only that extra half.
    def fin_extra(fins) -> float:
        return fins.count * fins.planform_area_single * fins.thickness * fins.material_density

    # Nose ballast is a real lump of steel at a known station, so it must reach OpenRocket
    # like any other transferred mass. Omitting it silently biases the CG comparison.
    ballast: list[tuple[str, float, float]] = (
        [("Nose ballast", by_name["nose ballast"].mass, by_name["nose ballast"].x)]
        if "nose ballast" in by_name else []
    )

    transfers: list[tuple[str, float, float]] = ballast + [
        ("Avionics bay", by_name["avionics bay (budget)"].mass, by_name["avionics bay (budget)"].x),
        ("Recovery hardware", by_name["recovery (budget)"].mass - chute_mass,
         by_name["recovery (budget)"].x),
        ("Canard servos x4", by_name["canard servos x4"].mass, by_name["canard servos x4"].x),
        ("Canard shafts, bearings, sled", by_name["canard shafts/bearings/sled"].mass,
         by_name["canard shafts/bearings/sled"].x),
        ("Couplers and bulkheads", by_name["structure: couplers_bulkheads"].mass,
         by_name["structure: couplers_bulkheads"].x),
        ("Motor mount rings and retainer",
         by_name["structure: motor_mount_centering_rings"].mass - mount_tube_mass,
         by_name["structure: motor_mount_centering_rings"].x),
        ("Fasteners", by_name["structure: rail_buttons_fasteners"].mass,
         by_name["structure: rail_buttons_fasteners"].x),
        ("Epoxy and fillets", by_name["structure: epoxy_and_fillets"].mass,
         by_name["structure: epoxy_and_fillets"].x),
        ("Aft fin tabs and hardware", fin_extra(rocket.aft_fins), rocket.aft_fins.cp_station),
        ("Canard tabs and hardware", fin_extra(rocket.canards), rocket.canards.cp_station),
        ("Mass contingency 10%", by_name["contingency"].mass, by_name["contingency"].x),
    ]

    # Bucket the transferred masses by which component they land in. Stations forward of
    # the first body tube belong to the nose cone; locate() cannot express that.
    nose_masses: list[tuple[str, float, float]] = []
    per_tube: dict[int, list[tuple[str, float, float]]] = {i: [] for i in range(len(rocket.tubes))}
    for name, m, station in transfers:
        if m <= 0:
            continue
        if station < rocket.tube_station(0):
            nose_masses.append((name, m, min(station, rocket.nose.length)))
            continue
        i, off = locate(rocket, station)
        per_tube[i].append((name, m, off))

    x = Xml()
    x.raw("<?xml version='1.0' encoding='utf-8'?>")
    x.open("openrocket", 'version="1.10" creator="RocketSenior scripts/make_ork.py"')
    x.open("rocket")
    x.leaf("name", "RocketSenior canard testbed")
    x.leaf("id", uid("rocket"))
    x.leaf("axialoffset", "0.0", 'method="absolute"')
    x.leaf("position", "0.0", 'type="absolute"')
    x.leaf(
        "comment",
        "Generated by scripts/make_ork.py -- do not edit geometry here, edit DesignParams "
        "and regenerate.\n\n"
        "Subsystem masses are transferred from the Python mass budget as mass components "
        "so that any static margin disagreement is attributable to aerodynamics rather "
        "than to differing mass assumptions. Structural mass (nose, tubes, fins, motor "
        "mount) is left for OpenRocket to compute from geometry and material density.\n\n"
        "The canards are the forward fin set, interdigitated 45 degrees from the aft fins. "
        "OpenRocket's Barrowman implementation does not model fin-to-fin interference, so "
        "it will not reproduce the roll coupling analysis -- that lives in design/control.py.",
    )
    x.leaf("designer", "RocketSenior")
    x.leaf("revision", "baseline")
    x.open("motorconfiguration", f'configid="{config}" default="true"')
    x.raw('<stage number="0" active="true"/>')
    x.close("motorconfiguration")
    x.leaf("referencetype", "maximum")

    x.open("subcomponents")
    x.open("stage")
    x.leaf("name", "Sustainer")
    x.leaf("id", uid("stage"))
    x.open("subcomponents")

    # ---- nose cone
    x.open("nosecone")
    x.leaf("name", "Nose cone")
    x.leaf("id", uid("nose"))
    x.leaf("finish", "normal")
    x.raw(fg())
    x.leaf("length", f"{rocket.nose.length:.6f}")
    x.leaf("thickness", f"{rocket.nose.wall_thickness:.5f}")
    x.leaf("shape", "ogive")
    x.leaf("shapeparameter", "1.0")
    x.leaf("aftradius", f"{radius:.5f}")
    x.leaf("aftshoulderradius", f"{radius - params.wall_thickness:.5f}")
    x.leaf("aftshoulderlength", "0.070")
    x.leaf("aftshoulderthickness", f"{params.wall_thickness:.5f}")
    x.leaf("aftshouldercapped", "true")
    x.leaf("isflipped", "false")
    # Anything stationed inside the nose cone (the ballast stack) is a child of it.
    # locate() only searches body tubes, so without this the mass would fall through to
    # its last-tube fallback and land ~750 mm aft of where it actually sits.
    if nose_masses:
        x.open("subcomponents")
        for name, m, station in nose_masses:
            mass_component(x, name, m, station, radius)
        x.close("subcomponents")
    x.close("nosecone")

    # ---- body tubes
    canard_tube, canard_off = locate(rocket, rocket.canards.x_root_le)
    aft_tube, aft_off = locate(rocket, rocket.aft_fins.x_root_le)
    labels = {"nav bay": "Nav bay", "canard module": "Canard module",
              "recovery bay": "Recovery bay", "booster": "Booster"}

    for i, tube in enumerate(rocket.tubes):
        x.open("bodytube")
        x.leaf("name", labels.get(tube.name, tube.name))
        x.leaf("id", uid(f"tube/{tube.name}"))
        x.leaf("finish", "normal")
        x.raw(fg())
        x.leaf("length", f"{tube.length:.6f}")
        x.leaf("thickness", f"{tube.wall_thickness:.5f}")
        x.leaf("radius", f"{radius:.5f}")
        x.open("subcomponents")

        if i == canard_tube:
            finset(x, "Canards", rocket.canards, canard_off, 45.0)

        if i == aft_tube:
            # Motor mount, sitting at the aft end of the booster.
            x.open("innertube")
            x.leaf("name", "Motor mount tube")
            x.leaf("id", uid("mount"))
            x.leaf("axialoffset", "0.0", 'method="bottom"')
            x.leaf("position", "0.0", 'type="bottom"')
            x.raw(fg())
            x.leaf("length", f"{mount_length:.6f}")
            x.leaf("radialposition", "0.0")
            x.leaf("radialdirection", "0.0")
            x.leaf("outerradius", f"{mount_outer_r:.5f}")
            x.leaf("thickness", f"{MOTOR_MOUNT_WALL:.5f}")
            x.leaf("clusterconfiguration", "single")
            x.leaf("clusterscale", "1.0")
            x.leaf("clusterrotation", "0.0")
            x.open("motormount")
            x.leaf("ignitionevent", "automatic")
            x.leaf("ignitiondelay", "0.0")
            x.leaf("overhang", "0.0")
            x.open("motor", f'configid="{config}"')
            x.leaf("type", "reload")
            # DERIVED, NOT TYPED. These were hardcoded to the J449 and silently described
            # the wrong motor the moment design/configure.py froze a different one.
            x.leaf("manufacturer", ORK_MANUFACTURER.get(
                motor.manufacturer, motor.manufacturer or "Unknown"))
            x.leaf("designation", MOTOR_FILE.stem.split("_", 1)[-1])
            x.leaf("diameter", "0.054")
            x.leaf("length", f"{motor.length:.3f}")
            x.leaf("delay", "none")
            x.close("motor")
            x.open("ignitionconfiguration", f'configid="{config}"')
            x.leaf("ignitionevent", "automatic")
            x.leaf("ignitiondelay", "0.0")
            x.close("ignitionconfiguration")
            x.close("motormount")
            x.close("innertube")

            finset(x, "Aft fins", rocket.aft_fins, aft_off, 0.0)

            # Instances step aft from the anchor rather than straddling it, so anchor the
            # forward button explicitly and keep the pair inside the booster.
            button_sep = 0.200
            button_fwd = tube.length - fins_root_offset_guard(tube.length, button_sep)
            x.open("railbutton")
            x.leaf("name", "Rail buttons")
            x.leaf("id", uid("railbutton"))
            x.leaf("instancecount", "2")
            x.leaf("instanceseparation", f"{button_sep:.3f}")
            x.leaf("angleoffset", "0.0", 'method="relative"')
            x.leaf("axialoffset", f"{button_fwd:.4f}", 'method="top"')
            x.leaf("position", f"{button_fwd:.4f}", 'type="top"')
            x.leaf("finish", "normal")
            x.raw('<material type="bulk" density="1420.0" group="Plastics">Delrin</material>')
            x.leaf("outerdiameter", "0.0159")
            x.leaf("innerdiameter", "0.0095")
            x.leaf("height", "0.0120")
            x.leaf("baseheight", "0.0020")
            x.leaf("flangeheight", "0.0020")
            x.close("railbutton")

        if tube.name == "recovery bay":
            parachute(x, "Drogue 18 in", DROGUE_DIAMETER, DROGUE_CD,
                      mass_mod.DEFAULT_RECOVERY_BUDGET["drogue_chute"],
                      0.05, radius, "apogee")
            parachute(x, "Main 60 in", MAIN_DIAMETER, MAIN_CD,
                      mass_mod.DEFAULT_RECOVERY_BUDGET["main_chute"],
                      tube.length * 0.55, radius, "altitude", MAIN_DEPLOY_ALTITUDE)

        for name, m, off in per_tube[i]:
            mass_component(x, name, m, off, radius)

        x.close("subcomponents")
        x.close("bodytube")

    x.close("subcomponents")
    x.close("stage")
    x.close("subcomponents")
    x.close("rocket")

    # ---- simulation
    x.open("simulations")
    x.open("simulation", 'status="notsimulated"')
    x.leaf("name", "Baseline J449")
    x.leaf("simulator", "RK4Simulator")
    x.leaf("calculator", "BarrowmanCalculator")
    x.open("conditions")
    x.leaf("configid", config)
    x.leaf("launchrodlength", f"{RAIL_LENGTH:.3f}")
    x.leaf("launchintowind", "true")
    x.leaf("launchrodangle", f"{RAIL_ANGLE_DEG:.1f}")
    x.leaf("launchroddirection", "90.0")
    x.leaf("windaverage", f"{WIND_MPS:.2f}")
    x.leaf("windturbulence", "0.1")
    x.leaf("winddirection", "1.5707963267948966")
    x.leaf("launchaltitude", "0.0")
    x.leaf("launchlatitude", "40.0")
    x.leaf("launchlongitude", "-105.0")
    x.leaf("geodeticmethod", "spherical")
    x.raw('<atmosphere model="isa"/>')
    x.leaf("timestep", "0.01")
    x.leaf("maxtime", "1200.0")
    x.close("conditions")
    x.close("simulation")
    x.close("simulations")
    x.close("openrocket")

    transferred = sum(m for _, m, _ in transfers if m > 0)
    summary = {
        "transferred_mass": transferred,
        "mount_tube_mass": mount_tube_mass,
        "python_dry": masses.dry_mass,
        "python_wet": masses.wet_mass,
        "python_dry_cg": masses.dry_cg,
        "python_wet_cg": masses.wet_cg,
    }
    return x.render(), summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", default="out/RocketSenior.ork")
    args = ap.parse_args()

    xml, summary = build_xml(BASELINE)
    out = ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("rocket.ork", xml)

    ev = evaluate(BASELINE, deflection_deg=8.0)
    r = ev.rocket
    print(f"wrote {out.relative_to(ROOT)}  ({out.stat().st_size / 1024:.1f} kB)\n")
    print("Transferred from the Python mass budget as mass components:")
    print(f"  {summary['transferred_mass']:.3f} kg")
    print("Left for OpenRocket to compute from geometry:")
    print("  nose, 4 body tubes, both fin sets, motor mount tube, rail buttons, canopies\n")
    print("Compare these against OpenRocket once it opens the file:\n")
    print(f"  {'quantity':28s} {'this tool':>12s}   OpenRocket")
    print(f"  {'-' * 28} {'-' * 12}   {'-' * 12}")
    print(f"  {'dry mass':28s} {summary['python_dry']:9.3f} kg")
    print(f"  {'wet mass (loaded)':28s} {summary['python_wet']:9.3f} kg")
    print(f"  {'CG, dry, from nose':28s} {summary['python_dry_cg'] * 1000:9.1f} mm")
    print(f"  {'CG, loaded, from nose':28s} {summary['python_wet_cg'] * 1000:9.1f} mm")
    print(f"  {'CP, subsonic, from nose':28s} "
          f"{__import__('design.aero', fromlist=['x']).stability(r, summary['python_wet_cg'], 0.1).cp_station * 1000:9.1f} mm")
    print(f"  {'static margin, loaded':28s} {ev.flight.min_static_margin:9.2f} cal")
    print(f"  {'apogee':28s} {ev.flight.apogee:9.0f} m")
    print(f"  {'max Mach':28s} {ev.flight.max_mach:9.3f}")
    print(f"  {'rail exit velocity':28s} {ev.flight.rail_exit_velocity:9.1f} m/s")
    print("""
Open it with:  open -a OpenRocket out/RocketSenior.ork

First thing to check: that the motor resolved. If the motor mount shows no motor, open the
motor selection dialog and pick it by hand -- OpenRocket matches on its own internal
digest and the designation string here may not match your database version.

Then compare CP. That number is the whole reason this file exists: it is the single
largest uncertainty in the design and the only way to attack it is a second opinion.""")


if __name__ == "__main__":
    main()
