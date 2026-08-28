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
| Read current NAR + TRA codes, write summary | You | Week 1 | TBD |
| Email club prefect describing the project, get written response | You | Week 1 | **DONE (Aug 2026).** File the written response in `docs/` — it is the evidence, not the email you sent |
| Advisor + export control office contact | You | Week 2 | TBD |

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
| R1 | Static margin, canards at zero, at rail exit | 1.5 – 2.5 cal **nominal**, and P(SM < 1.0) < 1% under mass/CP uncertainty. **Currently met only with 75 g+ of nose ballast** — see §7 | Below ~1.0 unsafe; above ~3 the vehicle weathercocks hard and fights the controller. The probabilistic half of this requirement is what sized the aft fins — see §7 |
| R2 | Static margin must stay > 1.0 cal with canards at full deflection | *(computed)* | Canards are ahead of the CG and are *destabilizing*; this is the trap in canard design |
| R3 | Rail exit velocity | ≥ 15 m/s (prefer ≥ 20) | Fin authority at rail exit; standard HPR practice |
| R4 | Thrust-to-weight at ignition | ≥ 5:1 | Standard HPR practice |
| R5 | Max Mach | ≤ 0.8 | Keeps you subsonic. Transonic aero invalidates Barrowman, makes the controller design far harder, and adds no value to a controls project |
| R6 | Apogee | ≤ 1600 m (5250 ft) AGL | **Neither a waiver limit nor a field-size limit** — both are unbounded at this site (C5, C5a). The cap is retained on the three grounds that survive: keeping max Mach under 0.8 with real margin (R5), keeping the manoeuvre visible and filmable from the pad, and holding search time and cost per flight low enough to fly five or six times *with the data intact*. An unbounded field removes the risk of landing off the property; it does not make a rocket easier to find. See `scripts/recovery_study.py` |
| R7 | Internal diameter for actuator bay | ≥ 69 mm → **75 mm airframe minimum** (see §4) | Drives airframe diameter |
| R8 | Commanded lateral acceleration authority early in coast | ≥ 0.5 g | Enough for a measurable, visible correction. Baseline achieves 2.36 g at 8°, for 513 m of crossrange |
| R9 | Roll authority | Net Cl_delta must retain correct sign at all conditions, with ≥ 50% of canard-only authority surviving interference | See §5 |
| R10 | Control loop rate | ≥ 100 Hz | Baseline pitch mode is 2.4 Hz, so 100 Hz gives ~40x margin |
| R11 | Recovery | Dual deploy: 18 in drogue at apogee, **56 in** main at 200 m (650 ft). 5.0 m/s landing, 49 ft·lbf, 102 s descent | Sized by `design/recovery.py`, drogue fixed at 18 in and main solved for the landing rate. Landing energy is inside the ~75 ft·lbf guidance; confirm the current figure with your prefect |
| R12 | Canards centered + locked on any fault, loss of nav, or after burnout+N s | Mandatory | Safety, and required to get range approval |

---

## 4. Actuator bay — why this sets the tube diameter

You were right that the body has to be bigger to fit servos and the computer, but the
binding constraint is more specific than "bigger." For **direct-drive canards**, the
servo sits radially, output shaft coincident with the canard shaft at the tube wall,
body pointing inward. So the servo's *length* eats the tube radius:

    required_ID ≈ 2 x (servo_length + shaft_hub + clearance)

That single relation is what rules out small tubes, and it is modelled in
`design/packaging.py`. Run `python scripts/packaging_report.py` for the table.

Result, for 4 canards on direct drive with an 8 mm shaft/coupler allowance:

| Airframe | ID | Sub-micro | Micro | Mini | Standard | Verdict |
|---|---|---|---|---|---|---|
| 54 mm | 53 mm | no | no | no | no | **Dead.** Not even a sub-micro servo fits radially. |
| 66 mm | 62 mm | no (−4 mm) | no | no | no | Marginal at best; do not design around it. |
| 75 mm | 75 mm | yes | yes (+2 mm) | yes (+3 mm) | no | **Minimum viable.** Chosen baseline. |
| 98 mm | 97 mm | yes | yes | yes (+25 mm) | no (−11 mm) | Comfortable, but heavier and needs a bigger motor for the same altitude. |
| 129 mm | 126 mm | yes | yes | yes | yes | Overkill for this mission. |

**Decision (D2): 75 mm (3 in) fiberglass airframe, mini-class servos on direct drive.**
Rationale: smallest airframe that houses four direct-drive canard actuators, takes a
54 mm motor mount with an enormous motor selection, and is light enough that a J motor
lands the apogee inside the target window. The packaging margin is only about +3 mm, so
the servo choice must be confirmed against real datasheet dimensions before ordering.

**Both torque and packaging bind, and they bind on different servo classes.** Peak
aerodynamic hinge moment is **0.0665 N·m per panel** at max dynamic pressure and 8°
deflection (`scripts/baseline.py`), with the hinge at 0.20c, forward of the 0.25c panel CP
so the panel is restoring rather than divergent. After a 0.4 derate on stall torque:

| Servo | Length | Stall | Packaging margin | Torque margin | Verdict |
|---|---|---|---|---|---|
| sub-micro class | 20.0 mm | 0.05 N·m | +9.2 mm | 0.30× | fits easily, nowhere near the torque |
| micro class | 23.6 mm | 0.20 N·m | +1.6 mm | 1.20× | fails both |
| mini class | 22.8 mm | 0.25 N·m | +3.1 mm | 1.50× | fails torque |
| mini high-torque class | 23.0 mm | 0.55 N·m | +3.1 mm | 3.31× | ok, but generic |
| **KST X08 Plus V6.0** | **23.5 mm** | **0.52 N·m** | **+2.3 mm** | **3.13×** | **selected (D4)** |
| MKS HV6100 | 22.5 mm | 0.333 N·m | +4.1 mm | 2.00× | fallback, exactly at the limit |

Note "micro" is *longer* than "mini high-torque" (23.6 vs 23.0 mm) despite the name — class
names track mass, not the dimension that consumes tube radius. A physically
smaller-sounding servo makes the packaging worse, not better.

The MKS HV6100 lands on exactly 2.00× and has no margin left; it is the shorter part, so it
buys +2.1 mm of bushing room against the KST's +1.2 mm, but it must run at 8.2 V and any
growth in hinge moment puts it under the requirement. Prefer the KST unless the bushing
turns out not to fit.

**Unresolved before ordering:** KST publish a 23.5 mm case but a 29.5 mm maximum dimension
including mounting lugs. These numbers use the case. If the lugs sit in the radial path
they consume 6 mm the 75 mm airframe does not have. Check the dimensioned drawing and the
output shaft position before buying four.

An earlier version of this section quoted 0.027 N·m and an 8× margin. That was computed on
the old 0.45 cal canards; the joint fin sizing in §7 grew them to 0.85 cal, which roughly
doubled panel area and with it the hinge moment.

---

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
| D2 | Airframe diameter | 54 / 75 / 98 mm | **75 mm**, set by actuator packaging (§4) | RESOLVED |
| D3 | Canard count | 3 / 4 | **4**, interdigitated at 45° with 4 aft fins (§5) | RESOLVED |
| D4 | Canard actuation | direct-drive / bellcrank | **direct drive**, **KST X08 Plus V6.0** (23.5×8×16.8 mm, 9 g, 5.3 kgf·cm @ 8.4 V); a linkage puts backlash inside the control loop. Fallback **MKS HV6100** (22.5×10×23.5 mm, 10 g) — shorter, so more bushing room, but HV-only and tighter on torque | RESOLVED, pending lug-clearance check against the dimensioned drawing |
| D5 | Aft fin count and size | 3 / 4, semispan 0.95–1.85 cal | **4 panels, semispan 1.55 cal.** Set jointly with the canards (D11) by the margin robustness study (§7), not by nominal stability. Larger fins raise static margin but cost authority and push toward roll reversal (§5) | RESOLVED |
| D11 | Canard size | semispan 0.70–1.00 cal | **0.85 cal semispan**, 0.70 cal root, 0.70 taper. Sized jointly with the aft fins (D5) under the probabilistic margin constraint — see §7. Sizing the two sets independently was the original mistake | RESOLVED |
| D10 | Nose ballast provision | none / fixed / adjustable | **Adjustable** threaded rod + washers in the nose shoulder. Lets you set margin after weighing the real vehicle (§7) | RESOLVED |
| D6 | Motor | 102 available 54 mm J/K motors | **Cesaroni Pro54 J449 Blue Streak** (`1261J449-15A`). ~2.9× the crossrange of the J430 while staying at Mach 0.542 and 8.6 g. Ranks 9th on crossrange alone; chosen on peak g, Mach margin and cost per flight. See `02-motor-selection.md` | RESOLVED |
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
| Canards | 4 panels, 55.6 root / 38.9 tip / **67.5 mm semispan**, 45° interdigitated |
| Aft fins | 4 panels, 151 root / 68 tip / **123.1 mm semispan**, 87 mm sweep |
| Mass | 5.37 kg dry, 5.99 kg wet |
| Static margin | 1.83 cal at rail exit, 2.32 cal in coast |
| Flight | apogee 1409 m (4623 ft), max Mach 0.542, max q 20.2 kPa, 8.6 g peak, T/W 7.5 |
| Control | 2.36 g lateral at 8° deflection, 513 m crossrange over an 11.5 s window |
| Roll | Cl_delta +6.15 /rad canards vs −0.95 /rad aft fins interdigitated (15.4% cancellation) |
| Actuator | KST X08 Plus V6.0, 3.1× torque margin, +2.3 mm packaging margin |
| Hinge | 0.0665 N·m per panel, hinge at 0.20c — forward of the 0.25c panel CP, so restoring |
| Fin flutter | aft fins 1.94× margin, canards 5.31× (see §8) |
| Recovery | 102 s descent, ~0.95 km walk at 15 mph wind, 56 in main |
| Nose ballast | **75 g minimum, 100 g design point** — required to meet R1 (see §7.1) |
| Margin robustness | P(SM < 1.0) = 1.8% bare / 0.58% with 100 g ballast, P(SM < 1.4) = 14.6% / 7.9% |
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
| 1.05 cal | 0.50 | 99.1% | 90.5% | 100% |
| 1.15 cal | 0.83 | 93.0% | 67.6% | 60% |
| 1.25 cal | 1.12 | 76.7% | 38.4% | 45% |
| 1.40 cal | 1.50 | 41.0% | 9.8% | 34% |
| 1.55 cal | 1.81 | 14.7% | 1.8% | 29% |

Buying acceptable risk this way costs over two thirds of the lateral authority.

**Second pass — size both fin sets together, and this is the one that set the airframe.**
Sizing them independently was the original mistake. They pull in opposite directions:
canard area buys authority but costs margin, aft area buys margin but costs authority.
Searched *jointly* under the probabilistic margin constraint plus the flutter and servo
torque limits, the answer is to grow **both**, which beats the original airframe on
crossrange and on safety at the same time instead of trading one against the other:

| Canard semispan | Aft semispan | Nominal SM | P(SM<1.0) | Lateral g | Crossrange | Flutter | Torque | Verdict |
|---|---|---|---|---|---|---|---|---|
| 0.70 cal | 1.55 cal | 2.11 | 0.2% | 1.69 g | 369 m | 1.93 | 3.4× | ok |
| 0.70 cal | 1.70 cal | 2.35 | 0.0% | 1.55 g | 335 m | 1.73 | 3.6× | ok |
| 0.85 cal | 1.40 cal | 1.49 | 10.5% | 2.66 g | 586 m | 2.19 | 2.3× | risk 10.5% |
| **0.85 cal** | **1.55 cal** | **1.80** | **2.1%** | **2.36 g** | **513 m** | **1.94** | **2.5×** | **selected, + ballast** |
| 0.85 cal | 1.70 cal | 2.05 | 0.4% | 2.15 g | 460 m | 1.74 | 2.6× | ok |
| 0.85 cal | 1.85 cal | 2.26 | 0.1% | 1.98 g | 420 m | 1.57 | 2.8× | ok |
| 1.00 cal | 1.70 cal | 1.78 | 2.4% | 2.82 g | 601 m | 1.75 | 2.1× | risk 2.4% |
| 1.00 cal | 1.85 cal | 2.00 | 0.5% | 2.58 g | 543 m | 1.58 | 2.2× | ok |

**Decisions D11 and D5: canard semispan 0.85 cal, aft semispan 1.55 cal, plus nose
ballast.**

### 7.1 Why the selected point needs ballast

Note the selected row sits at **2.1%**, above the 1% limit. That is a change from the
earlier answer, and the cause is hardware, not aerodynamics: the mass budget originally
carried a 55 g placeholder per servo, and the real part (KST X08 Plus, 9 g) removed ~180 g
from the canard module, which sits *forward* of the CG. CG moved 10.5 mm aft and nominal
margin fell 1.94 → 1.80 cal.

There are two ways to buy that back, and they are not equally good:

| | Crossrange | Flutter margin | Reversible after build? |
|---|---|---|---|
| Grow aft fins to 1.70 cal | 460 m | 1.74× | No — cut once |
| **Keep 1.55 cal, add nose ballast** | **~480 m at 100 g** | **1.94×** | **Yes — it is a washer stack** |

**Ballast wins.** It preserves flutter margin, costs less crossrange, and — the real
argument — it is the one variable you can still set *after* weighing the finished vehicle.
Fin size is a prediction you commit to at build time; ballast is a measurement you respond
to. Growing the fins to fix a mass estimate would be trading a tunable parameter for a
permanent one.

Ballast at a station 191 mm from the nose tip:

| Ballast | Median SM | 5th pct | P(SM<1.0) | P(SM<1.4) | Authority | R1 |
|---|---|---|---|---|---|---|
| 0 g | 1.80 | 1.17 | 1.79% | 14.6% | 100% | **FAIL** |
| 50 g | 1.87 | 1.24 | 1.09% | 10.8% | 96% | **FAIL** |
| **75 g** | **1.91** | — | **0.81%** | 8.9% | ~94% | **PASS** |
| 100 g | 1.94 | 1.31 | 0.58% | 7.9% | 93% | PASS |
| 200 g | 2.07 | 1.45 | 0.15% | 3.7% | 87% | PASS |
| 300 g | 2.20 | 1.58 | — | 1.7% | 82% | PASS |

**75 g is the minimum that satisfies R1; carry 100 g as the design point** and provision
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
