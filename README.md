# RocketSenior — canard-guided high power rocket

Senior capstone project: demonstrate closed-loop lateral guidance of a high power rocket
using forward canards, and handle the canard-wake-on-aft-fin interference problem
correctly.

This repository currently holds the **preliminary sizing tool**. It exists to answer the
questions you have to answer *before* you can draw anything in OpenRocket: how big is the
tube, how big are the fins, which motor, and can the canards actually do anything.

## Why a sizing tool instead of just using OpenRocket

OpenRocket is a verification tool. It answers "is *this specific* rocket stable, and how
high does it go." It cannot answer "what should my rocket be," because that depends on
constraints it knows nothing about:

- the internal diameter needed to house four canard servos (this sets your airframe size),
- the lateral acceleration you need for a visible manoeuvre,
- the static margin you are willing to trade away to get control authority,
- whether the canard wake reverses the sign of your roll moment.

This tool computes those, converges on a baseline, and then prints the numbers to type
into OpenRocket for an independent cross-check. Use both. Disagreement between them is
information.

## Quick start

```bash
pip install -r requirements.txt

python scripts/packaging_report.py   # what diameter do the actuators force on you?
python scripts/fetch_motors.py --diameter 54 --classes J K   # real thrust curves
python scripts/motor_trade.py        # rank every real L2 motor against the airframe
python scripts/sweep.py              # which (tube, motor, fin) combos meet requirements?
python scripts/baseline.py --plot    # full analysis + OpenRocket entry values
```

## Layout

```
design/
  atmosphere.py   US Standard Atmosphere 1976, troposphere
  recovery.py     dual-deploy sizing, descent time, wind drift
  geometry.py     nose / tube / fin set definitions, Barrowman CP geometry
  packaging.py    actuator bay packaging + hinge moment + servo torque margin
  aero.py         Barrowman CNa & CP buildup, component drag buildup
  mass.py         geometric structural mass + editable subsystem budget, CG
  motors.py       RASP .eng thrust curve parser + placeholder generic motors
  trajectory.py   3-DOF RK4 ascent to apogee
  control.py      canard pitch authority, roll authority, wake interference, crossrange
  configure.py    parameter set -> full vehicle -> requirement scoring
scripts/
  packaging_report.py   diameter vs servo class table
  fetch_motors.py       download real .eng thrust curves from ThrustCurve.org
  motor_trade.py        rank every available L2 motor against the baseline airframe
  burn_time_study.py    why burn time is not a control-time knob
  recovery_study.py     descent, drift and the recovery footprint constraint
  robustness.py         Monte Carlo on static margin; sets the aft fin size
  sweep.py              design space sweep against requirements
  baseline.py           detailed baseline report + OpenRocket values
docs/
  00-requirements.md    requirements, constraints, scoping, regulatory actions
  01-next-steps.md      ordered plan with concrete deliverables
  02-motor-selection.md L2 motor trade study and decision
```

## How this fits with OpenRocket and RocketPy

Three tools, each for what it is actually good at. Do not try to make one do everything.

| Tool | Use it for | Do not use it for |
|---|---|---|
| **This repo** | Actuator packaging, control derivatives (`Cm_delta`, `Cl_delta`, `Cl_p`), canard/aft-fin wake interference, hinge moments, requirement-driven sizing sweeps across 100+ motors | Final apogee or drag numbers |
| **OpenRocket** | Validated stability and trajectory, Mach-dependent drag, dual-deploy and recovery sizing, fin flutter, the airframe truth a reviewer will trust | Anything involving a deflected control surface. It has no concept of one |
| **RocketPy** | 6-DOF flight with wind, Monte Carlo dispersion, and closed-loop control. `LinearGenericSurface` takes coefficient derivatives as functions of Mach, alpha, beta and body rates; `Controller` runs your control law at a fixed sampling rate against simulated IMU and barometer sensors | Preliminary sizing; it needs a vehicle before it can fly one |

The intended pipeline: size here → validate the passive airframe in OpenRocket → export
the derivatives from here into a RocketPy `LinearGenericSurface` → close the loop in 6-DOF
→ fly, and replace the interference factors with measured values.

## Model validity and what you must not trust

Read this before you quote any number from this tool in a report.

| Component | Status | Notes |
|---|---|---|
| Atmosphere | Solid | Standard model, valid to 11 km. |
| Barrowman CNa / CP | Good | Standard method. Valid subsonic, small alpha, attached flow. |
| Body lift (Galejs) | Approximate | Nonlinear term linearised about 4 deg alpha. |
| Drag buildup | ±20% at best | Component buildup with empirical form factors. Cross-check against OpenRocket, then against measured flight data. |
| Mass budget | Estimate | Every subsystem line is a guess until you weigh the part. Weigh things. |
| Trajectory | Good given the above | 3-DOF, no wind, perfect weathercocking. |
| Inertias | ±30% | Crude analytical estimate. Measure before tuning gains. |
| Canard control derivatives | Approximate | Linear, quasi-steady, no wake effect on the canards themselves. |
| **Canard/aft-fin interference** | **Weakest part** | Empirical factors with no validation. Trends are believable, absolute values are not. Must be measured in flight. |
| Motor data | Real | 102 available 54 mm J/K certification curves from ThrustCurve.org in `data/motors/`. The `GENERIC` motors in `motors.py` are invented placeholders, kept only so the tool runs before a download. |

The interference model is the one to be honest about in your defense: it is a
physically-motivated parameterisation, not a validated prediction. The project plan
therefore makes measuring it a flight test objective rather than an assumption.

## Baseline result

75 mm (3 in) fiberglass airframe, 79.4 mm OD, 1361 mm long, 4 canards interdigitated 45°
from 4 aft fins, on a Cesaroni Pro54 J449 Blue Streak. 6.19 kg wet / 5.57 kg dry, apogee
1354 m (4444 ft), max Mach 0.523, static margin 1.96 cal at rail exit rising to 2.44 in
coast, 1.98 g of lateral authority at 8° of canard deflection, giving 428 m of crossrange
over an 11.3 second usable control window. Recovery is an 18 in drogue and 57 in main
deployed at 200 m, landing at 5.0 m/s and 51 ft·lbf after a ~0.92 km walk in a 15 mph wind.

Both fin sets were sized *together* by a Monte Carlo on margin robustness rather than
independently by nominal stability — canard semispan 0.85 cal, aft semispan 1.55 cal. They
pull in opposite directions, and searching them jointly under a probabilistic margin
constraint beats trading one against the other. See `docs/00-requirements.md` §7.

Every number above is an output of `scripts/baseline.py`. Regenerate them rather than
editing them by hand; they will move as the mass budget is replaced with weighed parts.

Run `scripts/baseline.py` for the current numbers; the ones above will drift as the mass
budget is replaced with measurements.
