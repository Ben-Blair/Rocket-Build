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
| Nose cone, fiberglass | 3 in, 4:1 tangent ogive, 318 mm, with shoulder | 1 | 0.180 kg | ~$75 | |
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
| Servo horn, ⌀4 mm 15T | **Buy, don't cut.** An internal 15-tooth spline in a 0.8 mm wall is specialist broaching; a horn is a stock part with that spline already on it. Bond the shaft's inboard end to it | 4 | in shafts | ~$3 ea | |
| Canard hinge bearing | **⌀6 / ⌀8 × 6.0 plain sleeve, iglidur G class.** Housing reamed **⌀8 H7** — a standard reamer; the interference comes from the bushing being supplied oversize. This is the part that keeps the panel bending out of the servo | 4 | in shafts | ~$5 ea | |
| ⌀8 H7 chucking reamer | The one piece of tooling this design actually requires. Reams the tube wall **and the printed collar together, after bonding** — see the build note below | 1 | — | ~$15 | |
| Canard shafts, bushings, hardware | The lines above plus fasteners and epoxy | 4 | 0.240 kg | ~$40 | |
| **G10 sheet, 0.6 mm** | Panel skins. 8 skins, 2 per panel | ~0.3 m² | in canards | ~$25 | |
| **G10 sheet, 2.0 mm** | Panel cores. The tang slot is a gap cut in this sheet, not a slot machined later | ~0.15 m² | in canards | ~$20 | |
| Printed canard bay | PETG / ASA / CF-nylon — **not PLA**, heat-set inserts. **Must carry the bearing housing collar**, 3.700 mm of ⌀8 bore per hinge — that collar is worth 3.2× → 21.3× on the bearing seat | 1 | in structure | ~$10 | |
| Printed panel bonding jig | Not a flight part. Holds skin/core/skin and the tang in alignment while the epoxy cures, 4× | 1 | — | ~$3 | |

**Two lines here are load path, not hardware, and buying the wrong thing quietly deletes
them.** The panel makes 0.0599 N·m about the hinge — that is what sizes the servo — and
**25.3 N at a bearing 29 mm away, which is 0.718 N·m of bending.** Without the plain bearing
that moment is carried by a 2.3 mm fibreglass hole and then by the servo's own output shaft:
175 MPa against an 80 MPa allowable, 0.46× where 2.0× is required. The **housing collar in
the printed bay** is the second: it holds 3.700 mm of the 6.0 mm bearing, and without it the
bearing seat runs at 3.2× instead of 21.3×.

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
**splined servo horn** for the X08's ⌀4 mm 15-tooth output. That is the part worth buying.
Cutting a 15-tooth internal spline into a ⌀6 shaft with a 0.8 mm wall is specialist
broaching; a horn arrives with the spline already on it for a few dollars. And the coupling
only has to carry **torque** — 0.520 N·m at servo stall — because the bearing sits outboard
of it and takes all the bending. So the shaft's inboard end simply bonds to a bought horn,
and the hardest feature on the part disappears.

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

Step 4 scope — listed for budget completeness, not yet specified (D7, D8 open).

| Item | Qty | Mass | Price | |
|---|---|---|---|---|
| Dual-deploy altimeter (StratoLoggerCF / Eggtimer / Raven) | 1 | 0.060 kg | ~$70–160 | |
| Flight computer / custom controller PCB | 1 | 0.060 kg | ~$150 | |
| GNSS receiver + antenna | 1 | 0.030 kg | ~$40 | |
| IMU daughterboard | 1 | 0.020 kg | ~$30 | |
| Battery, 2S LiPo 1500 mAh | 1 | 0.090 kg | ~$20 | |
| Servo power BEC | 1 | 0.025 kg | ~$15 | |
| Telemetry radio | 1 | 0.045 kg | ~$50 | |
| Independent GPS tracker | 1 | 0.060 kg | ~$100–200 | |
| Wiring, connectors, sled hardware | — | 0.230 kg | ~$60 | |

**Separate the servo supply from the IMU supply.** Four servos slewing on a shared bus next
to a MEMS gyro is a known way to corrupt attitude data.

## 6. Recovery

| Item | Spec | Qty | Mass | Price | |
|---|---|---|---|---|---|
| Drogue parachute | 18 in, deployed at apogee | 1 | 0.070 kg | ~$35 | |
| Main parachute | **56 in** solved; buy the Fruity Chutes Iris Ultra 60" Compact (nearest real size, lands slower). 193 g, 38.2 cu in packed | 1 | 0.280 kg budgeted | ~$110 | |
| Shock cord, quick links, swivels | Tubular nylon / Kevlar | set | 0.220 kg | ~$60 | |
| Nomex protectors | | 2 | 0.070 kg | ~$30 | |
| Ejection charge hardware, shear pins | | set | 0.060 kg | ~$25 | |

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
avionics, and it is the least specified — expect it to move once D7 and D8 close.

## Mass reconciliation

Model dry mass 5.476 kg, wet 6.100 kg including 100 g ballast and 0.498 kg of contingency
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
