"""D7 -- the flight computer trade, and what the board has to do.

    python scripts/avionics_trade.py            # to the terminal
    python scripts/avionics_trade.py --write    # and into out/avionics_trade.txt

Written the way `scripts/motor_trade.py` is: score every option against constraints the
project has already computed, print the argument, and let the decision be a decision rather
than a default. The requirements in the second half are DERIVED from the flight model, not
copied from a tutorial -- which matters, because one of them is tight and no tutorial would
have produced it.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import avionics, joints
from design.configure import baseline, evaluate

MM = 1000.0
OUT = Path(__file__).resolve().parents[1] / "out" / "avionics_trade.txt"
lines: list[str] = []


def say(t: str = "") -> None:
    lines.append(t)


def rule(t: str) -> None:
    say()
    say("=" * 92)
    say(t)
    say("=" * 92)


def main() -> None:
    p = baseline()
    ev = evaluate(p)
    navb = joints.budgets(ev.rocket, p.wall_thickness)["nav bay"]

    rule("D7 -- THE THREE ARCHITECTURES")
    say()
    say(f"  nav bay: {navb.usable_length * MM:.1f} mm of sled at a "
        f"{navb.min_bore * MM:.1f} mm bore (design/joints.py)")
    say()
    say(f"  {'':2s} {'architecture':28s} {'mass':>7s} {'cost':>7s} {'weeks':>6s} "
        f"{'sled':>8s} {'fit':>7s}")
    say("  " + "-" * 74)
    results = {}
    for o in avionics.OPTIONS:
        r = avionics.check_packing(navb.min_bore, navb.usable_length, o.nav_bay,
                                   end_closures=0)
        results[o.key] = r
        mark = "  <- SELECTED" if o.key == avionics.SELECTED else ""
        say(f"  {o.key:2s} {o.name:28s} {o.mass * 1000:5.0f} g ${o.cost:6.0f} "
            f"{o.build_weeks:5.1f} {r.required_length * MM:7.1f} mm "
            f"{'FITS' if r.fits else 'NO FIT':>7s}{mark}")
    say()
    for o in avionics.OPTIONS:
        say(f"  {o.key}. {o.note}")

    rule("THE 9 mm SHORTFALL WAS AN ARTEFACT, AND THAT IS THE FIRST RESULT")
    say()
    say("  Before this trade the nav bay was 9 mm short and the four listed ways out ran")
    say("  from 'measure the parts' to 'lengthen a frozen airframe'. Every option above")
    say("  FITS, and the reason is one line item:")
    say()
    say("    guessed 'flight computer PCB'   70 x 40 mm = 28.0 cm2")
    say(f"    real Teensy 4.1                 61 x 17.8 mm = "
        f"{avionics.TEENSY_41.footprint * 1e4:4.1f} cm2")
    say()
    say("  The guess was two and a half times the part. **This is correction 5 replaying,")
    say("  and it vindicates not having lengthened the bay** -- an estimate-driven")
    say("  shortfall, acted on, that was not in the hardware. The rule held twice now.")
    say()
    say("  Two envelopes moved the other way and are worth stating so this does not read")
    say("  as good news only: the StratoLoggerCF is 50.8 x 21.3 mm against a guessed")
    say("  45 x 18, and a GNSS patch antenna is bigger than the receiver behind it.")

    rule("PACKAGING DOES NOT SELECT THE ARCHITECTURE -- and that is worth knowing")
    say()
    say(f"  {'':2s} {'architecture':28s} {'sled needed':>12s} {'margin':>9s}")
    say("  " + "-" * 56)
    for o in avionics.OPTIONS:
        r = results[o.key]
        say(f"  {o.key:2s} {o.name:28s} {r.required_length * MM:9.1f} mm "
            f"{r.margin * MM:+7.1f} mm")
    say()
    say("  A CUSTOM BOARD IS NOT AUTOMATICALLY THE SMALL ONE. The intuition says one")
    say("  integrated PCB beats a dev board plus three breakouts; it does not, because the")
    say("  breakouts are postage stamps and the Teensy is narrow. Option C needs MORE sled")
    say("  than option A on these envelopes.")
    say()
    say("  So the packaging argument for a custom board -- which was the engineering case")
    say("  for taking on eight weeks of hardware risk -- is not there. **The case for")
    say("  option C is a career case, and it is a legitimate one, but it should be made")
    say("  honestly rather than dressed as a packaging win.**")

    rule("WHAT THE BOARD HAS TO DO -- derived from this vehicle, not from a tutorial")
    say()
    for r in avionics.board_requirements(ev):
        say(f"  {r.name.upper()}: {r.value}")
        say(f"      why    {r.why}")
        if r.slack:
            say(f"      slack  {r.slack}")
        say()

    rule("THE ONE THAT IS TIGHT")
    say()
    roll = ev.roll_interdig
    say(f"  Steady roll rate at 8 deg of canard deflection is "
        f"{roll.steady_roll_rate_deg_s:.0f} deg/s.")
    say(f"  Roll acceleration is {roll.roll_accel_deg_s2:.0f} deg/s^2.")
    say()
    say(f"  A +/-2000 deg/s gyro -- the top of the range on most 6-axis parts -- is at")
    say(f"  {roll.steady_roll_rate_deg_s / 2000 * 100:.0f}% of full scale there, and plenty of IMUs are +/-1000.")
    say()
    say("  **A saturated rate gyro in a roll loop is not a degraded measurement, it is a")
    say("  wrong one**, and the controller cannot tell. Three ways out, and the first is")
    say("  free:")
    say()
    say("    1. CAP THE ROLL COMMAND. Roll needs far less deflection than pitch -- the")
    say("       vehicle's roll inertia is tiny. At 2 deg the rate is about a quarter of")
    say("       this. baseline.py already notes roll control needs less deflection.")
    say("    2. PICK A WIDER PART. Some IMUs go to +/-4000 deg/s; it is a line in a")
    say("       datasheet and costs nothing at design time -- if you check before layout.")
    say("    3. MEASURE IT ON GV-2 FIRST. That flight exists to turn Cl_delta from an")
    say("       assumption into a measurement, and this number is downstream of Cl_delta,")
    say("       which docs/01 calls the weakest part of the whole analysis.")
    say()
    say("  Do 1 and 2. They are both free and they are not exclusive.")

    text = "\n".join(lines)
    print(text)
    if "--write" in sys.argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text + "\n")
        print(f"\nwritten to {OUT}")


if __name__ == "__main__":
    main()
