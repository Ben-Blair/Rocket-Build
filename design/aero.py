"""Subsonic aerodynamics: Barrowman normal-force and centre-of-pressure buildup,
plus a component drag buildup.

Validity: attached subsonic flow, small angle of attack (< ~10 deg), M < ~0.8. That
window is exactly why requirement R5 caps Mach at 0.8 -- staying inside it keeps this
model, and the linear controller you will design from it, honest.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import atmosphere
from .geometry import FinSet, Rocket


def prandtl_glauert(mach: float) -> float:
    """Subsonic compressibility factor applied to lift-curve slopes."""
    m = min(abs(mach), 0.85)
    return 1.0 / math.sqrt(1.0 - m * m)


def fin_cn_alpha(fins: FinSet, ref_diameter: float, mach: float = 0.0) -> float:
    """Barrowman fin-set normal force coefficient derivative, per radian,
    referenced to the body cross-sectional area. Includes body-fin interference."""
    s = fins.semispan
    d = ref_diameter
    cr, ct = fins.root_chord, fins.tip_chord
    lm = fins.mid_chord_line
    base = (4.0 * fins.count * (s / d) ** 2) / (1.0 + math.sqrt(1.0 + (2.0 * lm / (cr + ct)) ** 2))
    r_body = fins.body_diameter / 2.0
    interference = 1.0 + r_body / (s + r_body)
    return base * interference * prandtl_glauert(mach)


def panel_cn_alpha(fins: FinSet, ref_diameter: float, mach: float = 0.0) -> float:
    """Per-panel normal force derivative, referenced to body area. Used for control
    effectiveness and hinge moments.

    NOTE THIS IS A ROLL-AVERAGED SHARE, NOT ONE FIN'S LIFT SLOPE. `fin_cn_alpha` is
    Barrowman's fin-SET value, which already accounts for the set's orientation relative to
    the angle of attack -- averaged over roll angle, only about half of an N-fin set carries
    normal force in any one plane. Dividing by N therefore gives each fin's average SHARE of
    the set, which is roughly half of what one fin actually produces. For anything where
    every fin is fully effective regardless of clocking -- roll damping and roll authority --
    use `single_fin_cn_alpha` instead. See design/control.roll_damping_cl_p.
    """
    return fin_cn_alpha(fins, ref_diameter, mach) / fins.count


def single_fin_cn_alpha(fins: FinSet, ref_diameter: float, mach: float = 0.0) -> float:
    """One fin's own normal force derivative, referenced to body area.

    Barrowman's fin-set formula is a roll-averaged result: of N fins, about N/2 are effective
    in any given plane at angle of attack. So one fin's own slope is the set value divided by
    N/2, not by N. That factor of two is exactly what `panel_cn_alpha` is missing for roll.

    Checked against OpenRocket 24.12, which reports roll forcing for a canted fin set
    directly: its Cl_delta for the aft fins is 1.885x what `panel_cn_alpha` implies, against
    the 2.0x this returns. The 6% residual is Barrowman versus OpenRocket's Diederich
    planform correlation and sits well inside this module's stated accuracy.
    See `scripts/openrocket_roll_check.py`.

    Valid for 3-4 fins, which is the range Barrowman's own formula is valid over. Above 4 the
    effective count stops being N/2 and needs the correction table in Niskanen's OpenRocket
    technical documentation; this vehicle has never used anything but 4.
    """
    return fin_cn_alpha(fins, ref_diameter, mach) / (fins.count / 2.0)


def body_lift_cn_alpha(
    rocket: Rocket, mach: float = 0.0, k: float = 1.1, alpha_ref_deg: float = 4.0
) -> tuple[float, float]:
    """Galejs body-lift correction, linearised about a reference angle of attack.
    Returns (equivalent CNa, cp_station).

    Barrowman assumes a slender body produces no normal force away from the nose, which
    under-predicts CP travel at angle of attack. The Galejs correction is

        CN_body = k * (A_planform / A_ref) * sin^2(alpha)

    Note the *squared* sine: this is a nonlinear term that contributes nothing to the
    lift-curve slope at alpha = 0, so it cannot be dropped into a linear buildup at full
    strength. Here it is linearised as CN/alpha evaluated at `alpha_ref_deg`, which is a
    representative trimmed angle of attack for this vehicle. It acts at the planform
    centroid, forward of the total CP, so it is mildly *destabilizing* -- stability falls
    off as angle of attack grows, which is exactly why you do not want to fly a
    marginally stable rocket in gusty wind.
    """
    d = rocket.diameter
    planform = d * rocket.body_length + 0.5 * d * rocket.nose.length
    alpha_ref = math.radians(alpha_ref_deg)
    linearised = math.sin(alpha_ref) ** 2 / alpha_ref
    cn_alpha = k * (planform / rocket.reference_area) * linearised
    # Area-weighted centroid of the planform.
    nose_c = rocket.nose.length * (2.0 / 3.0)
    nose_a = 0.5 * d * rocket.nose.length
    body_c = rocket.nose.length + rocket.body_length / 2.0
    body_a = d * rocket.body_length
    cp = (nose_c * nose_a + body_c * body_a) / (nose_a + body_a)
    return cn_alpha * prandtl_glauert(mach), cp


@dataclass
class StabilityResult:
    cn_alpha: float  # total, per rad, ref body area
    cp_station: float  # m from nose tip
    cg_station: float
    static_margin_cal: float
    contributions: dict[str, tuple[float, float]]  # name -> (CNa, cp)

    @property
    def cm_alpha(self) -> float:
        """Pitching moment derivative per radian about the CG, nondimensionalised by the
        reference diameter. Negative == statically stable."""
        return -self.cn_alpha * self.static_margin_cal


def stability(
    rocket: Rocket,
    cg_station: float,
    mach: float = 0.0,
    include_body_lift: bool = True,
    canard_deflection_rad: float = 0.0,
) -> StabilityResult:
    """Static stability at a given CG.

    `canard_deflection_rad` does not change CNa, but is carried through so callers can
    document the condition. Deflection effects on trim are handled in `control.py`.
    """
    d = rocket.diameter
    contributions: dict[str, tuple[float, float]] = {}

    contributions["nose"] = (2.0 * prandtl_glauert(mach), rocket.nose.cp_station)

    if include_body_lift:
        contributions["body_lift"] = body_lift_cn_alpha(rocket, mach)

    if rocket.canards is not None:
        contributions["canards"] = (
            fin_cn_alpha(rocket.canards, d, mach),
            rocket.canards.cp_station,
        )

    contributions["aft_fins"] = (
        fin_cn_alpha(rocket.aft_fins, d, mach),
        rocket.aft_fins.cp_station,
    )

    total_cn = sum(c[0] for c in contributions.values())
    cp = sum(c[0] * c[1] for c in contributions.values()) / total_cn
    return StabilityResult(
        cn_alpha=total_cn,
        cp_station=cp,
        cg_station=cg_station,
        static_margin_cal=(cp - cg_station) / d,
        contributions=contributions,
    )


def skin_friction_coefficient(reynolds: float, roughness_ratio: float = 6e-5) -> float:
    """Turbulent flat-plate skin friction with a roughness floor."""
    if reynolds < 1e4:
        return 0.0148
    smooth = 0.074 / reynolds**0.2
    rough = 0.032 * roughness_ratio**0.2
    return max(smooth, rough)


def drag_coefficient(
    rocket: Rocket,
    velocity: float,
    altitude: float,
    include_base: bool = True,
    rail_button_cd: float = 0.02,
    interference: float = 1.05,
) -> float:
    """Zero-lift drag coefficient referenced to body cross-sectional area."""
    if velocity < 1.0:
        return 0.5

    temp, _, rho, sound = atmosphere.properties(altitude)
    mu = atmosphere.dynamic_viscosity(temp)
    mach = velocity / sound
    a_ref = rocket.reference_area

    reynolds = rho * velocity * rocket.length / mu
    cf = skin_friction_coefficient(reynolds)

    # Body: wetted area with a form factor for a finite fineness ratio.
    body_wet = rocket.nose.wetted_area + sum(t.wetted_area for t in rocket.tubes)
    cd_body = cf * (body_wet / a_ref) * (1.0 + 0.5 / max(rocket.fineness, 1.0))

    # Lifting surfaces: wetted area with a thickness form factor.
    cd_surfaces = 0.0
    for fins in (rocket.aft_fins, rocket.canards):
        if fins is None:
            continue
        t_over_c = fins.thickness / max(fins.mean_chord, 1e-6)
        cd_surfaces += cf * (fins.wetted_area / a_ref) * (1.0 + 2.0 * t_over_c)
        # Leading-edge / thickness pressure drag on the exposed panels.
        cd_surfaces += 1.2 * t_over_c**2 * (fins.count * fins.semispan * fins.thickness) / a_ref

    cd_base = (0.12 + 0.13 * mach**2) if include_base else 0.0

    cd_nose = 0.0
    if rocket.nose.shape == "cone":
        half_angle = math.atan(rocket.nose.base_diameter / 2.0 / rocket.nose.length)
        cd_nose = 0.8 * math.sin(half_angle) ** 2

    cd = interference * (cd_body + cd_surfaces + cd_base + cd_nose + rail_button_cd)

    # Transonic drag rise. Crude, and deliberately so -- if a design leans on this
    # region the answer is to change the design, not to refine the model.
    if mach > 0.8:
        cd *= 1.0 + 2.0 * (min(mach, 1.05) - 0.8) ** 2 / 0.0625
    return cd


def induced_drag_coefficient(cn_alpha: float, alpha_rad: float) -> float:
    """Drag penalty from flying at angle of attack, which is what a steering manoeuvre
    costs you in altitude. CD_i = CN * sin(alpha)."""
    return cn_alpha * alpha_rad * math.sin(alpha_rad)
