# What this vehicle lacks, versus a canard missile

A comparison against a classic rolleron Sidewinder (AIM-9B: canards, fixed tail, no
thrust vectoring). AIM-9X is a worse analog — it adds thrust vectoring.

> **THIS DOCUMENT IS ABOUT A VERTICAL LAUNCH, AND ONE OF ITS HEADLINE CONCLUSIONS DOES NOT
> SURVIVE A HORIZONTAL ONE (Sep 2026).** Section 7's bolded result — "agility on this
> airframe comes from static margin, not from the motor" — is correct here and is an
> artefact of **R6**: on a vertical flight the 1600 m apogee cap binds long before R5's
> Mach 0.8 does, so the search could never reach the speed band. Flown at a 30 deg rail,
> apogee is 250-650 m whatever the motor, the whole band from Mach 0.42 to Mach 0.80 opens,
> and heading rate is LINEAR in speed. The motor is back on the table.
>
> The rest of this document holds. The physics arguments in sections 1-6 are all still
> right, and section 7's ordering — that five of seven requirements cost nothing at the
> vertical optimum — is still the correct reading of a vertical flight. What changes when
> the vehicle is flown flat is WHICH requirement is in the way: not R1, which the
> horizontal point meets at 0.61%, but the **hinge bearing**, which nothing in this document
> or in `scripts/agility_sweep.py` ever checked. See **`docs/12-horizontal-agility.md`**
> and `scripts/horizontal_agility_sweep.py`.
>
> **Which vehicle the numbers describe.** Sections 1–6 were written against the *then*
> frozen baseline: Cesaroni J449, canards 0.85 cal, 1.41 g at 8°, ~2.0 km turn radius.
> Section 7 is the search that replaced it, and **the frozen baseline is now the J401FJ at
> 1.30 / 1.70 cal — 1.76 g, 6.47 °/s, 1.18 km** (`docs/00` §6.1). The J449 figures below
> are kept deliberately: they are what the physics arguments were derived on, and every
> one of those arguments still holds — the ratios move, the mechanisms do not.

This is not a goal statement. It is the physics of why 1.4 g is not 10 g.

**Section 7 is the quantitative answer** and it changes the framing twice. First, g is the
wrong scoreboard: on *turn radius* this vehicle already beats an AIM-9B, and pushing it to
10 g by flying faster would not improve the radius by a single metre. Second, the reachable
gain is real but it comes from the static margin, not the motor — **6.47 °/s and a 1.18 km
radius as built**, against 4.4 °/s and 2.04 km before, on a *smaller* motor. This point is
now the frozen baseline (`docs/00` §6.1, §7.2).

The original Sidewinder is about **10 g**, not 30. Later marks get ~30 g mostly because
they fly Mach 2.5. Matching 9B *heading rate* (~10 °/s) at this vehicle's speed is a
~3 g problem. Matching 30 g is a Mach 2.5 problem.

---

## 1. Flight regime

**Speed.** Mach 0.50 vs Mach 1.7 (9B) or 2.5+ (later). Fin force scales with speed
squared. This is the largest single hole. Same fins, same 8°, same 1° of lean, at 9B
speed, would be an order of magnitude more g — if the airframe survived, which it
would not.

**Launch energy.** A Sidewinder starts already at fighter speed. This rocket starts at
zero on a rail. The first seconds are spent becoming a rocket, not turning.

**Dynamic pressure that lasts.** Peak *q* is ~17 kPa, then it dies as the vehicle coasts
and climbs. A missile’s *q* stays huge because it stays fast. The control window is
~11 s, then the fins are decorations. A 9B still has ~20 s of mission time and is
supersonic for much of it.

**Altitude vs air.** Apogee is 1.3 km. Thinner air means less force and a larger turn
radius. Missiles often spend violent turns lower and faster, in thicker air.

**Subsonic by design (R5).** Mach ≤ 0.8. Transonic/supersonic is where missile canards
start earning 10–30 g. Crossing that line invalidates Barrowman and the rest of the
aero this repo is built on.

---

## 2. Stability

**Too much static margin.** 2.3–2.8 calibers. Missiles fly near neutral (sometimes
slightly unstable) and let the autopilot hold them. Stability is “I want to go
straight.” Every newton of canard is spent cancelling that desire. Trim alpha is
canard moment divided by that restoring moment (`pitch_authority` in
`design/control.py`). Large restoring moment → almost no lean → almost no body lift.

**Almost no angle of attack.** 8° of canard trims **1° of body alpha**. Missiles fly at
tens of degrees. Body lift is most of a missile’s g. This vehicle does not lean.

**The canard trap (R2).** Canards sit ahead of the CG, so they destabilize when
deflected. A missile accepts “deflect and get twitchier.” This design requires
remaining margin > 1.0 cal at full deflection so the rocket does not swap ends.

**Huge aft fins.** 1.55 cal semispan, ~67% of all lift. They exist so the vehicle does
not go unstable under mass/CP error. They also add drag, add roll damping, sit in the
canard wake, and fight turning.

**Weathercocking.** High margin means wind and the velocity vector boss the nose. A
missile’s nose goes where the autopilot points it.

**Nose ballast.** 100 g in the nose keeps static margin legal after the servos came in
light. Stability up, authority down.

---

## 3. Control surfaces

**Deflection cap of ±8°.** Design limit. Servos could travel ±60°. The vehicle uses 13%
of servo travel.

**Stall at ~12° local alpha.** Past that the canards quit — but "no hidden throw
behind 8°" was wrong, and the correction matters. Local alpha is `alpha_trim + delta`,
and at today's margin `alpha_trim` is only 0.125·δ, so 12° local is reached at **10.7°
of deflection**, not 8°. That extra throw is worth 1.88 g against today's 1.41 g. What
holds the vehicle at 8° is `DEFLECTION_LIMIT_DEG`, which `configure.py` documents as a
*sensing* limit (keeping the rate gyro in range), not an aerodynamic one.

**The stall ceiling is not a single number.** The tempting claim — "stall caps this
airframe near 3.6 g, so 10 g is impossible at Mach 0.5" — is circular. The 12° is a
budget *shared* between body lean and canard throw, and

    CN = CNa_vehicle · alpha_trim + CNa_canards · delta

with `CNa_vehicle` = 31.8 /rad against `CNa_canards` = 3.2 /rad. The same 12° is worth
ten times more spent as body alpha than as deflection, and how it splits is set entirely
by static margin. Today's 2.77 cal caps the vehicle at **1.88 g**; 3.74 g needs 0.69 cal;
the formula's asymptote at neutral stability is 9.35 g. So *stall is not what stops this
vehicle* — static margin and the servo are. See the ceiling table in
`scripts/agility_sweep.py`.

**No high-alpha aerodynamics.** Missiles use vortex lift, body vortices, sometimes grid
fins. This model is linear, small-alpha, attached flow. Correct for what it flies.
Not a 30 g toolkit.

**Canard wake on the tail.** At 45° clocking, ~17% of roll authority is still lost;
aligned, ~74%, and the sign can reverse. Growing the tail for safety walks toward
reversal. A TVC missile does not have this coupling.

**Hobby-servo hinges.** Peak hinge moment is ~0.05 N·m because *q* is tiny. At missile
*q* that moment scales with the air, and these servos lose. Early Sidewinders actuated
canards with motor bleed gas.

**No thrust vectoring, no jet vanes.** Hardware in a certified motor’s exhaust is
blocked. 9X’s tight turns at low speed are TVC. Fins cannot do that when *q* is gone.

**No boost-phase steering.** The law starts ~0.5 s after burnout. The motor is the only
time there is spare energy, and it is not used to turn.

---

## 4. Energy, time, and geometry

**The ±16 g accelerometer was written down and never enforced.** `docs/02` has listed it
as motor-selection criterion 3 since the J449 was picked — *"peak axial acceleration
≤ 16 g … clipping during boost corrupts velocity and attitude estimation exactly when it
matters."* It was simply never encoded in `configure.LIMITS`, which caps thrust-to-weight
from *below* and never from above, because on a J motor nothing was ever going to breach
it. A criterion that lives only in prose does not constrain a search. On a K it breaches immediately. The most agile motor in the whole
54 mm catalogue that satisfies every published requirement — the AeroTech K2050ST, 1393
N·s, 1461 m apogee, Mach 0.61, 2.40 g, 5.95 °/s — peaks at **31.4 g axial**, twice the
accelerometer's full scale (`design/estimation.ACCEL_16G`, docs/06). A clipped
accelerometer through the whole boost does not degrade the state estimate, it deletes it;
`design/estimation.py` stages the filter on exactly that signal. Enforcing it drops the
best legal motor swap from 5.95 °/s to 4.97 °/s (Cesaroni J760). *The most agile vehicle
in the search was one that cannot know where it is.*

**Motor length is a build constraint, not a parameter.** The mount tube as built is
332.08 mm (docs/09), sized around the J449's 321 mm case. `build_vehicle` grows the
booster parametrically, so the model never notices; the hardware would. The J760 at 329 mm
fits. Most K motors do not.

**Max motor impulse is L2.** NAR/TRA Level 2 is the ceiling: J, K, or L motors, not M
or above. The frozen motor is a Cesaroni J449 (~1,260 N·s). A 9B motor is tens of
kN·s. Similar burn time (~2–3 s), not similar violence. 9B axial is ~25 g; this motor
was chosen to stay near 8 g so the IMU does not clip.

**Turn radius ~2 km — and this is the one comparison the rocket WINS.** A 9B at
Mach 1.7 pulling 10 g turns on a **3.2 km** radius. This vehicle, at 1.41 g and 166 m/s,
turns on **2.0 km**. It already out-turns a Sidewinder in the plan view; what it lacks is
the speed to get round that circle quickly. A fighter at corner speed is a few hundred
metres, which is the honest benchmark for “tight”.

**Speed cannot fix the radius, at all.** Radius is V²/(n·g₀) and n goes as q, i.e. as
V². The two cancel *exactly*. Pushing this airframe to 10 g purely by flying faster:

| target | speed needed | heading rate | turn radius |
|---|---|---|---|
| today, 1.41 g | 166 m/s (M0.50) | 4.8 °/s | **1990 m** |
| 3 g by speed alone | 242 m/s (M0.71) | 7.0 °/s | **1990 m** |
| 5 g by speed alone | 312 m/s (M0.92) | 9.0 °/s | **1990 m** |
| 10 g by speed alone | 442 m/s (M1.30) | 12.7 °/s | **1990 m** |

Every row is the same circle. Speed buys *heading rate* (linearly, not as the g figure
suggests) and buys nothing else. Only CN at fixed speed — lower static margin, more
canard area, more throw — moves the radius. A 90° path change needs ~19 s at burnout
speed; ~11 s of control is available.

**Turn rate collapses as you slow.** Force scales as \(v^2\), rate as \(v\). The fins
fade in coast. A missile stays in the high-*q* band longer, or steers with the motor.

**No second burn, no sustain motor.** Coast is all there is.

**Not enough sky for a hook.** A 2 km-radius pushover to vertical needs on the order of
a kilometre of altitude to drop through. Burnout is at a few hundred metres.

---

## 5. Structure

**Flutter — real, but the cheapest problem on this list.** Aft fins at the frozen
3.2 mm are good to 355 m/s (2.1× today’s max), so a 3 g-by-speed vehicle at 242 m/s sits
at 1.47× and fails the 1.5× rule. One step up the G10 stock ladder fixes it: 4.0 mm gives
496 m/s (1.5× at 331 m/s), 4.8 mm gives 653 m/s. Flutter is not what caps this airframe
below Mach 0.8 — it is a thickness line item. Mach 1.7 is ~580 m/s and *that* is where the
fins genuinely come off.

**G capability.** Airframe, bulkheads, U-bolts, and harness are sized for launch,
coast, and a 5 m/s landing — not 10–30 g sideways.

**Tube with holes.** Four hinge bores take 13% of the section. Fine at 1.4 g. Not a
30 g fuselage.

**G10 fins, hobby adhesives, 3-inch fiberglass.** Correct for high-power sport
rocketry. Wrong margins for missile load factors.

---

## 6. Sensors and the autopilot plant

**Must know roll angle.** L1 is hold roll, then bank-to-turn. That needs a
magnetometer and a magnetically clean airframe. A rolleron 9B does not know which way
is up; seeker error drives canards, rollerons just kill spin.

**No seeker.** Nothing tracks a point in the sky. L3 is GPS lat/lon bias, not
proportional navigation on a hot target.

**IMU is hobby/breakout class, then a student STM32 board, ±16 g.** The motor was
chosen so peak axial stays under clip. Missile IMUs are built for high-g, high-rate,
high vibration.

**Roll cap of 2°.** Protects the gyro and the attitude estimate. Uncapped 8° is
~2000 °/s and wrecks the thing L1 is trying to do.

**Estimator is staged and fragile in boost.** Accelerometer is not “down” after rail
exit. Pitch/yaw aiding is GNSS velocity under small alpha — the same high-margin
assumption that kills turning. The sensing scheme needs the stability that the
turning scheme hates.

**No autopilot for an unstable plant.** Gain-scheduled, 100 Hz, on a 4 Hz pitch mode
of a *stable* rocket is a different job from flying a neutrally stable missile at
20° alpha.

**Bank-to-turn, not high-alpha skid-to-turn.** Roll first, then pull. A 9B just
deflects canards toward the error. The 2° roll cap makes that roll slow relative to
a free missile.

---

## What this vehicle does *not* lack

- **Attitude bandwidth.** Pitch mode ~4 Hz, nose nods in ~60 ms. The airframe is
  snappy. The path is not.
- **Roll hardware.** Four independently driven canards and an active roll loop. A 9B
  has rollerons instead. This vehicle is more modern in roll, and chooses not to use
  most of it.
- **A real control problem.** Wake interference, sign of `Cl_delta`, bank-to-turn,
  estimator staging. That is the project.
- **Enough g to see.** R8 asked for 0.5 g. The baseline has 1.4 g and ~300 m.
  Visible, measurable, not missile-like.

---

## 7. So what *is* reachable? — `scripts/agility_sweep.py`

Everything above is qualitative. The sweep searches motor × canard span × aft span ×
nose ballast against **every** requirement at once — `configure.LIMITS`, R1's Monte Carlo
risk budget, flutter, servo torque and fit, the ±16 g accelerometer — and maximises
*heading rate*, because that is the observable a Sidewinder comparison is about. 1026
vehicles; 68 of them legal.

**The best legal vehicle is a *smaller* motor.** This point was **adopted as the frozen
baseline in Sep 2026**; the "as built" column is what `scripts/baseline.py` reports now,
after the two structural consequences the search did not model (below).

| | old baseline | sweep predicted | **AS BUILT (frozen)** |
|---|---|---|---|
| motor | Cesaroni J449, 1260 N·s | AeroTech J401FJ, 1105 N·s | **AeroTech J401FJ, 1105 N·s** |
| canard / aft semispan | 0.85 / 1.55 cal | 1.30 / 1.70 cal | **1.30 / 1.70 cal** |
| nose ballast | 100 g | 60 g | **60 g** |
| canard panel | 3.2 mm | 3.2 mm | **3.6 mm** |
| harness anchors | M8, 191 g | M8, 191 g | **M10, 302 g** |
| nominal static margin | 2.22 cal | 1.90 cal | **1.94 cal** (P(SM<1.0) = 0.65%) |
| lateral g at 8° | 1.41 g | 1.93 g | **1.76 g** |
| peak heading rate | 4.40 °/s | 6.91 °/s | **6.47 °/s** |
| turn radius | 2.04 km | 1.13 km | **1.18 km** |
| heading over the window, 70% duty | 16.4° | 24.1° | **22.4°** |
| apogee / max Mach | 1271 m / 0.50 | 1046 m / 0.43 | **1011 m / 0.42** |
| aft fin thickness, servo, mount tube | — | unchanged | **unchanged** |

That is **1.47× the turn rate and 0.58× the radius** as built. It needs no new aft fin
stock, no new servo, and no new motor mount — the J401FJ's 325 mm case fits the 332 mm
tube docs/09 built. It costs new canard panels, new aft fins, and the M10 anchor set.

**The 6% between "predicted" and "as built" is the search's own blind spot**, and it is
worth more than the 6%: this constraint set has now been wrong twice in the same way.
First the ±16 g accelerometer, written in `docs/02` but never encoded. Then these two:

1. **The canard root joint.** A 1.30 cal panel puts 28.8 N through the tang instead of
   21.1, and its CP moves outboard, so bending at the wall *doubles*, 0.610 → 1.273 N·m.
   The 0.6 mm skin over the tang slot fell to 1.47× against 2.0×. Fixed by a 3.6 mm
   laminate (0.8 / 2.0 / 0.8, still three stocked sheets): 2.65×, costing 1.93 → 1.88 g.
2. **The recovery anchor is self-loading.** More fin → more mass → more descent weight →
   more opening shock → M8 becomes M10 and four anchors go 191 → 302 g, which is itself
   descent mass. `recovery_hardware.py` had predicted exactly this in writing. Converges
   in one pass; costs 1.88 → 1.76 g and takes recovery packing from 4.4 mm to 2.2 mm.

Anything `agility_sweep.py` prints is an **upper bound** until the structural chain has
been run on the winning point. See `docs/00-requirements.md` §7.2.

**Agility on this airframe comes from static margin, not from the motor.** This is the
result that overturns the "add *q*" intuition. Every requirement that bites — the IMU
clip, R6 apogee, R5 Mach, flutter, servo torque — is triggered by *speed*. None of them is
triggered by margin except R1 itself. So the search spends its budget on a slower motor
that keeps all of those slack, and buys the turn back through lean.

### The relaxation ladder: which requirement is actually in the way

Computed pre-freeze (3.2 mm panel, M8 anchors), so the absolute values run ~6% high; the
ordering, which is the point, is unaffected.

| requirement dropped | best deg/s | best g | radius |
|---|---|---|---|
| nothing | 6.91 | 1.93 | 1.13 km |
| R6 apogee ≤ 1600 m | 6.91 | — | *no change* |
| R5 Mach ≤ 0.8 | 6.91 | — | *no change* |
| flutter ≥ 1.5× | 6.91 | — | *no change* |
| servo torque ≥ 2.0× | 6.91 | — | *no change* |
| ±16 g accelerometer | 7.05 | 2.16 | 1.22 km |
| R11 recovery packing | 7.76 | 2.71 | 1.26 km |
| **R1 static margin band** | **11.35** | **3.31** | **0.72 km** |
| everything except stall | 30.96 | 19.65 | 0.51 km |

Five of the seven requirements cost **nothing at the optimum**. R1 costs 64% of the
available turn rate on its own — and it is the one requirement that exists to stop the
rocket killing someone.

### What R1 is actually buying

Motor held at the J401FJ, canard span and ballast walked together, everything else frozen.
Computed **before** the freeze, so at a 3.2 mm canard panel and M8 anchors: absolute g and
°/s run ~6% high against the as-built column above, but the *shape* of the curve — which is
what this table is for — is unaffected.

| canard / aft | ballast | nominal SM | P(SM<1.0) | g | deg/s | radius |
|---|---|---|---|---|---|---|
| 0.85 / 1.55 | 100 g | 2.39 | 0.0% | 1.08 | 3.78 | 2.12 km |
| 1.15 / 1.55 | 100 g | 1.91 | 0.7% | 1.66 | 5.88 | 1.35 km |
| **1.30 / 1.70** | **60 g** | **1.90** | **0.8%** | **1.93** | **6.91** | **1.13 km** |
| 1.30 / 1.55 | 25 g | 1.62 | 4.8% | 2.16 | 7.58 | 1.05 km |
| 1.45 / 1.40 | 25 g | 1.17 | 32.6% | 2.76 | 9.60 | 0.84 km |
| 1.45 / 1.25 | 100 g | 0.95 | 55.3% | 2.76 | 9.63 | 0.83 km |
| 1.45 / 1.15 | 25 g | 0.63 | 84.0% | 3.45 | 7.06 | 1.16 km |

Read the risk column, not the rate column. **Turn rate is smooth in margin; risk is not.**
The step from 6.91 to 7.58 °/s — 10% more turn — costs a 6× increase in the probability of
an unsafe margin, straight through R1's 1% budget. Reaching the 9B's 10 °/s means about
0.9 cal nominal, where **more than half of all flights** have a static margin under one
caliber.

And the last row is where the canards finally do quit: at 0.63 cal the trim alpha is large
enough to stall them at 8°, and the turn rate goes *down*. Stall is real — it is just the
last constraint to bind, not the first.

### Cross-check, and one number to stop quoting

`design.control.heading_change` was validated against `scripts/virtual_flight.py`, which
is an independent 3-DOF simulation that actually flies the manoeuvre. Same vehicle, same
window, same definition:

| | `heading_change` | `virtual_flight` (skid-to-turn) |
|---|---|---|
| **peak turn rate, frozen vehicle, 9.2° cap** | **7.31 °/s** | **7.33 °/s** |
| peak turn rate, frozen vehicle, 8° cap | 6.47 °/s | **6.49 °/s** |
| canard-induced heading, frozen | 32.0° | **34.6°** |
| *(pre-freeze, J449)* | *4.40 °/s / 23.4°* | *4.41 °/s / 25.0°* |

Three digits on the rate and under 8% on the integral, from two codes that share no
integration path. **The top row is the cross-check re-run after correction 61 took the
deflection cap to 9.2°** — 0.3% apart, on a vehicle whose canard laminate also changed —
and `design/horizontal.py` is now a third code that agrees with both (docs/12 §1). That is as good as this project's cross-checks get. `heading_change`
reads slightly low on the integral because it integrates against a trajectory that flew
straight up, while the 3-DOF run bleeds energy into the turn and reaches apogee earlier —
so the two windows are not identical.

**But `virtual_flight`'s headline `final_heading_deg` — 78.0° on the frozen vehicle — is
not that number.** It is `atan2(vy, vx)`, the compass azimuth of the *horizontal* velocity
component, and on a near-vertical trajectory it is ill-conditioned. The run ends at
vx 8.7, vy 40.7, vz ≈ 0: a 78° bearing on a velocity vector down to 42 m/s. The rocket did
not turn 78°; it nearly stopped, and what little velocity remained was mostly sideways.
The velocity vector rotated **34.6°** under canard force. Quote 34.6.

### The honest scorecard against an AIM-9B

| | AIM-9B | old baseline (J449) | **frozen, as built** |
|---|---|---|---|
| heading rate | ~10 °/s | 4.4 °/s (44%) | **6.5 °/s (65%)** |
| turn radius | 3.2 km | 2.0 km | **1.18 km** |
| lateral g | ~10 g | 1.4 g | 1.76 g |
| speed | Mach 1.7 | Mach 0.50 | Mach 0.42 |

On **radius** this vehicle already beats a Sidewinder and the legal optimum beats it by
2.8×. On **heading rate** it reaches roughly two-thirds. The g column is the only one where
the gap is an order of magnitude, and g is the one number that does not, by itself, mean
anything — it is what you must spend to turn at a given speed, not a measure of turning.

**Bottom line:** the open knob inside this design was worth **1.47× in turn rate and 1.73×
in radius**, and it was the *static margin*, spent through bigger canards and less ballast,
not the motor. It has now been spent — this is the frozen baseline, not a proposal.
Everything past it on this list is a different vehicle, and the next rung down (1.30/1.55,
25 g ballast) buys 10% more turn for a 6× increase in P(SM < 1.0). That is not a trade
this project takes.
