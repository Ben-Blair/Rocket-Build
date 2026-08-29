# Bill of materials

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
| G10 sheet, 3.0 mm | Canard blanks 56 × 68 mm each — cuts from the offcuts above | — | 0.142 kg | — | |

Aft fins: 4 panels, root 150.9 / tip 67.9 / semispan 123.1 mm, 87.3 mm sweep, through-wall
mounted. Canards: 4 panels, root 55.6 / tip 38.9 / semispan 67.5 mm, interdigitated 45°
from the aft fins. Flutter margins 1.97× and 5.42×.

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
| Servo frame with outboard bearing | Hyperflight SRB-KST-X08 or IDS/LDS kit — carries the panel bending moment off the servo spline | 4 | in shafts | ~$15 ea | |
| Canard shafts, bushings, hardware | Steel shaft through the tube wall into the canard root | 4 | 0.240 kg | ~$40 | |
| Printed canard bay | PETG / ASA / CF-nylon — **not PLA**, heat-set inserts | 1 | in structure | ~$10 | |

Servos mount **flat against the inner wall**, output shaft radial through the wall. Hinge
line at 0.20c, forward of the 0.25c panel CP so the panel is restoring. Torque margin 3.3×
against a peak hinge moment of 0.0626 N·m per panel. Packaging is not binding: 106 mm of
arc needed against 188 mm available, 45 mm central void.

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
| Main parachute | **56 in**, deployed at 200 m (650 ft) | 1 | 0.280 kg | ~$110 | |
| Shock cord, quick links, swivels | Tubular nylon / Kevlar | set | 0.220 kg | ~$60 | |
| Nomex protectors | | 2 | 0.070 kg | ~$30 | |
| Ejection charge hardware, shear pins | | set | 0.060 kg | ~$25 | |

Descent 100 s, landing 5.0 m/s at 50 ft·lbf, ~0.93 km walk in a 15 mph wind. Ground-test
ejection charges twice before flying.

## 7. Ballast — required, not optional

| Item | Spec | Qty | Mass | Price | |
|---|---|---|---|---|---|
| Threaded rod, washers, nuts | Nose shoulder stack at 191 mm from the tip. **100 g design point**, provision for 300 g | 1 | 0.100 kg | ~$15 | |

Without it P(SM < 1.0) is 1.8% against R1's 1% limit. 75 g is the minimum that satisfies
R1; 100 g brings it to 0.6%. This is the last free parameter — set it after weighing the
built vehicle, not before. See `00-requirements.md` §7.1.

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
