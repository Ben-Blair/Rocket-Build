"""Whether the airframe survives having holes cut through it, at the station where they are.

This module exists because `hinge.check_hinge_stack()` emits a note it cannot itself act
on:

    note  the wall bore is dia 7.97 mm in a 2.3 mm wall -- check the tube, not just the hinge

That note has been true and unactioned since the hinge stack went in. It is the same shape
of gap as the one `hinge.py` was written for: the hinge was sized against the hinge moment
and nobody had asked what the panel FORCE did to the bearing, and here the bore was sized
against the bearing and nobody has asked what four of them do to the TUBE. A part can be
correct in isolation and still be wrong about the structure it is cut into.

Four dia 7.975 bores at one axial station remove 13% of the circumference of a 79.4 x 2.3
tube. That is a real number and it deserves a real check rather than a note, because the
alternative -- discovering it at the pad -- is the expensive version.

WHAT THIS CHECKS, and it is deliberately local:

  1. Net section under boost axial compression, with a stress concentration at the bore.
  2. Net section under bending at that station, from a proper free body of everything
     forward of it, with inertial relief.
  3. Torsion, from a full roll command: four panels all pushing the same way around the
     axis, reacted by the tube.
  4. Shell buckling, since a thin fibreglass tube in compression fails by buckling long
     before it fails by stress.
  5. The bearing SEAT: the couple the bearing cannot swallow has to go into the bore wall
     as contact pressure, and the bore wall is G10, not steel.
  6. The press fit itself, which puts hoop tension around the bore before the rocket has
     even left the pad.

WHAT THIS DOES NOT CHECK, so that nobody reads a pass here as more than it is:

  * Global airframe beam bending under a gust or an off-nominal alpha. There is no
    structural model of the airframe anywhere in this project -- this is the first one --
    and the free body below runs at the TRIM condition the trajectory actually flies, not
    at a certification gust case. See `check_cut_station()`'s `gust_factor`.
  * The tube-to-tube joints either side of the module. Couplers are a mass line in
    `mass.py` and nothing more.
  * Anything about the printed bay, including the housing collar that carries 3.7 mm of
    the bearing. That is blocked on bracket hardware; see docs/05.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# ---------------------------------------------------------------------------------------
# Material allowables for the airframe tube.
#
# Stated once, here, so that arguing with them moves every conclusion downstream at the
# same time. This follows design/hinge.py deliberately.
#
# THE CAVEAT THAT MATTERS: these are NEMA G-10 / FR-4 SHEET properties, and a filament
# wound fiberglass airframe tube is not sheet. A wound tube with fibres at +/-45 deg is
# stiffer in torsion and weaker in axial than these numbers, and a pultruded or
# hand-rolled tube is different again. `configure.py` carries the tube as
# "G10/FR4 1850 kg/m^3" and that density is the only material fact the project has ever
# committed to. So: treat every margin below as indicative until the real tube is bought
# and its datasheet read, and note that the margins come out large enough that the
# distinction does not change the verdict. If a margin here ever lands under about 4x,
# stop and get the real numbers.
# ---------------------------------------------------------------------------------------

from .materials import (  # noqa: F401  -- re-exported; these are the tube's allowables
    G10_COMPRESSIVE, G10_TENSILE, G10_FLEXURAL, G10_BEARING, G10_SHEAR, G10_MODULUS,
    BUSHING_MODULUS, DATASHEET_CONFIDENCE_MARGIN,
)

# Required ratio of allowable to actual, matching hinge.BEARING_MARGIN_REQUIRED so that a
# marginal tube is not treated as better news than a marginal bearing.
SECTION_MARGIN_REQUIRED = 2.0

# Open-hole stress concentration. Kt = 3.0 is the flat-plate value for a circular hole in
# a uniform field. A hole in a CYLINDRICAL shell runs higher, by an amount that grows with
# the Lurie parameter beta = a / sqrt(R*t); this module reports beta so the assumption can
# be checked rather than trusted, and applies the flat-plate value below beta = 1.
#
# The bore is not actually open -- it has a bearing pressed into it -- and a filled hole
# concentrates less than an open one. Treating it as open is the conservative choice.
OPEN_HOLE_KT = 3.0

# Classical shell buckling is sigma_cr = 0.6*E*t/R, which real cylinders never achieve.
# 0.2 is the usual lower-bound empirical knockdown for an imperfection-sensitive shell of
# this radius-to-thickness ratio.
BUCKLING_KNOCKDOWN = 0.2

# BUSHING_MODULUS is imported above. The press fit generates contact pressure limited by
# the SOFTER of the two parts, which is the bushing: a 0.025 mm interference in a rigid
# hole is taken up almost entirely by the polymer.


@dataclass(frozen=True)
class CutStation:
    """A tube cross-section with holes through it.

    Stations follow the project convention: metres from the nose tip, positive aft.
    """

    station: float              # m from the nose tip
    outer_diameter: float
    wall_thickness: float
    hole_dia: float
    hole_count: int
    tube_name: str = ""

    @property
    def mean_radius(self) -> float:
        """Thin-wall properties are taken about the MEAN radius, not the outer. Using the
        outer overstates area by t/D -- about 3% here -- in the unconservative direction."""
        return (self.outer_diameter - self.wall_thickness) / 2.0

    @property
    def circumference(self) -> float:
        return 2.0 * math.pi * self.mean_radius

    @property
    def gross_area(self) -> float:
        return self.circumference * self.wall_thickness

    @property
    def removed_arc(self) -> float:
        """Circumference taken out by the holes. The bore is a cylinder cut through a
        curved wall, so its footprint is very slightly longer than its diameter; at
        d/D = 0.1 that correction is under half a percent and is ignored."""
        return self.hole_count * self.hole_dia

    @property
    def net_area(self) -> float:
        return (self.circumference - self.removed_arc) * self.wall_thickness

    @property
    def area_loss_fraction(self) -> float:
        return self.removed_arc / self.circumference

    @property
    def gross_inertia(self) -> float:
        """Second moment of a thin ring, I = pi * R^3 * t."""
        return math.pi * self.mean_radius ** 3 * self.wall_thickness

    @property
    def net_inertia(self) -> float:
        """Worst orientation: the bending axis is placed so that holes sit at BOTH extreme
        fibres, which is the case for a four-hole pattern at 90 degrees whichever way the
        vehicle is bent. Each such hole removes d*t of area at y = R.

        The two holes on the neutral axis are not credited back -- they remove material at
        y = 0, which contributes nothing to I either way.
        """
        holes_at_extreme = 2 if self.hole_count >= 4 else self.hole_count
        return (self.gross_inertia
                - holes_at_extreme * self.hole_dia * self.wall_thickness * self.mean_radius ** 2)

    @property
    def net_section_modulus(self) -> float:
        return self.net_inertia / self.mean_radius

    @property
    def polar_inertia(self) -> float:
        """J = 2*pi*R^3*t for a thin ring. Holes reduce it in the same proportion as the
        area, which is the standard approximation for a shear-carrying shell."""
        return 2.0 * math.pi * self.mean_radius ** 3 * self.wall_thickness

    @property
    def net_polar_inertia(self) -> float:
        return self.polar_inertia * (1.0 - self.area_loss_fraction)

    @property
    def lurie_beta(self) -> float:
        """a / sqrt(R*t). Below about 1 a hole in a shell behaves like a hole in a plate;
        above it, curvature drives Kt up and the flat-plate 3.0 is no longer conservative."""
        a = self.hole_dia / 2.0
        return a / math.sqrt(self.mean_radius * self.wall_thickness)

    @property
    def ligament(self) -> float:
        """Material left between adjacent holes, along the circumference."""
        return self.circumference / self.hole_count - self.hole_dia

    @property
    def hole_pitch_ratio(self) -> float:
        """d / pitch. Holes start interacting -- one hole's stress field reaching the
        next -- above roughly 0.3."""
        return self.hole_dia * self.hole_count / self.circumference


@dataclass(frozen=True)
class SectionLoads:
    """What the cut station carries, and where each number came from."""

    axial: float                # N, compression positive
    axial_case: str
    bending: float              # N*m
    bending_case: str
    torsion: float              # N*m
    torsion_case: str
    mass_forward: float         # kg, the mass the axial load is accelerating
    specific_force_g: float     # g the vehicle pulls at the axial case
    drag_at_axial_case: float   # N, the part of the axial load that is NOT inertial

    # --- bearing seat, one hole ---------------------------------------------------------
    seat_moment: float          # N*m the bearing hands to its seat
    seat_normal: float          # N


@dataclass
class SectionResult:
    axial_stress: float
    bending_stress: float
    peak_stress: float          # Kt * (axial + bending), at the bore edge
    shear_stress: float
    buckling_allowable: float
    seat_pressure: float
    press_fit_pressure: float
    press_fit_hoop: float
    kt_used: float
    margins: dict[str, float]
    ok: bool
    violations: list[str]
    notes: list[str]


def mass_forward_of(masses, station: float, rocket,
                    exclude: tuple[str, ...] = ("canards", "canard servos",
                                                "canard shafts")) -> float:
    """Mass the tube has to push, at and forward of `station`.

    Three modelling choices, each of which changes the answer and so is written down:

      * TUBES ARE DISTRIBUTED, not points. `mass.build_mass()` puts each tube's whole mass
        at its own mid-station, which would put the entire canard module tube aft of a
        hinge at 48% of its length. It is pro-rated by length instead.

      * CONTINGENCY IS DISTRIBUTED over the whole vehicle. `build_mass()` carries it as a
        single point mass at the vehicle CG, which is a statement about the CG and not
        about where the mass is. Pro-rating it by station is the honest reading of "a
        uniformly distributed 10%", which is what its docstring says it is.

      * THE CANARD PANELS AND THEIR HARDWARE ARE EXCLUDED. They do not load the tube
        THROUGH this station; they hang off the hinge AT it, so their inertia goes into
        the shaft and the bearing rather than into the tube section forward of the cut.
        Including them would overstate the axial load by about 30%, in the direction that
        looks conservative and is actually just wrong about the load path.
    """
    total = 0.0
    body_length = rocket.length
    for item in masses.items:
        name = item.name.lower()
        if any(name.startswith(x) for x in exclude):
            continue

        if name.startswith("contingency"):
            total += item.mass * min(1.0, max(0.0, station / body_length))
            continue

        if name.startswith("tube:"):
            for i, tube in enumerate(rocket.tubes):
                if name.endswith(tube.name.lower()):
                    x0 = rocket.tube_station(i)
                    frac = (station - x0) / tube.length
                    total += item.mass * min(1.0, max(0.0, frac))
                    break
            continue

        if item.x < station:
            total += item.mass
    return total


def bending_at_station(rocket, stab, station: float, q: float, alpha_rad: float,
                       vehicle_mass: float, mass_fwd: float, cg_fwd: float) -> float:
    """Airframe bending moment at `station`, from a free body of everything FORWARD of it.

        M = sum(aero normal force forward * arm)  -  mass_fwd * a_lat * arm_to_fwd_cg

    The inertial relief term is not a refinement, it is the whole reason a rocket airframe
    is not sized like a cantilever: the nose is not held still while the air pushes on it,
    it accelerates sideways, and most of the aero load is spent doing that rather than
    bending the tube. Dropping the term would overstate this moment by roughly 3x.

    Runs at the TRIM alpha the trajectory flies. It is not a gust case; see the module
    docstring.
    """
    a_ref = rocket.reference_area
    lateral_force = 0.0
    moment = 0.0
    for _, (cna, cp) in stab.contributions.items():
        if cp >= station:
            continue
        f = q * a_ref * cna * alpha_rad
        lateral_force += f
        moment += f * (station - cp)

    # Lateral acceleration of the whole vehicle, from the TOTAL normal force.
    total_normal = q * a_ref * stab.cn_alpha * alpha_rad
    a_lat = total_normal / vehicle_mass if vehicle_mass > 0 else 0.0

    moment -= mass_fwd * a_lat * (station - cg_fwd)
    return abs(moment)


def cg_forward_of(masses, station: float, rocket) -> float:
    """CG of the mass counted by `mass_forward_of()`. Same distribution assumptions."""
    num = den = 0.0
    body_length = rocket.length
    for item in masses.items:
        name = item.name.lower()
        if any(name.startswith(x) for x in ("canards", "canard servos", "canard shafts")):
            continue
        if name.startswith("contingency"):
            frac = min(1.0, max(0.0, station / body_length))
            m = item.mass * frac
            x = 0.5 * station * frac
        elif name.startswith("tube:"):
            m = x = 0.0
            for i, tube in enumerate(rocket.tubes):
                if name.endswith(tube.name.lower()):
                    x0 = rocket.tube_station(i)
                    frac = min(1.0, max(0.0, (station - x0) / tube.length))
                    m = item.mass * frac
                    x = x0 + 0.5 * frac * tube.length
                    break
            if m == 0.0:
                continue
        elif item.x < station:
            m, x = item.mass, item.x
        else:
            continue
        num += m * x
        den += m
    return num / den if den > 0 else 0.0


def check_cut_station(cut: CutStation, loads: SectionLoads,
                      bearing_od: float, seat_interference: float,
                      seat_length: float, gust_factor: float = 1.0) -> SectionResult:
    """Stresses and margins at a cut station.

    `seat_length` is how much of the bearing is actually held by the TUBE. It is not the
    bearing length: 3.700 mm of this bearing sits inboard of the tube ID and is carried by
    a housing collar off the printed bay, which does not exist yet. Pass the wall thickness
    to price the bearing with no collar -- the vehicle's current state -- and the full
    bearing length to price it with one. The peak pressure goes as 1/L^2, so the two
    answers are not close, and that gap IS the argument for building the collar.

    `gust_factor` scales the bending case. It is 1.0 by default -- the trim condition --
    and exists so that a reviewer who wants a 2x or 3x off-nominal alpha can get one
    without editing the load path.
    """
    v: list[str] = []
    notes: list[str] = []

    sigma_a = loads.axial / cut.net_area
    sigma_b = gust_factor * loads.bending / cut.net_section_modulus
    kt = OPEN_HOLE_KT
    peak = kt * (sigma_a + sigma_b)
    tau = loads.torsion * cut.mean_radius / cut.net_polar_inertia

    # Shell buckling, on the GROSS section: buckling is a stiffness phenomenon over a
    # length of shell, not a stress at a point, and the holes are local. The knockdown
    # covers a multitude of sins, this among them.
    sigma_cr = BUCKLING_KNOCKDOWN * 0.6 * G10_MODULUS * cut.wall_thickness / cut.mean_radius

    # Bearing seat: the couple the bushing hands to the bore, spread over the bushing OD
    # and length, peaking at the ends. Same 1/L^2 form as hinge.hinge_loads(), because it
    # is the same physics one interface further out.
    ell = seat_length
    p_seat = (6.0 * loads.seat_moment / (bearing_od * ell * ell)
              + loads.seat_normal / (bearing_od * ell))

    # Press fit. The interference is taken up by whichever part is softer, and a polymer
    # bushing in a G10 hole is softer by 6x. Contact pressure follows the BUSHING's
    # stiffness, not the hole's -- assuming the hole's is how you get a hoop stress five
    # times too big and condemn a tube that is fine.
    radial_interference = seat_interference / 2.0
    p_fit = BUSHING_MODULUS * radial_interference / (bearing_od / 2.0)
    # Hoop at the edge of a pressurised hole in a wide plate is equal to the pressure.
    hoop = p_fit

    margins = {
        "net section (compression + bending, Kt)": G10_COMPRESSIVE / peak if peak > 0 else math.inf,
        "shell buckling": sigma_cr / sigma_a if sigma_a > 0 else math.inf,
        "torsional shear": G10_SHEAR / tau if tau > 0 else math.inf,
        "bearing seat crush": G10_BEARING / p_seat if p_seat > 0 else math.inf,
        "press-fit hoop": G10_TENSILE / hoop if hoop > 0 else math.inf,
    }

    for name, m in margins.items():
        if m < SECTION_MARGIN_REQUIRED:
            v.append(f"{name} margin is {m:.2f}x, short of {SECTION_MARGIN_REQUIRED:.1f}x")

    if cut.lurie_beta > 1.0:
        v.append(
            f"Lurie beta is {cut.lurie_beta:.2f}; above 1.0 shell curvature drives the "
            f"stress concentration above the flat-plate Kt = {OPEN_HOLE_KT:.1f} used here, "
            f"so this check is no longer conservative")
    else:
        notes.append(
            f"Lurie beta {cut.lurie_beta:.2f} (< 1.0), so the flat-plate Kt = "
            f"{OPEN_HOLE_KT:.1f} stands")

    if cut.hole_pitch_ratio > 0.3:
        v.append(
            f"holes occupy {cut.hole_pitch_ratio * 100:.0f}% of the circumference; above "
            f"30% adjacent bores interact and the single-hole Kt understates the peak")
    else:
        notes.append(
            f"{cut.ligament * 1000:.1f} mm of ligament between adjacent bores "
            f"({cut.hole_pitch_ratio * 100:.0f}% of the circumference removed)")

    if cut.hole_dia > 0.25 * cut.outer_diameter:
        v.append(f"bore dia {cut.hole_dia * 1000:.2f} exceeds a quarter of the tube "
                 f"diameter; a thin-ring section model does not apply")

    worst = min(margins.values())
    if worst < DATASHEET_CONFIDENCE_MARGIN:
        notes.append(
            f"worst margin is {worst:.1f}x, under the {DATASHEET_CONFIDENCE_MARGIN:.0f}x at "
            f"which the G10-sheet allowables "
            f"in this module stop being good enough -- get the real tube datasheet")

    return SectionResult(
        axial_stress=sigma_a, bending_stress=sigma_b, peak_stress=peak,
        shear_stress=tau, buckling_allowable=sigma_cr,
        seat_pressure=p_seat, press_fit_pressure=p_fit, press_fit_hoop=hoop,
        kt_used=kt, margins=margins, ok=not v, violations=v, notes=notes,
    )


# ---------------------------------------------------------------------------------------
# Assembling the load case for the canard module. This is the part that needs the whole
# vehicle rather than just a cross-section, so it is kept separate from the check above.
# ---------------------------------------------------------------------------------------

def peak_axial_load(rocket, flight, mass_fwd: float) -> tuple[float, float, str]:
    """Largest compressive load the station carries during boost, with the condition.

    Returns (force, specific force in g, drag, description).

    Free body of everything forward of the station:

        F = m_fwd * (a + g) + D_fwd     and     (a + g) = (thrust - drag) / m_total

    The (a + g) grouping is the specific force -- what an accelerometer on the vehicle
    would read -- and it is what the structure feels. Using the kinematic acceleration
    alone would drop a full g of the load, which for a rocket at 8 g is a 12% error in the
    unconservative direction.

    D_fwd is taken as the WHOLE vehicle's drag, which is an upper bound: only the nose and
    the forward body actually load this station in compression. The bound is used rather
    than a split because the answer is two orders of magnitude clear of the allowable, and
    a defensible over-estimate is worth more than an arguable split.
    """
    from . import aero, atmosphere

    worst = 0.0
    worst_sf = 0.0
    worst_drag = 0.0
    worst_what = "no boost point found"
    for pt in flight.points:
        if pt.thrust <= 0.0:
            continue
        cd = aero.drag_coefficient(rocket, pt.speed, pt.z)
        drag = cd * pt.q * rocket.reference_area
        specific_force = (pt.thrust - drag) / pt.mass
        f = mass_fwd * specific_force + drag
        if f > worst:
            worst = f
            worst_sf = specific_force / atmosphere.G0
            worst_drag = drag
            worst_what = f"t = {pt.t:.2f} s, thrust {pt.thrust:.0f} N, drag {drag:.0f} N"
    return worst, worst_sf, worst_drag, worst_what


def canard_module_loads(rocket, masses, flight, stab, station: float,
                        panel_normal_force: float, panel_cp_radius: float,
                        seat_moment: float, alpha_trim_rad: float, q: float) -> SectionLoads:
    """The load case at the canard hinge station.

    Three loads, from three different flight conditions, deliberately not combined into one
    worst case: the axial peak is at maximum thrust near the pad, the bending peak is at
    maximum q, and the torsion peak is at a full roll command. Combining them would be
    physically wrong -- the vehicle is not doing all three at once -- and the margins are
    wide enough that the question does not arise. If any margin ever lands near 2x, THEN
    build a combined case; do not do it speculatively.
    """
    mass_fwd = mass_forward_of(masses, station, rocket)
    cg_fwd = cg_forward_of(masses, station, rocket)
    axial, specific_force_g, drag, axial_case = peak_axial_load(rocket, flight, mass_fwd)

    bending = bending_at_station(rocket, stab, station, q, alpha_trim_rad,
                                 vehicle_mass=masses.wet_mass,
                                 mass_fwd=mass_fwd, cg_fwd=cg_fwd)

    # Full roll command: all four panels push the same way around the axis, and the tube
    # between the canards and the aft fins reacts every bit of it.
    n_panels = rocket.canards.count if rocket.canards is not None else 0
    torsion = n_panels * panel_normal_force * panel_cp_radius

    return SectionLoads(
        axial=axial,
        axial_case=axial_case,
        bending=bending,
        bending_case=(f"q = {q / 1000:.2f} kPa at {math.degrees(alpha_trim_rad):.2f} deg trim "
                      f"alpha, free body forward of the station with inertial relief"),
        torsion=torsion,
        torsion_case=f"full roll command, {n_panels} panels x {panel_normal_force:.1f} N "
                     f"at R {panel_cp_radius * 1000:.1f} mm",
        mass_forward=mass_fwd,
        specific_force_g=specific_force_g,
        drag_at_axial_case=drag,
        seat_moment=seat_moment,
        seat_normal=panel_normal_force,
    )
