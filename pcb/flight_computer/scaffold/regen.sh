#!/bin/bash
# Regenerate flight_computer.kicad_pcb from the schematic, in the ONE order that works,
# route it, and build the JLCPCB fab + assembly package.
#
# pcb/README.md spells out why the order matters: layout.py loads whatever the .kicad_pcb
# already contains and ADDS a set of passives, vias and zones to it, so running it twice on
# its own output silently doubles everything and every number in the "Verified state" table
# stops matching.  gen_pcb.py always rebuilds from scratch, so it must run first, and
# layout.py must run exactly once after it.
#
# CLOSE KICAD FIRST.  pcbnew holds the board in memory and writes it back on save, so a
# regeneration underneath an open editor is lost the moment anyone hits Ctrl-S.  The script
# refuses to run if it sees a lock file.
#
# Does NOT run scaffold/gen.py -- that regenerates the schematics and the .kicad_pro from
# design.py, which is a much bigger hammer and is only needed when the NETLIST changes.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT=$(cd ../.. && pwd)
KICAD=/Applications/KiCad/KiCad.app
CLI="$KICAD/Contents/MacOS/kicad-cli"
KPY="$KICAD/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3"

if compgen -G "./~*.lck" > /dev/null; then
    echo "REFUSING: KiCad has this project open (lock file present)."
    echo "Close the PCB editor and the project, then re-run."
    exit 1
fi
[ -x "$CLI" ]  || { echo "no kicad-cli at $CLI"; exit 1; }
[ -x "$KPY" ]  || { echo "no KiCad python at $KPY"; exit 1; }

echo "== ERC =="
"$CLI" sch erc --severity-all -o erc.rpt flight_computer.kicad_sch
echo "== netlist =="
"$CLI" sch export netlist --format kicadsexpr -o net.net flight_computer.kicad_sch
echo "== gen_pcb =="
python3 scaffold/gen_pcb.py .
echo "== layout (exactly once) =="
"$KPY" scaffold/layout.py flight_computer.kicad_pcb 2>&1 | grep -v 'wxApp' || true
echo "== finish: pre-route, Freerouting, silkscreen (exactly once) =="
# Re-importing the committed session instead of re-routing: add  --ses routing/board.ses
"$KPY" scaffold/finish.py flight_computer.kicad_pcb 2>&1 \
    | grep -v -e 'wxApp' -e 'memory leak' -e 'INFO' -e 'Debug' || true
echo "== DRC (all severities) =="
"$CLI" pcb drc --severity-all -o drc.rpt flight_computer.kicad_pcb
grep -E '^\*\* Found' drc.rpt
echo "== placement gate =="
python3 "$ROOT/scripts/pcb_placement_report.py" || true
echo "== JLCPCB package =="
python3 scaffold/fab.py

echo
echo "Expected, per pcb/README.md 'Verified state':"
echo "  ERC 0/0 / DRC 0 errors, 0 unconnected, 14 warnings (all library-footprint, listed"
echo "  in the README) / placement 1 failure (C3, accepted)"
