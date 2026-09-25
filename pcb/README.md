# `pcb/` — the Stage 2 flight computer board

One project so far: **`flight_computer/`**, the custom STM32F405 board that
`docs/06` selected, `docs/07` gave sensors to, and `docs/14` turned into a BOM. This
directory is where that BOM becomes a schematic and a board. **As of 2026-09-24 it is
placed, routed, DRC-clean and has a JLCPCB fab + assembly package** in
`flight_computer/fab/` — read `fab/ORDERING.md` and "What is not done" at the bottom before
you order: two parts are out of stock and every assembly rotation needs a look in JLC's
preview.

## Opening it

```
open pcb/flight_computer/flight_computer.kicad_pro
```

The schematics are still **KiCad 8 file format** (`.kicad_sch` 20231120) and open
unchanged in KiCad 8, 9 and 10. **`flight_computer.kicad_pcb` no longer is** — the
layout pass (below) is done with KiCad's own `pcbnew` Python module, which saves in
whatever format the KiCad it's running under uses, and on this machine that's
**KiCad 10.0.6, board format 20260206**. Opening the `.kicad_pcb` in KiCad 8 or 9 will
prompt to upgrade the file. If that matters, say so before more layout work happens
on it — reverting is easy now and gets harder every pass after.

The symbol and footprint bodies embedded in the files were copied from this
machine's libraries — so if a symbol looks odd in another KiCad install, that is the
first place to look.

`sym-lib-table` registers one project-local symbol library,
`RocketSenior.kicad_sym`, for the three parts that needed one (below).
`fp-lib-table` registers one project-local **footprint** library,
`RocketSenior.pretty`, holding exactly one footprint —
`MMC5983MA_LGA-16_3x3mm_P0.5mm`, redrawn for `U5`, for the reason in "MMC5983MA"
below. Both tables use `${KIPRJMOD}`, so there is nothing to install; everything
else is stock KiCad libraries.

### Verified state

Reproducible from a clean checkout by regenerating in order (see "How the board gets
built" below — running only some of these steps, or out of order, does not match this
table):

| check | result |
|---|---|
| `kicad-cli sch erc` | **0 errors, 0 warnings** |
| `kicad-cli pcb drc --severity-all` | **0 errors, 0 unconnected**; 14 warnings, all library-footprint cosmetics — listed under "Routing" |
| netlist vs. `scaffold/design.py` | **57 real nets, exact match** (96 in the raw KiCad netlist — the other 39 are its own one-per-pin `unconnected-(REF-Pad)` placeholders for every NC pin, not a discrepancy) |
| footprint assigned on every component | **76 / 76** |
| `python scripts/pcb_placement_report.py` | **1 failure** (`C3`, accepted), median 2.60 mm |

```
bash pcb/flight_computer/scaffold/regen.sh      # close KiCad first; it refuses otherwise
```

which is, in order: ERC, netlist export, `gen_pcb.py`, `layout.py`, `finish.py` (hand-drawn
critical copper + Freerouting + silkscreen), full-severity DRC, the placement report, and
`fab.py`. Freerouting is **not deterministic** — to rebuild *this* board rather than an
equally valid re-route, pass `--ses routing/board.ses` to `finish.py` (see its docstring).
It needs `tools/freerouting-2.4.1.jar` (64 MB, gitignored): download it from
<https://github.com/freerouting/freerouting/releases>. Java is already installed.

`kicad-cli` is not on `PATH` by default on this machine; it lives at
`/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`.

**Do not run `layout.py` twice in a row on the same file, and do not run it without
regenerating the skeleton first.** It loads whatever `flight_computer.kicad_pcb`
already contains and adds a full new set of passives/vias/zones on top; run on its
own prior output it silently doubles everything and every number above stops
matching. `gen_pcb.py` always rebuilds the board from scratch, so the correct order
is always: export the netlist, run `gen_pcb.py`, then run `layout.py` exactly once.

Before 2026-09-24 the 133 unconnected items were every signal net — the board was placed
and planed but not routed. They are all routed now; see "Routing".

Nothing here moved by exclusion — every DRC violation was fixed in geometry:

| | first pass | then | now | why |
|---|---|---|---|---|
| DRC violations | 23 | 11 | **0** | 12 were `U5`'s adjacent-pad clearance (fixed in copper, see "MMC5983MA"); the last 11 were GND stitching vias landing on `U2`'s pads — see "Planes" below |
| unconnected items | 136 | 133 | **133** | the 3 unstitched `GND` pads are stitched; the rest is unrouted signal |
| placement failures | — | 14 | **2** | the pre-routing placement pass — see "Placement" below |

## Placement — the pass before routing, and the check that holds it

**ERC and DRC are connectivity checks and cannot see geometry.** Both passed on a board
whose 12 pF crystal load cap sat **21.5 mm** from its crystal, with the 8 MHz oscillator
node routed the length of the MCU and past the IMU. `design/pcb_placement.py` is the check
that closes that gap, `scripts/pcb_placement_report.py` prints it, and `scripts/baseline.py`
carries the verdict so it cannot regress quietly. Read that module's docstring before
changing a limit — in particular, why the check is scoped to two-terminal passives plus
three named nets rather than run over every pad.

What moved, and the measured effect:

| | before | now |
|---|---|---|
| `OSC_IN` (crystal to MCU, worst pad) | 14.39 mm | **3.75 mm** |
| `OSC_OUT` | 5.98 mm | **4.96 mm** |
| `GNSS_RF` (`U8` pin 11 to the u.FL) | 13.93 mm | **2.59 mm** |
| `C2`, 100 µF bulk, to the star point | 11.21 mm | **4.60 mm** |
| `R1`/`C4`, the regulator's enable and bypass | 14.3 / 13.6 mm | **2.99 / 1.98 mm** |
| median over all checked pads | 3.47 mm | **2.59 mm** |
| failures | 14 | **2** |

The moves that made room, all in `scaffold/gen_pcb.py`'s `PLACE`:

- **`J10` and `SW1` were in the two best pockets on the board** and are bring-up-only
  parts. `J10` (debug UART) held a 3.5 × 11.2 mm channel beside `U1` — which is *why*
  `C2`/`C4`/`R1` had been hand-relocated 14 mm away in an earlier pass, with a note saying
  the corner was saturated. It was saturated by a debug header. `SW1` sat in the only pocket
  that could take the crystal. Both are grouped with `J3` on the aft edge now; `NRST` is on
  the SWD header anyway, so `SW1` belongs there electrically as well as ergonomically.
- **`TP3` (a GND probe point) had claimed the gap between `U1` and its VIN cluster.** A test
  point's courtyard is 1.25 × 0.00 mm, so it slips into gaps no real part can claim.
- **`J5` moved to the forward edge** beside `U8`'s RF pad, which points at the nose where
  the antenna is. `U8` shifted 2.0 mm aft to open the strip — its courtyard is 11.8 mm wide
  against a 9.7 × 10.1 mm package and left only 3.0 mm of edge for a 4.4 mm connector.
- **`Y1` moved against `U2` pins 5/6, at 180°** so its `OSC_IN` pad faces the MCU and the two
  traces do not cross.

**`U5` did not move, and is confirmed not to have moved**: pad 1 is still at
(162.7500, 109.2250) — `pcb_placement.self_check()` asserts it on every run, because a
pad-rotation sign error would otherwise be invisible in the aggregate.

### The two remaining failures, both accepted

`C3.1` at **3.40 mm** and `R1.1` at **2.99 mm** against a 2.5 mm `VIN` limit. The aft-left
corner really is saturated once the four servo headers, the pack connector, the regulator,
the inductor and the power LED are in it — that part of the earlier note was right. Both are
about 1 mm over a limit set by judgement rather than by a datasheet. If the buck's input loop
ever needs to be tighter than this, the lever is `docs/14`'s own rule — *"if layout wants
more, take it out of height, not width"* — not another shuffle of the same corner.

## How the schematic is drawn, and why it looks like that

Four hierarchical sheets — `power`, `mcu`, `sensors`, `io` — under a root sheet that
carries the board-level notes.

**There are no drawn buses.** Every pin gets a short stub with a global label or a
power symbol on the end. That is a deliberate trade: it makes the netlist exactly
what `design.py` says and nothing else, and it means the auto-placement of symbols on
the sheet carries no meaning at all. **Rearranging the sheets into something a human
would draw is expected work, and it cannot break connectivity** as long as you move
labels with their pins. Sheet sizes were picked as the smallest ISO size each fit on
(io A3, power/sensors A2, mcu A1).

## Bus map — this is `docs/14`, unchanged

```
SPI1  CS1_IMU     PA4    ICM-42688-P    alone on the bus, 1 kHz burst on DMA
SPI2  CS2_MAG     PB12   MMC5983MA      100 Hz
      CS3_BARO    PC7    MS5611         50 Hz
SPI3  CS4_FLASH   PB5    W25Q128JV      log flash, write-mostly
USART1 PA9/PA10          MAX-M10S       10 Hz UBX
USART2 PA2/PA3           debug console  bring-up only
TIM4  CH1-4  PB6 PB7 PB8 PB9            4x servo PWM, 333 Hz / 1520 us
SWD   PA13 PA14 (+ PB3 SWO)
USB   PA11/PA12 full speed, 8 MHz HSE crystal
```

CS net names are `CS1_IMU`, `CS2_MAG`, `CS3_BARO`, `CS4_FLASH` so both `docs/14`'s
number and the function are in the name.

**Flash only — no microSD**, per `docs/14`'s socket-eject argument. The SDIO pins
(PC8-PC12/PD2) are not all free because SPI3 took PC10-PC12; if a microSD is ever
wanted, that is the trade to reopen.

**No pyro, no continuity, no e-match anything.** An independent StratoLoggerCF fires
the charges. This is `docs/14`'s non-negotiable and the board honours it.

## Things found while drawing it

These came out of reading datasheets to place pins, and several of them change a part,
a component count or a footprint. **None of them touches ±4000 or the airframe
freeze.**

### 1. `docs/14` names the wrong regulator — TPS62163 is 5.0 V, not 3.3 V

`docs/14`'s BOM row reads `3.3 V regulator | TPS62163DSGT`. TI's own device-options
table (SLVSAM2E, *TPS62160/61/62/63*, §5 Device Voltage Options) maps the suffixes:

| output | part |
|---|---|
| adjustable | TPS62160 |
| 1.8 V | TPS62161 |
| **3.3 V** | **TPS62162** |
| 5.0 V | TPS62163 |

**The 3.3 V part is TPS62162DSGT.** Verified against TI's own PDF, not a mirror:
`ti.com/lit/ds/symlink/tps62162.pdf`, SLVSAM2E §5 *Device Voltage Options*, which also
confirms DSG = WSON(8) and the DSG pinout the power sheet is wired to (1 PGND, 2 VIN,
3 EN, 4 FB, 5 AGND, 6 VOS, 7 SW, 8 PG).

**This is now fixed in all three places** — the schematic already had it, and
`docs/14-flight-computer-bom.md` and `design/flight_computer.py` have been changed from
`TPS62163DSGT` to `TPS62162DSGT`. `out/flight_computer.txt` was regenerated
(`python scripts/flight_computer_report.py --write`) so the report no longer copies the
wrong line. The intent in `docs/14` was never ambiguous ("3.3 V regulator", 2S in,
112 mA logic rail) — it was a wrong MPN, and ordering the line as written would have put
5.0 V onto the 3.3 V logic rail.

Wired per the same datasheet: `FB` (pin 5) to AGND, which is what TI specifies for
the fixed-output versions; `VOS` (pin 6) is the output sense and goes to the 3.3 V
rail; `PG` is open-drain and gets a 100 k pull-up, landed on PC13 so firmware can see
the rail come up.

### 2. The magnetometer needs a 10 µF capacitor that was in nobody's parts count

MMC5983MA **pin 10 is `CAP`** — "Connect a 10 µF capacitor for SET/RESET" (MEMSIC
MMC5983MA Rev A, Pin Description). That is not decoupling; it is the reservoir that
drives the degauss coil, and the SET/RESET cycle is exactly what this vehicle needs
the magnetometer for (`docs/12`, roll observability). It is `C23` on the sensors sheet.

Full pin list taken from that table, since no stock KiCad symbol exists:
`1 SCL/SPI_SCK, 2 VDD, 3 NC, 4 SPI_CS, 5 SPI_SDO, 6-8 NC, 9 GND, 10 CAP, 11 GND,
12 NC, 13 VDDIO, 14 NC, 15 INT, 16 SDA/SPI_SDI`.

### 3. The MS5611 has *two* CSB pins, and the stock KiCad symbol is right

`Sensor_Pressure:MS5611-01BA` puts `CSB` on both pin 4 and pin 5, which looks like a
library bug. It is not. The TE datasheet's PIN CONFIGURATION table has a merged cell
spanning pins 4 and 5 — "Chip select (active low), **internal connection**". Both
pads go to `CS3_BARO`. Left as-is, this is the kind of thing that gets "fixed" during
layout and quietly breaks the part.

## Pinouts, and how much to trust each one

| part | pinout source | confidence |
|---|---|---|
| STM32F405RGT6 | stock `MCU_ST_STM32F4` symbol | high |
| MS5611-01BA03 | **TE datasheet read directly** (pin table above) | high |
| MMC5983MA | **MEMSIC Rev A read directly** — pinout *and* land pattern, and the footprint is now redrawn from it | high |
| W25Q128JVS, MAX-M10S, USBLC6 | stock KiCad symbols | high |
| TPS62162DSGT | **TI SLVSAM2E read directly** | high |
| **ICM-42688-P** | **TDK DS-000347 rev 1.6 read directly** | high |

## Datasheet verification — the pinouts are no longer single-sourced

An earlier revision of this file said DS-000347 could not be fetched and that the
ICM-42688-P pinout rested on one SnapEDA-derived symbol. **That has been closed.** The
403 was not a paywall or a bot wall on the file — it was a missing browser
`User-Agent`/`Referer`. This gets the real PDF:

```
curl -L -o ds347.pdf \
  -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) \
AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36" \
  -H "Referer: https://product.tdk.com/" \
  https://product.tdk.com/system/files/dam/doc/product/sensor/mortion-inertial/\
imu/data_sheet/ds-000347-icm-42688-p-v1.6.pdf
```

The same trick (UA + a `Referer` on the vendor's own domain) worked for MEMSIC and TI.
Do not re-record any of these as "unfetchable".

| document | what was read | SHA-256 of the PDF |
|---|---|---|
| TDK InvenSense **DS-000347 rev 1.6**, 110 pp | §4.1 Table 10 *Signal Descriptions*, Fig. 5 pin-out, §10.2 package drawing | `5710af93…2ce1b9c` |
| MEMSIC **MMC5983MA Rev A**, 20 pp (4/3/2019) | Pin Description table, p.11 SPI connection, p.20 package drawing + LAND PATTERN | `d82083b9…5731f7` |
| TI **SLVSAM2E** (TPS62160/61/62/63) | §5 Device Voltage Options, §6 DSG pin configuration | — |
| u-blox **UBX-20035208 R08**, 24 pp (30-Jan-2026) | §3.1 Table 10 *Pin assignment*, §4.2 Table 13 *Operating conditions* | `e36d9c85…8df6bec` |

**`U8`'s whole pin map was checked against Table 10 and is correct as drawn — including
every no-connect.** Pin 15 `VIO_SEL` is the one worth naming: *"Connect to GND for 1.8 V
supply, or leave open for 3.3 V supply."* **Open is the 3.3 V setting and is deliberate**;
tying it to GND would drop `V_IO` to 1.8 V and break every interface on the board. Pins 13
and 14 (`LNA_EN`, `VCC_RF`) are outputs, open because the antenna is passive (`docs/14`).
Pin 6 is `V_BCKP` and sits on `+3V3`, i.e. the same rail as `VCC`, so the backup domain dies
with the board and **every power-up is a cold start** — accepted, not missed: `docs/14`
budgets 60 minutes armed on the pad, which is many times a cold TTFF.

### ICM-42688-P pin table, from DS-000347 §4.1 Table 10 verbatim

| pin | name | datasheet says | schematic does |
|---|---|---|---|
| 1 | AP_SDO / AP_AD0 | SPI serial data out (4-wire) | `SPI1_MISO` |
| 2 | RESV | *No Connect or Connect to GND* | NC |
| 3 | RESV | *No Connect or Connect to GND* | NC |
| 4 | INT1 / INT | interrupt 1 | `IMU_INT1` |
| 5 | VDDIO | IO supply | `+3V3` |
| 6 | **GND** | power supply ground | `GND` |
| 7 | **RESV** | **"Connect to GND"** — not optional | **`GND`** |
| 8 | **VDD** | power supply voltage | `+3V3` |
| 9 | INT2 / FSYNC / CLKIN | see the FSYNC note below | NC |
| 10 | RESV | *No Connect or Connect to GND* | NC |
| 11 | RESV | *No Connect or Connect to GND* | NC |
| 12 | AP_CS | SPI chip select | `CS1_IMU` |
| 13 | AP_SCL / AP_SCLK | SPI serial clock | `SPI1_SCK` |
| 14 | AP_SDA / AP_SDIO / AP_SDI | SPI serial data in (4-wire) | `SPI1_MOSI` |

**Pins 6 and 8 were the ones worth checking, and the SnapEDA symbol had them right:
6 is GND, 8 is VDD.** The whole symbol matched, pin for pin. The old warning about
VDD/GND swapped on a 2.5 × 3.0 mm LGA can be retired.

**What did change: pin 7.** The datasheet distinguishes the reserved pins, and it is
the only one of the five that reads *"Connect to GND"* flat, with no "No Connect or"
in front of it. It was a no-connect here — the conservative-looking choice that was
in fact the wrong one. It is now on `GND` in `scaffold/design.py`, the schematic and
the board. Pins 2, 3, 10 and 11 genuinely are "No Connect **or** Connect to GND", so
leaving them NC is compliant and they stay NC.

**FSYNC (pin 9) is safe as a no-connect, but only because of a register default.**
`INTF_CONFIG5` (bank 1, 0x7B) bit 2:1 `PIN9_FUNCTION` resets to `00` = INT2, which is
an *output*, so a floating pin 9 drives nothing and floats nothing. The datasheet's
"Connect to GND if FSYNC not used" applies to the FSYNC configuration only. **This is
now a firmware constraint: do not set `PIN9_FUNCTION` to `01` (FSYNC) on this board.**
There is no pad to ground it from if you do. Note `FSYNC_CONFIG` (0x62) resets to
`0x10`, i.e. FSYNC tagging into `TEMP_OUT` LSB is *already enabled* — harmless while
pin 9 is INT2, not harmless if you switch the pin.

### Footprints, against the two land patterns

**ICM-42688-P — `Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y` is correct, no
change.** DS-000347 §10.2 gives the package, and the KiCad footprint reproduces it
exactly: pad centres at **±1.1625 mm** on the 4-pin columns and **±0.9125 mm** on the
3-pin rows — the same two numbers the drawing dimensions as `2X 1.1625` and
`2X 0.9125`. Body 3.0 (E) × 2.5 (D) mm, 0.5 pitch, 4+3+4+3 with pin 1 top-left in top
view and counter-clockwise numbering. Pads are 0.625 × 0.35 mm against a 0.475 × 0.25
terminal (`L` × `W`), i.e. a normal IPC expansion. The library entry is labelled for
an ST LSM6DS3TR-C, which is why it needed checking; the geometry is the same package
and it lands.

**MMC5983MA — the assigned footprint was wrong, and it has been changed.** It was
`Package_LGA:LGA-16_3x3mm_P0.5mm_LayoutBorder3x5y`, which is **5 pads on two sides and
3 on the other two**. The MMC5983MA is **4 pads on every side** (MEMSIC Rev A p.20,
top view: 4/3/2/1 across the top, 5-8 down the left, 9-12 across the bottom, 16/15/14/13
down the right). Nothing but the pitch would have matched. That part would not have
soldered.

It is now **`RocketSenior:MMC5983MA_LGA-16_3x3mm_P0.5mm`**, a project-local
footprint in `RocketSenior.pretty` drawn for this part, and it matches the MEMSIC
LAND PATTERN drawing exactly:

| | MEMSIC Rev A p.20 | `RocketSenior:MMC5983MA_LGA-16_3x3mm_P0.5mm` |
|---|---|---|
| pads per side | 4 | 4 |
| pitch | 0.500 | 0.5 |
| pad size | 0.450 × 0.300 | 0.45 × 0.30 (rot 90 on the side columns) |
| row-to-row, centre to centre | 2.550 both axes | ±1.275 both axes |
| pad 1 | right end of the top row | right end of the top row |

(The 2.550 dimensions are centre-to-centre, not outer-edge — the extension lines land
on the pad midlines. Checked by magnifying the drawing; it is the one reading that
makes the numbers close.)

#### Why it is project-local, and why `U5` is at 0° and not 270°

The copper above is the same copper the stock `Package_LGA:LGA-16_3x3mm_P0.5mm`
has — that library entry is fine, and it is where this geometry was copied from.
The difference is **numbering**. Both number counter-clockwise, 4 per side, so pin
*n* lands on pad *n* for all 16; what differs is where the sequence starts. The
stock footprint's pad 1 is the top of the **left column**, while the chip's pin 1 is
the right end of the **top row** — one 90° step apart (stock pad *n* sits where chip
pin *n+4* would). Left at 0° on the stock footprint, the die sits rotated 90° CCW off
datasheet-upright and mag X/Y come out swapped against the board.

**For one revision that was corrected by placing `U5` at 270°. The axis answer was
right and the copper was wrong.** KiCad stores each pad's rotation **absolutely** in
the board file, not relative to its footprint: rotating the footprint 270° subtracts
270° from every pad's effective local angle. The side pads lose the 90° that made a
0.45 × 0.30 rectangle fit a 0.5 mm pitch, the 0.45 mm dimension ends up running
*along* the pitch, and adjacent-pad gaps collapse from 0.200 mm to **0.05 mm** —
under the `Default`/`Power` netclass's 0.127 mm and under JLCPCB's 0.127 mm minimum.
That produced 12 DRC clearance violations. They were never excluded; the geometry
was fixed.

The fix moves the 90° step out of the *placement* and into the *footprint*: the
local copy carries the same land pattern with the **chip's own numbering**, so `U5`
is placed at **0°**, upright, and nothing is rotated. Consequences:

- **Copper is the land pattern again.** All 16 adjacent pairs measure **0.200 mm**
  edge-to-edge (0.5 pitch − 0.30 pad) on the four sides, and 0.212 mm across each
  corner. Measured from `pcbnew`'s real pad polygons, not from size arithmetic — a
  pad with a wrong rotation flag cannot hide from that check. The 12 clearance
  violations are gone from `kicad-cli pcb drc`.
- **The die is datasheet-upright, and the axis convention `docs/12` needs is
  unchanged.** Mag axes aligned with board, mounting matrix board-in-airframe only.
  The strongest evidence that nothing moved: **every one of the 16 pad centres, and
  every net on them, is bit-identical to the old 270° placement.** Pad 1 is still at
  (162.7500, 109.2250). Only the pad rectangles' orientation changed. `docs/12` leans
  on this part for roll observability, so this was worth confirming rather than
  assuming.
- **`PLACE["U5"]` in `scaffold/gen_pcb.py` is `0` now**, `scaffold/design.py` and
  `scaffold/gen.py` both name the local footprint, and `gen.py` writes the
  `fp-lib-table` that resolves it — so a regen cannot revert any of it. `ksym.py`
  searches `RocketSenior.pretty` before the stock library, so a project-local redraw
  always wins over a same-named stock part.
- **Pin 1 is marked three ways, all at the top-right corner**: the silkscreen arrow
  above pad 1, the `F.Fab` outline chamfer, and a deliberately oversized filled
  circle on `F.Fab` at (1.9, −1.9). That circle used to be welded on at generation
  time by `gen_pcb.py`'s `EXTRA_FAB_MARK`, because the part was rotated on a
  footprint labelled for its sibling; it is now **drawn into the footprint itself**,
  so it is right in the footprint editor and on any other board too. Do not re-add a
  `U5` entry to `EXTRA_FAB_MARK` — that would draw the dot twice.

KiCad's own `--schematic-parity` check resolves the local library and reports **no
issue at all for `U5`** — the board's embedded copy of the footprint matches the
library exactly.

### Residual risk

- **Solder-paste apertures are the library's, not the vendor's.** Neither vendor
  publishes a stencil recommendation; both footprints use KiCad's default 1:1 paste
  layer. For two bottom-terminated 0.5 mm-pitch parts that is normal practice, not a
  verified number.
- **No 3D models were checked**, so nothing has confirmed that the ICM's pin-1 corner
  chamfer or the MMC's package outline agree with the footprint's fab layer. The
  local MMC footprint keeps the stock `LGA-16_3x3mm_P0.5mm.step` reference — the
  package body is the same, but **the model was drawn for the stock numbering**, so
  if it carries a pin-1 feature of its own it will point at the top of the left
  column, not the top-right corner where this footprint's pin 1 is. Believe the
  `F.Fab` marks, not the render.
- **The MMC5983MA's `MAG_CAP` net is not really a separate node.** MEMSIC Rev A p.11:
  "VDD and CAP pins are shorted together inside the device." `C23` (10 µF) therefore
  sits on the same node as `+3V3` through the package. That is exactly what MEMSIC's
  own SPI connection diagram draws, so it is kept as drawn — but **do not route
  `MAG_CAP` as a signal**, and do not let anyone "clean it up" by merging it into
  `+3V3` on the schematic, which would move the 10 µF away from the CAP pad.
- **DS-000347 rev 1.6 is not the newest revision** — TDK is at least at 1.9. Nothing
  read here (pin table, package drawing, `PIN9_FUNCTION`, `FSYNC_CONFIG`) is the kind
  of thing that moves between revisions, but the ordering check before fab should be
  done against whatever revision is current then.
- **The ICM footprint's toe extends to 1.475 mm against a 1.5 mm package half-width**,
  i.e. the land sits entirely under the body with no external fillet. That is inherent
  to LGA and matches the drawing; it just means optical inspection cannot see these
  joints and X-ray is the only real check.

## Power, and the rail split `docs/14` asked for

`docs/14`: the KST X08 runs straight off the 2S pack, so there is no BEC, and
"separate supply from the IMU" becomes a separate feed and filter off a star point at
the pack. On the board that is:

- **`VBATT`** — raw 2S from `J1`, **two wire pads for an 18 AWG XT30 pigtail** (was a
  JST-GH rated 1 A per contact — see "Routing and fab"). Goes to the four servo headers `J6`-`J9`
  and nowhere else. Its own netclass (`ServoPower`, 1.2 mm tracks, 0.3 mm clearance)
  because it carries the **4.1 A all-four-stalled** case from `docs/14`.
- **`VIN`** — the logic branch, through ferrite `FB1`. Making it a separate net is
  what puts the star point in the netlist instead of in a comment.
- **`+3V3`** — 1 A buck. The 112 mA logic rail has plenty of headroom.
- **`VDDA`** — through `FB2` off `+3V3`, with 1 µF ‖ 10 nF.

Each servo header is a normal 3-pin SIG/V+/GND so a servo lead plugs straight in.
**Nothing on this board feeds a servo from 3.3 V** — check that first if you rearrange
the power sheet.

`J4` is USB-C, and **VBUS is not connected to any rail**: the board is powered from
the pack. `D1` + solder jumper `JP1` (**default open**) exist so you can close the
link and run the board off USB on the bench without a pack. Do not close it with a
pack plugged in.

## Board

70.0 × 45.0 mm outline on `Edge.Cuts`, 4 layers, 1.6 mm, ENIG, four M2.5 corner
holes. Against `docs/08`'s sled that leaves +39.0 mm long / +14.4 mm wide / +9.1 mm
tall. **`docs/14`: hold 70 × 45; if layout wants more, take it out of height, not
width** — the board is the one line in the nav bay whose size is a design decision.

Major parts sit at `docs/14`'s zoning; passives are placed next to the pin they
decouple:

- **aft/left** — pack in, regulator, four servo headers. The noisy end.
- **centre** — MCU, with the IMU below it over the solid ground pour.
- **forward/right** — magnetometer `U5` and the GNSS receiver, diagonally as far from
  the servo headers and the battery lead as a 70 × 45 outline allows.

That last one is a requirement, not aesthetics:
`estimation.required_magnetic_cleanliness()` gives **18.0 mgauss** against
**40 mgauss** from a single untwisted 1 A servo lead at 50 mm. Twisted pairs on the
servo leads and keeping the 2S run off the forward end are how that budget gets met.

Netclasses are in the `.kicad_pro`, mirrored by `NETCLASS_PATTERNS`/`TRACK_WIDTH` in
`scaffold/layout.py`: `Default` and `Power` at 0.127 mm clearance (anything wider fails
against the LQFP-64 and LGA pad pitches), `ServoPower` at 0.3 mm / 1.2 mm tracks, `USB` with
a 0.2 mm / 0.4 mm differential pair, and **`RF` at 0.36 mm for `GNSS_RF`**.

**0.36 mm is 50 ohm on this stackup**, and 50 ohm is what the part asks for: MAX-M10S `RF_IN`
has `Zin` = 50 ohm with a built-in DC block (u-blox UBX-20035208 R08, Table 13). Hammerstad
microstrip over `In1` — h = 0.2104 mm, er = 4.5, t = 35 um — gives **59.9 ohm at the
`Default` 0.25 mm** and 50.0 ohm at 0.360 mm. `GNSS_RF` had been sitting in `Default`, i.e. a
~20% impedance error on the one net on this board that has an impedance.
`scripts/pcb_placement_report.py` prints the solve rather than leaving 0.36 as a constant.

### One routing rule that is not a netclass: the `VBATT` trunk

`ServoPower` is a single width, but `VBATT` carries two very different currents. The branches
to `J6`-`J9` take **<= 1 A each** and 1.2 mm is right for them (and is what fits a 2.54 mm
header). The trunk from `J1` to the branch point carries `docs/14`'s **4.1 A all-four-stalled**
case, which that document explicitly calls "a conductor question".

On 1 oz external copper, 1.2 mm is **2.73 A** at a 10 degC rise; at 4.1 A it runs about
**27 degC** hot. 2.0 mm brings that to ~11 degC. **Route the `J1` -> branch-point trunk at
2.0 mm**, keep the branches at 1.2 mm, and keep the whole run tight over `In1` (see "Planes").
It is a short run through an otherwise empty corner, so this costs nothing — but it has to be
done by hand, because a netclass cannot express "this part of this net".

## How the board gets built — two separate, one-way passes

`flight_computer.kicad_pcb` is not hand-edited directly and is not one script's
output; it comes from two passes that must run **in order**, and each one **destroys
what the other one did if run out of order or twice**:

1. **`scaffold/gen_pcb.py`** — rebuilds the *entire* board from KiCad's own exported
   netlist: layers, stackup, nets, every footprint at its `PLACE[...]` position (or
   parked off-board if not in `PLACE`), the outline and its notes. This is the
   skeleton generator described lower down; it has no memory of anything a previous
   layout pass did. Run it after any schematic/`design.py` change, before touching
   layout.
2. **`scaffold/layout.py`** — the hand-layout pass, run once against that skeleton
   with KiCad's own bundled Python (it needs the real `pcbnew` module, which is not
   on a normal `python3`):
   ```
   /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3 \
     pcb/flight_computer/scaffold/layout.py pcb/flight_computer/flight_computer.kicad_pcb
   ```
   It places every passive next to the pin it decouples (anchored by shared net,
   nearest IC preferred over a connector, with a small hand-curated override table
   for rail/bulk caps that a shared `+3V3`/`VBATT`/`GND` net can't disambiguate on
   its own — see `OVERRIDE_ANCHOR` in the script), pours and fills the ground planes,
   stitches every surface-mount `GND` pad into them with its own via, adds the one
   hand-drawn stitch in `MANUAL_GND_STITCH` (`U1`'s exposed pad — see "Planes"), and
   stops. **It does not route signal nets** — see below.

Running `layout.py` a second time on its own output does not "improve" the layout —
it loads whatever is already in the file and adds a whole second set of
passives/vias/zones on top, silently doubling everything. If you need to change
something after `layout.py` has run, either edit the `.kicad_pcb` directly in KiCad,
or start over from step 1.

### Placement

All 53 passives that `gen_pcb.py` parks off-board are placed by `layout.py`, each
next to the specific pin it serves (not just "somewhere on the net" — see
`resolve_anchors` / `OVERRIDE_ANCHOR`). Collision is resolved against real `F.CrtYd`
courtyard geometry read from `pcbnew` (not a pad-bounding-box guess, which
undercounts a JST connector's or a switch's real body badly), by the same kind of
push-apart relaxation `gen_pcb.py` already used for the major parts. Four items
needed a hand nudge afterward into open space nearby, each individually checked
against `kicad-cli pcb drc` before being hard-coded — see `MANUAL_FIXUP` in the
script; the comments there say why each one didn't fit where the automatic pass put
it. The aft/left corner (four servo headers + `J1` + the regulator + `J10`, all
`docs/14` zoning decisions, not this pass's to move) is genuinely saturated — there
was no pocket left near `J1` itself for its own bulk caps, which live one zone over
instead.

### Planes

`In1.Cu` and `In2.Cu` are each one solid `GND` pour, the whole board.

**`In2` used to be split in two** at `x = 120.5`, with a 1.5 mm copper gap, so that "servo
return current has no direct path across `In2` under the sensors". **That never worked and
could not have**: both halves were net `GND` and `In1` is an unbroken full-board pour, so
every stitching via tied them together. They were one node the whole time.

What the gap did do was real. The stackup is `F.Cu` / 0.2104 prepreg / `In1` / 1.065 core /
`In2` / 0.2104 prepreg / `B.Cu`, so a `B.Cu` trace references `In2` at 0.21 mm while `In1`
is 1.28 mm away. **Any `B.Cu` trace crossing `x = 120.5` lost its return path** — and
`SERVO1-4`, `+3V3` and `VIN` all have to cross it, because the MCU is at `x = 137` and the
regulator and servo headers are at `x = 103.5-117`. The split was costing exactly the thing
it was meant to protect, on the layer where the routing has to happen.

**Servo-return isolation comes from routing, not from a slot**: keep the `VBATT` trunk tight
over `In1` so its return image stays directly underneath it. At 0.21 mm of prepreg that image
is a ~0.1 mgauss dipole at the magnetometer against the 18.0 mgauss budget — four orders of
margin, which is why the binding magnetic risk in that budget is the untwisted servo *leads*
off-board and never the on-board copper. A genuine split would have to slot `In1` as well and
enforce a single star point, and it would put a plane slot under a board carrying both an IMU
and a magnetometer. That is a decision, not a default.

Every `GND` pad gets its own short stub and via down into `In1`. The escape direction is
searched over eight directions at five increasing offsets, and the first position clearing
**0.40 mm** to the nearest other-net pad *bounding box* is taken; if none clears, the best
available is used and the script **says so** on stdout.

That replaced a best-of-four-cardinal-directions-at-one-offset search measured **centre to
centre**, which is what produced all 11 of the previous pass's DRC violations: centre-to-centre
treats a 1.7 mm LQFP-64 finger and an 0402 terminal as the same point, so an escape "1.4 mm
from the centre" of a long pad was landing 0.10 mm off its edge. On a 0.5 mm-pitch part the
cardinal directions all run down a row of pins and the diagonals are the only way out.

**The three `GND` pads that used to be left out are stitched. There are no `GND`
items in `kicad-cli pcb drc`'s unconnected list at all now.** What they actually
were is worth recording, because an earlier revision of this file diagnosed two of
them wrongly:

- **`SW1` pin 2 and `J5` pin 2 — the zone filler was innocent.** This file used to
  say the filler was pruning the copper around their vias as an "island". It was
  not: those vias sit inside solid `In1` pour, checked against the filled polygons
  with holes accounted for. The real cause is **duplicate pad numbers**. `SW1`
  (`SW_SPST_TL3342`, a 4-terminal tactile switch) has *two* pads numbered `2`, and
  `J5` (U.FL) has two as well — one netlist pin, two separate lumps of copper.
  `stitch_gnd_vias` walked the netlist and took `next(p for p in fp.Pads() if
  p.GetNumber() == pin)`, i.e. **the first pad only**, so the second lump of each
  pair never got a stub and never touched the plane. The loop now stitches *every*
  pad carrying the number. It also skips through-hole pads, which reach `In1`
  through their own barrels and need no escape via — that is what keeps `J4`'s four
  same-numbered USB-C shield tabs from collecting four redundant vias, and it is why
  the stitched-via count reads 65 rather than 69 while *more* copper is connected.
- **`U1`'s WSON-8 exposed pad (pin 9)** is real and is handled by hand. It sits
  exactly at the footprint's own centre on a 2×2 mm body with pins 6/7 straddling
  it, so no cardinal escape direction clears them, and a via dropped into the pad
  itself would be an unplugged 0.3 mm drill under a bottom-terminated part — a
  solder-wicking risk taken for nothing, since the TPS62162 dissipates on the order
  of **40 mW** here (112 mA at 3.3 V, ~90 % efficient) and needs no thermal path at
  all. `MANUAL_GND_STITCH` in `scaffold/layout.py` runs a 0.25 mm `F.Cu` track east
  out of the pad at *y* = 139.25 to pin 5 (`GND`), which already has its own stub and
  via. The only other-net copper it passes is pin 6 (`+3V3`), and the measured gap
  is **0.250 mm** against the 0.127 mm `Power` requirement. If a proper thermal via
  array under the EP is ever wanted, it is a fab-time decision about plugged vias,
  not a connectivity one.

### Routing and fab (2026-09-24) — `scaffold/finish.py` and `scaffold/fab.py`

`layout.py`'s greedy router (`route_signal_nets`) is still off, for the reason it always
was: two-bend Manhattan paths cannot route an LQFP-64 escape on a populated board, and it
fell back to shorts. The board is routed by a **third pass, `scaffold/finish.py`**, run
exactly once on `layout.py`'s output:

1. **Inner layers typed as power planes.** `In1`/`In2` were "signal" layers; left that way
   Freerouting routes through the GND pours and the zone filler cuts the plane round each
   track.
2. **Copper a netclass cannot express, drawn by hand and locked** (Freerouting routes
   around locked copper):
   - **`VBATT` at 2.0 mm, the whole run.** `J6`-`J9` pin 2 all sit at *x* = 106.04 between
     pin 1 (signal) and pin 3 (GND); a 2.0 mm spine straight down that column clears both
     by 0.69 mm against the 0.3 mm `ServoPower` clearance, so every header hangs off one
     2.0 mm conductor and there is no narrower "branch" — the J9→J8 segment carries three
     servos anyway. `C1` moves 1.2 mm and flips so its `VBATT` pad sits *on* the trunk's
     corner instead of in its way.
   - **`GNSS_RF`**: `U8` pin 11 straight to `J5` at 0.36 mm, 2.59 mm long.
   - **`U1` pins 2/3 (`VIN`, `EN`)**: left to the autorouter, `VIN` boxed `R1`'s `EN` pad in
     (the one unrouted link of the first run). `R1` turns 180° and both leave between
     `U1`'s two GND stitch vias as parallel 0.2 mm tracks (0.15 mm clear of each via).
   - **`J4` pins A1/B12 (GND)** are tied on F.Cu to the USB-C shield tab. `layout.py`'s
     stitch via there ended up on an island of `In1`/`In2` once the router's vias
     surrounded it (DRC: "via connected on one layer").
3. **Freerouting 2.4.1**, headless, via Specctra DSN/SES with KiCad's own
   `ExportSpecctraDSN`/`ImportSpecctraSES`. It completes every signal net.
4. **Silkscreen**: every reference re-placed at JLCPCB's 1.0 mm minimum where it overlaps
   no pad, via, other label, other part's silk or other part's *body* (a label under a
   part vanishes on assembly — the first pass put "J10" under the GNSS module). Eight
   0402s in the MCU cluster have no such spot; their silk reference is hidden and they
   are on the assembly drawing (`fab/flight_computer-assembly.pdf`). "+"/"−" marks sit
   beside the `J1` wire pads.

**The 14 DRC warnings that remain are all library-footprint cosmetics, and none is
excluded** (there are still no exclusions in this project): 8 × `lib_footprint_mismatch`
(the embedded copies of stock footprints are older than KiCad 10.0.6's library — no pad
changed), 4 × `silk_over_copper` on `SW1` (the stock TL3342 footprint's own silk crosses
its pads; the plotter clips it), 2 × `silk_edge_clearance` on `J4` (its outline runs to the
edge because the connector is edge-mounted — below).

`scaffold/fab.py` then writes `fab/`: Gerbers + Excellon zip, a JLC BOM and CPL (61 placed
parts; LCSC numbers live in `fab.py`, not in symbol fields, because `gen.py` regenerates
the schematics), an assembly PDF and `ORDERING.md`.

### Things found while finishing it (2026-09-24)

Like the regulator and the magnetometer cap above, several of these change a part:

1. **`J1` could not carry the current.** JST-GH is rated **1 A per contact** (LCSC's own
   listing says so) against `docs/14`'s **4.1 A** all-four-stalled case. Replaced, per Ben,
   by two 1.25 mm-drill wire pads for an **18 AWG XT30 pigtail**: the XT30 (15 A) lives on
   the wire, and the wire rather than the PCB takes the pack lead's pull and vibration.
2. **`C2` "100 µF/25 V" in 1210 does not exist** — 100 µF in 1210 stops at 10 V. Now
   **22 µF/25 V**, the same part as `C1`; at 8.4 V X5R keeps ~12 µF each, so ~25 µF of bulk
   on `VBATT`. If servo transients ever want more, that is a footprint change
   (a polymer tantalum), not a value change.
3. **The `RF` netclass was never in the project file.** `gen.py` defined it, but `gen.py`'s
   `.kicad_pro` template had Python `#` comments *inside the JSON string*, so it could not
   have written a valid file; the `.kicad_pro` on disk predated the RF change, and
   `GNSS_RF` was sitting in `Default` at 0.25 mm (59.9 Ω) the whole time this README said
   0.36. `gen.py` now builds the project JSON from Python tables (`NETCLASSES`,
   `BOARD_RULES`) and the file on disk has been merged to match.
4. **`Power` at 0.6 mm could not enter the fine-pitch pins.** A 0.6 mm track into a 0.3 mm
   LQFP/WSON/LGA pad on 0.5 mm pitch violates clearance to the neighbour. Now 0.3 mm
   (+3V3 is 112 mA, VIN ~60 mA; 0.3 mm is ~1 A on 1 oz), with 0.6/0.3 mm vias.
5. **The USB pair netclass was ~76 Ω, not 90.** 0.4/0.2 mm → **0.25/0.15 mm = 90.9 Ω**
   (`scripts/pcb_placement_report.py` prints both). At 12 Mbit/s over ~25 mm this is
   bookkeeping, not signal integrity.
6. **`J4`'s mouth was 1.1 mm inboard of the edge.** `gen_pcb.py` clamps every courtyard
   inside the outline, so the USB-C receptacle sat at *y* 140.25 with its face at 143.9 —
   a plug's overmold would have hit the PCB edge before seating. `J4` is now `EDGE_MOUNT`
   in `gen_pcb.py`, registered so its body front lands exactly on *y* = 145.0.
7. **Board rules now match JLCPCB's 4-layer capabilities** (via hole to track 0.2 mm,
   min track 0.15 mm because Freerouting necks 0.25 mm tracks to 0.187 at fine-pitch
   pads, silk text ≥ 1.0 mm). They were stricter in places JLC is not (hole clearance
   0.25) and looser where it is (text 0.8 mm).
8. **The power corner is frozen in `layout.py`'s `MANUAL_FIXUP`.** Changing *one* footprint
   (`J1`) reshuffled seven passives through `relax()`, and `finish.py`'s hand-drawn copper
   depends on that geometry. Pinned at the positions that passed DRC and the placement gate.
9. **Placement gate: 2 failures → 1.** Turning `R1` put its `VIN` pad beside `U1`; `C3`
   (3.40 mm vs 2.5) is the one left, accepted as before.

The antenna stays **passive** (`docs/14`) — routing is where "cheapest to make before
layout freezes" expired for the active-antenna option.

### IMU LDO, GNSS via fence, and simulation (2026-09-24, second pass)

- **`U9` LP2985-33** now feeds the ICM-42688-P (`+3V3_IMU`, both supply pins and the CS
  pull-up `R8`), from `VIN` through an **RC pre-filter `R33` 10 Ω + `C30` 1 µF**. The
  usual gyro LDOs (LP5907, TPS7A20) stop at 5.5–6 V in; a full 2S pack is 8.4 V.
  `+3V3` no longer reaches the IMU at all.
- **GNSS via fence**: `finish.py via_fence()` adds GND vias 0.7–1.3 mm either side of
  `GNSS_RF` and round `J5`, each checked against every pad/track/via. Four fit, plus
  the four existing GND-pad vias of `U8` and `J5` around the 2.6 mm run.
- **`scripts/pcb_sim_report.py`** simulates the routed board with KiCad's own bundled
  ngspice (`design/ngspice.py`, nothing to install) and numpy/scipy, from copper read by
  `design/pcb_copper.py`. Output is saved in `out/pcb_sim_report.txt`. Findings:
  1. **Servo stall (4.1 A)**: no brown-out even from a cold, nearly flat pack (VIN ≥ 6.05 V
     against a 2.6 V UVLO); the sag is the pack's internal resistance, the board adds
     ~26 mV. The trunk runs about +11 °C at stall.
  2. **IMU supply noise**: 3.5 mV rms on the old shared `+3V3` → **34 µV rms** (new LP2985
     silicon) / **294 µV rms** (legacy silicon) on `+3V3_IMU` — 40 / 21.5 dB. Without
     `R33` the legacy silicon passed the buck's 1.1 MHz switching ripple *through* the LDO;
     that is why the RC is there.
  3. **Magnetometer — found by the simulation, then fixed with a star ground.** At DC (a
     stall, or servos holding against aero load) a servo return through the GND planes
     spreads by resistance instead of running under the trunk; the loop put **~25 mgauss at
     `U5` at 4.1 A** against the **18.0 mgauss** allowance. The "~0.1 mgauss" in "Planes"
     above assumed the high-frequency return path, which DC does not take.
     **Now:** the servo return is its own net, **`SERVO_GND`** — `J6`-`J9` pin 3, `C1`
     and `J1` pad 2 — drawn by `finish.py route_servo_gnd()` as a 2.0 mm F.Cu column 2.5 mm
     beside the VBATT spine, then on B.Cu directly under the trunk to `J1` pad 2. It meets
     `GND` at exactly one point, **net tie `NT1`** beside `J1` pad 2; logic GND reaches the
     pack through `NT1`, and no servo current enters the planes. **As built: 3.2 mgauss at
     the 4.1 A worst case (18 % of the allowance), ~0.8 mgauss per amp.** Not the ideal
     0.7: the return cannot sit under the spine on B.Cu (the headers' VBATT pins are
     through-hole there) and the pair splits over the last few mm to the two wire pads.
     Servo signals now reference GND across the star: ~40 mV of offset at a full stall,
     irrelevant to 3.3 V PWM.
  4. `+3V3` reaches the MCU's top edge through ~100 mm / ~165 mΩ of autorouted track (the
     shortest-resistance path). ~16 mV DC and ~9 mVpp of load-step noise at 100 mA — fine
     for the MCU, and the reason the IMU is no longer on that rail.
- What these are not: vendor SPICE models. The TPS62162 is modelled from its datasheet's
  power-save equations, the LP2985 from its ripple-rejection figures; every assumption is a
  named constant at the top of the script. Trust ratios and orders of magnitude, not µV.

### Pre-fab audit (2026-09-24, third pass)

- **Pack voltage to the MCU.** Nothing could read the 2S pack. `R34` 100k / `R35` 33k /
  `C33` 100 nF into **PA0** (ADC123_IN0): 8.4 V reads 2.08 V, full scale 13.3 V. `R34` sits
  at `FB1` so no VBATT copper crosses the board; the divided, filtered node does.
- **BOM re-checked on LCSC product pages**: 32 of 39 lines confirmed with stock. `SW1` moved
  to TL3342F160QG (C2886898, 2,200 in stock) — the reel part was out.
- Pins re-read against datasheets where a wrong tie is a dead part: MS5611 PS = GND (SPI).
- `R8` pinned in `MANUAL_FIXUP` — adding parts at the MCU re-rolled `relax()` and threw it
  20.8 mm from U4.

## What is not done

**Routed, simulated, DRC-clean, fab package built. What is left before and after ordering:**

1. **At order time** (`fab/ORDERING.md`): `U4` ICM-42688-P and `L1` are out of stock at LCSC
   (global sourcing / any 2.2 µH 1210 with Isat ≥ 1.2 A); confirm 7 flagged lines in JLC's
   BOM tool; **check every rotation in JLC's placement preview**; select the
   **JLC04161H-7628** stackup.
2. **Height is a mechanical question, not a PCB one.** The four vertical servo headers are
   8.5 mm and a mated servo plug stands ~14-15 mm above the copper — inside the sled's
   18.7 mm half-height per face, but over `docs/14`'s "≤ 8 mm tallest component" and the
   12 mm envelope `avionics.STM32_BOARD` feeds the packing check. Options: accept and update
   the envelope, right-angle headers (needs the header rows turned to exit an edge), or
   solder the servo leads like the XT30 pigtail.
3. **No firmware exists** (memory/`docs/01`: Step 4 is hardware-first). Bring-up needs at
   least: clocks + SWD, each SPI device's WHO_AM_I, the ADC on PA0, TIM4 PWM, GNSS UART.
4. **First-article checks the simulations cannot replace:** scope `+3V3` and `+3V3_IMU`
   ripple; log IMU and magnetometer with the servos stalled vs idle (the star ground's real
   test); verify `J1` polarity before the first pack.
5. No 3D models for `J4`/`U8` (renders show bare pads) — cosmetic.
6. The `.kicad_pcb` is KiCad-10-only format (20260206).

Committed on branch `flight-computer-pcb`. Nothing has been ordered.
