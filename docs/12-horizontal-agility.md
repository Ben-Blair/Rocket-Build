# Horizontal launch: what the vehicle can actually do, and what stops it

Written September 2026, against the frozen J401FJ / 1.30 / 1.70 / 60 g baseline. This
document answers one question — **how fast can the velocity vector be made to turn on a
horizontal or near-horizontal launch** — and it reverses the headline conclusion of
`docs/11-agility-comparison.md`, which was derived on a vertical flight.

Everything here comes from `design/horizontal.py` and `scripts/horizontal_agility_sweep.py`
(output in `out/horizontal_agility.txt`).

> **FROZEN AT 1.45 / 1.85 cal WITH A POINTED-DELTA CANARD, Sep 2026 (corrections 61–63).**
> §13 is the planform change; the performance numbers below are correction 62's and move
> by −1.6% at §13. `design/configure.py`
> carries `DEFLECTION_LIMIT_DEG = 9.2`, a 4.0 mm canard laminate and **canard 1.45 /
> aft 1.85 cal**; `design/hinge.py` carries a **⌀10 journal**; `design/bay.py` a 16.0 mm
> collar. **9.92 °/s peak, 880 m radius, P(SM < 1.0) = 0.45%.**
>
> §10 is where 1.45/1.85 came from and **§11 is the correction to it** — the number that
> put it on the "unlocked" list was computed on a hinge that cannot be built, and adopting
> it properly cost one more link in the chain.
>
> The paragraph below records the FIRST freeze, at 1.30/1.70. **Applying it moved three things this study had not predicted**, all of them
> downstream of the bearing, and §9 is the record of what applying it cost:
>
> 1. The proposed 7.0 mm bearing at a 5.5 mm servo move **failed `check_hinge_stack`** —
>    0.59 mm of boss clearance against its 1.0 mm minimum. §8.1 had flagged that as the
>    tightest margin in the proposal; it was not tight, it was illegal.
> 2. Length was never available anyway. **The bearing cannot exceed 6.2 mm at the as-built
>    servo position**, and nothing checked it — a fourth defect of the family `hinge.py`
>    exists to catch, now closed.
> 3. The journal went ⌀6 → ⌀8 instead, which took the bearing OD to ⌀10, which broke the
>    printed collar's wall, which grew `COLLAR_OD` 12 → 14 mm, which exposed a hardcoded
>    printed bore that had silently become a boring operation.
>
> The headline numbers below are unchanged — **8.97 °/s** — because none of that touched
> the aerodynamics. What changed is the parts list and one requirement: **the printed bay's
> housing collar is now structure, not a nice-to-have.**

---

## 0. The result in one table

| | frozen, vertical | frozen, flown flat | **proposed default** | stretch |
|---|---|---|---|---|
| launch elevation | 85° (5° rail) | 30° | **30°** | 28° |
| deflection | 8.0° | 8.0° | **9.2°** | 9.1° |
| canard / aft semispan | 1.30 / 1.70 | 1.30 / 1.70 | **1.30 / 1.70** | 1.45 / 1.85 |
| nose ballast | 60 g | 60 g | **60 g** | 60 g |
| canard laminate | 3.6 mm | 3.6 mm | **4.0 mm** | 4.0 mm |
| hinge bearing | 6.0 mm | 6.0 mm | **7.0 mm, ⌀6** | 7.5 mm, ⌀6.5 needed |
| **peak heading rate**, 90° bank | **6.47 °/s** | **7.95 °/s** | **8.97 °/s** | 9.92 °/s |
| sustained rate, holding altitude | — | 7.00 °/s | **8.13 °/s** | 9.18 °/s |
| turn radius | 1179 m | 1123 m | **990 m** | 880 m |
| lateral g | 1.76 | 2.11 | **2.38** | 2.64 |
| heading over the window, 70% duty | 22° | 50° | **59°** | 67° |
| nominal SM / P(SM < 1.0) | 1.94 / 0.65% | 1.94 / 0.65% | **1.96 / 0.61%** | 1.99 / 0.4% |
| verdict | — | hinge bearing 1.57× | **every requirement met** | blocked at ⌀6 — **but see §10** |

**8.97 °/s is 90% of an AIM-9B's heading rate, and the turn radius beats it by 3.2×.**
It costs no new motor, no new fin planform, no static margin and no R1 relaxation. It
costs a launch rail set to 30°, a deflection cap raised from 8° to 9.2°, one thicker
canard laminate and one longer hinge bearing.

**Two rates, because there are two honest answers.** A stable rocket cannot lean; all of
its lateral force comes from canard-trimmed alpha, and roll angle decides where that force
points. Bank 90° and every newton of it turns the ground track — that is the 8.97 °/s, and
it is the number an AIM-9B comparison wants — but nothing is holding the vehicle up and it
descends at 1 g while it turns, which on a flat flight is a 7.2 s window. Bank to
`arccos(1/n)` = 65° instead, spend 1 g holding altitude and turn with the rest, and the
rate falls to 8.13 °/s while the window doubles to 16.2 s. Peak rate and total heading want
opposite things; §6 recommends flying the second and bursting into the first.

---

## 1. Why flying flat is worth 1.23× before anything is redesigned

`control.heading_change` integrates a turn rate against `trajectory.simulate`'s **vertical**
speed history. On a vertical flight that is defensible and it cross-checks to three digits
against `scripts/virtual_flight.py`. On a flat launch it is not an approximation, it is the
wrong flight. Four things change:

**Gravity stops being an axial decelerator.** A vertical J401FJ flight spends ~27 m/s of
its burn fighting gravity and then decelerates at 1 g plus drag all the way to apogee.
Flown flat, gravity is perpendicular to the velocity — it curves the path and does not slow
it. Burnout speed goes **141.3 → 157.5 m/s** at a 30° rail (159.8 at 25°), and the
decay after it is drag alone.

**The air stays thick.** A vertical flight manoeuvres between 200 m and 1000 m. A flat one
stays near the ground, and density appears linearly in both rate and radius.

**The window ends at the ground, not at apogee.** Launch elevation becomes a design
parameter with a real optimum — see §2.

**Azimuth becomes the right number.** `docs/11` had to retract a 78° heading figure because
`atan2(vy, vx)` is ill-conditioned on a near-vertical flight — `psi_dot = a_h / v_horiz`
with `v_horiz -> 0`. Flown flat that singularity is gone and azimuth is the honest heading
rate. It is *not* the same as the velocity-vector rotation the vertical codes report, and
the gap is physics rather than error: at 90° of bank the two agree (8.97 against 8.79 on
the recommended point), and under an altitude-holding bank they separate (8.13 against
8.79) because part of the force is rotating the vector out of the ground plane instead of
around it. `horizontal.py` carries both and the sweep prints both, with a `steep_azimuth`
flag that fires when the flight path passes 45° and the azimuth number stops meaning
anything.

The organising equation is the same one `docs/11` derives, read the other way round:

```
psi_dot = n g0 / V  and  n g0 = q S CN / m = 0.5 rho V^2 S CN / m

  =>  psi_dot = 0.5 rho V S CN / m       LINEAR in speed, linear in density
      R       = 2 m / (rho S CN)         contains no V at all
      delta_psi = path length / R
```

**Total heading change is path length divided by turn radius.** Not time. A flat flight
turns further because it covers more ground before it runs out of air. And the sweep's own
motor table confirms the radius identity empirically: across nine motors from 1105 to
1620 N·s, peak rate goes 9.0 → 13.1 °/s while the radius moves only 977 → 879 m.

### The validation that makes this quotable

`design/horizontal.fly` is a third integration path. Run at 85° elevation — the 5°-off-
vertical rail the frozen baseline actually uses — it must reproduce the two codes that
already agree:

| | peak °/s | total ° | window s |
|---|---|---|---|
| `control.heading_change` | 6.47 | 32.0 | 9.7 |
| `scripts/virtual_flight.py` | 6.49 | 34.6 | — |
| **`horizontal.fly` @ 85°** | **6.50** | **31.9** | **9.7** |

0.5% on the rate, and apogee 1009 m against `trajectory.py`'s 1011 m. The flat numbers in
this document are therefore differences in the **flight**, not in the code.

---

## 2. Launch elevation, and the floor nobody had to think about before

You cannot launch this vehicle horizontally. **Gravity droop during boost is worth about
20° of flight path angle**, and it is not a small correction:

```
delta_gamma = integral(g cos(gamma) / V dt) ~ (g/a) ln(V_burnout / V_rail)
            = (9.81 / 64) ln(160 / 21) = 19.9 deg
```

The velocity vector rotates fastest early, when V is only 21 m/s off the rail. A 20° rail
is already **descending** by burnout and hits the ground before the control law is allowed
to start — `fly` returns a zero-length control window, which is the honest answer.

| elevation | apogee | peak °/s | window | verdict |
|---|---|---|---|---|
| 15–20° | 12–37 m | — | 0.0 s | never reaches the 50 m manoeuvre floor |
| 22° | 91 m | 7.95 | 11.2 s | no dual-deploy room |
| 28° | 234 m | 7.96 | 14.4 s | flies flat: 6° flight path at burnout |
| **30°** | **273 m** | **7.95** | **15.1 s** | **the lowest rail that clears the recovery floor** |
| 35° | 395 m | 7.62 | 16.6 s | |
| 45° | 576 m | 7.29 | 19.4 s | |
| 60° | 816 m | 6.87 | 23.3 s | |

**28–30° is the practical floor and it flies flat anyway**, because the boost has already
spent the elevation. The recommended vehicle needs 30° rather than 28° purely because the
thicker canard laminate made it heavier; the frozen one clears the floor at 28°. Higher T/W
would buy a lower rail; the J401FJ's 6.17 does not.

The floor is set by recovery, not by aerodynamics: below ~250 m of apogee there is no room
for a dual-deploy sequence at all, because the main fires at 200 m.

---

## 3. What the horizontal launch ADDS: apogee is no longer a slow event

This is the single most important consequence of the profile and it has nothing to do with
turning.

Vertically, the vehicle arrives at apogee doing **1.1 m/s**. The whole recovery
architecture rests on that: the drogue costs nothing to deploy, and `configure.evaluate`
sizes the M10 anchors, the 3/4" harness and the quick links against the **main** opening at
the drogue descent rate — **1604 N** (docs/10).

Flown flat at 30°, the vehicle arrives at apogee doing **93.8 m/s**, because the horizontal
component never went away. Apogee is still the correct deployment trigger — it is the
minimum-speed point of a flat arc — but it is no longer a free one:

Recommended vehicle, 18 in drogue, deployed at apogee:

| elevation | apogee | speed at apogee | drogue shock | vs. the docs/10 design load |
|---|---|---|---|---|
| 28° | 249 m | 95.5 m/s | 2283 N | 1.42× |
| **30°** | **290 m** | **93.8 m/s** | **2193 N** | **1.37×** |
| 35° | 388 m | 88.8 m/s | 1946 N | 1.21× |
| 45° | 564 m | 76.8 m/s | 1431 N | 0.89× |
| 85° | 1011 m | 0.8 m/s | ~0 N | 0.00× |

**The drogue inverts: it is sized by its own opening shock, not by descent rate.** Holding
the shock to the load the recovery chain is already built for means a **15.4 in** drogue
instead of 18 in, which still brings the vehicle to the main's 200 m firing altitude at
**23.5 m/s** — faster than the 20 m/s the 18 in gives vertically, and inside the 30 m/s at
which the main itself becomes the problem. The sweep sizes it
per candidate (`Candidate._deployment`) exactly the way `with_flutter_fix` sizes fin
thickness — it is the price of the flight profile, not an agility knob.

Nothing else in the recovery chain has to change. That is the point of sizing the drogue
rather than accepting a 1.4× overload on parts that were sized once and drawn.

---

## 4. Fin sizing for the turn: area and margin first, outline second

The brief asked for the rationale in that order, and the order is the answer.

**First: `CN` at fixed speed is the only thing that moves the radius.** `R = 2m/(rho S CN)`.
Not the motor, not the deflection cap, not the outline. `CN` splits as

```
CN = CNa_vehicle * alpha_trim  +  CNa_canards * delta
       38 /rad                     3.2 /rad
```

so the same degree of local alpha is worth about **ten times more spent as body lean than
as canard throw**, and how the 12° stall budget splits between them is set entirely by
static margin. That is why margin, not area, is the efficient lever — and it is also why
the efficiency is weaker than the asymptotic argument suggests. At the frozen 1.93 cal,
body lean is only **16%** of an 11° local alpha; even at 0.87 cal it is 32%. The asymptote
is real and the vehicle is nowhere near it.

**Second: the two sets are sized jointly or not at all.** Canard area buys `Cm_delta` and
costs margin; aft area buys margin and costs authority through wake interference. The
result the vertical search never reached is that **growing both together beats growing
either**: 1.45/1.85 makes 9.92 °/s at P(SM < 1.0) = **0.4%**, better than the frozen
1.30/1.70 on *both* axes. Bigger canards for the authority, bigger tail to pay for them.

**Third, and only third: the outline.** Root chord and taper are held to constant panel
area (`configure.py`), sweep is matched to the aft fin angle so the two sets read as one
vehicle, and 45° interdigitation is kept — nothing found in this study argues for a
different clocking, and the 16.8%/73.9% interference numbers are unchanged by launch angle.

---

## 5. What breaks on the current freeze if you push toward 10 °/s

Ranked by what actually binds. **The first two were not in any search until this study, and
both fail on the frozen geometry the moment it is flown flat.**

**1. The hinge bearing — and it is the wall.** Peak pressure is `6M/(dL²) + N/(dL)`, so it
is driven by the panel normal force, not the hinge moment, and it goes as `1/L²`. A flat
flight's max q is the burnout value at sea level rather than at 230 m — 15.5 kPa against
12.4 — before any extra deflection is asked for. The frozen 6.0 mm bearing falls to
**1.57×** against this project's 2.0×.

The fix is length, and length runs out. The bearing grows *inboard* from the panel root
straight at the servo's output face, so buying it means moving the servo further inboard,
and `hinge.selected` already records the ceiling: 4.000 mm is "the largest move the four
servo cable bosses allow with a millimetre to spare". `boss_collision_margin` falls 1.0 mm
per mm and reaches zero at **6.09 mm**.

Panel normal force is 38.0 N at 1.30 cal and 42.6 N at 1.45 cal, both at the flat flight's
own max *q*:

| bearing | servo move | boss margin | margin @ 1.30 cal | margin @ 1.45 cal |
|---|---|---|---|---|
| 6.0 mm, ⌀6 (as built) | 4.0 mm | 2.09 mm | 1.57× | 1.27× |
| **7.0 mm, ⌀6** | **5.5 mm** | **0.59 mm** | **2.11×** | 1.70× |
| 7.5 mm, ⌀6 | 6.0 mm | 0.09 mm | 2.41× | 1.94× |
| 7.5 mm, ⌀6.5 | 6.0 mm | 0.09 mm | 2.61× | 2.11× |

> **This table is the PRE-FREEZE state and it is what forced the journal change. What was
> actually built is ⌀8 at the as-built 6.0 mm length — 2.11× at 1.30 cal and 2.27× at 1.45 —
> which is why §10 exists.** The reasoning below is kept because it is what ruled length out.

**1.30 cal clears 2.0× with a 1 mm longer bearing and nothing else. 1.45 cal does not clear
it at any length** — it needs the journal opened to ⌀6.5 *and* the servo driven to the
0.09 mm boss margin, which is past what `hinge.selected` says it wanted. At its ceiling the
hinge carries about **44 N** at 2.0×, and that is what caps the canard near **1.50 cal** on
a flat flight — not stall, not static margin, and not servo torque. Every one of those was
checked before this was.

**2. The canard root joint.** Skin over the tang slot falls to **1.93×**. Stress goes as
`1/t²`, so one stocked step of laminate — 3.6 → 4.0 mm, skins 0.8 → 1.0 mm, stack
1.0/2.0/1.0 — takes it to **3.09×**. Cheap, and the manufacturing argument in
`configure.py` survives intact: still three sheets you can buy, still a slot left as a gap
in the middle one. The **tang** does not improve with laminate (2.53× at 1.30 cal, 2.06× at
1.45) because it carries the panel force, not the skin's bending. It is also why the
laminate stops at 4.0 mm at every span the search reached: one stocked step fixes the skin,
and a second one buys nothing.

**3. Servo torque.** Hinge moment goes as q, and the frozen KST X08 Plus is the strongest
part that fits four-abreast in a 79.4 mm tube — the only stronger option, `mini_ht`, is 6%
better. Torque holds at **2.27×** on the recommended point and fails on every faster motor:
J760 1.58×, K400C 1.86×, K445 1.22×.

This one *is* fixable, and it is worth stating because it is the only structural wall that
is: moving the hinge line aft from 0.20c toward the 0.25c panel CP shrinks the hinge moment
linearly in `(cp_frac - hinge_frac)`. 0.20 → 0.225c halves it. **It does nothing for the
bearing**, which carries the force and not the moment — `hinge.py` makes exactly this point
("a 0.06 N·m hinge moment and a 25 N panel load are the same panel"). It also halves the
separation that keeps the panel self-centring, and the panel CP moves with Mach, so it
trades servo margin against divergence margin. Not taken here; priced.

**4. Deflection.** `DEFLECTION_LIMIT_DEG = 8.0` is documented in `configure.py` as a
*sensing* limit — "what keeps the rate gyro inside its range". Read `estimation.py` and
that argument is entirely about the **roll** axis: `check_estimation` compares the gyro's
full scale against `roll_capped` and `roll_limit`, the roll rates at the 2° roll command
cap and at the 8° deflection. A pitch/yaw deflection on a stable vehicle produces no large
body rate; it trims to a slightly larger alpha. **Raising the pitch/yaw cap does not touch
the gyro, provided `ROLL_COMMAND_CAP_DEG` stays at 2.0** — which correction 58 already
settled it should.

What does bind is stall, and it binds as a cliff rather than a rolloff:

Recommended hardware, 30° rail, peak azimuth at 90° of bank:

| deflection | local alpha | stall headroom | peak °/s |
|---|---|---|---|
| 8.0° | 9.53° | 2.47° | 7.81 |
| 9.0° | 10.72° | 1.28° | 8.78 |
| **9.2°** | **10.95°** | **1.05°** | **8.98** |
| 10.0° | 11.91° | 0.09° | 9.76 |
| 10.5° | 12.50° | **stalled** | **6.15** |

Past the limit the rate does not degrade, it **collapses below where it started** — 6.15 °/s
against the 7.81 that 8° was already making. A design point with 0.09° of headroom against a
stall limit that is itself a modelling constant
(`STALL_LIMIT_DEG = 12.0`, linear attached flow) is not a design point. **1.0° of headroom
is one gust**, and it is what the sweep leaves.

**5. R1, and it is no longer the thing in the way.** This is the reversal. On the vertical
search R1 cost 64% of the available turn rate and every other requirement cost nothing. On
a flat launch the recommended point sits at P(SM < 1.0) = **0.61%**, inside R1 as written,
and what stops it going faster is the hinge. Peak azimuth at 90° of bank, every row
converged through the structural chain — **and scored at the ⌀6 journal, i.e. BEFORE the
freeze. §10 re-runs it at ⌀8 and three of these rows stop being blocked:**

| canard/aft | ballast | nominal SM | P(SM<1.0) | peak °/s | sustained | radius | binding |
|---|---|---|---|---|---|---|---|
| **1.30/1.70** | **60 g** | **1.96** | **0.61%** | **8.97** | **8.13** | **990 m** | **— (legal)** |
| 1.30/1.70 | 25 g | 1.92 | 0.9% | 9.23 | 8.47 | 967 m | — *(legal, on R1's edge)* |
| 1.30/1.55 | 25 g | 1.67 | 3.8% | 9.50 | 8.77 | 950 m | R1 |
| 1.45/1.85 | 60 g | 1.99 | **0.4%** | 9.92 | 9.18 | 880 m | hinge bearing 1.94× |
| 1.45/1.70 | 60 g | 1.78 | 1.9% | 10.17 | 9.46 | 868 m | R1, hinge bearing 1.92× |
| 1.50/1.85 | 60 g | 1.94 | 0.7% | 10.30 | 9.59 | 846 m | servo 2.0×, hinge 1.82×, tang 1.89× |
| 1.45/1.55 | 25 g | 1.50 | 9.7% | 10.74 | 10.10 | 835 m | R1 badly, hinge |
| 1.60/1.85 | 60 g | 1.83 | 1.5% | 11.05 | 10.39 | 785 m | servo 1.9×, hinge 1.6×, R1 |

Read the binding column. **Every row above 9.9 °/s is stopped by the hinge or the servo, and
the two closest to 10 °/s have BETTER static-margin risk than the recommended point** — which
is exactly why the freeze's own hinge fix turned out to be worth more than the freeze (§10). Spending static margin no longer buys what it bought on a vertical flight,
because the flat flight already collected the speed and density that margin was standing in
for.

**6. The motor, which is now a real lever and was not before.** `docs/11` concluded in bold
that "agility on this airframe comes from static margin, not from the motor". That is
correct for a vertical launch and it is an artefact of **R6**: apogee ≤ 1600 m binds long
before R5's Mach 0.8 does, so the vertical search could never reach the speed band. Flown
flat, apogee is 250–650 m whatever the motor and the whole band from Mach 0.42 to Mach 0.80
opens — worth nearly 2× in heading rate, linearly.

The band is *reachable* and mostly *unusable*, because the servo and the hinge both scale
with q:

Frozen 1.30/1.70 fins and 60 g throughout; hinge and laminate sized; peak azimuth at 90° of
bank:

| motor | N·s | peak °/s | radius | servo | bearing | P(SM<1) | verdict |
|---|---|---|---|---|---|---|---|
| **J401FJ** | **1105** | **8.97** | **990 m** | **2.32×** | **2.11×** | **0.6%** | **legal** |
| J540R | 1136 | 9.58 | 967 m | 2.06× | 2.14× | 1.8% | R1 only |
| K400C | 1306 | 10.18 | 954 m | 1.88× | 1.95× | 1.1% | servo + hinge + R1 |
| J760 | 1264 | 11.13 | 935 m | 1.59× | 1.65× | 1.3% | servo + hinge + R1 |
| K445 | 1620 | 12.68 | 900 m | 1.24× | 1.29× | 2.0% | servo + hinge + R11 |

**12.7 °/s exists on this airframe and the actuator cannot hold the canard still enough to
use it.** Note the radius column again: 990 → 900 m across a 47% impulse increase, which is
the `R = 2m/(rho S CN)` identity showing up in a search that never assumed it.

The nearest thing to a free motor swap is the **J540R** — 9.58 °/s, servo 2.06×, bearing
2.14×, 314 mm case inside the built 332 mm mount, every structural margin met — and it is
stopped by R1 alone, at 1.8%. **That is the one place in this whole study where relaxing R1
buys something real: taking the risk budget from 1% to 2% is worth 7% of turn rate.** It is
not recommended — 7% is not worth doubling the chance of an unsafe margin on a vehicle that
also has to fly vertically — but the brief asked for the price to be named rather than
buried, and that is the price.

---

## 6. Recommended freeze, and how to fly it vertically

### Horizontal-primary default

```
motor                J401FJ            unchanged
canard / aft         1.30 / 1.70 cal   unchanged
nose ballast         60 g              unchanged
aft fin thickness    3.2 mm            unchanged
canard laminate      3.6 -> 4.0 mm     1.0 / 2.0 / 1.0, three stocked sheets
hinge journal        dia 6 -> dia 8     bearing OD dia 8 -> dia 10; servo does NOT move
hinge bearing        6.0 mm             UNCHANGED -- 6.2 mm is all the length there is
bay collar OD        12.0 -> 14.0 mm    follows the bore; and it is STRUCTURE now
deflection cap       8.0 -> 9.2 deg     pitch/yaw only; roll cap stays 2.0
launch rail          5 deg from vertical -> 30 deg above horizontal
drogue               18 in -> 15.4 in   sized by opening shock, not descent rate
```

**The collar is the requirement this freeze adds.** `check_cut_station`'s bearing-seat crush
margin at the flat flight's load is **1.80× on the bare 2.3 mm wall and 12.10× with the
housing collar bonded in**. Vertically the bare wall was 2.23× and the collar was optional —
`design/bay.py` has always priced it that way, "a part that exists in CAD is not yet a part
that carries load". On a horizontal launch it carries load. It is designed, it is in the
Fusion assembly, and it now has to be printed, reamed and bonded before the vehicle flies
this profile.

**8.97 °/s peak at 90° of bank, 8.13 °/s sustained while holding altitude, 990 m radius,
2.38 g, 59° of heading at 70% duty over a 16.2 s window, apogee 290 m, 93.8 m/s at apogee,
ground range 1.82 km, P(SM < 1.0) = 0.61% on 8000 samples.** Every requirement met:
servo 2.32×, hinge bearing 2.11×, root skin 3.09×, tang 2.53×, flutter 1.97×, R11 packing
fits.

**Fly the altitude-holding bank and burst into the 90° one.** At 30° the max-rate policy
alone tops out at 136 m of apogee, which has no recovery sequence; the sustain policy
reaches 290 m and buys 16.2 s. The peak rate is available inside that window whenever the
guidance wants it, at the cost of altitude while it is held.

### The same airframe, vertical

Nothing about the hardware changes, and **the deflection cap does not change either** — it
is a stall limit, and stall does not know which way the rail is pointing. Set the rail to
5° from vertical, fit the 18 in drogue, and fly the same 9.2°:

| | value | requirement |
|---|---|---|
| apogee | 1003 m | R6 ≤ 1600 m — OK |
| max Mach | 0.42 | R5 ≤ 0.8 — OK |
| static margin | 2.02 – 2.41 cal | R1 band — OK |
| P(SM < 1.0) | 0.61% | R1 < 1% — OK |
| peak heading rate | **7.31 °/s** | — |
| recovery packing | fits | R11 — OK |
| peak axial | 6.5 g | ±16 g accelerometer — OK |

**The secondary mission got faster too, 6.47 → 7.31 °/s**, which was not the plan and is
worth being explicit about: the deflection cap was never a launch-angle-dependent number.
The 4.0 mm laminate costs 1.9% of it (6.47 → 6.35 at the old 8° cap) and the cap gives back
15%.

**There is no ballast swap and no fin swap between the two modes.** That is the direct
consequence of the recommended point not spending static margin: because the horizontal
gain came from the profile, the deflection cap and the hinge rather than from margin, the
vehicle that flies it is the same vehicle that flies vertically. The two "modes" are a rail
angle and a drogue.

If the stretch point (1.45/1.85) is taken instead, that stops being true — it is a
different fin set, and the vertical mode inherits it with a nominal SM of 1.99 cal and
P(SM<1.0) = 0.4%, which is *better* than the freeze but is a second set of parts to build,
and it needs the hinge bearing question of §5.1 answered first.

### Locked-canard vertical (R12)

The canards do not disappear when locked — they are still 27.8% of `CNa`. The failsafe
vehicle is the same airframe at zero deflection: **2.02 cal at rail exit, 1.96 nominal,
P(SM < 1.0) = 0.61%**. Raising the deflection cap does not change any of those numbers,
because static margin is a derivative and does not depend on deflection. The locked-canard
mode is unaffected by everything proposed here.

---

## 7. Failsafe on a horizontal launch — and it is the mirror image of the vertical one

Documented for engineering honesty. Range access is settled; this is about what the vehicle
does when the loop opens, not about whether it is allowed to fly.

**The vertical failsafe problem is "guidance off late in flight when q is gone."** After
apogee a vertical flight has no dynamic pressure and no authority. R12 centres and locks
the canards, the vehicle is stable, and the drogue is already out.

**A flat flight has the opposite problem: q never goes away.** The vehicle arrives at the
ground with the canards still fully effective — 94.8 m/s at apogee, ~130 m/s at impact.
There is no phase of a horizontal flight in which a runaway canard is harmless.

Three consequences, none of which the vertical design had to answer:

**The manoeuvre floor is a hard requirement, not a convention.** `horizontal.ALTITUDE_FLOOR_M
= 50 m`: below it the control law must centre and hold regardless of what guidance wants,
because there is no recovery event left to fire. At the recommended point the vehicle
crosses 50 m at t = 19.5 s and reaches the ground at t = 20.2 s — **0.75 s**, at about
101 m/s. That is the whole reaction budget below the floor, and it is why the floor has to
be enforced by the flight computer rather than by the trajectory.

**A centred-canard failure is benign; a hardover is not.** Centred, the vehicle is a stable
ballistic dart on a known arc — close to the 1.84 km downrange impact it was already going
to make, which is why the failsafe is still "centre and lock". A hardover at full deflection
puts 2.38 g into an unplanned arc with up to 16 s of authority left. **The R12 watchdog has
to be fast against the turn, not against the flight**: at 8.13 °/s a one-second detection
lag is 8° of heading, and eleven seconds is a quarter turn. The vertical vehicle could afford a
slow watchdog because it ran out of q; this one does not run out of q until it lands.

**The footprint is directional.** A vertical flight lands in a cone around the pad; a flat
one lands in a 1.8–2.3 km corridor downrange whose width is set by how much heading the
vehicle accumulated before the fault. That is a range-safety conversation to have with real
numbers rather than a design blocker, and the numbers are in §2's table.

**What does not change:** the canards are still centred and locked on any fault, loss of
nav, or burnout + N seconds. R12's text is correct as written for a horizontal launch. What
changes is the *timeliness* requirement behind it, which R12 has never stated.

---

## 8. Proposed delta to `docs/00-requirements.md`

Proposed, not applied. `configure.py` and `docs/00` are untouched until this is accepted.

**Read this first: R1 is not relaxed, and that is a finding rather than a reflex.** The
brief said not to keep maximising R1 margin as a hidden objective. The recommended point
sits at P(SM < 1.0) = 0.61% against R1's 1% budget and a nominal 1.96 cal inside R1's
1.5–2.5 band, so R1 is not in the way and there is nothing to buy by moving it. On a
vertical flight R1 cost 64% of the available turn rate; on a flat one the binding
constraint is the hinge bearing, three requirements down the ladder. The delta below moves
what actually binds.

### §1.2 — status

> ~~Regulatory / range-access constraint — RESOLVE IN WEEK 1~~
> **Regulatory / range-access constraint — CLOSED.** Written approval for guided /
> research flights is held (club, advisor, export control) and range access is settled.
> This section is retained as the record of what was obtained and from whom. **It is not a
> design constraint and must not be used as one** — in particular, the failsafe behaviour
> in R12 is specified below on engineering grounds, not to satisfy an approval that has
> already been granted.

### §1.1 — mission priority (NEW, replaces the L1→L2→L3 recommendation as the ordering)

> **Primary: path agility on a horizontal or near-horizontal launch.** Maximise peak
> heading rate and minimise turn radius after boost. Target: AIM-9B-class heading rate,
> ~10 °/s. Achieved: 8.97 °/s peak, 990 m radius (docs/12).
>
> **Secondary: fly the same airframe on a high-angle rail** as a recoverable, analysable
> research HPR, with the canards either locked or at reduced authority. This must not
> require a second airframe, and at the recommended point it does not require a second
> configuration either — only a rail angle and a software deflection limit.
>
> The L0–L4 capability ladder in §1.1 is unchanged and still describes what the *control
> law* has to do. What has changed is which flight profile it does it on.

### R1 — unchanged

> Static margin, canards at zero, at rail exit: 1.5–2.5 cal nominal, P(SM < 1.0) < 1%.
> **Met at 1.96 cal nominal and P = 0.61% on the horizontal-primary point (docs/12 §6),
> which is the same airframe and the same ballast as the vertical freeze.**

### R2 — unchanged, with the deflection cap it refers to restated

> Static margin must stay > 1.0 cal with canards at full deflection. **"Full deflection" is
> now 9.2°, not 8.0° — see R13.** Static margin is a derivative and does not depend on
> deflection, so the numeric verdict is unchanged; the requirement is restated only so that
> "full" means the same thing here and in `configure.py`.

### R5, R7, R8, R9, R10 — unchanged

R8's 0.5 g floor is met with 4.8× margin (2.38 g). It is worth noting that lateral g is the
wrong scoreboard — see docs/11 §4 — but as a *floor* it costs nothing and it still catches a
vehicle with no authority at all.

### R6 — apogee, now two-sided

> ~~Apogee ≤ 1600 m AGL~~
> **Vertical mode: apogee ≤ 1600 m AGL.** Unchanged, and unchanged in its reasoning.
> **Horizontal mode: apogee ≥ 250 m AGL.** The main fires at 200 m (R11); below ~250 m of
> apogee there is no dual-deploy sequence, only a drogue-to-ground descent this vehicle is
> not sized for. This is the mirror image of the vertical cap and it is the constraint that
> sets the minimum launch elevation — 30° on the recommended point, 28° on the frozen
> vehicle before its canard laminate got thicker. **The upper cap does not
> bind a flat flight at any motor in the 54 mm catalogue**, which is why the horizontal
> search reaches speeds the vertical one could not (docs/12 §5.6).

### R11 — recovery, with the deployment case corrected

> Dual deploy: drogue at apogee, **56 in** main at 200 m. 5.0 m/s landing.
> **The drogue is sized by its OPENING SHOCK on a horizontal launch, not by descent rate.**
> A flat flight arrives at apogee at ~95 m/s, not ~1 m/s, because the horizontal velocity
> component never goes away. Apogee remains the correct trigger — it is the minimum-speed
> point of a flat arc — but an 18 in drogue there produces 2193 N against the 1604 N the
> M10 anchors, the 3/4" harness and the quick links were sized for (docs/10).
> **Horizontal mode: 15.4 in drogue**, which holds the shock to the existing design load
> and brings the vehicle to 200 m at 23.5 m/s. **Vertical mode: 18 in, unchanged.**
> Neither the anchors, the harness, the quick links nor the bay length change.

### R12 — failsafe, with a deadline

> Canards centred + locked on any fault, loss of nav, or after burnout + N s. **Mandatory.**
> **NEW: the fault-to-centred latency shall be ≤ 0.5 s, and the canards shall centre
> unconditionally below 50 m AGL regardless of guidance state.**
>
> Rationale, and it is specific to the horizontal profile. The vertical failsafe problem is
> guidance-off late in flight when *q* is gone: after apogee there is no authority and a
> slow watchdog is harmless. **A flat flight never runs out of *q*.** It reaches the ground
> with the canards fully effective, so a hardover is dangerous for the whole flight rather
> than the first third of it. At 8.13 °/s a one-second lag is 8° of heading. Below 50 m
> there are 0.75 s and about 101 m/s left, which is not a reaction budget — hence the
> unconditional floor.
>
> R12's existing text is correct as written. What it never stated is *how fast*, and on a
> vertical flight it did not have to.

### R13 — canard deflection limit (NEW, promoted out of `configure.py`)

> **Pitch/yaw deflection ≤ 9.2°, set by canard stall with 1.0° of local-alpha headroom
> against `control.STALL_LIMIT_DEG` = 12°. Roll command ≤ 2.0°, set by rate-gyro full
> scale. These are different limits for different reasons and must not be merged.**
>
> `configure.DEFLECTION_LIMIT_DEG` is documented as a *sensing* limit — "what keeps the rate
> gyro inside its range". Reading `estimation.check_estimation`, that argument is entirely
> about the **roll** axis: it compares gyro full scale against the roll rates at the 2° roll
> cap and at the 8° deflection. A pitch/yaw deflection on a stable vehicle produces no large
> body rate, so **raising the pitch/yaw cap does not touch the gyro provided
> `ROLL_COMMAND_CAP_DEG` stays at 2.0**, which correction 58 independently concluded it
> should. Verified by running `estimation.check_estimation` and
> `estimation.mag_aided_roll_error` at both deflections: identical output, 647.96 °/s of
> roll rate and 0.079° of aided roll error either way, `ok = True` either way.
>
> The real limit is stall, and it is a cliff: at 10.5° of deflection the vehicle stalls and
> peak rate falls to 6.15 °/s — **below where it started at 8° (7.81)**. 1.0° of headroom is one
> gust, and it is the minimum this project should fly.

### R14 — hinge bearing and its seat (NEW, and it is the binding structural requirement)

> **Hinge bearing peak pressure margin ≥ 2.0× at the maximum dynamic pressure of the
> flight profile being flown.**
>
> **AND: the bearing SEAT in the tube shall meet 2.0× at the same condition. It does so
> only with the printed bay's housing collar bonded in — 1.80× bare, 12.10× with — so the
> collar is structure and shall be treated as such in the build sheet and the mass budget.**
>
> This is not a new *kind* of requirement — the project already requires 2.0× everywhere —
> but it has never been stated at vehicle level, and it is now the constraint that caps the
> design. A flat flight's max *q* is the burnout value at sea level (15.5 kPa) rather than
> at 230 m (12.4), so the as-built 6.0 mm bearing falls to 1.57×. Peak pressure goes as
> 1/L², the bearing grows inboard at the servo's face, and the four servo cable bosses meet
> on the axis at 6.09 mm of inboard move — so bearing length ends at about 8.0 mm and the
> hinge carries about 44 N of panel normal force at 2.0×.
>
> **That is what caps the canard near 1.50 cal semispan.** Not stall, not static margin, not
> servo torque. Any future proposal to grow the canards has to answer this requirement
> first, and the honest fixes are a larger journal diameter (at 7.5 mm and 1.45 cal, ⌀6 → ⌀6.5
> buys 1.94 → 2.11×) or
> a better bearing material — *not* hinge-line balance, which shrinks the servo's moment and
> does nothing for the bearing's force.

### R15 — launch elevation (NEW)

> **Horizontal mode: launch elevation 30° above horizontal (rail 60° from vertical).
> Vertical mode: 5° from vertical, unchanged.**
>
> A true horizontal launch is not available on a T/W of 6.17. Gravity droop during boost
> rotates the velocity vector down by ~20° — `(g/a)·ln(V_burnout/V_rail)` = 19.9° — so a 20°
> rail is descending by burnout and reaches the ground before the control law starts. 30° is
> the lowest elevation that still satisfies R6's horizontal floor **for the recommended
> vehicle** — the frozen one clears it at 28°, and the 2° is the thicker canard laminate
> showing up as descent mass. It flies flat anyway: 6° of flight path angle at burnout.

### Residual risk, stated plainly

1. **The hinge bearing has 0.59 mm of boss clearance at the recommended 5.5 mm servo move**,
   against the 1 mm `hinge.selected` says it wanted. This is the tightest geometric margin
   in the proposal and it is in a part that has to be assembled by hand.
2. **The tang does not improve with a thicker laminate.** It is 2.53× at 1.30 cal and 2.06×
   at 1.45 cal, and it carries panel force, not skin bending. The recommended point has
   room; the stretch point has almost none.
3. **`Cl_delta` is still unmeasured.** Everything downstream of the roll loop — including
   the bank angle this whole horizontal scheme depends on — sits on an analytic
   interference model that has never been flown. This is unchanged by anything here, and it
   is the largest single unknown in the project.
4. **The 12° stall limit is a modelling constant**, not a measured one, and the recommended
   point spends 11.0° of the 12. If the real limit is 11°, the recommended deflection is
   already past it and the rate falls to the post-stall value rather than degrading.
5. **A flat flight has full control authority at impact.** R12's new latency requirement
   mitigates it; it does not remove it.
6. **The horizontal numbers have never been flown.** `design/horizontal.py` reproduces two
   existing codes on a vertical flight to 0.5%, which is evidence that the integrator is
   right — it is not evidence that the flat-flight *aerodynamics* are. Nothing in this repo
   has ever validated the drag model, the trim model or the interference model at a 6°
   flight path angle near the ground, and no rocket in this project has flown at all.


---

## 9. What applying the freeze actually cost

Kept because the proposal in §8 was wrong about the cheap part of this, and the way it was
wrong is the same way this project has been wrong five times now: a number was checked
against the requirement it was chosen for, and not against the one next to it.

**§6 proposed a 7.0 mm bearing at a 5.5 mm servo move. It is not buildable.**
`check_hinge_stack` requires 1.0 mm between adjacent servo cable bosses at the rocket axis
and a 5.5 mm move leaves 0.59 mm. §8's residual-risk list called that "the tightest
geometric margin in the proposal"; it was not tight, it was over the line, and the proposal
should have run the check rather than describing it.

**And the length was never on the table.** The bearing grows inboard from a fixed outboard
end at the panel root, and the sleeve it turns on begins 0.300 mm outboard of the servo's
output face. At the as-built servo position the sleeve starts at R 33.485 and the bearing's
outboard end is at R 39.700, so **6.2 mm is all the length there is** — a 6.5 mm bearing
puts its inboard end 0.285 mm inside the sleeve, i.e. inside the servo.

**Nothing checked that.** `check_hinge_stack` tested where the *sleeve* starts, not where
the *bearing* ends, and the two are independent. It is now a fourth violation in that
function, in the family of the three it was written for: "a dia 5.000 shaft in a dia 5.000
hole is not an interference, so nothing in the CAD will ever object to it."

**So the journal grew instead**, and that is strictly the better answer — it needs no servo
move, spends no central void, keeps the boss clearance at its as-built 2.09 mm, and takes
the sleeve wall over the ⌀4 spline socket from 1.00 to 2.00 mm, which is the dimension ⌀6
was itself chosen to fix. ⌀6 → ⌀8: **1.57× → 2.10×**.

Then the chain ran:

| link | from | to | because |
|---|---|---|---|
| journal | ⌀6 | ⌀8 | bearing pressure 1.57× → 2.10× |
| wall bore / bearing OD | ⌀8 | ⌀10 | `journal + 2 × bearing wall`, derived |
| tube net section at the hinge | 13% | 17% | four bigger bores at one station |
| bay collar OD | 12.0 mm | 14.0 mm | 1.00 mm of wall failed the 1.60 mm FDM minimum |
| collar printed bore | 7.5 mm, typed | derived | 7.5 under a ⌀10 ream is 1.25 mm of stock on the radius — a boring operation, and the check only tested that the stock was positive |
| bearing seat crush, flat load | 2.23× vertical | **1.80× bare / 12.10× with the collar** | the collar becomes structure |

Six links, and the only one anybody typed was the first. Five of the six were caught by
checks that already existed; the two that were not — the bearing overhanging its sleeve,
and a printed bore that no longer matched its reamer — are now checks too.

**No aerodynamic number moved.** 8.97 °/s, 990 m, P(SM<1.0) = 0.61%. What moved is the
parts list, and one requirement: the collar is load-bearing now.

### What is now stale

`control.check_measured_geometry` fires on the frozen vehicle:

> canard module: tensor measured on a 3.6 mm panel, vehicle now has 4.0 mm

That is correct and it is the system working. **The Fusion canard module needs rebuilding**
— 4.0 mm panels, a ⌀8 shaft, a ⌀10 wall bore and seat, and a 14.0 mm collar reamed to ⌀10.
Every generator derives from `design/*.py`, so the scripts do not change; they need running.
Nothing was rebuilt as part of this freeze.


---

## 10. What the freeze unlocked, which was not the point of it

Re-running the search **after** the freeze turns up something the pre-freeze search could
not: **the ⌀8 journal removes the wall that blocked the 1.45 cal canard.** §5.5's Pareto
had 1.45/1.85 stopped at a 1.92× bearing; at ⌀8 it is 2.27×, and the point is legal.

Every row below passes **every** requirement including R1, with the structural chain run:

| point | motor | canard / aft | ballast | nominal SM | P(SM<1.0) | peak °/s | sustained | radius |
|---|---|---|---|---|---|---|---|---|
| **frozen** | J401FJ | 1.30 / 1.70 | 60 g | 1.96 | 0.61% | **8.97** | 8.14 | 990 m |
| canards + tail | J401FJ | 1.45 / 1.85 | 60 g | 1.99 | **0.45%** | **9.92** | 9.18 | 880 m |
| ″ , more tail | J401FJ | 1.45 / 2.00 | 25 g | 2.14 | **0.12%** | **9.93** | 9.16 | 875 m |
| ″ + motor | J525 | 1.45 / 2.00 | 25 g | 1.91 | 0.94% | **10.08** | 9.30 | 861 m |

**The middle two are better than the frozen point on both axes at once** — more turn rate
*and* less static-margin risk — which is the same "grow both sets together" result §4
predicted and could not reach. The last row crosses the AIM-9B's 10 °/s outright, on a
motor whose 327 mm case still fits the 332 mm mount docs/09 built.

**This is reported, not adopted.** The freeze is what was accepted and it stands. What it
costs to move further is now a parts question rather than a physics one: new canard panels,
new aft fins, and for the last row a different motor.

**The one chain the search still does not run is the recovery anchor**, which is the
self-loading loop docs/11 §7 records — bigger fins → more descent mass → more opening shock
→ bigger anchors → more descent mass. `mass.harness_anchors` is a fixed 0.302 kg, not
derived, so a bigger fin set does not re-trigger it automatically. **Checked by hand here
and it is small**: dry mass 6.080 → 6.213 kg and the main's opening shock 1604 → 1675 N,
**1.04×** against an M10 anchor sized at 3.89×, with recovery packing unchanged at +2.2 mm.
It converges without changing a part. That is the only gap between these rows and a
buildable freeze.


---

## 11. Adopting 1.45 / 1.85 — and the correction to §10

§10 said 1.45/1.85 was legal on the frozen hinge at a 2.27× bearing margin. **It was not,
and the 2.27× was measured on a hinge that cannot be built.**

`scripts/horizontal_agility_sweep.Candidate._structure` used to size the bearing itself,
walking `BEARING_STEPS_M` and deriving a servo inboard move from each length — **and it
never called `check_hinge_stack`.** On the 1.45 cal canard it selected a 7.0 mm bearing at a
5.5 mm servo move, which leaves **0.59 mm** between adjacent servo cable bosses against that
check's 1.0 mm minimum: the same combination §9 had already rejected one correction earlier,
re-derived by a different piece of code that did not know about it.

On the hinge as actually frozen — ⌀8, 6.0 mm, 4.0 mm move — 1.45/1.85 runs at **1.69×**.

**This is the fifth instance of this project's recurring failure, and the first one in code
written to catch it.** docs/11 §7 lists the others: the ±16 g accelerometer written in
docs/02 and never encoded; the canard root joint; the self-loading recovery anchor; then the
hinge bearing and the drogue's deployment shock. Every one is a constraint that was settled
somewhere and not consulted by the search that needed it. `_structure` now calls
`hinge.selected()` as **frozen hardware** and validates it with `check_hinge_stack` rather
than re-deriving a hinge of its own.

### What adopting it actually cost: the journal grows again

| link | from | to | because |
|---|---|---|---|
| journal | ⌀8 | **⌀10** | panel normal force 38.0 → 42.3 N at 1.45 cal; bearing 1.69× → 2.11× |
| bearing OD / wall bore | ⌀10 | **⌀12** | `journal + 2 × bearing wall`, derived |
| tube net section at the hinge | 17% | **20%** | four bigger bores at one station — still passes |
| bay collar OD | 14.0 mm | **16.0 mm** | 2.00 mm of wall around a ⌀12 bore |
| sleeve wall over the ⌀4 spline | 2.00 mm | **3.00 mm** | free, and in the right direction |
| recovery anchors | M10, 296.2 g | **M10, 296.2 g** | **converged with no change** — see below |

**The self-loading anchor chain converged in zero passes.** This is the one docs/11 §7
records as having been missed at the 1.30/1.70 freeze, so it was run first this time: dry
mass 6.080 → 6.185 kg, main opening shock 1604 → 1660 N, and the M10 U-bolt goes 3.69× →
**3.57×** on the crown, which is what governs it. No size change, no mass change, recovery
packing unchanged at **+2.2 mm**. `mass.harness_anchors` stays 0.302 kg against 296.2 g of
sized hardware — the same 5.8 g of conservatism it already carried.

### The frozen vehicle

| | 1.30 / 1.70 (correction 61) | **1.45 / 1.85 (correction 62)** |
|---|---|---|
| launch elevation | 30° | **28°** |
| deflection | 9.2° | 9.2° (9.16° stall-limited) |
| canard laminate | 4.0 mm | 4.0 mm |
| hinge journal | ⌀8 | **⌀10** |
| collar OD | 14.0 mm | **16.0 mm** |
| **peak heading rate**, 90° bank | 8.97 °/s | **9.92 °/s** |
| sustained, holding altitude | 8.14 °/s | **9.18 °/s** |
| turn radius | 990 m | **880 m** |
| lateral g | 2.38 | **2.63** |
| heading, 70% duty | 60° over 16.2 s | **66° over 16.4 s** |
| nominal SM / P(SM<1.0) | 1.96 / 0.61% | **1.99 / 0.45%** |
| drogue | 15.4 in | **16.1 in** |
| apogee / V at apogee | 291 m / 93.8 m/s | **252 m / 90.9 m/s** |
| vertical mode | 1003 m, 7.31 °/s | **974 m, 8.04 °/s** |

**Better on both axes**, as §10 predicted — the prediction was right even though the number
behind it was not.

### Margins at the freeze, tightest first

| check | margin | required |
|---|---|---|
| **canard root tang** (best material, 4140) | **2.02×** | 2.0× |
| **servo torque** | **2.07×** | 2.0× |
| hinge bearing pressure, flat | 2.11× | 2.0× |
| canard root skin over the slot | 2.49× | 2.0× |
| aft fin flutter | 1.78× | 1.5× |
| tube bearing seat, **with the collar** | 11.72× | 2.0× |
| tube bearing seat, bare 2.3 mm wall | **1.74×** | — (R14: the collar is structure) |
| recovery packing | +2.2 mm | > 0 |
| R1, P(SM < 1.0) | 0.45% | < 1% |

**Two margins are effectively on the line — the tang at 2.02× and the servo at 2.07×.**
Neither has anywhere to go: the tang carries panel force and does not improve with a thicker
laminate (§5.2), and the KST X08 Plus is the strongest servo that fits four-abreast in a
79.4 mm tube (§5.3). **1.45 cal is the last canard this airframe can actuate**, and it is
now three independent checks deep rather than one.


---

## 12. The Fusion rebuild

Rebuilt once, at the final freeze — not at 1.30/1.70 first. `CanardControlModule` is saved.

**Deleted and regenerated:** `Tube`, `Panel0-3`, `Shaft0-3`, `CanardBay`, `Bearing`,
`AftFin0-3` — 15 occurrences, 24 bodies. `Servo`, the nose, nav bay, recovery and
motor-mount parts were untouched: nothing in this freeze moves them, and the servo stayed
put because the servo inboard move did not change (§9).

| body | was | now |
|---|---|---|
| tube | 79157.63 mm³, ⌀8 bores | **78577.02 mm³, 4 × ⌀12 bores** |
| panel ×4 | 16814.31 mm³ | **21002.01 mm³** (1.45 cal, 4.0 mm) |
| shaft ×4 | 698.14 mm³, ⌀6 | **1032.76 mm³, ⌀10** |
| bearing ×4 | 130.25 mm³, ⌀6/⌀8 | **204.51 mm³, ⌀10/⌀12** |
| canard bay | 28257.58 mm³, ⌀12 collars | **27683.86 mm³, ⌀16 collars, ⌀12 bore** |
| aft fin ×4 | 52410.96 mm³ | **56579.40 mm³** (1.85 cal) |

`BoosterTube` verified rather than rebuilt: the aft fin grew outboard, but its root chord
and the derived 11.15 mm tab did not, so the four slots are unchanged.

**Interference: 14 pairs, every one at exactly 0.000000000 mm³** — servo in its tray, spline
in its socket, nose plate in its shoulder bore, all coincident faces and no volume. The
driven check sweeps 0 / ±4.6 / ±9.2° and reports **144 pairs across 6 angles, none over the
0.05 mm³ tolerance**.

### Two things the rebuild found

**1. The tube's bore-volume check was a fudge, and the fudge did not scale.**
`make_hinge_stack_fusion.py` modelled each wall bore as `πr²t` and carried a "measured"
0.2 mm³/hole tolerance for the error. At ⌀12 that model is **0.796 mm³/hole** out, four of
which failed a 0.8 mm³ budget on the first build attempt.

The 0.2 was never a Fusion precision limit — it was that model's own error at ⌀8 (0.156
mm³), measured and then treated as noise. A radial hole through a *curved* wall removes

```
V = ∫(-a..a) 2·√(a²−y²) · [√(Ro²−y²) − √(Ri²−y²)] dy
```

because the wall is that thick along the hole's own axis at each chordwise offset, not
`(Ro − Ri)`. `_radial_bore_volume()` integrates it (Simpson over `y = a·sin θ`,
dependency-free so the emitted script stays runnable inside Fusion). It lands **0.041
mm³/hole** from Fusion, so the tolerance **tightened 4×** to 0.05 mm³/hole and no longer
moves when the bore does. Fusion measured 78577.0227 against a predicted 78576.8575.

**2. The joint scripts were driving 8.0° and claiming it was the deflection limit.**
`make_canard_joints_fusion.py` and `check_canard_interference_driven_fusion.py` both
hardcoded 8.0, and the second one's docstring said in as many words that it "matches
design/configure.py's `DEFLECTION_LIMIT_DEG`". It did, until correction 61 took that to 9.2
— after which the driven interference check was sweeping **87% of the commanded throw and
calling it the range**, which is precisely where a clash at full deflection would hide.
Both now derive from `DEFLECTION_LIMIT_DEG`.

### The tensor, and the density trap firing exactly as predicted

`CANARD_MODULE_CAD` is re-read and `check_measured_geometry()` is quiet.

| | 1.30 cal / 3.6 mm | **1.45 cal / 4.0 mm** |
|---|---|---|
| mass | 0.352842 kg | **0.386057 kg** (+9.4%) |
| station from module face | 0.081173 m | **0.082349 m** |
| i_transverse | 992.057e-6 kg m² | **1222.745e-6** (+23%) |
| **i_roll** | 1313.230e-6 kg m² | **1735.964e-6** (+32%) |

The module came back at **1.574165 kg — 4.08× the truth** — because every rebuilt body was
Fusion's default Steel again. `control.py`'s own note predicted this ("this will happen
again on the next rebuild; check the density before trusting a mass, every time") and it was
right. The five custom materials from the previous rebuild were still in the document, so
this was reassignment rather than re-creation.

**Cross-checked against the repo's own volumes rather than trusted**: 4 panels × 21002.0135
mm³ × 1850, tube × 1850, 4 shafts × 2700, bay × 1300, 8 retainer bars × 1300, 4 bearings ×
1450 and 4 servos at a datasheet 9 g sum to **0.386054 kg** against Fusion's **0.386057** —
three parts in a million, from two routes that share no arithmetic.

**i_roll moving 32% is the number that matters**, because roll inertia sets the bandwidth
every control gain is scheduled against. The pitch mode reads 3.6 Hz and the derived control
loop floor 72 Hz, both comfortably inside R10's 100 Hz.

### Not run

`check_canard_rebuild_cross_check_fusion.py` cannot run and is not expected to: its oracle
is the old hidden 28-body rebuild, which M6 deleted at cutover. It is migration history.


---

## 13. The pointed-delta canard — a cosmetic change, priced

Asked for on looks alone: the 0.40-taper trapezoid read as a clipped panel with a wide tip,
and the vehicle is meant to look like a canard missile. Budget: 3% of heading rate, and no
2.0× structural margin allowed to fail.

| | before | **after** |
|---|---|---|
| root chord | 67.5 mm | **88.6 mm** |
| tip chord | 27.0 mm | **8.9 mm** |
| taper ratio | 2.5 : 1 | **10 : 1** |
| LE sweep | 30.7° | **42.2°** |
| TE sweep | +13.7° | +12.1° |
| semispan | 115.1 mm | 115.1 mm *(unchanged)* |
| panel area | 5439 mm² | 5611 mm² (+3.2%) |
| **peak heading rate** | 9.92 °/s | **9.76 °/s (−1.63%)** |
| turn radius | 880 m | 893 m |
| **P(SM < 1.0)** | 0.40% | **0.34%** |
| servo torque | 2.067× | **2.067×** |
| hinge bearing | 2.11× | **2.53×** |
| root tang | 2.02× | **2.46×** |
| root skin | 2.49× | **2.99×** |
| **canard flutter** | 4.50× | **3.51×** |
| aft fin flutter | 2.01× | 2.01× |

### A canard outline is not free on this airframe, and two constraints say so

**1. The hinge station moves with the planform.** `hinge.canard_hinge_station` is 0.20c of
the MAC, so it depends on root chord, taper *and* sweep. Change the outline naively and the
shaft, the four bay collars, the four servos and the four wall bores all move with it —
that is a bay rebuild, not a cosmetic change. So **`canard_sweep_cal` is solved, not styled**:
1.316336 cal is the value that holds the hinge at 521.720232 mm, and it lands within a
nanometre. That is what made this a four-panel rebuild instead of a whole-module one — the
tube and shafts verified byte-identical afterwards.

**2. Servo torque does not get to pay for looks.** It is 2.067× and one of the two tightest
margins in the vehicle (§11). Hinge moment goes as panel area × mean chord, so root chord
was then solved to hold the torque margin *exactly* at 2.067×. That fixes the area at +3.2%
and is what the −1.63% of heading rate buys back.

Two constraints, two free variables, no styling latitude left. The only genuinely free
choice was **taper**, and 0.10 is the sharp end of the range asked for. 0.08 was also legal
(−1.89%, every margin better still) and was not taken: a 7.2 mm tip chord on a 4.0 mm
laminate is a stub, not a point.

### What it cost that was not asked about

**Canard flutter, 4.50 → 3.51×.** `design/flutter.py` takes t/c on the **root** chord, and
the root chord is what grew: 0.0593 → 0.0451. `configure.py` has warned about exactly this
since the 0.70/0.70 → 0.85/0.40 change — *"this is now the parameter to watch if the panel
ever gets thinner"* — and it was right to; the panel did not get thinner, the chord got
longer, which is the same ratio. 3.51× is still 2.3× the requirement and the canards are not
the flutter-critical set (the aft fins are, unchanged at 2.01×), but **a further sharpening
would spend flutter, not the structural margins**, and that is the wall to watch next.

Everything else moved the right way, and none of it was the point: less area outboard means
less panel normal force, so the bearing, the tang and the root skin all gained, R1 improved,
and the module's roll inertia fell 11%.

### CAD

DXFs regenerated (`out/cad/canard_planform.dxf`, 113.4 × 123.1 mm envelope). **Only
`Panel0-3` were rebuilt in Fusion** — 21002.02 → 21649.37 mm³ each, verified to +0.0004 mm³.
Interference clean at rest (32 pairs) and driven (144 pairs across 0 / ±4.6 / ±9.2°).
`CANARD_MODULE_CAD` re-read: mass 0.386057 → **0.390847 kg**, i_roll 1735.964 →
**1539.655e-6 kg·m²** (−11%). `check_measured_geometry()` quiet, document saved.

**The density trap fired twice in one rebuild**, and the second way is new: the four new
panels came back Steel as always — but so did the **shafts and the canard bay, which were
never rebuilt**. Deleting the four panel occurrences and their joints reverted material
assignments made after those features in the timeline. Reading the tensor there would have
given 0.598210 kg against a true 0.390847. **Reassign every module body and verify none is
Steel before reading — not just the ones you rebuilt.**
