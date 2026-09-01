"""Static ports and bay vents: which volumes the altimeter is allowed to sense.

WHY THIS IS A SEPARATE MODULE FROM `seal.py`. The seal answers "what holds the pressure
back". This answers "where is the pressure allowed to go", and the second question turned
out to have a better answer than the first one assumed.

THE CORRECTION THIS FILE EXISTS TO RECORD.

`design/seal.py` argued -- and `docs/05` was written to say -- that the canard module has
"exactly two faces it could breathe through", that it must not be the aft one because that
is where the ejection charge fires, and that it therefore vents FORWARD into the nav bay,
which makes the module part of the altimeter's static volume.

The first half is right and the conclusion is wrong, because **a bay is not a box with two
faces. It is a cylinder, and the third surface is the wall.** Every other bay in high-power
rocketry vents through its own wall; this one has four dia 8 mm bores through that wall
already. Two dia 2 mm holes cost nothing and change the architecture:

  * the module is **not** in the altimeter's sense volume, so the nav bay's ports are sized
    for the nav bay and nothing else;
  * a leak past the aft gas seal goes overboard through the module's own vents instead of
    into the pressure sensor that fires the charges;
  * the wiring pass-through can then be **potted solid** around the wires, which is a better
    seal than one that has to pass air.

The framing is what went wrong, not any number. "It has two faces, and one of them is
disqualified" is a complete-sounding argument that silently excluded the answer. Same shape
as correction 1 -- the servo was assumed to point inward, and every conclusion after that
was sound.

WHAT A STATIC PORT IS FOR, AND WHAT THIS MODEL FOUND OUT ABOUT IT.

The altimeter measures ambient pressure to get altitude. It sits inside a sealed bay, so the
bay has to track the outside air. Too small and the bay lags -- and the case that matters is
not the ascent, it is the DESCENT, because a bay that lags on the way down fires the main
below the 200 m it was set for, and there is no margin under 200 m. That is the failure this
model was written to size against.

**It does not bind, and by a factor of about 300.** The nav bay holds 303 cm3 of air and the
pressure changes at about 2 kPa/s at burnout; the lag budget below is met by 4 holes of
0.65 mm, while convention on an airframe this size is 3 holes of 3.2 mm -- eighteen times
the area, three hundred times the margin. Any drillable hole passes.

So the honest statement is that **the port size is set by convention and not by this model,
and the model's job was to find that out**. This project counts a check that confirms as a
result (docs/01: "two of the rest are checks that CONFIRMED it, which is its own kind of
result"), and the confirmation is worth having, because "the bay must breathe fast enough"
is the reason everyone gives for these holes and it turns out not to be the reason.

What actually decides the size, once lag is off the table, is a set of things none of which
has a model here: the hole must be big enough to survive a bit of tape, paint or a wasp; it
must be small enough that the ejection transient and the local flow field do not drive the
sensed pressure; and it must be drillable and deburrable by hand. Convention encodes all
three. Hence a floor from the model, a ceiling from practice, and a design point at the
ceiling.

WHAT THIS DOES NOT DO. It does not model the flow disturbance around the port, which is why
the upper bound comes from convention rather than from theory. It does not model the
transient of the ejection event. And it says nothing about where the NAV BAY's ports go
beyond the ring rule below, because that placement is about the local pressure coefficient
and this project has no panel-method model of its own airframe. The CANARD MODULE's vents
are placed here -- see MODULE_VENT_STATION -- and they can be, precisely because that bay
feeds no sensor and so no Cp argument is needed to put a hole in it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import atmosphere

# Discharge coefficient of a plain drilled hole in a thin wall. 0.6-0.65 is the standard
# range for a sharp-edged orifice; 0.62 is taken. It is not worth arguing about -- the
# answer goes as 1/Cd and every other input here is softer than that.
DISCHARGE_COEFFICIENT = 0.62

# THE ERROR BUDGET. The bay may lag ambient by the pressure equivalent of this much altitude.
# 3 m is tight against what a barometric altimeter achieves in the real world anyway, and it
# is deliberately tight because the consequence is asymmetric: lag on the way down fires the
# main LOW.
#
# It turns out not to matter what this number is. The conventional port passes it 300x over,
# so anything from 0.5 m to 30 m selects the same hardware. That is worth knowing before
# anyone spends an afternoon defending the value.
ALLOWABLE_LAG_ALTITUDE = 3.0  # m

# Convention, and it is what actually selects the part. Common practice on a 3-4 inch
# airframe is three or four holes of 1/8 in (3.2 mm). That is eighteen times the area the lag
# model asks for, which is not a contradiction: practice is sizing for blockage tolerance,
# for the ejection transient, and for what a person can drill and deburr by hand -- none of
# which is modelled here. The model gives the FLOOR, convention gives the DESIGN POINT.
CONVENTIONAL_PORT_DIAMETER = 0.0032  # m
CONVENTIONAL_PORT_COUNT = 3

# Ports go in a ring, not in a line, so that the bay reads an average and not one point of a
# flow field that is asymmetric whenever the vehicle is at an angle of attack. Three is the
# minimum that averages; four is easier to lay out on a 90 degree pattern.
MIN_PORT_COUNT = 3


# ======================================================================================
# WHERE THE CANARD MODULE'S OWN VENTS GO
#
# The header of this file says it "says nothing about port PLACEMENT". That was true and it
# was a gap, not a boundary: the module vent was decided as a SIZE (2 x dia 2 mm) and a
# SURFACE (its own wall) and then handed to CAD with no station and no clocking, which is
# not something a hole can be drawn from. Settled here.
#
# THE RULE THAT GOVERNS THE NAV BAY DOES NOT GOVERN THIS ONE, and that is the whole reason
# it can be settled without a panel-method model. The nav bay's ports feed a PRESSURE
# SENSOR, so they have to sit where local static approximates freestream, and getting that
# wrong fires a charge at the wrong altitude. The canard module's vent feeds nothing. Its
# job is that the module not be a sealed volume -- `trapped_differential` below is the
# entire load case, 8 kPa and about 350 N on a bulkhead. A local Cp error moves a number
# that nothing reads. So placement here is set by what is INSIDE the tube and by the leak
# path, both of which are known exactly.
#
# STATION. The module tube runs Z 0 -> 142.900 from its forward face. Two bands of wall
# have nothing bonded behind them: forward of the printed bay (Z < 53.13) and aft of it
# (Z > 94.63, up to the aft gas seal's fillet at ~135.1). The aft band wins, and the
# argument is the leak path rather than the flow field.
#
# design/seal.py's stated intent is that a leak past the aft gas seal "goes overboard
# instead of into the sensor that fires the charges". For that to be true the leaked gas
# has to REACH a vent. Vent the forward band only, and the escape path for hot, sooty
# ejection gas runs the full length of the module -- across four servos, the printed bay
# and every wire in the vehicle -- before it finds a hole. Vent the aft band and the path
# is a couple of centimetres of empty tube. The seal's argument was written as if the
# module had a vent somewhere; WHERE turns out to be load-bearing for it.
#
# Z = 120.0 mm places the ring:
#   * 25.4 mm aft of the printed bay's aft face -- clear of that bond line
#   * 12.1 mm forward of the seal's forward fillet -- clear of that one. (That figure came
#     out of seal.stack_length(), not off a ruler: the first pass here assumed a 4.8 mm disc
#     plus 3 mm of fillet and got 15.1 mm, when the assembled stack is 10.8. The clearance
#     is comfortable either way, which is exactly when a wrong number survives.)
#   * 14.8 mm aft of the canard root trailing edge (Z 105.20), so it is outside the panel's
#     surface footprint and not under the root bond
#   * 51.7 mm from the hinge bore station (Z 68.27), so its stress concentration does not
#     stack with the four dia 8 bores that already remove 13.2% of that section
MODULE_VENT_STATION = 0.120        # m, from the canard module's FORWARD face
MODULE_VENT_DIAMETER = 0.002       # m
MODULE_VENT_COUNT = 2

# CLOCKING. 45 and 225 degrees: diametrically opposed, and each bisecting the gap between
# two canard panels (the canards sit at 0/90/180/270).
#
# Opposed rather than adjacent for the ordinary reason -- two holes 180 degrees apart mean
# the module still breathes with the vehicle at any roll angle, and one hole blocked by
# paint, tape or a scrap of wadding still leaves one. This is blockage tolerance, which is
# the same thing CONVENTIONAL_PORT_COUNT above is really buying.
#
# Note that MIN_PORT_COUNT = 3 does NOT apply here and the two are not in conflict. Three is
# the minimum that AVERAGES a flow field, and averaging is a requirement only for a bay that
# is being measured. Two is enough for a bay that is only being equalised.
MODULE_VENT_CLOCKING_DEG = (45.0, 225.0)


def module_vent_clearances(station: float, bay_aft: float, seal_fillet_forward: float,
                           canard_root_te: float, hinge_station: float) -> dict[str, float]:
    """Signed clearances, m, from the module vent station to everything it must miss.

    Every argument is a station read off the real geometry by the caller -- the printed bay
    from `design/bay.py`, the seal from `design/seal.py`, the canard root and hinge from the
    vehicle -- so that this cannot agree with itself while disagreeing with the CAD. That is
    correction 14's failure mode and it is the one this project keeps repeating.

    Positive means clear. A negative entry means the hole lands ON the thing named.
    """
    return {
        "aft of the printed bay": station - bay_aft,
        "forward of the seal fillet": seal_fillet_forward - station,
        "aft of the canard root TE": station - canard_root_te,
        "from the hinge bore station": abs(station - hinge_station),
    }


def pressure_lapse(altitude: float) -> float:
    """dP/dh at `altitude`, Pa per metre. Negative going up; the magnitude is returned."""
    _, _, rho, _ = atmosphere.properties(altitude)
    return rho * atmosphere.G0


def lag_pressure(altitude: float, lag_altitude: float = ALLOWABLE_LAG_ALTITUDE) -> float:
    """The pressure error that `lag_altitude` of altitude error corresponds to, Pa."""
    return pressure_lapse(altitude) * lag_altitude


@dataclass(frozen=True)
class VentedBay:
    """A sealed volume that has to track ambient through a set of drilled ports."""

    name: str
    volume: float  # m^3, FREE volume -- what the air actually occupies
    n_ports: int
    port_diameter: float  # m

    @property
    def area(self) -> float:
        return self.n_ports * math.pi * self.port_diameter**2 / 4.0

    def lag(self, altitude: float, climb_rate: float) -> float:
        """Steady-state pressure lag, Pa, at a given altitude and vertical speed.

        The bay is a volume behind an orifice. In steady climb the flow through the port has
        to carry the mass the bay's own compression demands, so the lag settles where

            V/P * dP/dt  =  Cd * A * sqrt(2 dP / rho)

        Isothermal, quasi-steady, incompressible through the orifice. All three are the
        usual approximations, all three are good while dP is a fraction of a percent of P,
        and dP here is about 0.03%. The one to watch is not any of them: it is that the
        model assumes the port is the only leak, when a real bay also leaks around every
        joint. A bay that leaks tracks BETTER, so this is the conservative direction.
        """
        _, p_amb, rho, _ = atmosphere.properties(altitude)
        dpdt = pressure_lapse(altitude) * climb_rate
        if self.area <= 0.0:
            return float("inf")
        q = self.volume * dpdt / p_amb  # volumetric flow the bay demands, m^3/s
        v = q / (DISCHARGE_COEFFICIENT * self.area)  # through the port, m/s
        return 0.5 * rho * v**2

    def lag_altitude(self, altitude: float, climb_rate: float) -> float:
        """The same lag expressed as metres of altitude error."""
        return self.lag(altitude, climb_rate) / pressure_lapse(altitude)


def port_area_for_lag(volume: float, altitude: float, climb_rate: float,
                      lag_altitude: float = ALLOWABLE_LAG_ALTITUDE) -> float:
    """Total port area, m^2, that keeps the lag inside `lag_altitude`. Inverse of `lag()`."""
    _, p_amb, rho, _ = atmosphere.properties(altitude)
    dpdt = pressure_lapse(altitude) * climb_rate
    dp = lag_pressure(altitude, lag_altitude)
    q = volume * dpdt / p_amb
    return q / (DISCHARGE_COEFFICIENT * math.sqrt(2.0 * dp / rho))


def size_ports(volume: float, altitude: float, climb_rate: float,
               n_ports: int = 4, lag_altitude: float = ALLOWABLE_LAG_ALTITUDE) -> float:
    """Port diameter, m, for `n_ports` holes meeting the lag budget."""
    area = port_area_for_lag(volume, altitude, climb_rate, lag_altitude)
    return math.sqrt(4.0 * area / (n_ports * math.pi))


def trapped_differential(sea_level_pressure_altitude: float, apogee: float) -> float:
    """Pressure a bay sealed at the pad carries at apogee, Pa.

    The reason a bay that contains nothing delicate still needs a vent. It is not a large
    number and it is not what sizes anything, but it is the number people are surprised by,
    so it is computed rather than asserted.
    """
    _, p_pad, _, _ = atmosphere.properties(sea_level_pressure_altitude)
    _, p_apogee, _, _ = atmosphere.properties(apogee)
    return p_pad - p_apogee


@dataclass
class VentCheck:
    ok: bool
    violations: list[str]
    notes: list[str]


def check_venting(nav: VentedBay, module: VentedBay, altitude: float, climb_rate: float,
                  apogee: float, pad_altitude: float = 0.0,
                  module_wall_area: float = 0.0) -> VentCheck:
    """Both vented volumes, and the rule that keeps them separate.

    `module_wall_area` is the vent area drilled through the CANARD MODULE'S OWN WALL. It is
    an argument rather than a property of `module` because the whole point of this check is
    that the module vents somewhere other than into `nav`, and that has to be stated
    explicitly enough to fail if it is ever undone.
    """
    v: list[str] = []
    notes: list[str] = []
    mm = 1000.0

    # --- the sense volume ------------------------------------------------------------
    lag = nav.lag_altitude(altitude, climb_rate)
    if lag > ALLOWABLE_LAG_ALTITUDE:
        v.append(
            f"{nav.name}: {nav.n_ports} x dia {nav.port_diameter * mm:.1f} mm lags "
            f"{lag:.1f} m at {climb_rate:.0f} m/s, against a {ALLOWABLE_LAG_ALTITUDE:.1f} m "
            f"budget -- the main charge would fire low")
    else:
        notes.append(
            f"{nav.name} lags {lag:.2f} m at {climb_rate:.0f} m/s and "
            f"{nav.lag_altitude(apogee, 30.0):.2f} m descending at 30 m/s under drogue, "
            f"which is the case that actually matters: lag on the way DOWN fires the main "
            f"low, and there is no room below 200 m")

    if nav.n_ports < MIN_PORT_COUNT:
        v.append(
            f"{nav.name} has {nav.n_ports} port(s); at least {MIN_PORT_COUNT} in a ring, so "
            f"the bay reads an average rather than one point of an asymmetric flow field")

    conventional = (CONVENTIONAL_PORT_COUNT * math.pi
                    * CONVENTIONAL_PORT_DIAMETER**2 / 4.0)
    if nav.area > conventional:
        notes.append(
            f"{nav.name} port area {nav.area * 1e6:.1f} mm2 is above the conventional "
            f"{CONVENTIONAL_PORT_COUNT} x dia {CONVENTIONAL_PORT_DIAMETER * mm:.1f} mm "
            f"({conventional * 1e6:.1f} mm2). Bigger is not safer past this point")
    else:
        notes.append(
            f"{nav.name} port area {nav.area * 1e6:.1f} mm2 sits between the "
            f"{port_area_for_lag(nav.volume, altitude, climb_rate) * 1e6:.1f} mm2 the lag "
            f"model needs and the {conventional * 1e6:.1f} mm2 convention uses -- the model "
            f"is the floor, convention is the ceiling, and both are satisfied")

    # --- the volume that must NOT be in the sense volume -----------------------------
    if module_wall_area <= 0.0:
        v.append(
            "the canard module has no vent of its own, so it can only breathe through the "
            "wiring pass-through into the nav bay -- which puts it inside the altimeter's "
            "sense volume and makes a leak past the aft gas seal a pressure-sensor fault "
            "rather than a soot problem")
    else:
        combined = VentedBay(nav.name, nav.volume + module.volume, nav.n_ports,
                             nav.port_diameter)
        notes.append(
            f"the canard module vents through its OWN WALL "
            f"({module_wall_area * 1e6:.1f} mm2), so the sense volume is "
            f"{nav.volume * 1e6:.0f} cm3 and not {combined.volume * 1e6:.0f} cm3. Sharing "
            f"them would take the nav bay's lag {lag:.2f} -> "
            f"{combined.lag_altitude(altitude, climb_rate):.2f} m and put ejection gas one "
            f"leak away from the sensor that fires the charges")
        notes.append(
            "SO POT THE WIRING PASS-THROUGH SOLID. It is a wire route, not an air route -- "
            "and it is only allowed to be solid because the module vents overboard instead")

    trapped = trapped_differential(pad_altitude, apogee)
    notes.append(
        f"a bay sealed at the pad carries {trapped / 1e3:.1f} kPa at {apogee:.0f} m, which "
        f"is {trapped * math.pi * 0.0748**2 / 4.0:.0f} N on a bulkhead -- small, and not "
        f"what sizes anything, but it is why every sealed volume in the vehicle gets a hole")

    return VentCheck(ok=not v, violations=v, notes=notes)
