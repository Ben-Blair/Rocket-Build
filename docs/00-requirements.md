# Requirements & Constraints — Canard-Guided High Power Rocket

Status: **DRAFT v0.1**. Every `TBD` is a decision that must close before the airframe
is frozen. Nothing gets ordered until this document has no `TBD` in the "Frozen by"
column for that item.

---

## 1. Mission statement

Demonstrate closed-loop lateral guidance of a high power rocket using forward canards,
including correct handling of canard-induced flow interference on the aft fin set.

### 1.1 Scoping the word "waypoint"

This matters more than any geometry decision, so it goes first.

A rocket under boost and coast has control authority only while it has airspeed, and it
cannot loiter, slow down, or turn around. A "waypoint" in the sense used in UAV work
(fly to a 3-D point, arrive, proceed to the next) is not physically achievable on a
ballistic high power flight. What *is* achievable, in increasing order of difficulty:

| Level | Capability | Notes |
|---|---|---|
| L0 | Passive flight, canards locked at zero | Baseline. Proves airframe + avionics. |
| L1 | **Roll control** — hold roll angle / null roll rate | Single axis, well-posed, the standard first result. This is where the canard/aft-fin interference problem shows up most sharply. |
| L2 | **Attitude hold** — hold commanded pitch/yaw attitude, e.g. vertical | Nulls wind-induced weathercocking. Visibly impressive on video. |
| L3 | **Guidance to a ground target** — bias attitude to steer the impact/apogee point toward a commanded lat/lon | This is the closest honest analogue to "waypoint." Crossrange is limited (the tool in this repo computes how much). |
| L4 | Multi-waypoint path following during ascent | Not physically meaningful for this vehicle class. |

**Recommendation:** define the project as L1 → L2 → L3, with L1 as the minimum
success criterion and L3 as the stretch goal. Frame it as "closed-loop guidance
to a commanded ground target" rather than "waypoints in the air." That is defensible
in a defense, and it is achievable in two semesters.

If you genuinely want multi-waypoint navigation, the standard way to get it is a
**guided recovery** phase: deploy a steerable parafoil at apogee and navigate under
canopy, where you have minutes of flight time instead of seconds. That is a separate
subsystem and arguably a separate project. Decide now; do not try to do both.

### 1.2 Regulatory / range-access constraint — RESOLVE IN WEEK 1

Actively steered rockets sit in a genuinely restricted area, and this can kill the
project outright if discovered late. Before any hardware is purchased, you must
personally confirm all of the following in writing:

- **Club safety codes.** NAR and Tripoli sanctioned launches place restrictions on
  rockets carrying active guidance intended to steer the vehicle toward a target.
  Read the *current* NAR High Power Rocket Safety Code and Tripoli Safety Code
  yourself, then talk to the prefect/RSO of the specific club you intend to fly with.
  Active roll and attitude *stabilization* research projects have flown at research
  launches with prior approval; do not assume, get it approved.
- **FAA.** 14 CFR Part 101 Subpart C governs amateur rockets and the waiver your club
  files. Confirm with the club whether an actively guided vehicle is covered by their
  standing waiver.
- **Export control.** Guided rocket technology can touch ITAR (USML Category IV).
  For a university project this is normally handled by your institution's export
  control / research compliance office. Ask your faculty advisor to loop them in.
- **University IRB/EH&S and advisor sign-off.**

Practical mitigations that keep you clearly inside the lines and are commonly
accepted: (a) authority-limited actuators, so the vehicle physically cannot deviate
far; (b) canards mechanically locked to zero for the first flight; (c) a hard
"disarm on anomaly" that centers and locks the canards; (d) framing and documenting
the work as active stabilization research rather than target guidance; (e) flying at a
site that explicitly permits research/experimental flights (e.g. FAR, or a Tripoli
research launch).

| Action | Owner | Due | Status |
|---|---|---|---|
| Read current NAR + TRA codes, write summary | You | Week 1 | **DONE (Aug 2026)** — file the summary in `docs/` |
| Email club prefect describing the project, get written response | You | Week 1 | **DONE (Aug 2026).** File the written response in `docs/` — it is the evidence, not the email you sent |
| Advisor + export control office contact | You | Week 2 | **DONE (Aug 2026)** — keep the written response on file; it is the first thing a reviewer asks for |

---

## 2. Hard constraints (the things you cannot design around)

| # | Constraint | Value | Source |
|---|---|---|---|
| C1 | Certification level held | TBD (assume none today) | You |
| C2 | Max motor impulse you may legally fly | L1 → H/I, L2 → J/K/L | NAR/TRA |
| C3 | Budget ceiling | TBD | You |
| C4 | Calendar: design freeze / build / flight window | TBD | Academic calendar |
| C5 | Field waiver altitude at your site | **No ceiling** (per prefect). Get this in writing — an unlimited ceiling is unusual and normally implies restricted airspace or a special waiver, and the actual document matters for flight cards | Club |
| C5a | Recovery area dimensions | **RESOLVED (Aug 2026): effectively unbounded.** No property boundary within any credible drift radius, so field size no longer sets max apogee and this is no longer the governing constraint. The apogee cap in R6 survives on other grounds | Club |
| C6 | Machining/fab access (lathe, mill, printer, layup) | TBD | Your school |

### 2.1 Certification is a schedule driver, not a formality

To fly a J motor or above you need **Level 2**, which requires holding **Level 1**
first, plus a written exam. Each cert is a separate flight on a separate launch day,
and launch days are weather-dependent and often monthly. Working backward from a
spring flight window, an L1 attempt needs to happen very early in the fall.

Do **not** attempt certification on the guided vehicle. Build a simple, cheap,
throwaway L1/L2 airframe for the cert flights. It is also the best possible avionics
testbed: fly the flight computer as a passive data logger in the cert rocket, so by
the time it flies in the guided vehicle the sensor stack and logging are already
flight-proven.

| Milestone | Target date | Status |
|---|---|---|
| L1 cert flight (H/I motor, simple kit) | TBD — earliest possible | TBD |
| L2 written exam | TBD | TBD |
| L2 cert flight (J motor) | TBD | TBD |
| Guided vehicle flight 1 (canards locked) | TBD | TBD |
| Guided vehicle flight 2 (roll control active) | TBD | TBD |

---

## 3. Derived requirements

These are the numbers the sizing tool in `design/` either consumes or produces.
Values marked *(computed)* are outputs of `scripts/sweep.py` and
`scripts/baseline.py`, not guesses.

| # | Requirement | Target | Rationale |
|---|---|---|---|
| R1 | Static margin, canards at zero, at rail exit | 1.5 – 2.5 cal **nominal**, and P(SM < 1.0) < 1% under mass/CP uncertainty. **Met with the 100 g of nose ballast now carried in the design** — see §7.1 | Below ~1.0 unsafe; above ~3 the vehicle weathercocks hard and fights the controller. The probabilistic half of this requirement is what sized the aft fins — see §7 |
| R2 | Static margin must stay > 1.0 cal with canards at full deflection | *(computed)* | Canards are ahead of the CG and are *destabilizing*; this is the trap in canard design |
| R3 | Rail exit velocity | ≥ 15 m/s (prefer ≥ 20) | Fin authority at rail exit; standard HPR practice |
| R4 | Thrust-to-weight at ignition | ≥ 5:1 | Standard HPR practice |
| R5 | Max Mach | ≤ 0.8 | Keeps you subsonic. Transonic aero invalidates Barrowman, makes the controller design far harder, and adds no value to a controls project |
| R6 | Apogee | ≤ 1600 m (5250 ft) AGL | **Neither a waiver limit nor a field-size limit** — both are unbounded at this site (C5, C5a). The cap is retained on the three grounds that survive: keeping max Mach under 0.8 with real margin (R5), keeping the manoeuvre visible and filmable from the pad, and holding search time and cost per flight low enough to fly five or six times *with the data intact*. An unbounded field removes the risk of landing off the property; it does not make a rocket easier to find. See `scripts/recovery_study.py` |
| R7 | Internal diameter for actuator bay | Not binding — 4 servos need 79 mm of arc against 188 mm available, 45 mm central void (see §4) | **Superseded.** Diameter is set by the 54 mm motor mount and recovery packing volume, not by the actuators |
| R8 | Commanded lateral acceleration authority early in coast | ≥ 0.5 g | Enough for a measurable, visible correction. Baseline achieves **1.82 g** at 8°, for **390 m** of crossrange |
| R9 | Roll authority | Net Cl_delta must retain correct sign at all conditions, with ≥ 50% of canard-only authority surviving interference | See §5 |
| R10 | Control loop rate | ≥ 100 Hz | Baseline pitch mode is 4.3 Hz, so 100 Hz gives ~23x margin. `baseline.py` derives a ≥87 Hz floor from it |
| R11 | Recovery | Dual deploy: 18 in drogue at apogee, **56 in** main at 200 m (650 ft). 5.0 m/s landing, 50 ft·lbf, 100 s descent | Sized by `design/recovery.py`, drogue fixed at 18 in and main solved for the landing rate. Landing energy is inside the ~75 ft·lbf guidance; confirm the current figure with your prefect |
| R12 | Canards centered + locked on any fault, loss of nav, or after burnout+N s | Mandatory | Safety, and required to get range approval |

---

## 4. Actuator bay — and why it does *not* set the tube diameter

**This section previously argued the opposite, and was wrong.** The correction matters, so
it is documented rather than quietly edited away.

### 4.1 The error

The original argument: for direct-drive canards the servo sits radially with its body
pointing inward, so the servo's *length* consumes tube radius —

    required_ID ≈ 2 × (servo_length + shaft_hub + clearance)

— which ruled out 54 mm and 66 mm airframes, made 75 mm "minimum viable," and left a
packaging margin of only +2.3 mm that drove servo selection for weeks.

That geometry requires the output shaft to sit on the servo's **end** face. **No hobby
servo is built that way.** The output shaft is on a large face, verified against the part
(Aug 2026).

### 4.2 The real arrangement

The servo lies **flat against the inner wall**, output shaft radial, passing through the
wall into the canard root. Its *thickness* consumes radius — 8.0 mm for the KST X08 Plus,
not 23.5 mm. Its *length* runs fore-and-aft along the rocket axis, and only its
*height* has to fit around the circumference:

| Airframe | Inward (old, wrong) | Flat (as built) |
|---|---|---|
| 54 mm | no fit | fits, 21 mm central void |
| 66 mm | no fit | fits, 32 mm central void |
| **75 mm** | +2.3 mm, knife edge | **fits, 45 mm central void** |

Four servos need 79 mm of arc against 188 mm available. **Actuator packaging is not a
binding constraint and never was.** `design/packaging.py` models both; `check_flat_mount()`
is the one describing the vehicle.

This also retires two risks carried for weeks: the mounting-lug clearance question (the
lugs extend the *length* axis, which no longer competes for radius) and the shaft bushing
budget, which now has 45 mm of void to sit in rather than 1.55 mm.

### 4.3 What actually sets the diameter

With actuators out of the way, three things do:

| Constraint | 66 mm | 75 mm |
|---|---|---|
| 54 mm motor mount (57.0 mm OD) | 5.0 mm annulus, 2.5 mm radial | **17.8 mm, 8.9 mm radial** |
| Recovery bay volume for an 18 in drogue + 56 in main | 1.08 L | **1.57 L** against 1.24 L of packed hardware |
| Everything downstream: fin sizing (§7), motor trade, margin robustness, OpenRocket correlation | would all need redoing | **already done** |

**D2 stands at 75 mm, on new grounds.** 66 mm is now theoretically possible where it
previously was not, but a 2.5 mm radial annulus around the motor leaves almost nothing for
centering rings and retention, the recovery packing gets genuinely tight, and the vehicle
does not need to shrink — it meets every requirement with margin. The right response to
"the constraint you thought was binding isn't" is to bank the freedom, not to spend it.

### 4.4 Torque

Torque is unaffected by any of this, and remains the constraint that actually selects the
servo. Peak aerodynamic hinge moment is **0.0577 N·m per panel** at max dynamic pressure
and 8° deflection (`scripts/baseline.py`), with the hinge at 0.20c, forward of the 0.25c
panel CP so the panel is restoring rather than divergent. After a 0.4 derate on stall
torque, against a 2.0× requirement:

| Servo | Length | Thickness | Stall | Torque margin | Verdict |
|---|---|---|---|---|---|
| sub-micro class | 20.0 mm | 8.6 mm | 0.05 N·m | 0.32× | nowhere near |
| micro class | 23.6 mm | 11.6 mm | 0.20 N·m | 1.28× | fails |
| mini class | 22.8 mm | 12.5 mm | 0.25 N·m | 1.60× | fails |
| Hitec HS-5065MG | 23.4 mm | 11.4 mm | 0.219 N·m | 1.40× | fails — the common rocketry pick |
| **KST X08 Plus V6.0** | **23.5 mm** | **8.0 mm** | **0.52 N·m** | **3.60×** | **selected (D4)** |
| MKS HV6100 | 22.5 mm | 10.0 mm | 0.333 N·m | 2.13× | fallback |

Note the Hitec HS-5065MG, the usual choice in hobby rocketry active-control work, misses at
1.40×. Most rocketry servo use is airbrakes and parachute releases — one-shot or lightly
loaded. A canard held against 19 kPa for the whole coast is a harder duty, so the community
answer does not transfer. Capping deflection to about 5.6° at peak q would bring it to
2.0×, which is a legitimate route if availability ever matters.

### 4.5 Mounting

Direct drive, servo bonded or clamped flat into the printed bay, output shaft radial
through a bearing in the tube wall. **Commercial servo frames for this family already do
this** — the Hyperflight SRB-KST-X08 frame and the IDS/LDS kits carry an outboard ball
bearing on the output shaft, which is exactly the load path the canard needs: the bearing
takes the panel bending moment, the servo spline takes only torque.

A bellcrank or pushrod (`check_bellcrank`) also fits, with +33.8 mm to spare, and is the
only way to fit a standard-size servo. It is **not** selected: linkage backlash becomes
deadband in the control loop, and worse, it corrupts GV-2's measurement of `Cm_delta` —
command 8°, the panel reaches 7.2°, and the derivative you publish is wrong. Direct drive
removes that error source. Keep the linkage as the fallback only.

## 5. The canard / aft-fin interference problem

Deflected canards shed a downwash field and a pair of trailing vortices. Those
convect aft and strike the aft fin set, which is what makes canard control
counter-intuitive:

1. **Roll reversal.** Canards deflected differentially to command roll one way induce,
   via their downwash on the aft fins, a roll moment the *other* way. The two partially
   cancel. Depending on geometry, spacing, and interference strength, the *net* roll
   moment can reverse sign — the controller commands right roll and the vehicle rolls
   left, and a naive feedback loop then diverges.
2. **Reduced pitch/yaw effectiveness.** Canard downwash reduces the local angle of
   attack at the aft fins, eroding the moment you thought you had.
3. **Roll-pitch cross-coupling** as the vehicle rolls and the canard plane rotates
   relative to the aft fin plane.

Mitigations, in the order you should consider them:

- **Interdigitate**: place canards at 45° to the aft fins (for 4+4) so the shed
  vortices pass *between* the aft fins rather than onto them. Cheapest and most
  effective fix. Note this makes the aft fins' relative position sensitive to roll
  angle, which is a good argument for closing the roll loop first.
- **Maximize canard-to-fin spacing** so the vortices decay and spread.
- **Keep canard deflection small** and rate-limited; interference grows nonlinearly.
- **Use canards for pitch/yaw only and put roll control on a separate mechanism**
  (or accept roll and de-rotate in software). A legitimate design choice.
- **Identify the sign in flight**: first powered flight does an open-loop deflection
  sweep and logs the response, so you *measure* the sign and magnitude of
  `Cl_delta` and `Cm_delta` rather than trusting a model.

`design/control.py` models items 1 and 2 with an explicit interference factor, and
reports the deflection/geometry region where the net roll moment changes sign.

---

## 6. Open decisions

| # | Decision | Options | Recommendation | Status |
|---|---|---|---|---|
| D1 | Guidance level | L1 / L2 / L3 (§1.1) | L1 min, L3 stretch | TBD |
| D2 | Airframe diameter | 54 / 66 / 75 / 98 mm | **75 mm.** Originally justified by actuator packaging; that argument was wrong (§4.1). Now set by the 54 mm motor mount annulus, recovery packing volume, and the fact that every downstream analysis rests on it. 66 mm became possible once the packaging error was found, and is not worth reopening | RESOLVED, on revised grounds |
| D3 | Canard count | 3 / 4 | **4**, interdigitated at 45° with 4 aft fins (§5) | RESOLVED |
| D4 | Canard actuation | direct-drive / bellcrank | **direct drive**, **KST X08 Plus V6.0** (23.5×8×16.8 mm, 9 g, 5.3 kgf·cm @ 8.4 V); a linkage puts backlash inside the control loop. Fallback **MKS HV6100** (22.5×10×23.5 mm, 10 g) — shorter, so more bushing room, but HV-only and tighter on torque | RESOLVED, pending lug-clearance check against the dimensioned drawing |
| D5 | Aft fin count and size | 3 / 4, semispan 0.95–1.85 cal | **4 panels, semispan 1.55 cal.** Set jointly with the canards (D11) by the margin robustness study (§7), not by nominal stability. Larger fins raise static margin but cost authority and push toward roll reversal (§5) | RESOLVED |
| D11 | Canard size | semispan 0.70–1.00 cal | **0.85 cal semispan**, 0.70 cal root, 0.70 taper. Sized jointly with the aft fins (D5) under the probabilistic margin constraint — see §7. Sizing the two sets independently was the original mistake | RESOLVED |
| D10 | Nose ballast provision | none / fixed / adjustable | **Adjustable** threaded rod + washers in the nose shoulder. Lets you set margin after weighing the real vehicle (§7) | RESOLVED |
| D6 | Motor | 102 available 54 mm J/K motors | **Cesaroni Pro54 J449 Blue Streak** (`1261J449-15A`). ~2.7× the crossrange of the J430 while staying at Mach 0.524 and 8.3 g. Ranks **11th** on crossrange alone; chosen on peak g, Mach margin and cost per flight. See `02-motor-selection.md` | RESOLVED |
| D7 | Flight computer | COTS + custom controller board / full custom | TBD | TBD |
| D8 | State estimation | IMU-only / IMU+baro / IMU+baro+GNSS | IMU+baro+GNSS for L3 | TBD |
| D9 | Airframe material | cardboard / Blue Tube / fiberglass | fiberglass, at minimum for the canard module | TBD |

### 6.1 Baseline airframe as computed

On the selected Cesaroni J449 Blue Streak:

| Item | Value |
|---|---|
| Airframe | 79.4 mm OD (3 in) fiberglass, 2.3 mm wall, 1361 mm long, L/D 17.1 |
| Nose | 4:1 tangent ogive, 318 mm |
| Bays, nose to tail | nav 127 mm, canard module 143 mm, recovery 357 mm, booster 416 mm |
| Avionics location | flight computer, altimeter, GNSS, IMU, battery, BEC in the **nav bay**; telemetry radio and GPS tracker in the **nose** at station 282–318 mm (docs/01 correction 30) |
| Joints | nose/nav **access**, nav/canard **access**, canard/recovery **separation** (main), recovery/booster **separation** (drogue). 1 cal engagement each; a coupler costs bore, not length — `design/joints.py`, docs/01 correction 31 |
| Nose module | Instrumentation, self-contained, one connector. Swappable for a payload up to ~300 g in 469 cm³ (correction 32) |
| Canards | 4 panels, 67.5 root / 27.0 tip / **67.5 mm semispan**, **35.4° LE sweep** matching the aft fins, 45° interdigitated |
| Aft fins | 4 panels, 151 root / 68 tip / **123.1 mm semispan**, 87 mm sweep |
| Mass | **5.55 kg dry, 6.18 kg wet** (includes 100 g nose ballast) |
| Static margin | **2.11 cal at rail exit, 2.60 cal in coast** |
| Flight | apogee **1358 m (4457 ft)**, max Mach **0.524**, max q 18.9 kPa, 8.3 g peak, T/W 7.3 |
| Control | **1.82 g** lateral at 8° deflection, **390 m** crossrange over an 11.6 s window |
| Roll | Cl_delta +5.66 /rad canards vs −0.95 /rad aft fins interdigitated (16.8% cancellation) |
| Actuator | KST X08 Plus V6.0, 3.6× torque margin, 79 mm of arc needed against 188 mm (§4.2) |
| Hinge | 0.0577 N·m per panel, hinge at 0.20c of MAC — forward of the 0.25c panel CP, so restoring at any sweep |
| Fin flutter | aft fins 1.97× margin, canards 4.46× — the 0.40 taper's longer root chord costs the canards 5.42 → 4.46 (see §8) |
| Recovery | 100 s descent, ~0.93 km walk at 15 mph wind, 56 in main. Bay 4.5 cal, verified against vendor pack volumes with +13 mm (§4.3) |
| Nose ballast | **100 g at 191 mm from the nose tip**, ~25 g minimum for R1, provision 300 g (§7.1) |
| Margin robustness | P(SM < 1.0) = 0.4% as designed, 1.2% bare; P(SM < 1.4) = 5.8% / 11.3% |
| OpenRocket correlation | CNa agrees to 0.3%, CP to 0.17 cal (see `03-openrocket-correlation.md`) |

## 7. Static margin robustness

`scripts/robustness.py` runs a Monte Carlo over mass, component position, motor mass and
CP prediction uncertainty. This is the analysis that set **both** fin sizes.

Two results came out of it, and the second one superseded the first.

**First pass — grow the aft fins alone.** The original 1.05 cal aft semispan gave a
*nominal* margin of 0.50 cal and a **90.5% probability of the built vehicle coming out
below 1.0 caliber**, which is not survivable across five or six flights. Growing the aft
semispan alone walks that back, but pays for it in control authority:

| Aft semispan | Nominal SM | P(SM<1.4) | P(SM<1.0) | Relative authority |
|---|---|---|---|---|
| 1.05 cal | 0.69 | 93.0% | 67.4% | 100% |
| 1.15 cal | 0.99 | 76.7% | 38.2% | 73% |
| 1.25 cal | 1.25 | 52.5% | 15.8% | 60% |
| 1.40 cal | 1.58 | 20.3% | 3.0% | 49% |
| 1.55 cal | 1.86 | 5.7% | 0.4% | 43% |

Buying acceptable risk this way costs over two thirds of the lateral authority.

**Second pass — size both fin sets together, and this is the one that set the airframe.**
Sizing them independently was the original mistake. They pull in opposite directions:
canard area buys authority but costs margin, aft area buys margin but costs authority.
Searched *jointly* under the probabilistic margin constraint plus the flutter and servo
torque limits, the answer is to grow **both**, which beats the original airframe on
crossrange and on safety at the same time instead of trading one against the other:

> **The absolute figures in this section and the next predate August 2026**, when the
> dual-deploy altimeter went into `design/mass.py` (docs/01 correction 26). The selected
> point now reads **1.82 g and 390 m**, and `scripts/robustness.py` now picks canard 1.15 /
> aft 1.85 cal rather than 1.00 / 1.70. **The comparisons and the conclusions hold** — every
> row moved the same way — but regenerate with `python scripts/robustness.py` before quoting
> any single number.


| Canard semispan | Aft semispan | Nominal SM | P(SM<1.0) | Lateral g | Crossrange | Flutter | Torque | Verdict |
|---|---|---|---|---|---|---|---|---|
| 0.70 cal | 1.40 cal | 2.00 | 0.5% | 1.57 g | 346 m | 2.22 | 3.6× | ok |
| 0.70 cal | 1.55 cal | 2.28 | 0.1% | 1.45 g | 316 m | 1.96 | 3.7× | ok |
| 0.85 cal | 1.25 cal | 1.38 | 16.4% | 2.36 g | 525 m | 2.56 | 2.5× | risk 16.4% |
| 0.85 cal | 1.40 cal | 1.72 | 3.3% | 2.13 g | 466 m | 2.23 | 2.7× | risk 3.3% |
| **0.85 cal** | **1.55 cal** | **2.00** | **0.5%** | **1.96 g** | **424 m** | **1.97** | **2.8×** | **selected** |
| 0.85 cal | 1.70 cal | 2.23 | 0.1% | 1.83 g | 390 m | 1.77 | 2.9× | ok |
| 0.85 cal | 1.85 cal | 2.43 | 0.0% | 1.72 g | 362 m | 1.60 | 3.0× | ok |
| 1.00 cal | 1.40 cal | 1.46 | 11.7% | 2.74 g | 597 m | 2.24 | 2.1× | risk 11.7% |
| 1.00 cal | 1.55 cal | 1.74 | 2.8% | 2.50 g | 538 m | 1.98 | 2.2× | risk 2.8% |
| *1.00 cal* | *1.70 cal* | *1.98* | *0.6%* | *2.32 g* | *493 m* | *1.78* | *2.3×* | *ok — beats the selected point* |
| *1.00 cal* | *1.85 cal* | *2.19* | *0.1%* | *2.18 g* | *456 m* | *1.61* | *2.4×* | *ok — beats the selected point* |

**Decisions D11 and D5: canard semispan 0.85 cal, aft semispan 1.55 cal.** It satisfies
every constraint — P(SM<1.0) at 0.5% against a 1% limit, flutter 1.97 against 1.5, servo
torque 2.8× against 2.0.

**It is NOT the highest crossrange that does, and this document used to claim it was.**
That claim survived because the table above quoted a subset of rows that happened to
exclude the ones that beat it. Ranking every fully-passing combination:

| | crossrange | |
|---|---|---|
| canard 1.00 / aft 1.70 | **493 m** | passes everything — `robustness.py` picks this as BEST |
| canard 1.00 / aft 1.85 | 456 m | passes everything |
| **canard 0.85 / aft 1.55** | **424 m** | **selected — third, not first** |
| canard 0.85 / aft 1.70 | 390 m | passes everything |
| canard 0.70 / aft 1.40 | 346 m | passes everything |

So `scripts/robustness.py` and this document disagree about the answer, and the script is
the one doing the arithmetic. **The 0.85/1.55 point is retained deliberately, on margin
rather than on authority**: 1.00/1.70 buys 16% more crossrange but spends flutter margin
(1.78 against 1.97) and servo torque margin (2.3× against 2.8×) to get it. The flutter
number is the one to weigh, because §8 reads it as ±25% — published G10 shear modulus spans
3–7 GPa and flutter speed goes as sqrt(G) — so 1.78 nominal has a materially worse tail than
1.97 does. There is also a practical lock-in: the Onshape canard module is built to a
0.85 cal semispan, and growing it means rebuilding that model.

**This is a live decision, not a closed one.** If crossrange turns out to matter for GV-5,
1.00/1.70 is the row to revisit, and the cost is a CAD rebuild plus a thinner flutter tail.
Do not let it stay buried in a table again.

Note the table is computed **with** the 100 g of nose ballast the design now carries; §7.1
explains why that ballast is not optional.

### 7.1 Why the design carries ballast

Without it the selected point sits at **1.2%**, above the 1% limit. The cause is hardware,
not aerodynamics: the mass budget originally carried a 55 g placeholder per servo, and the
real part (KST X08 Plus, 9 g) removed ~180 g from the canard module, which sits *forward*
of the CG.

The 35.4° sweep briefly retired this requirement — swept canards are less destabilising,
and at the old 0.70 taper the bare vehicle sat at 0.7%. Sharpening the taper to 0.40 put
the authority back (CNa 6.34 → 6.55) and with it the destabilising moment, so the bare
vehicle is at 1.2% again and **ballast is required once more**. That round trip is worth
remembering: canard authority and static margin are the same knob viewed from two ends.

There are two ways to buy that back, and they are not equally good:

| | Crossrange | Flutter margin | Reversible after build? |
|---|---|---|---|
| Grow aft fins to 1.70 cal | 390 m | 1.77× | No — cut once |
| **Keep 1.55 cal, add 100 g ballast** | **424 m** | **1.97×** | **Yes — it is a washer stack** |

**Ballast wins.** It preserves flutter margin, costs less crossrange, and — the real
argument — it is the one variable you can still set *after* weighing the finished vehicle.
Fin size is a prediction you commit to at build time; ballast is a measurement you respond
to. Growing the fins to fix a mass estimate would be trading a tunable parameter for a
permanent one.

Ballast at a station 191 mm from the nose tip:

| Ballast | Median SM | 5th pct | P(SM<1.0) | P(SM<1.4) | Authority | R1 |
|---|---|---|---|---|---|---|
| 0 g | 1.86 | 1.23 | 1.21% | 11.3% | 100% | **FAIL** |
| 25 g | 1.90 | 1.26 | 0.93% | 9.9% | ~98% | PASS (minimum) |
| 50 g | 1.93 | 1.30 | 0.73% | 8.3% | 96% | PASS |
| **100 g** | **2.00** | **1.37** | **0.43%** | **5.8%** | **93%** | **PASS — design point** |
| 200 g | 2.13 | 1.51 | 0.14% | 2.6% | 87% | PASS |
| 300 g | 2.26 | 1.64 | 0.04% | 1.1% | 82% | PASS |

**About 25 g is the minimum that satisfies R1; carry 100 g as the design point** and provision
for at least 300 g so you have room to respond to whatever the scale actually says. Note
that authority falls roughly as 1/SM, so ballast is not free — but at 100 g it costs 7% of
a quantity you have 4.7× more of than R8 requires.

**The dominant uncertainty is not any mass line — it is the CP prediction itself**
(±0.35 cal, 1σ, assumed). No amount of ballast or fin area fixes that; only an independent
check does. Two consequences:

1. The OpenRocket cross-check is not a formality, it directly attacks the largest single
   source of risk in the design. Do it before ordering anything.
2. Barrowman is generally *conservative* at low angle of attack (real CP tends to sit aft
   of prediction), so the symmetric error band used here is likely pessimistic on the
   dangerous side. That is the correct direction to be wrong in.

**Also required: a nose ballast provision.** A threaded rod and washer stack in the nose
shoulder. §7.1 above sizes it; this is the hardware note. It converts static margin from a
prediction you are betting the vehicle on into a parameter you measure and set after
weighing the built rocket, and it has just earned its place by absorbing a 180 g change in
the servo line without touching the airframe.

Every number above is an output of `scripts/baseline.py` and will move as the mass budget
is replaced with weighed components.
