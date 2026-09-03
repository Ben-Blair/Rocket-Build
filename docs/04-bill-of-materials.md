# Bill of materials

Shareable version: https://claude.ai/code/artifact/9ab713c4-d227-4edb-b377-f45deb504bc2

Vehicle as frozen in `design/configure.py`. Masses are the model's, not weighed — every
line is a prediction until the part is on a scale, and `scripts/robustness.py` should be
rerun as each one is retired.

**Price confidence is marked.** ✅ = researched, vendor and figure cited below. ~ = typical
HPR component pricing, verify at order. Prices are USD, exclude shipping and hazmat, and
were gathered August 2026.

---

## 1. Airframe

| Item | Spec | Qty | Mass | Price | |
|---|---|---|---|---|---|
| Body tube, G12 fiberglass | 3 in, 79.4 mm OD / 74.8 mm ID, 2.3 mm wall. Need 1043 mm; buy one 48 in (1219 mm) length | 1 | 1.075 kg | ~$130 | |
| Nose cone, fiberglass | 3 in, 4:1 tangent ogive, 318 mm, **1 cal hollow shoulder** — its bore is usable nav bay, see `design/joints.py` | 1 | 0.180 kg | ~$75 | the instrumentation module; meant to come off |
| Coupler tube, fiberglass | 3 in, for 3 bay joints | 1 length | in structure | ~$50 | |
| Bulkheads and centering rings | G10 or birch ply, 3 in | set | 0.300 kg | ~$35 | |

Bay lengths, nose to tail: nav 127 mm, canard module 143 mm, recovery 357 mm, booster
416 mm. Total airframe length 1361 mm.

## 2. Fins

| Item | Spec | Qty | Mass | Price | |
|---|---|---|---|---|---|
| G10 sheet, 1/8 in (3.2 mm) | Aft fin blanks 155 × 124 mm each, plus through-wall tabs. One 12 × 24 in sheet covers both sets | 1 | 0.637 kg | ~$45 | |
| G10 sheet, 3.0 mm | Canard blanks 68 × 68 mm each — cuts from the offcuts above | — | 0.142 kg | — | |

Aft fins: 4 panels, root 150.9 / tip 67.9 / semispan 123.1 mm, 87.3 mm sweep, through-wall
mounted. Canards: 4 panels, root 67.5 / tip 27.0 / semispan 67.5 mm, **47.9 mm sweep**,
interdigitated 45° from the aft fins. Both sets carry the same 35.4° leading-edge sweep.
Flutter margins 1.97× and 4.46×.

## 3. Propulsion

| Item | Spec | Qty | Mass | Price | |
|---|---|---|---|---|---|
| Cesaroni Pro54 3-grain casing | P54-3G, reusable | 1 | 0.498 kg | **$98.20** | ✅ |
| Cesaroni reload | 1261J449-15A Blue Streak, 1260 N·s | 1 | 0.624 kg prop | **$136.50** | ✅ |
| Motor mount tube | 54 mm, 416 mm long | 1 | 0.250 kg | ~$25 | |
| Motor retainer | 54 mm screw-on (Aeropack or equivalent) | 1 | in structure | ~$45 | |

Requires **Level 2 certification**. Budget 5 reloads for the GV-1…GV-5 campaign
(+$546), plus separate cert motors.

## 4. Canard actuation

| Item | Spec | Qty | Mass | Price | |
|---|---|---|---|---|---|
| Servo, KST X08 Plus V6.0 | 23.5 × 8.0 × 16.8 mm, 9 g, 5.3 kgf·cm @ 8.4 V | 4 | 0.036 kg | **$43–55 ea** | ✅ |
| ~~Servo frame with outboard bearing~~ | **INVESTIGATED AND DROPPED, Aug 2026.** See the note below — it does not do what this line used to claim, and it probably does not fit | 0 | — | — | ❌ |
| Canard hinge shaft | ⌀6 **6061-T6** rod, 32.2 mm long, one end milled to a **1.8 × 11.9 × 25.5 mm blade**. The only custom-machined part in the module | 4 | in shafts | stock rod ~$10 | |
| ~~Servo horn, ⌀4 mm 15T~~ | **INVESTIGATED AND DROPPED, Aug 2026. It does not fit.** There is 0.515 mm between the servo's output face and the bearing, and outboard of that everything passes down the ⌀6 journal. Every female-spline part sold is ⌀7 or bigger. See the note below | 0 | — | — | ❌ |
| Anaerobic retaining compound | **Loctite 638 class**, plus the matching activator/primer. This is the coupling: a ⌀4.100 × 3.20 drilled socket in the shaft, filled and pushed onto the spline, so the compound cures in the tooth valleys and *becomes* the female spline. Releases at ~250 °C, which is what makes a servo swappable | 1 bottle | in shafts | ~$20 | ✅ |
| Canard hinge bearing | **⌀6 / ⌀8 × 6.0 plain sleeve, iglidur G class.** Housing reamed **⌀8 H7** — a standard reamer; the interference comes from the bushing being supplied oversize. This is the part that keeps the panel bending out of the servo | 4 | in shafts | ~$5 ea | |
| ⌀8 H7 chucking reamer | The one piece of tooling this design actually requires. Reams the tube wall **and the printed collar together, after bonding** — see the build note below | 1 | — | ~$15 | |
| Canard shafts, bushings, hardware | The lines above plus fasteners and epoxy | 4 | 0.240 kg | ~$40 | |
| **G10 sheet, 0.6 mm** | Panel skins. 8 skins, 2 per panel | ~0.3 m² | in canards | ~$25 | |
| **G10 sheet, 2.0 mm** | Panel cores. The tang slot is a gap cut in this sheet, not a slot machined later | ~0.15 m² | in canards | ~$20 | |
| Printed canard bay | **PETG-CF** (plain PETG passes too, at 10.0× instead of 14.5×) — **not PLA**, 8× M2 heat-set inserts. **Carries the bearing housing collar**, 3.700 mm of ⌀8 bore per hinge, worth 3.4× → 14.5× on the bearing seat. 39 g, one print. Design in `design/bay.py`, CAD by `scripts/make_bay_cad.py` | 1 | in structure | ~$10 | ✅ |
| Printed panel bonding jig | Not a flight part. Holds skin/core/skin and the tang in alignment while the epoxy cures, 4× | 1 | — | ~$3 | |

**Two lines here are load path, not hardware, and buying the wrong thing quietly deletes
them.** The panel makes 0.0599 N·m about the hinge — that is what sizes the servo — and
**25.3 N at a bearing 29 mm away, which is 0.718 N·m of bending.** Without the plain bearing
that moment is carried by a 2.3 mm fibreglass hole and then by the servo's own output shaft:
175 MPa against an 80 MPa allowable, 0.46× where 2.0× is required. The **housing collar in
the printed bay** is the second: it holds 3.700 mm of the 6.0 mm bearing, and without it the
bearing seat runs at 3.4× instead of 14.5×.

**Why the servo frame was dropped.** This line used to read "carries the panel bending
moment off the servo spline", and that was an assumption nobody had checked. The commercial
frames — Hyperflight SRB-KST-X08, the Flightcomp/Servorahmen "third bearing frame", the
Aloft LDS kit — are built for **RC glider linkage**, where a servo swings an arm that pushes
a rod to a control surface. Their "counter bearing" supports that *arm* on the far side of
the case; it does not give you a supported shaft coaxial with the servo output, which is
what a direct-drive canard hinge needs. The third-bearing frame is also **50 × 37 × 9 mm**,
against a servo of 23.5 × 8 × 16.8 — four of those inside a 74.8 mm bore is a packaging
problem on its own. Our ⌀6/⌀8 sleeve in the wall already does the job the frame was
imagined to do, and does it in the right place.

**What the search did turn up, and it is the useful half:** those kits all include a
**splined servo horn** for the X08's ⌀4 mm 15-tooth output. **That paragraph was wrong and
is kept below only as the record; the horn does not fit.** See "The coupling" after it.
Cutting a 15-tooth internal spline into a ⌀6 shaft with a 0.8 mm wall is specialist
broaching; a horn arrives with the spline already on it for a few dollars. And the coupling
only has to carry **torque** — 0.520 N·m at servo stall — because the bearing sits outboard
of it and takes all the bending. So the shaft's inboard end simply bonds to a bought horn,
and the hardest feature on the part disappears.

### The coupling: fifteen keys, cast rather than cut

The horn does not fit, and neither does anything else with a female spline on it. There is
**0.515 mm** between the servo's output face and the bearing's inboard end, and everything
outboard of that has to pass down the **⌀6 journal** that turns in the bearing. Fifteen
teeth on a ⌀4 pitch circle need metal around them, so every horn, hub and adapter sold is
⌀7 or larger. Neither space will take one.

What is true in the paragraph above is that **broaching is the thing to avoid**. So don't
cut teeth — **cast them**:

1. Drill the shaft's inboard end **⌀4.100 × 3.20 deep**. A plain round hole, 0.050 mm on
   the radius over the spline's crests. One drilled feature on a part already being turned.
2. Prime the bore (6061 is a *passive* metal; anaerobics need an activator on it — the
   steel spline cures fine on its own).
3. Fill with retaining compound and push it onto the spline.

The compound cures in the tooth valleys and **becomes** the female spline — fifteen keys,
formed by the very part they have to mate with, so they fit by construction. The socket is
drilled 0.30 mm deeper than the spline engages, and that reservoir is not slop: a close
plug pushed into a blind hole full of liquid hydraulic-locks and will not seat.

This is only allowable because **the coupling carries torque and no moment**. The bearing
sits outboard and takes all 0.806 N·m of panel bending; this joint sees 0.520 N·m of servo
stall. An adhesive joint in a bending path would be a bad idea — this is not one.

| | |
|---|---|
| adhesive shear | 6.79 MPa against 17 MPa — **2.50×**, computed as if the socket were smooth |
| the fifteen cast keys | would carry it at 29.9 MPa of bearing — **not counted** in that margin |
| shaft wall in torsion | 15.7 MPa — 10.2× on 6061-T6 |
| serviceable? | yes: releases at ~250 °C, which is the whole reason to use a retaining compound and not epoxy |

**The canard panels are a laminate, not a plate: 0.6 / 2.0 / 0.6 mm G10, bonded, 3.2 mm
total.** The middle sheet is cut away over 12.1 × 25.5 mm at the root, and that gap IS the
tang slot — so the slot never has to be machined. Cutting it into a solid plate instead
would be a 13:1 deep blind cut needing a slitting saw on a mill; as a laminate it is a flat
shape you can cut before bonding. **Order two thicknesses, 0.6 and 2.0.** Both are stocked;
1.8 mm, which an earlier revision specified, is not sold anywhere.

**Two build notes that matter more than any dimension here.**

*Ream the bearing seat after the bay is bonded in, not before.* The bearing needs 6.0 mm of
support and the tube wall is only 2.3 mm of it, so a collar on the printed bay carries the
other 3.700 mm. Those two bores have to be concentric — if they are not, the bearing is
pinched and the hinge binds. Bond the bay in first, then run a **⌀8 H7 reamer through the
wall and the collar in one pass.** Concentricity is then automatic instead of being a
tolerance you have to hold across two parts made by different processes. Print the collar
bore undersize, around ⌀7.5, and let the reamer finish it.

*Bond the panels in a printed jig.* The laminate's whole advantage is that the skin
thickness is set by the sheet rather than by a machine setup — but only if the three layers
and the tang stay put while the epoxy cures. A printed fixture that locates the tang on the
hinge axis at the right chordwise station, and clamps the stack flat, costs an hour of
print time and removes the only real risk in this approach. Keep epoxy off the ⌀6 journal.

Servos mount **flat against the inner wall**, output shaft radial through the wall. Hinge
line at 0.20 of MAC, forward of the 0.25c panel CP so the panel is restoring. Torque margin
3.5× against a peak hinge moment of 0.0599 N·m per panel. Packaging is not binding: 44 mm of
arc needed against 144 mm available — but the **central void is 12 mm, not the 45 mm this
line used to claim**. The servo moved 4.000 mm inboard to make room for the hinge bearing
and every band lost the same 8 mm. The wiring has to fit ⌀12.17 over the 8.2 mm band where
the cable bosses sit. Regenerate with `python scripts/baseline.py`.

## 5. Avionics

Step 4 scope. **D7 and D8 are both closed** (docs/06, docs/07), so the sensor set is
settled even though most envelopes are still estimates.

| Item | Qty | Mass | Price | |
|---|---|---|---|---|
| Dual-deploy altimeter — **PerfectFlite StratoLoggerCF** | 1 | **0.011 kg** | ~$70 | 50.8 × 21.3 × 12.7 mm, 20 Hz logging. **Fires the charges; independent of the flight computer in every stage** |
| Flight computer — **custom STM32F405 board** (guided vehicle) | 1 | 0.045 kg | ~$400 | D7 RESOLVED, docs/06. Carries IMU, **magnetometer**, baro, GNSS. 70 × 45 mm is a **layout target**, not a measurement |
| Flight computer — **Teensy 4.1 + breakouts** (L1/L2 cert logger) | 1 | 0.015 kg | ~$40 | 61 × 17.8 mm. Stage 1; also the HIL target and the reference implementation |
| GNSS receiver + antenna | 1 | 0.030 kg | ~$40 | |
| IMU daughterboard | 1 | 0.020 kg | ~$30 | ≥ ±2000 dps gyro, ≥ ±16 g accel, **≥ 1 kHz ODR** — the rate is D8's, and it is not the loop rate |
| **Magnetometer** | 1 | 0.005 kg | ~$5 | **D8, docs/07.** The only sensor that observes roll angle; L1 is defined on roll angle. Keep it off the servo bus |
| Battery, 2S LiPo 1500 mAh | 1 | 0.090 kg | ~$20 | |
| Servo power BEC | 1 | 0.025 kg | ~$15 | |
| Telemetry radio | 1 | 0.045 kg | ~$50 | **in the nose**, station 282–318 mm |
| Independent GPS tracker | 1 | 0.060 kg | ~$100–200 | **in the nose**, with its own battery |
| Wiring, connectors, sled hardware | — | 0.230 kg | ~$60 | |

**Separate the servo supply from the IMU supply.** Four servos slewing on a shared bus next
to a MEMS gyro is a known way to corrupt attitude data.

**This table and `design/mass.py` used to disagree by 60 g, and it was the altimeter**
(docs/01 correction 26). Fixed Aug 2026 by adding `deployment_altimeter` to
`DEFAULT_AVIONICS_BUDGET`; both now total 620 g. It cost 18 m of apogee and 26 m of
crossrange and it *improved* static margin, because the altimeter lands forward of the CG.

**Where all of this physically goes: the nav bay**, 127 mm of 74.8 mm ID at station
318–445 mm, forward of the canard module and behind the nose cone. `configure.py` puts it
there for GNSS sky view and to keep the antenna away from the servo power wiring.

**THE TRACKER AND THE RADIO ARE NOT IN THIS BAY.** As of Aug 2026 they ride in the **nose**,
on the ballast rod at station **282–318 mm** (docs/01 correction 30) — 105 g moved from
station 381 mm to 300 mm. Both are RF parts, neither needs a short wire to the flight
computer, and the nose shoulder is the one place a fibreglass airframe stops shielding an
antenna. An independent tracker with its own battery in its own compartment is what
"independent" is supposed to mean.

**And the nose is a MODULE, meant to come off** (correction 32). After GV-2 the campaign
stops needing telemetry and the same nose can carry a payload: **up to about 300 g with no
other change**, in **469 cm³** between station 200 mm and the nose base. Two build rules
follow and neither is optional if the swap is to be real — **the module carries its own
battery**, and it has **exactly one connector** to the vehicle (the radio's data link; the
tracker needs nothing). The one drawback is RF: the GNSS antenna stays in the nav bay under
the shoulder, so a dense payload sits between it and the sky.

**AND THE BAY FITS — ON THE AREAL MODEL.** `design/avionics.py` is the packing check the
nav bay never had; `python scripts/avionics_report.py` is the argument. It wants **110.4 mm
of sled against 115.0 mm available at a 70.2 mm bore** — so **+4.6 mm**, having been 47 mm
short before the tracker and radio moved to the nose and 9 mm short before D7 closed. *(This
paragraph carried the 9 mm figure until Sep 2026, two corrections after it stopped being
true. The script itself carried a hardcoded "STILL SHORT BY 14 mm" line directly under its
own computed FITS verdict; both are fixed.)*

**BUT THE AREAL MODEL DOES NOT PLACE ANYTHING**, and placing it changes the answer.
`design/sled.py` puts the same stack down as real rectangles on two real faces:
the four boards fit on the 56.16 mm plate `SLED_WIDTH_FRACTION = 0.80` gives, and the
**80 g wiring loom then has nowhere to go** — not on a face, and not in the corner
crescents, which would need it at 1.84 g/cm³. The plate has to reach **59.00 mm**, and
M4 rods allow **59.20 mm**. See `python scripts/sled_report.py`.

Every envelope in that check is an estimate for a part nobody has chosen, so this is a
**warning and not a violation**, and correction 5 is why: an estimate-driven shortfall was
once acted on here and turned out not to be in the hardware. **Measure the loom and count
the conductors before concluding anything** — the 80 g is a line called `wiring_connectors`,
and connectors are not loom.
What the check is sure of is the shape of the problem: a flat sled in a round tube can only
use the rectangle inscribed in the circle, so the binding quantity is footprint on two
faces, not volume — the bay looks two-thirds empty by volume and is not.

Two more things about this bay:

- **The nose shoulder is settled** (docs/01 correction 31). A shoulder is a hollow tube and
  its bore is usable, so it costs *diameter* — 74.8 → 70.2 mm over its 79 mm — and not
  length. The sled runs up inside it, and gets all **115 mm** of usable length at 70.2 mm
  bore. `design/joints.py` models all four joints. *(This bullet said "and the shortfall is
  9 mm" until Sep 2026, three paragraphs under the same section's own **+4.6 mm FITS** —
  the third copy of that stale figure, and the one correction 41 missed while fixing the
  other two.)* Since correction 42 the bore is narrowed over the **whole 127 mm**, not just
  the shoulder's 79: the aft coupler is bonded into the remaining 47.64 mm, which is where
  the static ports are drilled.
- **The firing circuits leave this bay going aft**, cross the canard module, and cross the
  aft gas seal, because there is no room for an av-bay next to the charges. See docs/05.
- **The static ports go here and only here**, 3 × ⌀3.2 mm — and they are now *placed*:
  **station 420.82 mm from the nose tip, clocked 15/135/255°, 4.60 mm deep**, drilled after
  bonding through the airframe tube **and the aft coupler behind it** (docs/01 correction 42,
  `design/ports.py`). That is the only drillable wall in this bay: the nose shoulder occupies
  the forward caliber and its joint comes apart, so a hole there would have to re-align on
  every assembly. The canard module vents through its own wall so that it is *not* part of
  this bay's sensed volume — docs/01 correction 28.
- **The aft coupler is 0.600 cal of bond into the nav bay, not 1.0**, because that is all the
  nose shoulder leaves in a 1.60 cal tube. Its other end — 0.639 cal of engagement into the
  canard module — and the next joint's 0.608 cal anchor there are bounded the same way, by
  the printed canard bay sitting mid-tube rather than by convention (docs/01 correction 42);
  all three fit, with 43.9 mm to spare in the canard module's own tube. All three are below
  the 1.0 cal convention, and **nothing in this project sizes a coupler in bending**, so that
  stays an open item rather than a checked one — the capacity does not. The forward coupler's
  retaining screws are not placed and will want the same 47.64 mm band the ports are in.

## 6. Recovery

| Item | Spec | Qty | Mass | Price | |
|---|---|---|---|---|---|
| Drogue parachute | 18 in, deployed at apogee | 1 | 0.070 kg | ~$35 | |
| Main parachute | **56 in** solved; buy the Fruity Chutes Iris Ultra 60" Compact (nearest real size, lands slower). 193 g, 38.2 cu in packed | 1 | 0.280 kg budgeted | ~$110 | |
| Shock cord, quick links, swivels | **3/4" tubular nylon, 2 × 3.40 m** (2500 lbf) + links/swivels | set | **0.186 kg** | ~$50 | **sized, not budgeted** — 4.2× on the 1.32 kN opening shock after a knot derating. 1" nylon is 6.7× and costs a quarter of the bay. Kevlar packs smaller but does not stretch: use a Kevlar **leader** at the charge end, not a Kevlar harness. docs/01 correction 33 |
| Nomex protectors | | 2 | 0.070 kg | ~$30 | |
| Ejection charge hardware, shear pins | | set | 0.060 kg | ~$25 | |

### Deployment hardware — the aft gas seal

Sized Aug 2026; `design/seal.py`, argument in `out/seal_report.txt`, docs/05.

| Item | Spec | Qty | Mass | Price | |
|---|---|---|---|---|---|
| Aft gas seal disc | **G-10 sheet, 4.8 mm**, cut to 74.8 mm | 1 | 0.039 kg | ~$15 | thickness set by the wire hole, not the plate |
| Internal bulkhead disc | **G-10 sheet, 4.8 mm**, 1 × ⌀6 mm conduit feed-through | 1 | 0.039 kg | ~$15 | no shear pins protect this one |
| Harness U-bolt + backing plate | M5 stainless, with a backing plate — the plate is structure | 4 | 0.120 kg | ~$32 | 4 cm³ each of envelope out of the packing volume |
| Charge well + 2-pole terminal block | Bulkhead-mount, aft face | 2 | — | ~$10 | in `ejection_hardware_charges` |
| Shear pins | **3 × 2-56 nylon** per separation joint | pack | — | ~$6 | the intended fuse; buy spares, they are consumed |
| High-temp RTV, potting | 315 °C service, **forward face only** | 1 | — | ~$10 | |
| Wiring conduit | ⌀5 mm thin-wall, ~240 mm, drogue circuit through the main compartment | 1 | 0.010 kg | ~$5 | costs 1.2 mm of the bay's margin, which is **+8.4 mm** after docs/01 correction 42 |
| Black powder | **1.17 g** per main charge, sized at a 2.0× separation factor | — | — | ~$20 | **ground test twice; the calculation is not the arbiter** |

Descent 100 s, landing 5.0 m/s at 50 ft·lbf, ~0.93 km walk in a 15 mph wind. Ground-test
ejection charges twice before flying.

## 7. Ballast — required, not optional

| Item | Spec | Qty | Mass | Price | |
|---|---|---|---|---|---|
| Threaded rod, washers, nuts | Nose shoulder stack at 191 mm from the tip. **100 g design point**, provision for 300 g | 1 | 0.100 kg | ~$15 | |

Without it P(SM < 1.0) is 1.2% against R1's 1% limit. About 25 g is the minimum that
satisfies R1; 100 g brings it to 0.43%. This is the last free parameter — set it after
weighing the built vehicle, not before. See `00-requirements.md` §7.1.

## 8. Consumables

| Item | Qty | Mass | Price |
|---|---|---|---|
| Epoxy, fillets, tip-to-tip if used | — | 0.200 kg | ~$50 |
| Rail buttons, fasteners, shear pins | set | 0.060 kg | ~$25 |

---

## Budget summary

| Group | Cost |
|---|---|
| Airframe | ~$290 |
| Fins | ~$45 |
| Propulsion (case + 1 reload + mount + retainer) | ~$305 |
| Canard actuation | ~$310 |
| Avionics | ~$525 |
| Recovery | ~$260 |
| Ballast and consumables | ~$90 |
| **One complete guided vehicle** | **~$1,825** |
| 4 further reloads for GV-2…GV-5 | +$546 |
| L1 / L2 cert airframe and motors | +~$300 |
| **Full campaign** | **~$2,670** |

Excludes shipping, hazmat fees on motors, and any spare vehicle. The single largest line is
avionics. **D7 and D8 are both closed** (docs/06, docs/07) and three envelopes are off
datasheets. D8 added one part — a ~$5 magnetometer — so the line did not move, and the
sensor set will not move again on its own. What is still open is that most of these
envelopes and masses are estimates: the number that matters is what a scale says, not what
a decision says. See docs/01 step 5.

## Mass reconciliation

Model dry mass **5.515 kg**, wet **6.139 kg** including 100 g ballast and 0.501 kg of contingency
(10%, carried deliberately — every real build comes out heavy). Weigh each part as it
arrives, replace the estimate in `design/mass.py`, and rerun `scripts/robustness.py`. Every
guess retired shrinks the static margin distribution, and the ballast is what you adjust in
response.

## Before ordering

- Confirm the KST X08 Plus mounting scheme against the servo frame — the stock lugs extend
  the length axis and the body is bonded or clamped flat (§4.5).
- Confirm the Pro54 case grain count matches the reload. A 3-grain reload needs a 3-grain
  case.
- Confirm your site permits Blue Streak propellant on the day; sparky and propellant
  restrictions vary by season.
- C3 (budget ceiling) and C4 (calendar) are still TBD in `00-requirements.md`. This document
  is the input to closing C3.

## Sources

Researched prices: [Cesaroni J449-15A reload, CS Rocketry](https://www.csrocketry.com/rocket-motors/cesaroni/motors/pro-54/3g-reloads/cesaroni-j449-15a-blue-streak-rocket-motor.html) · [Cesaroni P54-3G casing, Apogee](https://www.apogeerockets.com/Rocket_Motors/Cesaroni_Propellant_Kits/54mm_Motors/3-Grain_Motors/Cesaroni_P54-3G_Blue_Streak_J449) · [KST X08 Plus, Hobby Club $42.95](https://www.hobbyclub.com/index.php?main_page=product_info&products_id=1828) · [KST X08 Plus, MPI Hobby $55.00](https://mpihobby.com/products/kst-x08-plus-digital-servo-8-4v-0-09s-5-3kg-cm-73oz-in) · [Servo frame with outboard bearing, Hyperflight](https://www.hyperflight.co.uk/products.asp?code=SRB-KST-X08)

Airframe and recovery vendors to price against: [Wildman Rocketry](https://wildmanrocketry.com/collections/fiberglass-1), [Mach 1 Rocketry](https://www.mach1rocketry.com/fiberglass-tubes), [Apogee Components](https://www.apogeerockets.com).
