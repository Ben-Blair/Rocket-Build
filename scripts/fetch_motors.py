"""Download real thrust curves from ThrustCurve.org into data/motors/.

Run:  python scripts/fetch_motors.py --diameter 54 --classes J K

ThrustCurve.org is the community motor database maintained by the National Association of
Rocketry. Its curves are the certification data (or manufacturer data) for each motor, so
these are the numbers to design against -- not the placeholders in design/motors.py.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path

API = "https://www.thrustcurve.org/api/v1"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "motors"


def post(endpoint: str, payload: dict) -> dict:
    req = urllib.request.Request(
        f"{API}/{endpoint}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def search(diameter: int, impulse_class: str) -> list[dict]:
    data = post(
        "search.json",
        {
            "diameter": diameter,
            "impulseClass": impulse_class,
            "availability": "available",
            "maxResults": 200,
        },
    )
    return data.get("results", [])


def safe_name(motor: dict) -> str:
    raw = f"{motor.get('manufacturerAbbrev', 'unk')}_{motor.get('designation', 'unk')}"
    return re.sub(r"[^A-Za-z0-9_.-]", "_", raw)


def download_curves(motors: list[dict]) -> int:
    """Fetch RASP-format data for each motor and write .eng files."""
    ids = [m["motorId"] for m in motors if m.get("motorId")]
    written = 0
    for chunk_start in range(0, len(ids), 20):
        chunk = ids[chunk_start : chunk_start + 20]
        data = post("download.json", {"motorIds": chunk, "format": "RASP", "data": "file"})
        for entry in data.get("results", []):
            motor = next((m for m in motors if m["motorId"] == entry["motorId"]), None)
            if motor is None or "data" not in entry:
                continue
            import base64

            text = base64.b64decode(entry["data"]).decode("utf-8", errors="replace")
            path = OUT / f"{safe_name(motor)}.eng"
            path.write_text(text)
            written += 1
    return written


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--diameter", type=int, default=54)
    ap.add_argument("--classes", nargs="+", default=["J", "K"])
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    all_motors: list[dict] = []
    for cls in args.classes:
        found = search(args.diameter, cls)
        print(f"  class {cls}: {len(found)} available {args.diameter} mm motors")
        all_motors += found

    # Solid motors only: hybrids need a fill/vent system that is out of scope here.
    solids = [m for m in all_motors if m.get("type") != "hybrid"]
    print(f"  {len(solids)} solid motors after excluding hybrids")

    n = download_curves(solids)
    print(f"  wrote {n} .eng files to {OUT}")

    index = OUT / "index.json"
    index.write_text(json.dumps(solids, indent=2))
    print(f"  wrote metadata index to {index}")


if __name__ == "__main__":
    main()
