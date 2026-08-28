# Motor selection (L2)

Method: `scripts/fetch_motors.py` downloaded all 102 currently-available 54 mm J and K
solid motors from ThrustCurve.org as RASP `.eng` curves. `scripts/motor_trade.py` flies the
frozen baseline airframe on every one of them and scores against the requirements.

These are real certification thrust curves, not estimates. The airframe mass around them is
still a budget, so treat apogee as ±15% until components are weighed.

## Criteria, in priority order

1. **Hard requirements** (`docs/00-requirements.md`): T/W ≥ 5, rail exit ≥ 15 m/s, static
   margin 1.4–3.0 cal, apogee inside the waiver window.
2. **Max Mach ≤ 0.6**, tighter than the 0.8 requirement. Barrowman, the linear control
   derivatives, and the controller derived from them are all subsonic. Margin away from
   the transonic region is worth more than altitude.
3. **Peak axial acceleration ≤ 16 g.** Most MEMS accelerometers on a flight computer clip
   at ±16 g. Clipping during boost corrupts velocity and attitude estimation exactly when
   it matters. Choosing a gentler motor is far cheaper than dual-range sensor fusion.
4. **Non-sparky propellant.** Sparky/Skidmark propellants are restricted at many sites in
   dry conditions, and this project needs five or six repeatable flights on a schedule. A
   propellant that can be banned on launch day is a schedule risk.
5. **Reloadable, widely stocked, minimal-assembly.** Same reason. Also: a motor CATO from
   a misassembled reload takes your flight computer and your data with it.
6. Then maximise usable control: coast seconds at meaningful dynamic pressure, and the
   resulting crossrange.

## Result for a ~3000 ft waiver

Only 7 of 102 motors satisfy every hard requirement and every preference.

| Motor | Mfr | Prop | N·s | Burn | T/W | Peak g | Mach | Apogee | Static margin | Ctrl window | Crossrange |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **821J430-18A** | Cesaroni Pro54 | White Thunder | 817 | 1.96 s | 7.7 | 8.7 | 0.39 | 838 m | 1.68–2.05 | 9.0 s | 118 m |
| J460T | AeroTech RMS-54 | Blue Thunder | 848 | 2.16 s | 7.3 | 9.3 | 0.41 | 926 m | 1.67–2.07 | 9.3 s | 132 m |
| J350-SF | Loki | Spitfire (sparky) | 983 | 2.70 s | 6.1 | 6.9 | 0.41 | 961 m | **1.43**–1.93 | 9.5 s | 159 m |
| 838J293-13A | Cesaroni Pro54 | Blue Streak | 831 | 2.90 s | 5.3 | 5.5 | 0.36 | 806 m | 1.64–2.05 | 8.4 s | 91 m |
| J615ST | AeroTech RMS-54 | Super Thunder | 763 | 1.24 s | 11.4 | 14.0 | 0.38 | 760 m | 1.66–2.02 | 8.7 s | 111 m |
| J550ST | AeroTech RMS-54 | Super Thunder | 732 | 1.39 s | 9.7 | 10.5 | 0.36 | 696 m | 1.64–2.00 | 8.2 s | 90 m |
| J315R | AeroTech RMS-54 | Redline | 752 | 2.66 s | 5.2 | 6.0 | 0.33 | 703 m | 1.65–2.05 | 7.6 s | 66 m |

### Decision: Cesaroni Pro54 J430 White Thunder (`821J430-18A`)

Not the top of the crossrange column, and chosen anyway:

- Best static margin in the group (1.68 cal at rail exit) with a healthy T/W of 7.7.
- Peak 8.7 g, comfortably clear of accelerometer clipping.
- Mach 0.39, less than half the transonic threshold, so every linear assumption in the
  analysis holds with margin.
- Pro54 reloads ship as pre-assembled cartridges — slide in, done. For a project where
  your time belongs in avionics rather than motor assembly, this materially reduces risk.
- Adjustable delay, and can be flown plugged for electronic dual deploy.
- Not sparky. 236 mm case is the cheap, common Pro54 3-grain hardware.

**Rejected despite better numbers:** Loki J350 Spitfire tops the crossrange column but is
sparky, is the heaviest reload in the group (1260 g, which drags the rail-exit static
margin down to 1.43 cal — only 0.03 above the floor), and Loki hardware is less commonly
stocked. Wrong trade for a project needing repeatable flights.

**Closest alternative:** AeroTech J460T is essentially equivalent on flight performance
and slightly better on crossrange. Choose it if you already own RMS-54 hardware. It needs
full reload assembly, which is more steps to get wrong.

**Avoid** J615ST and J550ST: 10–14 g peak for a shorter control window. All cost, no gain.

## Why burn time is not a control-time knob

The natural objection to a 1.96 s burn is that a longer burn should give more time to
steer. It does not, and `scripts/burn_time_study.py` demonstrates this two ways.

**Controlled experiment**, synthetic constant-thrust motors at a fixed 817 N·s:

| Burn | Peak g | V at burnout | q max | ∫q dt (coast) | ∫q dt (all flight) | Control window | Crossrange |
|---|---|---|---|---|---|---|---|
| 0.6 s | 25.4 | 146 m/s | 13.0 kPa | 45.0 kPa·s | 48.1 | 9.6 s | 171 m |
| 1.2 s | 11.9 | 139 m/s | 11.8 kPa | 40.0 kPa·s | 45.3 | 9.2 s | 145 m |
| 2.0 s | 6.7 | 130 m/s | 10.3 kPa | 33.9 kPa·s | 41.4 | 8.7 s | 115 m |
| 3.0 s | 4.1 | 120 m/s | 8.7 kPa | 27.3 kPa·s | 36.8 | 8.0 s | 85 m |
| 5.0 s | 2.1 | 100 m/s | 6.0 kPa | 17.4 kPa·s | 28.4 | 6.9 s | 43 m |
| 8.0 s | 1.4 | 80 m/s | 3.8 kPa | 12.4 kPa·s | 21.9 | 5.1 s | 13 m |

**Natural experiment**, all real catalogue motors between 770 and 880 N·s:

| Motor | Burn | Peak g | V at burnout | Crossrange |
|---|---|---|---|---|
| AeroTech J1299N | 0.68 s | 26.5 | 151 m/s | 194 m |
| Cesaroni J430 | 1.96 s | 8.7 | 131 m/s | 118 m |
| AeroTech J460T | 2.16 s | 9.3 | 137 m/s | 132 m |
| Cesaroni J293 | 2.90 s | 5.5 | 122 m/s | 91 m |
| Cesaroni J244 | 3.50 s | 4.0 | 119 m/s | 82 m |
| AeroTech J275W | 3.90 s | 5.3 | 113 m/s | 67 m |
| AeroTech J180T | 4.81 s | 4.9 | 95 m/s | 34 m |

Same impulse, 5.7× the crossrange from the shortest burn versus the longest.

**Mechanism.** Total impulse is a fixed momentum budget, and gravity spends part of it
during the burn: roughly `g·t_burn` of velocity that never becomes airspeed. Canard
authority scales with dynamic pressure, which goes as V², so that linear velocity loss is
punished quadratically. The control *window* also shrinks slightly rather than growing,
because a slower vehicle coasts for less time. Note that the all-flight column falls too,
so this is not an artifact of excluding the boost phase.

**What burn time is actually for.** Lower peak acceleration (accelerometer clipping,
structural loads), lower peak Mach, and lower apogee for a tight waiver. Those are real
benefits, purchased with steering authority. The J430 at 1.96 s is deliberately mid-range:
short enough to bank velocity efficiently, long enough to keep peak acceleration at 8.7 g.
The J1299N proves the point from the other end — largest crossrange in the compliant set,
rejected at 26 g on accelerometer and structural grounds, not on steering.

**Where the intuition is right.** "Longer burn = more control time" is exactly correct for
thrust vector control, where the actuator *is* the motor and control ends at burnout.
Canards invert that: the actuator is airspeed, the motor's job is to hand over kinetic
energy efficiently and get out of the way, and the control phase is the coast. Here the
burn is 2 s and the controllable coast is 8.7 s.

## FINAL DECISION (updated): the field has no altitude ceiling

The prefect confirmed no waiver ceiling, which removes the constraint that had rejected 83
of 94 motors. It does not, however, create an objective — nothing about a guidance project
improves by flying higher, and recovery risk, transonic aerodynamics, visibility and cost
per flight all get worse.

With the ceiling gone, the binding constraint became **recovery footprint**
(`scripts/recovery_study.py`), because drift scales with descent time which scales with
apogee. **That constraint has since been retired too:** the club confirmed (Aug 2026) that
the recovery area is effectively unbounded, so no walk distance in the table below puts the
vehicle off the property. The walk column is now a launch-day time and search-risk cost,
not a hard limit. The decision below was re-examined against that and stands — see the
note after the reasoning bullets:

| Motor | Apogee | Mach | Peak g | Crossrange | Descent | Main | Walk @ 15 mph |
|---|---|---|---|---|---|---|---|
| J430 White Thunder | 814 m | 0.39 | 8.2 | 178 m | 72 s | 55" | 641 m |
| **J449 Blue Streak** | **1409 m** | **0.54** | **8.6** | **513 m** | **102 s** | **56"** | **951 m** |
| J760 White Thunder | 1456 m | 0.59 | 14.4 | 678 m | 104 s | 56" | 946 m |
| K535 | 1638 m | 0.60 | — | 667 m | 113 s | 56" | 1052 m |
| K445 | 1907 m | 0.64 | — | 818 m | 125 s | 57" | 1186 m |
| K630 Blue Streak | 1950 m | 0.70 | — | 1038 m | 128 s | 56" | 1194 m |

K445 and K630 now sit above R6's 1600 m apogee window and are **rejected outright by the
trade study**, which is why they carry no peak-g figure — `motor_trade.py` never scores a
motor it has already screened out. They remain in the recovery table above as reference
points, not as candidates.

**Selected: Cesaroni Pro54 J449 Blue Streak (`1261J449-15A`).** 1260 N·s, 2.85 s burn,
T/W 7.5, 8.6 g, Mach 0.542, apogee 1409 m, static margin 1.83–2.32 cal, 11.5 s usable
control window, and **2.36 g of lateral authority at 8° deflection for 513 m of
crossrange** — roughly 3.6× the J430.

Reasoning for stopping here rather than going to a K:

- 513 m of crossrange is already an unmistakable, filmable, easily-measured manoeuvre. The
  deliverable is a working closed-loop controller, not a crossrange record. Past the point
  where the correction is clearly measurable, extra authority buys nothing.
- Mach 0.542 keeps every assumption in the analysis valid with real margin. K630 at Mach
  0.68 starts approaching where centre-of-pressure movement and drag rise matter.
- 8.6 g stays well clear of accelerometer clipping.
- ~~Roughly 0.96 km walk per flight instead of 1.2–1.5 km, across five or six flights.~~
  **Void as of Aug 2026** — with an unbounded recovery area this is a longer walk, not a
  lost vehicle. It is the only one of these five reasons that field size ever supported.
- J-class reloads are meaningfully cheaper than K, and flight count is what this project
  is actually short of.

**Re-examined after C5a was resolved (Aug 2026).** Four of the five reasons above never
depended on field size: crossrange is already unmistakably measurable, Mach 0.542 keeps
every modelling assumption valid, 8.6 g stays clear of accelerometer clipping, and J-class
reloads buy more flights than K-class. The J449 stands. Flying a K now costs the same
vehicle and buys crossrange this project does not need, at a Mach number that makes the
aero harder to defend.

**Contingency:** the interference model is the least trustworthy part of the analysis. If
GV-2 measures materially less authority than predicted, more impulse is the upgrade path
that needs no airframe change — the 54 mm mount takes all of it.

Note the contingency moved. On the older, smaller-finned airframe the K445 was the obvious
step up; on the current airframe it produces 1851 m and is screened out by R6's 1600 m
window. The in-window upgrades are now **K513FJ** (1538 m, Mach 0.58, 9.3 g, 572 m
crossrange) and **K535** (1584 m, Mach 0.58, 9.2 g, 565 m) — both roughly 1.3× the J449's
crossrange while staying inside every requirement. Going past them to a K445 or K630 means
consciously relaxing R6, which the unbounded recovery area now makes arguable, but it costs
Mach margin and visibility. Budget for a K-class reload either way.

## The full trade, current airframe

`scripts/motor_trade.py`, 102 real L2 certification curves, apogee window 450–1600 m AGL,
preferred max Mach 0.60. **29 fully compliant, 5 compliant with caveats, 68 rejected
outright.** Rejection reasons: apogee ×51, T/W ×25, static margin ×21, Mach ×11, rail ×5,
other ×2. Apogee is still the largest single rejection reason, which is R6 doing its job.

Ranked by crossrange, the top of the compliant list:

| Motor | Cls | N·s | Burn | T/W | Peak g | Mach | Apogee | Static margin | Ctrl | Crossrange |
|---|---|---|---|---|---|---|---|---|---|---|
| 1266J760-19A | J | 1264 | 1.73 s | 12.5 | 14.4 | 0.59 | 1456 m | 1.89–2.35 | 12.5 s | 678 m |
| K513FJ | K | 1473 | 2.73 s | 8.3 | 9.6 | 0.59 | 1590 m | 1.84–2.52 | 12.7 s | 675 m |
| K610-SK | K | 1530 | 2.70 s | 8.4 | 10.1 | 0.59 | 1589 m | 2.08–2.66 | 12.7 s | 654 m |
| K530SS | K | 1401 | 2.67 s | 8.1 | 8.7 | 0.58 | 1524 m | 1.82–2.55 | 12.6 s | 646 m |
| J800T | J | 1248 | 2.09 s | 10.2 | 13.5 | 0.59 | 1483 m | 1.83–2.31 | 12.3 s | 632 m |
| J670-LB | J | 1267 | 1.96 s | 10.8 | 12.7 | 0.56 | 1409 m | 1.81–2.24 | 12.2 s | 614 m |
| K475 | K | 1392 | 2.94 s | 7.5 | 8.5 | 0.56 | 1477 m | 1.91–2.42 | 12.2 s | 562 m |
| 1281K360-13A | J | 1275 | 3.50 s | 6.2 | 6.1 | 0.53 | 1450 m | 1.41–1.98 | 11.9 s | 534 m |
| **1261J449-15A** | **J** | **1260** | **2.85 s** | **7.5** | **8.6** | **0.54** | **1409 m** | **1.83–2.32** | **11.8 s** | **513 m** |
| K454-SK | K | 1364 | 3.15 s | 6.9 | 7.8 | 0.55 | 1472 m | 1.98–2.59 | 12.0 s | 511 m |

**The J449 ranks 9th on crossrange, and that is fine** — the selection above rests on
peak g, Mach margin, and cost per flight, not on topping this column. Of the eight motors
that beat it, four are K-class (cost, and fewer flights for the same budget) and three of
the four J-class ones do it at 12.7–14.4 g, which presses accelerometer clipping.

**One candidate is worth a second look before you order:** `1281K360-13A` beats the J449
on crossrange (534 m vs 513 m) *and* on peak g (6.1 vs 8.6), at the same Mach. Its cost is
static margin — 1.41 cal at rail exit against the J449's 1.83, which eats most of the
robustness buffer that §7 of the requirements spent two thirds of the control authority to
buy. That is very likely the wrong trade, but it is the one alternative the numbers do not
immediately dismiss, and it deserves an explicit sentence in your report rather than
silence.

*(This section replaces an older "the answer when a ~5000 ft ceiling applied" reference
table. There was never a ceiling — see C5 — and that table also predated the joint fin
sizing, so it was stale in two independent ways. Removed rather than corrected, because it
documented a hypothetical that never applied.)*

## Before ordering

- ~~Confirm your club's **waiver ceiling**. It changes the recommendation.~~ Done: no
  ceiling, and the recovery area is unbounded too. Get both in writing for the flight card.
- Confirm the motor is in stock and that **you have or can borrow the case**. Pro54 case
  length must match the reload grain count.
- Confirm your site permits the propellant (sparky restrictions vary by day and season).
- Re-run `scripts/motor_trade.py` after replacing budgeted masses with weighed values.
  Motor mass sits at the extreme aft end, so it has strong leverage on static margin: a
  heavier reload moves CG aft and eats your margin.
- Cross-check the chosen motor in OpenRocket, which has the same ThrustCurve data.

## Certification flight

Do **not** certify on the guided vehicle. Fly L2 on a simple, cheap airframe. Using the
same J430 for the cert flight is worth the small extra cost: you learn the motor and its
assembly on a vehicle you can afford to lose, and you get a flight of avionics data as a
passive logger before it ever has to control anything.
