"""Dual-deploy recovery sizing, descent time, and wind drift.

Once an altitude waiver stops being the binding constraint, the constraint that replaces
it is the size of the recovery area. Drift under canopy scales with descent time, which
scales with apogee, so "we can fly as high as we want" quietly becomes "we can walk as far
as we want, and we can lose the vehicle and all its data."

For a project that needs five or six repeatable flights on an academic calendar, recovery
footprint is a first-class design constraint, not an afterthought.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import atmosphere

# Landing kinetic energy guidance. NAR/TRA range safety commonly looks for each
# independently-descending section to land below roughly 75 ft-lbf. Confirm the current
# figure with your prefect; treat this as a design target, not a quoted rule.
LANDING_KE_LIMIT_J = 75.0 * 1.35582


@dataclass
class Canopy:
    name: str
    diameter: float  # m
    drag_coefficient: float

    @property
    def area(self) -> float:
        return math.pi * self.diameter**2 / 4.0

    @property
    def cd_a(self) -> float:
        return self.drag_coefficient * self.area

    def descent_rate(self, mass: float, altitude: float = 0.0) -> float:
        rho = atmosphere.density(altitude)
        return math.sqrt(2.0 * mass * atmosphere.G0 / (rho * self.cd_a))


def size_for_descent_rate(
    mass: float, target_rate: float, drag_coefficient: float = 2.2, altitude: float = 0.0
) -> float:
    """Canopy diameter, in metres, giving `target_rate` m/s at sea level."""
    rho = atmosphere.density(altitude)
    cd_a = 2.0 * mass * atmosphere.G0 / (rho * target_rate**2)
    return math.sqrt(4.0 * cd_a / (drag_coefficient * math.pi))


@dataclass
class DescentResult:
    drogue_rate: float
    main_rate: float
    drogue_time: float
    main_time: float
    total_time: float
    landing_energy: float
    drift_by_wind: dict[float, float]  # wind m/s -> total drift m

    def report(self, apogee: float, downrange_at_apogee: float = 0.0) -> str:
        lines = [
            f"  apogee                {apogee:7.0f} m ({apogee * 3.28084:.0f} ft)",
            f"  drogue descent rate   {self.drogue_rate:7.1f} m/s",
            f"  main descent rate     {self.main_rate:7.1f} m/s",
            f"  descent time          {self.total_time:7.0f} s "
            f"({self.drogue_time:.0f} s drogue + {self.main_time:.0f} s main)",
            f"  landing energy        {self.landing_energy:7.0f} J "
            f"({self.landing_energy / 1.35582:.0f} ft-lbf) "
            f"{'OK' if self.landing_energy <= LANDING_KE_LIMIT_J else 'TOO HIGH'}",
            "  drift and minimum field radius:",
        ]
        for wind, drift in sorted(self.drift_by_wind.items()):
            total = drift + downrange_at_apogee
            lines.append(
                f"    {wind * 2.23694:4.0f} mph wind  ->  {drift:6.0f} m drift, "
                f"{total:6.0f} m from the pad ({total * 0.000621371:.2f} miles)"
            )
        return "\n".join(lines)


def simulate_descent(
    apogee: float,
    mass: float,
    drogue: Canopy,
    main: Canopy,
    main_deploy_altitude: float = 200.0,
    winds: tuple[float, ...] = (2.24, 4.47, 6.71, 8.94),  # 5, 10, 15, 20 mph
    steps: int = 200,
) -> DescentResult:
    """Descent time and drift, integrating density variation with altitude."""

    def leg_time(top: float, bottom: float, canopy: Canopy) -> float:
        if top <= bottom:
            return 0.0
        dh = (top - bottom) / steps
        t = 0.0
        for i in range(steps):
            h = top - (i + 0.5) * dh
            t += dh / canopy.descent_rate(mass, h)
        return t

    main_alt = min(main_deploy_altitude, apogee)
    t_drogue = leg_time(apogee, main_alt, drogue)
    t_main = leg_time(main_alt, 0.0, main)
    total = t_drogue + t_main

    landing_rate = main.descent_rate(mass, 0.0)
    energy = 0.5 * mass * landing_rate**2

    # Drift assumes the canopy moves with the airmass, which is the standard
    # approximation and is close enough for field sizing.
    drift = {w: w * total for w in winds}

    return DescentResult(
        drogue_rate=drogue.descent_rate(mass, apogee),
        main_rate=landing_rate,
        drogue_time=t_drogue,
        main_time=t_main,
        total_time=total,
        landing_energy=energy,
        drift_by_wind=drift,
    )


# ======================================================================================
# PACKING VOLUME
# ======================================================================================
#
# Sizing a canopy tells you its diameter. It does not tell you whether it fits in the
# tube, and on a 79.4 mm airframe that is the binding question: a 60 in main is a lot of
# nylon to push down a 74.8 mm hole.
#
# `recovery_bay_cal = 4.5` in configure.py was an assumed constant, not a result. These
# functions make the bay length fall out of the canopy choice.
#
# THE HONEST LIMITS OF THIS MODEL. Packed volume is estimated from fabric mass and a bulk
# density, because that is the only input available before you own the parts. Hand-packed
# ripstop lands somewhere around 350-500 kg/m^3 -- roughly 30-45% of solid nylon, which is
# what you get rolling a canopy by hand. That is a factor-of-1.4 spread and it propagates
# straight into the required length, so a result inside that band is not an answer, it is
# a prompt to go measure.
#
# Measure it like this: pack the real canopy, slide it into a tube of known ID, and read
# off the length it occupies. Then set `measured_volume` and this stops being a guess.
# Vendor pack volumes (Fruity Chutes and Rocketman both publish them) are the next best
# thing and are worth using the moment you pick a part number.

PACKED_BULK_DENSITY = 400.0  # kg/m^3, hand-packed ripstop canopy. Range 350-500.
WEBBING_BULK_DENSITY = 550.0  # kg/m^3, z-folded tubular nylon packs tighter than canopy.
PROTECTOR_BULK_DENSITY = 500.0  # kg/m^3, Nomex blanket.
STEEL_DENSITY = 7850.0  # kg/m^3, quick links and hardware. Heavy, negligible volume.

# You cannot fill a tube to its geometric volume. The canopy will not conform to the ends,
# you need slack to slide the stack in and out without abrading it, and a bay packed to
# 100% is a bay that will not close on the launch rail with cold hands. 0.85 is a working
# figure; if yours packs tighter than this you are compressing the canopy, which is how
# you get a chute that does not open.
FILL_LIMIT = 0.85

# Each internal bulkhead separating two compartments costs length: the plate itself, its
# epoxy fillet, and the eyebolt/U-bolt boss standing proud of it.
BULKHEAD_THICKNESS = 0.012  # m

# Quick links, swivel, and hardware spliced into the harness. Steel, so it contributes
# essentially nothing to volume but is inside the `shock_cord_and_links` mass line and
# would otherwise be counted as if it were fabric.
HARNESS_HARDWARE_KG = 0.050

# THE DROGUE'S FIRING CIRCUIT HAS TO CROSS THE MAIN'S COMPARTMENT.
#
# The altimeter is in the nav bay -- configure.py puts it there for GNSS sky view -- so both
# firing circuits start forward of the whole recovery section. The main's charge terminates
# on the aft gas seal, millimetres from where its wires come through (design/seal.py). The
# drogue's charge is on the far side of the internal bulkhead, and the only path to it runs
# straight through a compartment packed with the main canopy.
#
# Wires loose in a packed compartment abrade, snag on the canopy going out, and are the kind
# of thing that works on the bench every time. So they go in a thin-wall conduit bonded along
# the tube wall, sealed where it passes through both bulkheads.
#
# THE ALTERNATIVE, PRICED, because it is the standard high-power layout and it is worth
# knowing why this vehicle cannot have it: an av-bay between the two compartments, with the
# altimeter and its own static ports sitting next to the charges, needs roughly 60 mm of tube
# and two further bulkheads. The bay has 13 mm of margin. The conduit costs 1.2 mm of it.
CONDUIT_OUTER_DIAMETER = 0.005  # m, thin-wall tube, carries 2 x 24 AWG with room to pull
CONDUIT_DENSITY = 1400.0  # kg/m^3, thin-wall PETG or glass tube -- a few grams either way

# A U-bolt standing proud of a bulkhead is rigid and the canopy packs AROUND it, so it takes
# its own volume out of the compartment rather than compressing with the fabric.
#
# THIS WAS 6.0e-6 AND THAT WAS A BOUNDING BOX, which is the error correction 23 records in
# another form: a 25 x 20 x 12 mm envelope for an M5 U-bolt describes a solid block, and a
# U-bolt is a wire loop with a hole in the middle that the harness threads through. The
# fabric goes round the rod, not round the box.
#
# Rod: about 65 mm of 5 mm bar bent into the U, 1.3 cm3. Backing plate 25 x 20 x 3, 1.5 cm3.
# Call it 3.0 cm3 and note that it is still the loosest number in this calculation -- but it
# is now loose about the right object. The difference is 2.7 mm of recovery bay, which is
# the entire margin, so it was worth getting right rather than staying "conservative".
#
# IT WAS LOOSE BY 2.2x, AND THE REASON IS THE ONE THE PARAGRAPH ABOVE COULD NOT KNOW: the
# U-bolt is M8, not M5. `design/recovery_hardware.py` sizes the anchor against the mode that
# governs it -- bending in the CROWN, not shear in the legs -- and the rod goes up two sizes,
# taking the crown's swept volume and the backing plate with it. 6.57 cm3 is the sized part:
# the crown proud of this face, plus the plate and two nuts of the opposing U-bolt lying flat
# against it, which both existing bulkheads carry because each takes a harness both ways.
# `recovery_hardware.check_recovery_hardware()` re-derives this and fails if the two drift,
# the same guard `configure.evaluate()` puts on `mass.py`'s harness line.
#
# 5.95 -> 8.39 cm3 with the M10 rod of the 1.30 cal freeze. Same derivation, bigger crown
# and a wider backing plate. This one costs PACKING, not mass, and the recovery bay had
# 4.4 mm of spare length before it.
UBOLT_ENVELOPE_VOLUME = 8.39e-6  # m^3

# THE CHARGE WELL IS RIGID TOO, and `default_soft_goods()` used to say in as many words that
# it was not: "charge wells, e-matches and terminal blocks mount on the bulkhead face and do
# not consume packing volume." A well is a 12 mm tube standing 19 mm off the face, directly
# in the canopy's way. Sized in `design/recovery_hardware.py`; drift-checked there.
# Converged, not typed: the well displaces packing, the packing sets the compartment
# volume, the volume sets the charge and the charge sizes the well. Two passes settle
# it to under a hundredth of a cm3 -- the same fixed point `add_conduit()` already runs
# for the drogue conduit, and for the same reason.
WELL_ENVELOPE_VOLUME = {"main": 2.92e-6, "drogue": 1.61e-6}  # m^3

# ======================================================================================
# THE HARNESS
# ======================================================================================
#
# It is a quarter of the recovery bay's volume, it carries every newton of the opening
# shock, and until Aug 2026 NOTHING IN THIS PROJECT HAD EVER SIZED IT. Its volume came from
# `shock_cord_and_links = 0.220 kg` in the mass budget divided by an assumed bulk density --
# a budget line nobody had checked, turned into a volume by a guess. Its strength came from
# nowhere at all.
#
# Sizing it against the load it actually carries is what fixed the recovery bay's margin,
# and the direction of the answer is the point: **the harness was about twenty times
# stronger than it needs to be.** 1 inch tubular nylon is rated 17.8 kN. The main's opening
# shock is 1.31 kN (design/seal.py, and note that even that is the infinite-mass bound). A
# number that was never checked came out enormous, which is the same shape as the tube at
# the hinge station running at 256x -- except that here the excess was not free, because it
# was spending a bay whose margin turned out to be 0.1 mm.
#
# THE DERATING MATTERS MORE THAN THE RATING. Webbing is joined with knots or sewn loops and
# a knot costs roughly half the rated strength -- that is the standard figure and it is not
# a detail, it moves the selection by two sizes. Sewn loops do better but only if somebody
# sews them properly, which is not a thing to assume about a part you have not made yet.
#
# WHY NOT KEVLAR, since it packs smaller and survives the ejection gas: it does not stretch.
# Nylon takes 20-30% elongation and absorbs the shock; Kevlar transmits it, and this project
# has no model of harness elasticity, so switching would raise a load (`seal.opening_shock`)
# that nothing here could recompute. A Kevlar LEADER at the charge end is the standard way
# to get the heat resistance without the stiffness, and it is what the protectors are for.
KNOT_STRENGTH_FACTOR = 0.5

# Harness margin. Higher than the 2.0x used elsewhere in this project on purpose: opening
# shock is the least well known load in the vehicle -- seal.opening_shock says nobody should
# believe it to better than a factor of two without a load cell -- and a harness failure
# loses the vehicle and all its data.
HARNESS_MARGIN_REQUIRED = 3.0

# Each harness leg, as a multiple of overall vehicle length. Long enough that the two
# sections cannot come back and hit each other, and long enough for the canopy to inflate
# clear of the airframe.
HARNESS_LENGTH_FACTOR = 2.5

# Tubular nylon as it is sold. Mass per metre is computed from the webbing geometry rather
# than quoted, and should be replaced with a vendor figure the moment a part number exists
# -- the same rule the canopies follow.
@dataclass(frozen=True)
class Webbing:
    name: str
    width: float  # m
    mass_per_metre: float  # kg/m
    rating: float  # N, straight pull

    @property
    def working_load(self) -> float:
        """Rating after the knot derating -- the number the check is against."""
        return self.rating * KNOT_STRENGTH_FACTOR


WEBBING_OPTIONS: list[Webbing] = [
    Webbing('1/2" tubular nylon', 0.0127, 0.011, 4448.0),    # 1000 lbf
    Webbing('9/16" tubular nylon', 0.0143, 0.014, 6672.0),   # 1500 lbf
    Webbing('3/4" tubular nylon', 0.0191, 0.020, 11121.0),   # 2500 lbf
    Webbing('1" tubular nylon', 0.0254, 0.030, 17793.0),     # 4000 lbf
]


def select_webbing(opening_load: float,
                   margin: float = HARNESS_MARGIN_REQUIRED) -> Webbing:
    """The lightest stocked webbing that carries `opening_load` with margin, after knots."""
    for w in sorted(WEBBING_OPTIONS, key=lambda x: x.mass_per_metre):
        if w.working_load >= margin * opening_load:
            return w
    return WEBBING_OPTIONS[-1]


@dataclass(frozen=True)
class Harness:
    webbing: Webbing
    length_each: float  # m, one leg
    opening_load: float  # N

    @property
    def total_length(self) -> float:
        return 2.0 * self.length_each

    @property
    def webbing_mass(self) -> float:
        return self.total_length * self.webbing.mass_per_metre

    @property
    def mass(self) -> float:
        return self.webbing_mass + HARNESS_HARDWARE_KG

    @property
    def margin(self) -> float:
        return self.webbing.working_load / self.opening_load

    @property
    def ok(self) -> bool:
        return self.margin >= HARNESS_MARGIN_REQUIRED


def size_harness(vehicle_length: float, opening_load: float) -> Harness:
    """Pick the webbing and the length from the load and the vehicle, not from a budget."""
    return Harness(
        webbing=select_webbing(opening_load),
        length_each=HARNESS_LENGTH_FACTOR * vehicle_length,
        opening_load=opening_load,
    )


# VENDOR PACK VOLUMES -- these replace the density estimate for the two canopies, which is
# the single biggest source of uncertainty in this whole calculation. Published figures,
# not measurements of your own hardware, and both are quoted by the vendor as assuming a
# TIGHT pack, so treat them as the optimistic end until you have packed the real thing.
#
#   main   Fruity Chutes Iris Ultra 60" Compact -- 6.8 oz, "3.9" D x 3.2" L : 38.2 cu""
#          https://shop.fruitychutes.com/products/iris-ultra-60-compact-parachute-19lbs-20fps-12lbs-15fps
#   drogue Fruity Chutes 18" Elliptical         -- 1.7 oz, "1.9" D x 3.5" L : 9.67 cu""
#          https://shop.fruitychutes.com/products/18-elliptical-parachute-1-2-lb-20fps
#
# 60" is the nearest real size to the 56" the sizing solves for -- Fruity Chutes make 48"
# and 60", not 56" -- and it lands slower, so it is the safe side of the rounding.
#
# NOTE the masses. The budget in design/mass.py carries 280 g for the main and 70 g for the
# drogue; these parts are 193 g and 48 g. That 109 g is real and it sits in the recovery
# bay, but the bay centroid is within ~35 mm of the CG so it moves the CG under a
# millimetre. Worth fixing when you weigh parts, not worth a design change now.
CU_INCH = 1.6387064e-5  # m^3
MAIN_PACK_VOLUME = 38.2 * CU_INCH
DROGUE_PACK_VOLUME = 9.67 * CU_INCH


@dataclass(frozen=True)
class SoftGood:
    """One item that has to physically go inside the tube.

    `measured_volume` overrides the density estimate. Set it as soon as you have either a
    vendor pack volume or a real packed measurement -- that is the whole point of the
    field, and every item that gets one shrinks the uncertainty on the bay length.
    """

    name: str
    mass: float  # kg
    bulk_density: float = PACKED_BULK_DENSITY
    measured_volume: float | None = None  # m^3

    @property
    def volume(self) -> float:
        if self.measured_volume is not None:
            return self.measured_volume
        return self.mass / self.bulk_density

    @property
    def estimated(self) -> bool:
        return self.measured_volume is None


@dataclass
class Compartment:
    """One independently-pressurised volume in the recovery bay.

    Dual deploy needs two of these, separated by a sealed bulkhead. They are not
    interchangeable and their contents cannot share space: the drogue compartment vents at
    apogee and the main compartment vents at 200 m, so a single volume holding both would
    dump the main at apogee -- which is the failure this whole architecture exists to
    prevent.
    """

    name: str
    contents: list[SoftGood]
    hardware: list[SoftGood] = field(default_factory=list)

    @property
    def volume(self) -> float:
        """Soft goods only -- the part that gets packed at `FILL_LIMIT`."""
        return sum(item.volume for item in self.contents)

    # NOTE: nothing sums `hardware` MASSES -- `measured_volume` overrides `SoftGood.volume`
    # and this class only ever contributes volume. The anchors' mass lives in
    # `mass.DEFAULT_RECOVERY_BUDGET["harness_anchors"]`, which is where it is actually
    # counted. The figures here are kept honest anyway so the two cannot be read as
    # disagreeing.
    @property
    def rigid_volume(self) -> float:
        """Rigid things that stand in the packing space, m^3.

        A conduit or a U-bolt does not pack. It occupies exactly its own volume and the
        canopy has to go round it, so it is added to the required length DIRECTLY rather
        than through the fill limit -- putting it through the fill limit would inflate it by
        1/0.85 and claim a bay shortfall that is not in the hardware. Correction 5 is the
        precedent: two estimates multiplied together once manufactured an 11 mm shortfall
        and nearly lengthened a frozen airframe.
        """
        return sum(item.volume for item in self.hardware)

    @property
    def any_estimated(self) -> bool:
        return any(item.estimated for item in self.contents + self.hardware)


@dataclass
class PackingResult:
    fits: bool
    required_length: float  # m, including bulkheads
    available_length: float  # m
    margin: float  # m
    fill_fraction: float  # of the geometric volume actually consumed
    inner_diameter: float
    compartments: list[tuple[str, float, float]]  # name, volume m^3, length m
    all_measured: bool
    estimated_items: list[str]
    reason: str

    def __str__(self) -> str:
        verdict = "FITS" if self.fits else "NO FIT"
        return (
            f"{verdict:6s} recovery bay     "
            f"need {self.required_length * 1000:5.1f} mm, "
            f"have {self.available_length * 1000:5.1f} mm "
            f"({self.margin * 1000:+6.1f} mm)  {self.reason}"
        )

    def report(self, caliber: float | None = None) -> str:
        lines = [
            f"  inner diameter        {self.inner_diameter * 1000:7.1f} mm",
            f"  contents:",
        ]
        for name, vol, length in self.compartments:
            lines.append(
                f"    {name:20s} {vol * 1e6:6.0f} cm3 -> {length * 1000:5.1f} mm of tube"
            )
        lines += [
            f"  required length       {self.required_length * 1000:7.1f} mm"
            + (f" ({self.required_length / caliber:.2f} cal)" if caliber else ""),
            f"  available length      {self.available_length * 1000:7.1f} mm"
            + (f" ({self.available_length / caliber:.2f} cal)" if caliber else ""),
            f"  margin                {self.margin * 1000:+7.1f} mm",
            f"  fill fraction         {self.fill_fraction * 100:7.0f} % of geometric volume"
            f"  (limit {FILL_LIMIT * 100:.0f} %)",
        ]
        if self.estimated_items:
            lines.append(
                "  NOTE: canopies use vendor pack volumes; still estimated from bulk "
                "density: " + ", ".join(self.estimated_items)
            )
        return "\n".join(lines)


def conduit_volume(length: float, outer_diameter: float = CONDUIT_OUTER_DIAMETER) -> float:
    """Volume a wiring conduit of this length stands in, m^3."""
    return math.pi * outer_diameter**2 / 4.0 * length


def add_conduit(comp: Compartment, inner_diameter: float,
                outer_diameter: float = CONDUIT_OUTER_DIAMETER,
                fill_limit: float = FILL_LIMIT) -> Compartment:
    """Return `comp` with the drogue firing conduit added to its rigid hardware.

    THE LENGTH IS A FIXED POINT: the conduit spans the compartment, and the compartment's
    length depends on what is in it, which now includes the conduit. Two passes converge to
    well under a tenth of a millimetre here because the conduit is 0.5% of the volume, and
    the alternative -- solving it properly -- would be precision this model does not have.
    """
    area = math.pi * inner_diameter**2 / 4.0
    length = comp.volume / (area * fill_limit) + comp.rigid_volume / area
    for _ in range(2):
        vol = conduit_volume(length, outer_diameter)
        length = (comp.volume / (area * fill_limit)
                  + (comp.rigid_volume + vol) / area)
    return Compartment(
        comp.name,
        comp.contents,
        hardware=comp.hardware + [
            SoftGood(f"drogue conduit, {length * 1000:.0f} mm",
                     conduit_volume(length, outer_diameter) * CONDUIT_DENSITY * 0.4,
                     measured_volume=conduit_volume(length, outer_diameter)),
        ],
    )


def default_soft_goods(
    recovery_budget: dict[str, float] | None = None,
    inner_diameter: float = 0.0748,
    harness: Harness | None = None,
) -> list[Compartment]:
    """The two compartments, built from the recovery mass budget in `design.mass`.

    Reading the masses from the budget rather than restating them here is deliberate: the
    packing check and the mass check then cannot disagree about what is in the rocket. If
    you add a deployment bag to the budget, it shows up in the volume automatically.

    `ejection_hardware_charges` is excluded from the SOFT goods, because a charge is not
    fabric. It is not excluded from the rigid hardware, and it used to be: this docstring
    said "charge wells, e-matches and terminal blocks mount on the bulkhead face and do not
    consume packing volume", which is true of a terminal block and false of a well. A well is
    a 12 mm tube standing 19 mm off the face, directly in the canopy's way. See
    `WELL_ENVELOPE_VOLUME` and `design/recovery_hardware.py`.

    The harness is split 60/40 between the main and drogue compartments, which is the usual
    proportion when the main harness is the longer of the two.
    """
    from .mass import DEFAULT_RECOVERY_BUDGET

    budget = recovery_budget if recovery_budget is not None else DEFAULT_RECOVERY_BUDGET

    # The harness mass comes from the SIZED harness when one is supplied, and from the
    # budget line only as a fallback. That budget line was the whole problem: it was never
    # checked, and dividing it by a bulk density turned an unchecked number into a volume.
    if harness is not None:
        webbing = harness.webbing_mass
    else:
        webbing = max(budget["shock_cord_and_links"] - HARNESS_HARDWARE_KG, 0.0)
    protector_each = budget["nomex_protectors"] / 2.0

    # The conduit runs the length of the MAIN compartment only: it starts at the aft gas
    # seal and ends at the internal bulkhead, where the drogue's charge is. Its length is
    # not known until the packing is solved, so it is priced here from the compartment's
    # own packed length -- see `conduit_for()` below, which the caller applies.
    main = Compartment(
        "main",
        [
            SoftGood("main canopy", budget["main_chute"],
                     measured_volume=MAIN_PACK_VOLUME),
            SoftGood("main harness", webbing * 0.60, WEBBING_BULK_DENSITY),
            SoftGood("main protector", protector_each, PROTECTOR_BULK_DENSITY),
            SoftGood("links/swivel", HARNESS_HARDWARE_KG * 0.60, STEEL_DENSITY),
        ],
        hardware=[
            # Two U-bolts stand in this compartment: one on the aft gas seal's aft face,
            # one on the internal bulkhead's forward face. Both ends of the main harness.
            SoftGood("2 x U-bolt", 2 * 0.0490, measured_volume=2 * UBOLT_ENVELOPE_VOLUME),
            SoftGood("main charge well", 0.0,
                     measured_volume=WELL_ENVELOPE_VOLUME["main"]),
        ],
    )
    drogue = Compartment(
        "drogue",
        [
            SoftGood("drogue canopy", budget["drogue_chute"],
                     measured_volume=DROGUE_PACK_VOLUME),
            SoftGood("drogue harness", webbing * 0.40, WEBBING_BULK_DENSITY),
            SoftGood("drogue protector", protector_each, PROTECTOR_BULK_DENSITY),
            SoftGood("links/swivel", HARNESS_HARDWARE_KG * 0.40, STEEL_DENSITY),
        ],
        hardware=[
            SoftGood("2 x U-bolt", 2 * 0.0490, measured_volume=2 * UBOLT_ENVELOPE_VOLUME),
            SoftGood("drogue charge well", 0.0,
                     measured_volume=WELL_ENVELOPE_VOLUME["drogue"]),
        ],
    )
    return [add_conduit(main, inner_diameter), drogue]


def check_packing(
    inner_diameter: float,
    bay_length: float,
    compartments: list[Compartment] | None = None,
    fill_limit: float = FILL_LIMIT,
    bulkhead_thickness: float = BULKHEAD_THICKNESS,
) -> PackingResult:
    """Does the recovery hardware fit in the bay you have?

    Length is consumed by the packed soft goods (at `fill_limit` of the geometric tube
    volume) plus one bulkhead per internal division between compartments.
    """
    comps = compartments if compartments is not None else default_soft_goods()
    area = math.pi * inner_diameter**2 / 4.0

    detail: list[tuple[str, float, float]] = []
    packed_length = 0.0
    for comp in comps:
        # Soft goods pack at the fill limit; rigid hardware standing in the same space
        # (a wiring conduit, a U-bolt) takes exactly its own volume and no more.
        length = comp.volume / (area * fill_limit) + comp.rigid_volume / area
        packed_length += length
        detail.append((comp.name, comp.volume + comp.rigid_volume, length))

    n_internal_bulkheads = max(len(comps) - 1, 0)
    required = packed_length + n_internal_bulkheads * bulkhead_thickness

    total_volume = sum(c.volume + c.rigid_volume for c in comps)
    fill_fraction = total_volume / (area * bay_length) if bay_length > 0 else float("inf")

    fits = required <= bay_length
    if fits:
        reason = f"{len(comps)} compartments, {fill_fraction * 100:.0f}% full"
    else:
        reason = f"short by {(required - bay_length) * 1000:.0f} mm"

    return PackingResult(
        fits=fits,
        required_length=required,
        available_length=bay_length,
        margin=bay_length - required,
        fill_fraction=fill_fraction,
        inner_diameter=inner_diameter,
        compartments=detail,
        all_measured=not any(c.any_estimated for c in comps),
        estimated_items=[i.name for c in comps for i in c.contents if i.estimated],
        reason=reason,
    )


def required_bay_length(
    inner_diameter: float,
    compartments: list[Compartment] | None = None,
    fill_limit: float = FILL_LIMIT,
    bulkhead_thickness: float = BULKHEAD_THICKNESS,
) -> float:
    """Bay length, in metres, that the recovery hardware actually needs.

    Divide by the airframe outer diameter to get the number to put in
    `DesignParams.recovery_bay_cal`. Set it deliberately -- do not have the geometry
    rebuild itself from this, or the frozen airframe stops being frozen.
    """
    return check_packing(
        inner_diameter, 0.0, compartments, fill_limit, bulkhead_thickness
    ).required_length


def bulk_density_sensitivity(
    inner_diameter: float,
    outer_diameter: float,
    densities: tuple[float, ...] = (350.0, 400.0, 450.0, 500.0),
) -> list[tuple[float, float, float]]:
    """Required bay length across the plausible packing-density range.

    Returns (density, length_m, length_cal). This is the calculation the vendor pack
    volumes REPLACE, kept because it shows what the answer looks like without them: a band
    wide enough to put 4.5 cal on either side of the verdict. It is the argument for
    sourcing a real number rather than the argument for any particular bay length.
    """
    from .mass import DEFAULT_RECOVERY_BUDGET

    out = []
    for rho in densities:
        webbing = max(
            DEFAULT_RECOVERY_BUDGET["shock_cord_and_links"] - HARNESS_HARDWARE_KG, 0.0
        )
        protector_each = DEFAULT_RECOVERY_BUDGET["nomex_protectors"] / 2.0
        # Scale the canopy density; webbing and Nomex pack by their own mechanisms.
        comps = [
            Compartment(
                "main",
                [
                    SoftGood("main canopy", DEFAULT_RECOVERY_BUDGET["main_chute"], rho),
                    SoftGood("main harness", webbing * 0.60, WEBBING_BULK_DENSITY),
                    SoftGood("main protector", protector_each, PROTECTOR_BULK_DENSITY),
                    SoftGood("links/swivel", HARNESS_HARDWARE_KG * 0.60, STEEL_DENSITY),
                ],
            ),
            Compartment(
                "drogue",
                [
                    SoftGood("drogue canopy", DEFAULT_RECOVERY_BUDGET["drogue_chute"], rho),
                    SoftGood("drogue harness", webbing * 0.40, WEBBING_BULK_DENSITY),
                    SoftGood("drogue protector", protector_each, PROTECTOR_BULK_DENSITY),
                    SoftGood("links/swivel", HARNESS_HARDWARE_KG * 0.40, STEEL_DENSITY),
                ],
            ),
        ]
        length = required_bay_length(inner_diameter, comps)
        out.append((rho, length, length / outer_diameter))
    return out
